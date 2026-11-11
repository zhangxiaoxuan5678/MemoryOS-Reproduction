# MemoryOS small-scale reproduction record

Construction and acceptance of the complete `conv-26` snapshot are finished: 215 pages / 419 utterances. The formal 25-question evaluation, three capacities and three runs each, is also complete. Real simplified F1 results are in [EVALUATION_RESULTS.md](EVALUATION_RESULTS.md); they are neither accuracy nor the paper's full benchmark scores. The chronological sections below retain earlier plans, stops and recoveries. Earlier statements that an operation had not run refer to that historical stage.

## Code baseline

- Upstream commit: `587ed7755c7aed179965792830ff1b5ad9a6fa92`.
- Research branch: `repro/memoryos-small-study`.
- Initial configuration changes: `2f8d438`.
- Environment: macOS arm64, Python 3.11.9; interpreter `../.venv/bin/python`.
- `requirements-macos.txt` records the environment's dependencies, without claiming a verified clean installation.

## Initial offline checks

From the repository root:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/offline_check.py
```

The script checks syntax, imports, missing-configuration errors, fake configuration propagation, environment precedence and embedding-model caching. It does not read real `.env`; network connections are blocked and SDK/embedding objects are mocked. Its `conv-26` statistics come from real source data and the original converter, not from construction or evaluation.

## Local configuration

Determine the provider's full API base URL and model identifier. Open the root `.env` in a local editor; create it from `.env.example` only if absent. Do not overwrite existing configuration.

The variables are `OPENAI_API_KEY`, `OPENAI_BASE_URL` and `OPENAI_MODEL`. Keep keys out of chat, screenshots, reports and Git. `.env` is ignored, and existing shell environment variables override file values. Every experiment stage uses the same configured model.

## Historical first connectivity-test plan

This was API connectivity testing, not MemoryOS evaluation:

- Fixed input: `Reply with OK only.`
- At most one SDK request, retries 0, timeout 30 seconds.
- Maximum output 128 tokens, not a monetary cap; charges depend on provider rates.
- No embedding download, memory build, dataset processing or scoring.
- After explicit authorization, use `../.venv/bin/python -B eval/smoke_api.py --allow-paid`.
- Without the paid flag, exit before client creation or configuration loading.

Real logs under `runs/smoke-*/result.json` retain code commit, working-tree state, request scope, response and provider usage, without keys or base URL. Errors preserve only their type to avoid exposing configuration. A timeout does not prove the server did not charge, and failures are not automatically rerun.

## Initial sequence and implementation issues

The plan was to configure the provider, check connectivity, authorize a very small construction/question-answering flow with a request limit, freeze one sample and 25 questions, correct completeness/repeated-build issues, compare retrieval capacities under fixed conditions, and prepare reports from real results only.

At this stage the original converter turned 419 utterances into 211 pages: 205 satisfied its build condition and six would be dropped because one side was empty. Pairing had not yet been corrected. Other known issues were repeated construction after loading old memory, duplicate retrieval pages, unstable tie sorting and simplified set F1. The upstream full entry point processed every sample and was unsuitable as a small trial.

## 2026-11-05: first real test

The user authorized a tiny flow after connectivity, with at most 10 cumulative API requests including retries. SDK retries were disabled and one shared counter enforced the limit.

Entry point: `eval/small_flow.py --allow-paid`, using independent directory `runs/small-flow-20261105T150339129990Z/`. `calls.jsonl` and `summary.json` retain real prompts/responses without keys or base URL. Summary source SHA-256 covers code that had not yet been committed at execution time.

Observed results:

- Model: `deepseek-flash`, thinking explicitly disabled.
- Connectivity response: `OK`.
- Requests: 1; SDK automatic retries: 0.
- Server usage: 9 input / 1 output / 10 total tokens, with no unknown usage.
- The single-page flow stopped at `local_embedding_preflight` with `OSError`. The local cache could not load `all-MiniLM-L6-v2`; no model was downloaded at that point.
- No memory construction, question-answer evaluation, formal experiment or scoring had run.

Any later authorized download/recovery had to continue from that one used request, leaving nine of the original 10. Re-running the entry point could not reset the budget. Offline mock validation of a 10-call counter used temporary files/fake SDK and was not real usage.

## 2026-11-05: single-page trial completed

The user authorized downloading the original embedding model and continuing within the same 10-request cumulative limit.

- Downloaded `sentence-transformers/all-MiniLM-L6-v2`, revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`. File hashes and download metadata were saved in `runs/embedding-download.json`.
- The first download failed because Xet could not write the default cache. Ordinary HTTP downloading then succeeded without model API calls. Logs are `runs/embedding-download.log` and `runs/embedding-download-attempts.log`.
- One-page construction succeeded. Retrieval then raised `NameError`: initial global-client cleanup had accidentally removed the `compute_time_decay` import. It was restored. Real local embedding/FAISS regression checks passed, with keyword calls mocked and no API cost.
- Retrieval resumed from saved mid-term memory without repeating connectivity or construction. The flow question retrieved one page and generated an answer.
- Cumulative real usage: **8 requests**, **0 automatic retries**, **1,048 input / 103 output / 1,151 total tokens**. No unknown usage or API-request errors occurred.
- Both local-stop summaries were retained; `workflow-errors.json` records the unavailable cache and missing import.
- Download/recovery commit: `70b5e6f`; import/checkpoint-recovery fix: `f1ac1e1`. The final `summary.json` retains the successful execution version and source hashes.

