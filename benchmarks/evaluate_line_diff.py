import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
from datasets import load_dataset
from dotenv import load_dotenv
from git import Repo

ChangesDict = Dict[
    str, Union[Dict[str, List[Tuple[int, int]]], Dict[str, List[Tuple[int, int]]]]
]


def load_swebench_test_data(repo_name: Optional[str] = None) -> pd.DataFrame:
    """Load data from huggingface"""
    dataset = load_dataset("princeton-nlp/SWE-bench", "default", split="test")
    test_df = pd.DataFrame(dataset)
    test_df = test_df[
        [
            "created_at",
            "base_commit",
            "hints_text",
            "repo",
            "problem_statement",
            "patch",
            "test_patch",
        ]
    ]
    if repo_name:
        if repo_name not in test_df["repo"].unique():
            raise ValueError(
                f"repo_name {repo_name} not found in swebench test data. Please choose from {test_df['repo'].unique()}"
            )
        test_df = test_df[test_df["repo"] == repo_name]
    # sort the data by created_at starting with the oldest data
    test_df = test_df.sort_values(by=["created_at"], ascending=True)
    return test_df


def checkout_or_clone_repo(repo_identifier: str, commit_hash: str) -> str:
    """
    Checks out the state of the repository prior to the specified commit.
    If the repo does not exist locally, it clones it first.

    Args:
        repo_identifier: Repository identifier in the format "owner/repo".
        commit_hash: The commit hash to check out.

    Returns:
        str: Absolute path to the repo directory.
    """
    repo_name = repo_identifier.split("/")[-1]
    clone_dir = os.getenv("CLONE_DIR")
    github_token = os.getenv("GITHUB_TOKEN")
    if not github_token:
        raise ValueError("GITHUB_TOKEN environment variable must be set.")
    if not clone_dir:
        raise ValueError("CLONE_DIR environment variable must be set.")
    # make the cloned dir if it doesn't exist
    os.makedirs(clone_dir, exist_ok=True)
    repo_path = os.path.join(clone_dir, repo_name)

    if os.path.exists(repo_path):
        repo = Repo(repo_path)
        repo.git.checkout(commit_hash + "~1")
    else:
        repo_url = f"https://github.com/{repo_identifier}.git"
        repo = Repo.clone_from(repo_url, repo_path, env={"GITHUB_TOKEN": github_token})
        repo.git.checkout(commit_hash + "~1")

    return repo_path


def parse_diff(diff: str) -> dict:
    changes: dict = {}
    lines = diff.split("\n")
    filepath = None  # Current filepath under processing
    old_line_num = 0
    new_line_num = 0

    for idx, line in enumerate(lines):
        # @@ symbols have lines after them. We need to parse them.
        processed = False
        line = line.strip()
        if line.startswith("--- "):  # Old file version
            filepath = line[6:]  # Extract filepath after prefix "--- a/"
            changes[filepath] = {"addition": [], "deletion": [], "delete_windows": []}
            processed = True
        elif line.startswith("+++ "):  # New file version
            new_filepath = line[6:]  # Extract filepath after prefix "+++ b/"
            # If filepath was already set from '---' line and differs from current, update it
            if new_filepath not in changes:
                filepath = new_filepath
                changes[filepath] = {
                    "addition": [],
                    "deletion": [],
                    "delete_windows": [],
                }
            processed = True
        elif line.startswith("@@"):
            # find the second pair of @@ and move what is after it to a new line as that is a piece of code we need to parse
            # for example: @@ -62,13 +92,13 @@ def check(self, instance):
            at_split = line.split("@@")
            line_nums = at_split[1]
            line_nums_split = line_nums.strip().split(" ")
            old_range = line_nums_split[0]
            new_range = line_nums_split[1]
            old_range_start = int(old_range.split(",")[0][1:])
            old_range_length = int(old_range.split(",")[1])
            changes[filepath]["delete_windows"].append(
                (old_range_start, old_range_start + old_range_length)
            )
            old_line_num = int(old_range.split(",")[0][1:])
            new_line_num = int(new_range.split(",")[0][1:])
            # we do not set processed, because we want to handle the line number parsing below
            line = at_split[2].strip()
        if filepath and not processed:
            if line.startswith("+"):
                changes[filepath]["addition"].append(new_line_num)
                new_line_num += 1
            elif line.startswith("-"):
                changes[filepath]["deletion"].append(old_line_num)
                old_line_num += 1
            else:
                old_line_num += 1
                new_line_num += 1

    # Filter out entries where there are no changes
    return {k: v for k, v in changes.items() if v["addition"] or v["deletion"]}


