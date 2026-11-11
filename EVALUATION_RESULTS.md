# MemoryOS conv-26 evaluation results

**The formal evaluation is complete: 225 valid answers, 450 requests, no failures, no truncated responses and no automatic retries.** The reduced A/B plans were not used. There were no budget increases or reused answers across repetitions.

## Overall results

F1 ranges from 0 to 1 and is not the proportion of correctly answered questions. Each run first averages its 25 question scores. The group mean and sample standard deviation are then calculated from the three run means (`ddof=1`). Each group contains 75 answers, but these are not treated as 75 independent runs when computing SD.

| queue_capacity | Mean simplified F1 ± sample SD | Mean pages / unique pages | Input / output tokens, including keywords | Active time, seconds | Peak, uncached cost estimate |
|---|---|---|---|---:|---:|
| 5 | 0.41735 ± 0.02452 | 5.00 / 4.40 | 709,353 / 860 | 178.39 | CNY 1.425586 |
| 10 | 0.45233 ± 0.00566 | 8.96 / 8.04 | 755,565 / 871 | 187.65 | CNY 1.518098 |
| 20 | 0.47478 ± 0.01142 | 13.00 / 11.40 | 799,704 / 859 | 186.34 | CNY 1.606280 |

The baseline is 10. Capacity 20 had the highest overall mean on this fixed question set: about 0.02246 above 10 and 0.05744 above 5. These are descriptive differences from a small sample, without a significance test. They do not establish that larger capacity always performs better.

## Category results: within-category mean ± sample SD across three runs

| Capacity | Category 1: multi-hop, 6 questions/run | Category 2: temporal, 6 questions/run | Category 3: open-domain, 6 questions/run | Category 4: single-hop, 7 questions/run |
|---|---|---|---|---|
| 5 | 0.57290 ± 0.03356 | 0.46296 ± 0.13472 | 0.24919 ± 0.09623 | 0.38906 ± 0.04287 |
| 10 | 0.67306 ± 0.02348 | 0.57253 ± 0.01711 | 0.19054 ± 0.00535 | 0.38449 ± 0.01443 |
| 20 | 0.68326 ± 0.00250 | 0.58241 ± 0.00000 | 0.20289 ± 0.01604 | 0.43690 ± 0.03804 |

In category 3, capacity 5 had a higher mean than either 10 or 20. In category 4, 10 also did not outperform 5. Overall ranking does not describe every category. The overall score gives equal weight to all 25 questions, rather than equal weight to the four category means.

## Means of the three independent answer-generation runs

| Capacity | Run 1 | Run 2 | Run 3 |
|---|---:|---:|---:|
| 5 | 0.39074062 | 0.42225577 | 0.43904629 |
| 10 | 0.45285981 | 0.45770829 | 0.44642002 |
| 20 | 0.48442868 | 0.46217760 | 0.47774870 |

## Fixed design and execution order

- Every run used the same complete `conv-26` memory snapshot: 19 sessions, 215 pages and 419 utterances. Manifest SHA-256: `501867dfe03c5ccdd29bd23ed4ce78a9bdf492c980f14ec427a537e7797b42d1`.
- The 25 fixed questions were the first six in each of categories 1–3 and the first seven in category 4, in original order, then sorted by global QA index. Selection did not depend on model outputs. Question-list SHA-256: `d05828c6775a6d0bace1ffa43c14432f1e1c1ebb09714b9a74f47ad4863dc5d7`.
- Nine independent copies started with contents identical to the frozen snapshot. Evaluation conversations and predicted answers were not written back, and profiles were not updated.
- The only controlled experimental variable was `queue_capacity=5/10/20`. Candidate-session `top_k=5`, thresholds of `.1`, long-term `top_k=10`, temperature `.7`, prompts, model and embedding weights stayed fixed.
- The original retrieval algorithm, duplicate pages and `id(page)` tie handling were retained. No deduplication or candidate cache was added. For every capacity, the ordered retrieved contents for all 25 questions were identical across the three repetitions. This observation does not remove the general limitation of the original tie rule.
- Capacities were interleaved for each question: 5/10/20 in repetition 1, 10/20/5 in repetition 2 and 20/5/10 in repetition 3. Thus, one capacity was not always executed first.
- All 450 request operation IDs and response IDs were unique: 225 keyword requests and 225 answer requests. Each repetition sent new requests even for the same question. Generated answers were not reused from a cache.
- Reference answers and evidence were read only by offline scoring. Generation received question text and existing memory. Incorrect answers and refusals were still included in F1 if they were normal complete responses; low scores did not cause questions to be dropped.
- The original retrieval implementation and `evalution_loco.calculate_f1` function matched their upstream counterparts at the function AST level. The metric is set F1 over lowercase, regex-tokenized words, not the official LoCoMo scoring implementation.

## Tokens, time and estimated cost

