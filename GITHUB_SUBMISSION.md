# Publishing the reproduction to a personal GitHub repository

The submitted repository is [zhangxiaoxuan5678/MemoryOS-Reproduction](https://github.com/zhangxiaoxuan5678/MemoryOS-Reproduction). These instructions explain the safe publication process and subsequent updates. Publication is complete; no experiment needs to be rerun to upload or review it.

## Use the safe publication copy

The prepared `MemoryOS-GitHub` directory contains reviewed current code and evidence, without old Git history from the research repository. Upstream examples outside `eval/` contained suspected hard-coded API keys; these were removed without testing whether they were valid. A deletion commit would not remove values from earlier history, so the original local research repository was not pushed. Original upstream/execution commit IDs remain in documentation and evidence, and the full research history remains locally retained.

The publication includes README and running/scoring guides, `requirements-macos.txt`, an empty-value `.env.example`, code and offline checks, fixed questions and separate scoring references, archives of 225 answers and 450 requests, the shared snapshot, construction ledger, hashes and independent verification. It excludes `.env`, virtual environments, model weights, download caches and the 1.4 GB local `runs/` directory.

The three ZIP files are public study evidence without credentials. The largest individual file is about 29 MiB, so ordinary Git is sufficient without Git LFS. Upstream LICENSE, authors and attribution are retained. This is a modified individual reproduction, not a benchmark release by the original authors.

## Step 1: offline checks

In the safe publication copy, quoting paths that contain spaces:

```sh
git status --short
git log -1 --oneline
python3 -B eval/verify_submission.py
python3 -B eval/checks/check_secrets.py --history
```

Verification should report 225 valid answers, 450 requests and matching hashes/simplified F1. It does not connect to the network, read `.env` or call models. Full evaluation dependencies are unnecessary.

For optional import checks, create a Python 3.11 virtual environment, install `requirements-macos.txt` and run the README's offline checks. Those dependencies record the original machine's versions; a clean installation has not been verified. Upload preparation does not require paid experiments.

## Step 2: create an empty personal repository

For a new publication, create a repository such as `MemoryOS-Reproduction` in the intended GitHub account, with visibility meeting course requirements. Leave README, LICENSE and `.gitignore` auto-generation unchecked to avoid first-push conflicts. Use GitHub's HTTPS clone URL without embedding an access token. This step is already complete for the linked submission.

## Step 3: configure the personal remote and push

Run these only in the **safe `MemoryOS-GitHub` publication copy**. Replace placeholders with the intended account/repository:

```sh
git remote -v
git remote add personal https://github.com/YOUR_USERNAME/YOUR_REPOSITORY.git
git push -u personal main
```

If `personal` already exists, inspect `git remote -v` before updating it with `git remote set-url personal ...`. Authentication belongs in the system credential manager, browser or SSH workflow. Keep passwords, API keys and GitHub tokens out of chat and command URLs. Push to the personal repository, not `BAI-LAB/MemoryOS`; do not use force or mirror pushes.

For a ZIP rather than an initialized directory, extract it, enter the code root, and run `git init -b main`, `git add .` and `git commit -m "Publish completed MemoryOS reproduction with audited evidence"` before configuring the remote and pushing. The ZIP excludes `.git`.

## Step 4: check the published page

Check README tables/links, all three evidence ZIP files, `questions.json`, `scoring_only/references.json`, `scores.json` and LICENSE. Ensure `.env`, weights and virtual environments are absent. Published history starts from the safe release and later publication updates, without old upstream history.

Submit the personal repository URL and disclose the single conversation, 25 questions, three capacities with three repetitions each, DeepSeek substitution, shared runtime corrections and simplified F1. Results are not directly comparable with the paper's full benchmark. Costs are estimates at verified historical rates, not verified account charges.

## Later updates

Edit the safe copy and inspect `git diff`, scan for secrets and verify evidence before committing. Do not merge/rebase old research history into the publication copy. Review any new source copied as files. Do not force-add the full original `runs/` directory.