def evaluate_search(
    pr_diff: str, predicted_search_results: List[Tuple[str, Tuple[int, int], str]]
) -> dict:
    """
    Evaluate the predicted search results against the actual PR diff.

    Parameters:
    - pr_diff (str): The unified diff string showing the changes made.
    - predicted_search_results (List[Tuple[str, Tuple[int, int], str]): A list of tuples containing the file path, line numbers, and text of the search results.

    Returns:
    - dict: A dictionary containing the recall, surplus rate, and precision.
    """

    def convert_search_to_dict(
        merged_results: List[Tuple[str, Tuple[int, int], str]]
    ) -> dict:
        results_dict: dict = {}
        for file, lines, _ in merged_results:
            if file not in results_dict:
                results_dict[file] = []
            results_dict[file].append(
                lines
            )  # We're not including text here since it's not used in evaluate_search
        return results_dict

    predicted_search_dict = convert_search_to_dict(predicted_search_results)

    # Parse the PR diff to get the delete_windows
    diff_data = parse_diff(pr_diff)

    # Metrics Initialization
    total_actual_lines = 0  # Total lines in delete_windows
    total_predicted_lines = 0  # Total lines in search window
    intersection_count = 0  # Count of lines correctly identified

    for filepath, search_windows in predicted_search_dict.items():
        if filepath not in diff_data:
            for start, end in search_windows:
                total_predicted_lines += end - start
            continue

        delete_windows = diff_data[filepath]["delete_windows"]

        for dw_start, dw_end in delete_windows:
            total_actual_lines += dw_end - dw_start

            for sw_start, sw_end in search_windows:
                total_predicted_lines += sw_end - sw_start
                # Calculate the intersection between delete window and search window
                intersection_start = max(dw_start, sw_start)
                intersection_end = min(dw_end, sw_end)
                if intersection_start < intersection_end:  # There is some overlap
                    intersection_count += intersection_end - intersection_start

    # Calculate metrics
    recall = intersection_count / total_actual_lines if total_actual_lines > 0 else 0
    surplus_rate = (
        (total_predicted_lines - intersection_count) / intersection_count
        if intersection_count > 0
        else 0
    )
    precision = (
        intersection_count / total_predicted_lines if total_predicted_lines > 0 else 0
    )

    return {"recall": recall, "surplus_rate": surplus_rate, "precision": precision}


def evaluate_diff(pr_diff: str, predicted_changes: dict) -> dict:
    """
    This function is intended to be used to evaluate the performance of a full SWE bot, that makes additions and deletions to code.
    It measures if the same number of additions AND deletions were made as predicted by the bot.

    TODO: Currently, the IOU metric, won't be quite right, because we should have a metric for measuring additions and deletions separately.
    We may need to also handle replacement separately as well.

    This takes in a pr_diff from github and predicted changes in the format:
    {
        "filepath1": {
            "addition": [Tuple(line_start: int, line_end: int)],
            "deletion": [Tuple(line_start: int, line_end: int)],
        },
        ...
    }

    returns:
    {
        "intersection": int,
        "union": int,
        "IoU": float,
    }
    """
    actual_changes = parse_diff(pr_diff)

    intersection = 0
    union = 0
    all_additions: dict = {}
    all_deletions: dict = {}

    # Calculate intersection and union for identified changes
    for filepath, file_predicted_change in predicted_changes.items():
        all_additions[filepath] = set()
        all_deletions[filepath] = set()
        actual_file_changes = actual_changes.get(
            filepath, {"addition": [], "deletion": []}
        )

        predicted_additions = set(file_predicted_change.get("addition", []))
        predicted_deletions = set(file_predicted_change.get("deletion", []))

        actual_additions = set(actual_file_changes["addition"])
        actual_deletions = set(actual_file_changes["deletion"])

        intersection += len(predicted_additions.intersection(actual_additions))
        intersection += len(predicted_deletions.intersection(actual_deletions))

        all_additions[filepath].update(predicted_additions)
        all_deletions[filepath].update(predicted_deletions)

    # Update union with actual changes
    for filepath, file_actual_change in actual_changes.items():
        if filepath not in all_additions:
            all_additions[filepath] = set()
        if filepath not in all_deletions:
            all_deletions[filepath] = set()
        all_additions[filepath].update(file_actual_change["addition"])
        all_deletions[filepath].update(file_actual_change["deletion"])

    # Calculate union
    for _, value in all_additions.items():
        union += len(value)
    for _, value in all_deletions.items():
        union += len(value)

    # Calculate IoU
    IoU = intersection / union if union != 0 else 0

    return {
        "intersection": intersection,
        "union": union,
        "IoU": IoU,
    }


def main():
    load_dotenv()
    # Assuming load_swebench_test_data() returns a DataFrame with the necessary information
    test_data = load_swebench_test_data()
    for _, row in test_data.iterrows():
        repo_identifier = row["repo"]
        commit_hash = row["base_commit"]
        try:
            repo_path = checkout_or_clone_repo(repo_identifier, commit_hash)
            print(
                f"Checked out {commit_hash} for repo {repo_identifier} at {repo_path}"
            )
        except Exception as e:
            print(f"Failed to checkout {commit_hash} for repo {repo_identifier}: {e}")

    # load_dotenv()
    # data = load_github_data("fast_api_issues.json")
    # repo_identifier = "tiangolo/fast_api"
    # diff_content = fetch_diff_from_github(repo_identifier)
    # print(diff_content)
    # commit_hash = data[repo_identifier]["prs"][0]["commit_hash"]

    # repo_path = checkout_or_clone_repo(repo_identifier, commit_hash)
    # metrics = evaluate_changes(diff_content, changes)
    # print(metrics)


if __name__ == "__main__":
    main()