| Stage | Requests | Input tokens | Output tokens | Total tokens |
|---|---:|---:|---:|---:|
| Retrieval keywords | 225 | 12,141 | 1,523 | 13,664 |
| Answer generation | 225 | 2,252,481 | 1,067 | 2,253,548 |
| Total | 450 | 2,264,622 | 2,590 | 2,267,212 |

The effective execution span was 553.479 seconds, about 9 minutes 13 seconds. Each group's active time in the overall table sums retrieval and answering for its own 75 questions. The groups total about 552.39 seconds; interleaved waiting is not counted as a group's processing time. `completed.json` separately retains run spans. Local model warm-up occurred before question timing. Network and server variability are included, so these times alone cannot establish algorithmic speed differences.

The budget ledger used the highest published rates verified at execution time and assumed all input tokens missed the cache: CNY 2 per million input tokens and CNY 8 per million output tokens. The total estimate was **CNY 4.549964**, below the authorized CNY 20. [Historical pricing source](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/). This is not the verified account charge; the account balance was not queried. The server separately reported 1,686,132 cached input tokens and 578,490 uncached input tokens. Applying the recorded peak cache rates gives a cache-aware estimate of about CNY 1.24514528, also not a verified bill.

These 450 requests / CNY 4.549964 belong to the separate evaluation phase. They exclude the earlier 1,052 construction requests / CNY 2.089654 estimate and the earliest eight small trial requests. All evaluation requests accumulated in one ledger, without restarting accounting to obtain more budget.

## Audit of full-input cost reservations

The earlier reservation of CNY 2.113152 was `(1048576 × 2 + 2000 × 8) / 1000000`: a full-context reservation, not a measure of actual input length. Evaluation instead counted the complete chat template with the official offline tokenizer, `trust_remote_code=False` and explicit `truncation=False`. Reserved input tokens were:

```text
max(ceil(offline_input_tokens * 1.25) + 512,
    complete_request_parameters_utf8_bytes + 1024)
```

The maximum cost for 2,000 output tokens was then added. No message was cropped.

The archive linked by the [official token-usage documentation](https://api-docs.deepseek.com/zh-cn/quick_start/token_usage/) had SHA-256 `e7310d1dafe0a86d8a5629fe78a7c763760f651db9b8682718a1781dcd6fe495`. Offline checks first covered the historical 1,052 requests and 75 distinct complete answer prompts. An independent audit then recomputed reservations for all 450 evaluation requests. Server-reported input counts differed from official offline counts by at most two tokens, and every reservation covered the reported usage.

Before each request, the program checked that known cumulative cost, reservations for unknown outcomes and the next request's maximum reservation stayed within CNY 20. Their maximum combined value was **CNY 4.643972**. There were exactly 450 requests, no unresolved in-flight usage and no unreleased reservations. A failure or truncation would save a `.failed.json` record with `valid_answer=false` and stop rather than be scored as a normal answer. Neither occurred in this evaluation.

## Shared corrections and limitations

Construction included lossless dialogue conversion, unified client configuration and shared output-limit changes: metadata summaries from 100 to 300, and profile merging from 2,000 to 4,000 and then 16,000 tokens. Three resends were explicitly authorized. Profile redundancy and continued growth remain; higher output limits did not fix them. All evaluation groups used the same final snapshot and correction history, without rebuilding memory per group.

This study covers one conversation, 25 selected questions and three repetitions. It substitutes DeepSeek for upstream `gpt-4o-mini` and includes shared runtime corrections, original retrieval duplicates and simplified F1. The results are not the paper's full benchmark scores and cannot be generalized to all LoCoMo data. Model-output randomness may also contribute to F1 differences. No universal causal claim is established.

## Versions, acceptance checks and files

Actual execution commit: `fc48ea6fee9f013fe2476666611edfdb78786023`. Upstream baseline: `587ed7755c7aed179965792830ff1b5ad9a6fa92`.

Independent verification confirmed unchanged hashes for the nine memory copies, original snapshot and question list; correct links between 225 answer records and 450 raw responses; matching per-question F1 and sample SD recomputations; and compliance with budget limits. The construction ledger remained at 1,052 requests.

Original local results directory: `/Users/caca/Documents/MemoryOS-Reproduction/MemoryOS/runs/eval-results-conv26-v1`. This is a historical path, not a required path on another machine. Public copies are in [evidence/](evidence/README.md).

- `scores.json`: overall, category, per-run and per-question F1 for all three groups.
- `kXX-rY/qNN.json`: raw answer, validity flag, retrieved-page IDs/content hashes, timing, usage and request links for each question.
- `calls.jsonl`: full inputs, real responses, usage, finish reasons, complete-input counts and pre-request reservations.
- `verification.json`: independent recomputation evidence supporting this report.
- `config.json`, `status.json`, `evaluation.log` and nine initial memory copies: versions, parameters, completion status and run-isolation evidence.

All 225 normal responses were included. No results were fabricated or filled in. This file documents the completed experiment; the accompanying assignment report and presentation were prepared afterward.