The same run directory contains `calls.jsonl`, the answer/full prompt in `answer.json`, `flow.log`, `short.json` and `mid.json`. This trial did not trigger long-term profile updates or validate long-term writes. Trial files were not committed to Git.

The question was a constructed flow check, not a benchmark item. It read no QA references, computed no F1 and supported no accuracy claim. The two unused requests were not spent. Formal study still required dialogue corrections, fixed questions/snapshot and a separately approved budget.

## Offline preparation for the formal study

Added the pure data module `eval/study_data.py`, correcting cross-session overwrites and lost one-sided utterances. `DynamicUpdate` accepts a page with either side nonempty and supplies Assistant content as topic input only when User content is absent. Normal two-sided pages retain the original topic-input rule.

`eval/prepare_study.py` exports separate construction inputs, 25 fixed questions, independent scoring references and hash manifests, refusing existing preparation directories. `runs/study-preparation-conv26-v1/` initially contained no memory, outputs or scores.

`eval/checks/check_study_data.py` checked all 10 samples for lossless utterances, pairing boundaries, one-sided-page propagation, deterministic questions and file separation. Snapshot requirements, variable design and static-call planning are in `STUDY_PLAN.md`. No new real requests occurred during preparation; trial usage remained eight requests / 1,151 tokens.

## Construction executor prepared before paid execution

Added `eval/build_runtime.py` and `eval/build_study.py`: persistent budgets, no automatic failure retries, successful-response replay, page transactions/checkpoints, hash/coverage acceptance and read-only snapshot publication. Construction reads frozen `build_input` and manifests, not questions/references. Default preview does not load configuration or a client.

Seven offline fault-injection checks in `eval/checks/check_build_runtime.py` passed, as did configuration/data checks. All SDK/model objects were fake and temporary outputs stayed outside real result directories. Real usage remained eight requests / 1,151 tokens. The proposed 1,200-call build limit in `BUILD_GUIDE.md` was initially preview-only, awaiting authorization. Formal memory, snapshot and 25-question results did not yet exist at that point.

## Complete construction and accepted snapshot

Construction stopped at three output limits and resumed only after explicit authorization, as detailed in `BUILD_GUIDE.md` and `DIFFERENCES.md`. The last truncated request, 697, was authorized for one resend with a 16,000-token profile-merge limit. Request 698 succeeded.

