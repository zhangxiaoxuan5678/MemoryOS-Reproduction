# MemoryOS single-sample study plan

**Status:** data preparation, integrity checks, construction and evaluation are complete. The shared snapshot covers 215 pages / 419 utterances, pinned by `STUDY_SNAPSHOT.json`. The original 25-question evaluation produced 225 answers; see [EVALUATION_RESULTS.md](EVALUATION_RESULTS.md). This document records the original design and does not authorize further paid execution.

## Fixed data and information boundaries

- Sample: `conv-26` in `locomo10.json`, including all 19 sessions and 419 utterances.
- Corrected conversion: 215 pages, including 11 one-sided pages. Pages retain session, date, image descriptions and original `dia_id` / indices.
- Pairing is separate within each session. Neither session boundaries nor consecutive turns by one speaker overwrite utterances.
- Complete two-sided pages retain the original User text as topic-summary input. An Assistant-only page uses its available Assistant text. This completeness correction is shared by all groups.
- Construction reads only `build_input/`, without access to `questions.json` or `scoring_only/`.
- Fixed questions: first six in original order from each of categories 1, 2 and 3, and first seven from category 4, then sorted by original QA index. Category 5 is excluded.
- This is a fixed category-stratified exploratory subset, not a random or outcome-selected sample and not representative of all LoCoMo.
- `questions.json` contains only `question_id` and `question`. `scoring_only/references.json` separately stores answers, categories and evidence, joined only after generation.
- `manifest.json` records source-data SHA-256, converter hash, question indices, category counts, exported-file hashes and code commit.

## Construction and snapshot requirements

Implementation details are in [BUILD_GUIDE.md](BUILD_GUIDE.md).

1. Start from the frozen 215-page inputs in an independent directory, without reading old test memory.
2. Share a persistent budget ledger across requests, with SDK retries set to 0. Count and log each attempt before sending; stop at limits. Failed attempts still count. Unknown usage is recorded separately, not as zero consumption.
3. After each page, save its checkpoint and coverage IDs. Invalid summary structure, empty topics or incomplete coverage cannot be treated as a successful build. Preserve the error rather than silently skipping it.
4. Freeze a snapshot only after full construction. Record hashes of short-/mid-/long-term memory, original model revision, configured model and thinking mode, code commit, full page coverage and real call counts.
5. After snapshot acceptance, evaluation loads it directly without rebuilding. Every run uses an independent copy so access counts and other state cannot contaminate another run.
6. Do not record keys. A provider identifier may replace the base URL. Retain questions, prompts, responses, usage and errors in their appropriate records for review.

## Only controlled experimental variable

Compare `queue_capacity = 5 / 10 / 20`, accurately described as the **maximum number of mid-term memory pages**.

All groups share the same model/thinking mode, embedding model, construction snapshot, 25 questions, candidate-session `top_k=5`, retrieval thresholds of `0.1`, long-term knowledge `top_k=10`, temperatures, prompts and scorer.

The final design retains the original retrieval algorithm: no frozen/shared retrieval results, added deduplication or changed `id(page)` tie sorting. Every independent run starts from a copy of the same complete snapshot. Each question makes a fresh keyword call and then generates a new answer. Actual pages, unique pages and content hashes are observed without changing retrieval. An offline candidate-threshold certificate shows that keywords cannot alter candidate membership for these 25 questions, but the formal flow still calls the original keyword model. Original tie handling and model randomness remain limitations reflected in repeated results; uncontrolled noise is not an additional deliberately changed variable.

Record configured capacity, actual unique pages, input tokens and answer per question. If all groups retrieve identical contents, report that the variable did not change actual retrieval rather than conclude capacity has no effect. Label the repository's simplified F1 explicitly; it is not official LoCoMo scoring.

## Historical static construction-call plan

For 215 valid pages progressing normally, the basic calls were estimated as:

- Continuity checks: 214.
- Metadata summaries: 215.
- Multi-topic summaries: 215.
- Basic total: 644.

New sessions additionally need keyword extraction, and triggered long-term profiles need analysis/merging. Counts depend on model outputs and segmentation state. Although the original summary prompt requests at most two topics, code does not strictly enforce the count. The prompt alone therefore provides no reliable total-call upper bound. The executor needs actual hard limits and output validation.

Construction was expected to require hundreds to over a thousand calls, beyond the eight-call trial. Separate construction and evaluation budgets were proposed and explicitly authorized after their controls could be inspected. These planning estimates are not actual usage. Completed usage appears in the build and evaluation records.

## Offline checks

From the repository root:

```sh
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/offline_check.py
HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 ../.venv/bin/python -B eval/checks/check_study_data.py
```

The second check covers utterances, speakers, dates and image descriptions in all 10 samples and synthetic boundary cases; passage of one-sided pages into memory updating; deterministic question export; and refusal to overwrite existing preparation directories. Model calls are mocked and incur no API cost.
