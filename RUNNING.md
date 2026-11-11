# Running, restoring and scoring

Run all commands from the repository root. The experiment is complete. The instructions below distinguish checking saved results from generating new answers. Use the saved evidence to review the submission rather than the upstream full-dataset `main_loco_parse.py` entry point.

## 1. Minimal offline verification: no dependencies or key

With Python 3.11:

```sh
python3 -B eval/verify_submission.py
python3 -B eval/checks/check_secrets.py --history
```

The first command reads the evidence ZIP files directly and recomputes the repository's original simplified F1. The second scans the safe publication copy and its history. The original research repository inherited suspected credentials in old upstream history, so deleting current lines alone would not make that history suitable for publication. The scan does not read `.env` contents or print matching values. It is heuristic and cannot guarantee detection of every secret format.

## 2. Restore the working layout on a fresh copy

```sh
python3 -B eval/restore_evidence.py
python3 -B eval/restore_evidence.py --restore
python3 -B eval/score_evaluation.py --run-dir runs/eval-results-conv26-v1
python3 -B eval/prepare_evaluation.py --output runs/eval-prepared-conv26-v1
```

The restore script verifies the public evidence first, then restores the question list, separate references, frozen snapshot, nine memory copies and original results under the ignored `runs/` directory. It refuses to overwrite any existing destination. The scoring command only recomputes scores from saved answers; its new `scores.json` is written under `runs/`, leaving `evidence/` intact. Evaluation preparation creates nine fresh state copies without networking, model downloads or API calls. These commands require only the standard library.

## 3. Full local evaluation environment

```sh
python3.11 -m venv ../.venv
../.venv/bin/python -m pip install -r requirements-macos.txt
../.venv/bin/python -m pip check
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/offline_check.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_study_data.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_build_runtime.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_evaluation.py
```

`requirements-macos.txt` records the direct dependencies installed on macOS arm64 / Python 3.11.9. Installation into an empty environment has not been verified. Installing packages requires internet access. The final evaluation check requires restoration and preparation from Section 2 first. The checks use a fake SDK, embeddings and tokenizer; they do not download resources or constitute new experiments. They exercise the actual cost-reservation logic. An audit using the official tokenizer is separately recorded in `evidence/input-budget-audit.json`. The original function may print a Chinese message meaning "calling GPT" along a mock path; that log message does not indicate a real request.

## 4. Generation entry points and additional prerequisites

Restoring the completed snapshot is enough to study retrieval; rebuilding memory is unnecessary. A new generation run would additionally require local model resources:

```sh
# Downloads embedding weights; does not run a paid API experiment.
../.venv/bin/python -B eval/download_embedding.py
```

The downloader pins the original weights used here to revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. It writes machine-specific path metadata to `runs/embedding-download.json`; an absolute path from the original machine is not a portable resource.

Evaluation cost reservation also requires the official offline tokenizer. Its original source and ZIP SHA-256 are recorded in `evidence/evaluation-config.json`. Expected locations are `runs/deepseek-v4-tokenizer/official.zip` and `deepseek_v4_tokenizer/tokenizer.json`, `tokenizer_config.json` beneath that tokenizer directory. Neither weights nor tokenizer files are committed to Git. Verify downloaded files against the recorded hashes rather than silently substituting another tokenizer.

For a separately planned generation run, create `.env` locally from `.env.example` only if it does not exist, and fill in the three variables. Keep keys out of shell commands and logs. The recorded experiment used official `deepseek-flash` with thinking disabled. Server-side models and prices may change; historical prices do not guarantee future rates.

Default evaluation preview, which neither loads API configuration nor creates a client:

```sh
../.venv/bin/python -B eval/run_evaluation.py \
  --prepared runs/eval-prepared-conv26-v1 \
  --run-dir runs/eval-new-study \
  --max-requests 450 --max-cost-cny 20
```

Add `--allow-paid` only for a separately authorized new paid run. Authorization for the completed experiment does not authorize further spending. The executor requires a clean working tree and a fresh results directory. It does not automatically retry failures or fill missing answers using previous outputs.

If a new memory build is needed for further research, offline preparation and the default preview are:

```sh
../.venv/bin/python -B eval/prepare_study.py --output runs/new-build-preparation
../.venv/bin/python -B eval/build_study.py \
  --prepared runs/new-build-preparation \
  --model-metadata runs/embedding-download.json \
  --run-dir runs/new-build \
  --max-requests 1200 --max-cost-cny 10
```

A new build is not guaranteed to reproduce the original paid execution exactly. It cannot replace the published snapshot shared by all reported groups. Historical output-limit changes, stops and explicitly authorized resends are documented in `BUILD_GUIDE.md` and the provenance inside `snapshot.zip`.