The final build completed 215 pages / 419 utterances, using 1,052 requests, 351,383 input and 173,361 output tokens. Estimated peak, uncached cost was CNY 2.089654, within cumulative CNY 10 / 1,200-request limits. All three truncations and three explicitly authorized resends were retained. SDK automatic retries were 0, with no new truncation in the final recovery.

The shared snapshot is `runs/formal-conv26-v1/snapshot`, manifest SHA-256 `501867dfe03c5ccdd29bd23ed4ce78a9bdf492c980f14ec427a537e7797b42d1`. Independent checks covered source data, 215 unique pages, four memory files and correction/diagnostic provenance hashes. `STUDY_SNAPSHOT.json` pins the same read-only snapshot for every group. Profile redundancy/growth remain; higher output limits did not resolve the algorithmic limitation.

Final construction runtime commit: `1cab993`. Final recovery execution took 12 minutes 38 seconds; four active construction rounds totaled 28 minutes 26 seconds, excluding development and waiting for authorization. The eight-call trial remains separate from the 1,052 construction calls. No evaluation/F1 had run when the snapshot was accepted. See `verification-complete.json` in the original run directory.

## Offline evaluation preparation before authorization

Preparation pinned snapshot manifest `501867dfe03c5ccdd29bd23ed4ce78a9bdf492c980f14ec427a537e7797b42d1` and question-list hash `d05828c6775a6d0bace1ffa43c14432f1e1c1ebb09714b9a74f47ad4863dc5d7`. `runs/eval-prepared-conv26-v1` contained nine independent copies; formal execution would create fresh copies from the source snapshot.

Added `prepare_evaluation.py`, `audit_evaluation.py`, `evaluation_common.py`, `run_evaluation.py` and `score_evaluation.py`. Original retrieval/search functions and simplified F1 matched upstream ASTs, without deduplication, sorting changes or cross-repetition answer reuse.

All 25 candidate-session cosine lower bounds exceeded 0.1, with minimum 0.2244379, independent of nonnegative keyword bonuses. Formal keyword calls were nevertheless retained. Offline mean pages for capacities 5/10/20 were 5/8.96/13; unique-page means were 4.4/8.04/11.4. These were structural checks, not answer scores. The first diagnostic exited with native-library code 139. Importing upstream `utils` before FAISS and setting FAISS/OMP to one thread stabilized it; every group shared that environment.

Four initial offline checks passed: fixed data/copy isolation; fake-SDK 450 independent calls and no memory writes; original F1 and sample SD of three run means; and default preview without client creation. Fake data stayed in temporary directories. The proposed separate evaluation budget was 450 requests / CNY 20, initially awaiting authorization. Construction remained at 1,052 calls with an unchanged snapshot. See `EVALUATION_GUIDE.md` for subsequent budget/scheduling checks.

## Completed formal evaluation: 225 answers

After topping up, the user cancelled reduced plan B and restored 25 questions, three capacities and three repetitions, explicitly authorizing a separate 450-request / CNY 20 budget. Actual execution used 450 requests and produced 225 valid answers, with 0 failures, truncations or automatic retries. Usage was 2,264,622 input / 2,590 output tokens, estimated peak/uncached cost CNY 4.549964, over an effective span of 553.479 seconds.

Capacity 5/10/20 simplified F1 means were 0.41734756 / 0.45232937 / 0.47478499. Sample SDs across three run means were 0.02452401 / 0.00566280 / 0.01141776. Runtime commit: `fc48ea6`. Full results are in `EVALUATION_RESULTS.md`; original directory: `runs/eval-results-conv26-v1`. The 225 question records, 450 complete requests, individual cost reservations and independent `verification.json` were retained.

Execution interleaved capacities per question and rotated the starting capacity across repetitions. Nine independent copies, source snapshot and question-list hashes stayed unchanged. Original retrieval and simplified F1 were retained. Full prompts were not cropped. Reservations used the official offline tokenizer with conservative margins and a full UTF-8 request-byte floor. Category results did not improve monotonically; this one-conversation, 25-question study does not establish the paper's broader conclusions.
