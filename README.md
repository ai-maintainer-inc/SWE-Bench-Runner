# SWE-Bench-Runner

# Getting Started

Use the venv you use elsewhere, but `pip install -r requirements.txt`
Then make sure to select your venv as your notebook kernel

make sure to download the test parquet from here: https://huggingface.co/datasets/princeton-nlp/SWE-bench/tree/main
The training one is explored in the jupyter notebook, although you shouldn't need that.

## Dataset notes:

The training set does not have any test diffs, but the test set does.
The train set does not have any failed or passed test information or version info either.

The test dataset has: 2294 records. this lines up with the filtered down number of issues they discussed in the paper.

There also is a column called first_hints this is effectively comments on the issue
