# Memory construction and budget controls

**Construction and independent acceptance are complete: 215 pages / 419 utterances.** `STUDY_SNAPSHOT.json` pins the shared snapshot location and hashes. The sections below preserve historical execution plans and authorized corrections. The saved snapshot should be used for the reported study; this guide is not new spending authorization.

## Entry-point behavior

By default, `eval/build_study.py` only validates frozen inputs and the original embedding-file hashes, then displays the scope. It does not read questions/references, load `.env`, create an OpenAI client or connect to the network.

Preview from the repository root:

```sh
../.venv/bin/python -B eval/build_study.py \
  --prepared runs/study-preparation-conv26-v1 \
  --model-metadata runs/embedding-download.json \
  --run-dir runs/formal-conv26-v1 \
  --max-requests 1200
```

Real construction additionally requires `--allow-paid`, to be added only for an explicitly authorized scope. The original execution has already finished; the flag's existence does not renew authorization.

## Original proposed scope

- Build only `conv-26`: 215 historical memory pages covering 419 utterances.
- Use the configured model with thinking explicitly disabled. Retain original temperatures, prompts and short-/mid-term capacities.
- At most 1,200 new API requests, including failures and unknown outcomes. SDK retries are 0; per-call timeout is 60 seconds. The original proposal allowed at most 2,000 output tokens; later role-specific corrections are documented below.
- A request limit is not a monetary limit or a completion guarantee. Stop at the limit, withhold incomplete snapshots and do not increase budgets automatically.
- Basic continuity/metadata/topic calls alone account for 644 planned calls. Keywords and profiles depend on actual model outputs, so static estimates are not actual usage.
- Account separately from the earlier eight-call trial. Its two unused requests were not transferred to construction.
- Use independent `runs/formal-conv26-v1/` without overwriting test memory or old results. Construction excludes the 25-question evaluation, scoring and new model downloads.

## Interruption and recovery

- `fsync` the request ledger before sending. Record response, `finish_reason` and usage afterward. Errors retain safe error types and HTTP status, not SDK error bodies or keys.
- Process each page in a separate work directory. Commit complete short-/mid-/long-term memory and updater state, then advance `checkpoint.json`, only when every step succeeds. Failed pages are not committed.
- Recovery with the same command/directory checks configuration, code commit, source and model hashes. The working tree must be clean.
- Reuse successful responses by input-page sequence, call sequence and full request fingerprint. Replay neither pays again nor recounts tokens. Fingerprint mismatches stop execution.
- Failed or unknown requests are not automatically resent even if budget remains. They require review and a separate decision; deleting the ledger is not a recovery procedure.
- With exhausted hard limits, same-budget recovery can only replay responses, not send new calls. New budget requires explicit authorization and reviewed configuration changes.
- A checkpoint published before an interrupted pointer update is moved to `abandoned`, retained as evidence, and reconstructed using saved responses.
- A process-level file lock prevents concurrent writers to the same run directory.

## Snapshot acceptance

Check saved speaker fields, dates, original sessions and utterance indices page by page. Every source page needs a unique `page_id`. Cross-topic references to one page are allowed but do not count as additional coverage.

Publish `snapshot/` only after all 215 pages are committed, short-term memory has no pending page and file hashes agree. Include memory files, updater state, hash manifest, source/configuration, coverage statistics and real usage. Snapshot files are read-only and rechecked when reopened.

These checks establish original-page coverage, not the factual correctness of every LLM summary or profile. Coverage does not replace quality evaluation.

## Offline checks

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_build_runtime.py
```

Seven tests use fake SDK/embedding objects and temporary directories: budgets/response replay/no failure retry; unknown responses and ledger corruption; summary validation; recovery after a response; orphaned checkpoints; budget interruption and hash corruption; long-term profile checkpoints and coverage audits. These are not real construction results.

The later evaluation and scoring are complete. They retained original duplicate pages and sorting without adding deduplication. See `README.md` and `EVALUATION_RESULTS.md` for results and safe offline verification.

## Authorized CNY 10 construction budget

The user authorized construction only for `conv-26`, without evaluation, adding `--max-cost-cny 10` alongside the 1,200-request limit. Recorded peak, uncached rates were fixed at CNY 2 per million input tokens and CNY 8 per million output tokens.

The initial gate did not use a character/token estimate. Each request reserved a conservative full-context 1,048,576 input tokens and 2,000 output tokens: CNY 2.113152. Known usage was charged at peak rates and the difference released. Unknown outcomes retained the full reservation and stopped, without retry. Insufficient remaining funds for the next maximum reservation caused an early stop without automatic expansion. This deliberately conservative policy could stop at actual estimated cost around CNY 7.89.

Usage exceeding bounds, missing usage or service errors stopped execution and were recorded. These controls relied on official prices and context limits verified at execution time; they were not provider-account hard limits. See `DIFFERENCES.md`.

## Authorized recovery at page 68: metadata limit 100 to 300

The user explicitly allowed one resend of request 333 and raised the metadata-summary output limit from 100 to 300. `--apply-meta300-correction` applies only to the audited state: 67 committed pages, 333 sent requests, and a final 100-token truncation at `page:67:call:2`.

Original `config.json` and the `calls.jsonl` prefix remain intact. New records include `config-meta300.json`, `correction-meta300.json`, `retry-authorizations.json` and copies of old state. Budgets remain cumulative CNY 10 / 1,200 requests. The correction is common to all groups, not an experimental variable. A repeated truncation requires another stop; the same authorization cannot be reused.

## Authorized profile limit 2,000 to 4,000

`--apply-profile4000-correction` applies only to 77 committed pages, 408 ledger requests and final `page:77:call:8` truncated at 2,000 output tokens. Original configuration/logs are retained. The new configuration is `config-profile4000.json`. After backing up the authorization list, one resend of 408 was appended and executed as request 409. Costs and request counts continue in the same ledger.

Only `gpt_update_profile.max_tokens` changes to 4,000. Its pre-request reservation is 1,048,576 input plus 4,000 output tokens, or CNY 2.129152. Only profile merging may exceed 2,000 output tokens. Failure, unknown outcomes or further truncation stop execution without automatic retry. Diagnostics remain under `diagnostics/`; higher limits must not be described as resolving redundancy.

## Authorized profile limit 4,000 to 16,000

The official interface documentation at execution time specified `max_tokens` from 1 to 393216 and supported 16,000. The user authorized one resend of request 697, recovering from page 142 with `--apply-profile16000-correction`. Migration matches only 141 completed pages, 697 sent requests and final `page:141:call:8` truncated at 4,000 tokens.

Original ledger/configuration are retained; the new configuration is `config-profile16000.json`. Profile merges reserve CNY 2.225152 for 1,048,576 input and 16,000 output tokens; other requests retain CNY 2.113152. Cumulative CNY 10 / 1,200-request limits do not reset. Insufficient budget or another truncation stops execution. The shared snapshot includes provenance files and hashes for every correction and redundancy diagnostic.
