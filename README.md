# SWE-Bench-Runner

# Getting Started

Use the venv you use elsewhere, but `pip install -r requirements.txt`
Then make sure to select your venv as your notebook kernel

make sure to download the test parquet from here: https://huggingface.co/datasets/princeton-nlp/SWE-bench/tree/main
The training one is explored in the jupyter notebook, although you shouldn't need that.

This is a bit slapdash, but in order to git checkout each commit hash for each swe-bench item you can run evaluate_line_diff.py

To explore the data a bit more, checkout the swe_bench.ipynb.

This is from 2-4 month old memory, but I believe that the actual SWE-Bench benchmark evaluates whether or not the relevant tests pass in the repo.

So to properly evaluate SWEEP.ai or any other coding agent, you would look at the tests that were patched and make sure that those tests pass after the model runs.
Since everything here is python you may just be able to run pytest or something like that in each of the associated repos? Since there are only 12 repos total, you may be able to just figure out how each test set is evaluated for each repo.

I think the SWE-Bench guys only run the tests that were changed though to determine success though, this handles lots of edge cases.

This is not done here.

## Dataset notes:

The training set does not have any test diffs, but the test set does.
The train set does not have any failed or passed test information or version info either.

The test dataset has: 2294 records. this lines up with the filtered down number of issues they discussed in the paper.

There also is a column called first_hints this is effectively comments on the issue
