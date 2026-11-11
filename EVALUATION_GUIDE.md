# conv-26 evaluation: completed run and historical preparation

The formal evaluation is complete: **450 real requests and 225 valid answers**. See [EVALUATION_RESULTS.md](EVALUATION_RESULTS.md). This guide retains the preparation steps and budget proposals in chronological context. The final authorization superseded the earlier proposals. Its 450-request allowance has been used; this document does not authorize another paid run. The construction ledger and shared snapshot remain unchanged.

## Frozen inputs and independent state

`STUDY_SNAPSHOT.json` pins the snapshot. Its manifest SHA-256 is `501867dfe03c5ccdd29bd23ed4ce78a9bdf492c980f14ec427a537e7797b42d1`. Hashes for all four memory files and provenance files were rechecked. The source snapshot is read-only.

The preparation directory, `runs/eval-prepared-conv26-v1`, contains `spec.json`, `questions.json`, `selection-audit.json`, nine independent memory copies and offline audits. Formal execution creates another nine fresh copies from the source snapshot, rather than reusing objects accessed during offline auditing. Retrieval access counts affect only the current run's in-memory state. No memory-write or profile-update entry point is called. File hashes are checked after each group, and the source snapshot is checked again.

The 25 questions are the first six in each of categories 1–3 and the first seven in category 4, then sorted by original global QA index. Category counts are 6/6/6/7. Original zero-based indices:

```text
0,1,2,3,4,5,6,7,8,9,11,13,14,15,22,27,30,42,82,83,84,85,86,87,88
```

`questions.json` SHA-256: `d05828c6775a6d0bace1ffa43c14432f1e1c1ebb09714b9a74f47ad4863dc5d7`.

Questions were not selected using model answers. Generation reads only `question_id`, `question` and the completed memory, not `scoring_only/references.json`. Categories, evidence and reference answers are not passed to generation. A separate scoring script loads the references. Evaluation questions and predictions are not written back to memory.

## Controlled variable and preservation of the original algorithm

The settings are `queue_capacity=5`, `10` and `20`; 10 is the baseline in the original `main_loco_parse` entry point. Three runs of 25 questions per setting give nine runs and 225 answers.

Shared settings are `deepseek-flash`, thinking disabled, original prompts, `temperature=.7`, candidate-session `top_k=5`, three retrieval thresholds of `.1`, long-term `top_k=10`, answer/keyword output limits of 2,000, short-term capacity 1, mid-term capacity 2,000, and identical model weights and encoding settings. FAISS/OMP uses one thread throughout. This shared environment setting also avoided a native-library crash seen in the first diagnostic; it does not change the similarity algorithm. Embeddings load only the original downloaded weights, without networking. One local model warm-up occurs before timing starts, without an API request, so the first group does not bear the cold-start cost.

The original `retrieve`, `search_sessions_by_summary`, `search_knowledge` and simplified F1 functions match the corresponding upstream `587ed775` functions at the AST level. Duplicate pages and `id(page)` tie handling remain. No deduplication, stable sorting, keyword cache or shared retrieval results were added. Tie handling may vary across independently loaded objects, and model generation is stochastic; both limitations are retained and reported.

Every run/question has independent request operation IDs. Regression checks with a temporary fake SDK verified 450 unique operations: 225 keyword calls and 225 answer calls. Answers are not reused across repetitions. The formal entry point rejects an existing results directory. Errors preserve completed records and stop execution; this version does not automatically recover or resend a failed evaluation. The scorer refuses final three-group statistics if the required 225 valid answers are incomplete.

## Does retrieval require a model call?

Yes. Each question calls `llm_extract_keywords` once for mid-term retrieval. Query, page and long-term knowledge embeddings are computed locally. The completed snapshot has nonempty mid-term memory, so each question requires one retrieval-assistance call and one answer call: 450 requests in total. No new memory build is needed.

The offline audit blocks network access and does not construct an OpenAI client. Across the 25 questions, the minimum summary cosine among the first five FAISS candidate sessions was 0.2244379, above `.1`. Keyword-overlap scores are nonnegative, so those candidates pass regardless of keyword output. The audit used zero overlap as a lower bound to check later page selection with the original code. It retained this mathematical certificate rather than presenting an empty keyword set as an actual LLM result. Formal evaluation still sent the original keyword requests; the certificate was not used to remove calls.

## Offline structural check: not answer scores

| Capacity | Retrieved pages: min / mean / max | Unique page_id values: min / mean / max |
|---|---|---|
| 5 | 5 / 5 / 5 | 3 / 4.4 / 5 |
| 10 | 5 / 8.96 / 10 | 4 / 8.04 / 10 |
| 20 | 5 / 13 / 20 | 4 / 11.4 / 18 |

Retrieved contents were identical for 2/25 questions between 5 and 10, 10/25 between 10 and 20, and 2/25 between 5 and 20. Ordered-content and content-set comparisons gave the same counts in this check. Per-question page IDs, ordered-content hashes, unique counts and long-term knowledge counts are saved in `offline-audit.json`. Unique counts are observations and do not filter or deduplicate retrieval.

These are certificates and structural results from one local precheck, not nine formal evaluation runs. The general noise risk from `id(page)` remains. Formal runs record their actual retrieved contents rather than substitute the offline values.

## Scoring and statistics

`score_evaluation.py` imports `evalution_loco.calculate_f1` directly, preserving its set tokenization, lowercase conversion and regex logic. Each run averages 25 question scores; each capacity then reports the mean and sample SD of its three run means (`ddof=1`). Category means are first calculated within each run, then summarized across three runs. Categories 1–3 have six questions each and category 4 has seven. The overall score weights 25 questions equally, rather than weighting the four categories equally.

Saved observations include per-question F1, keyword/answer token usage and total usage, retrieval/answer/total time, actual pages, unique pages and ordered-content hashes. Each run also records elapsed time. Preparation itself produced no real scores. Completed scores are in `EVALUATION_RESULTS.md` and `evidence/scores.json`.

## Historical request and cost proposal

The following estimates were made before execution. They are retained as planning history, not actual usage or current pricing:

- 225 keyword calls plus 225 new answers: 450 requests in a complete evaluation, with no automatic retries and up to 2,000 output tokens per call.
- Proposed independent limits: 450 requests / CNY 20. The previous CNY 10 construction allowance would neither be reused nor reset. New explicit authorization was required.
- Conservative recorded rates: CNY 2 per million input tokens and CNY 8 per million output tokens, assuming cache misses. [Historical pricing source](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/).
- The final profile contained 34,397 characters, producing answer prompts of about 42,458–55,675 characters per question. The 225 answer prompts totaled 10,414,695 characters; the 225 keyword prompts totaled 60,786.
- In 52 historical long construction inputs, the median character/token ratio was 4.55046 and the minimum was 3.84453. These empirical ratios were estimates, not exact DeepSeek tokenization. A central scenario used about 2.3 million input tokens, 30–100 answer output tokens/question and 5–15 keyword output tokens, totaling 7,875–25,875 output tokens. Its peak estimate was CNY 4.67–4.81; allowing for tokenization and retrieval variation suggested CNY 5–7 for planning.
- A stress scenario used the minimum empirical character/token ratio plus a 20% input margin: about 3.27 million input tokens, and 450 outputs all reaching 2,000 tokens, or 900,000 output tokens. It estimated CNY 13.74. This was not a mathematical upper bound.
- The initial proposal used the construction ledger's full-context reservation: 1,048,576 input plus 2,000 output tokens, or CNY 2.113152 per request. Actual usage would release the difference; failed/unknown outcomes would retain the reservation and stop. This could stop early near CNY 20. The final authorization below replaced the input-reservation method.
- Construction remained separately recorded at 1,052 requests / CNY 2.089654 estimated. Preparation added no real requests. Estimates are neither verified account charges nor price guarantees.

## Preview and execution entry points

```sh
../.venv/bin/python -B eval/run_evaluation.py \
  --prepared runs/eval-prepared-conv26-v1 \
  --run-dir runs/eval-results-conv26-v1 \
  --max-requests 450 --max-cost-cny 20
```

Without `--allow-paid`, this validates frozen inputs and prints the plan, without loading configuration or creating a client. Paid execution requires separate explicit authorization and the added flag. The results directory must not already exist. Failure does not automatically start a new budget. The completed experiment's authorization is not reusable.

Offline scoring after a complete run:

```sh
../.venv/bin/python -B eval/score_evaluation.py --run-dir runs/eval-results-conv26-v1
```

## Limits on interpretation

One conversation, 25 fixed questions and three runs per setting form a small exploratory sample selected by category and original order. DeepSeek replaces the original model. Dialogue completeness, client configuration, output limits and checkpoints are shared corrections. Original profile redundancy and retrieval duplicates remain. Results are not the paper's full benchmark, and simplified F1 is neither the official scorer nor a basis for generalizing to all LoCoMo data.

## Final authorization and execution configuration

After topping up the account, the user cancelled the 12-question B plan and restored the original 25 questions, capacities 5/10/20 and three runs each. The separate cumulative evaluation budget was explicitly authorized at 450 requests / CNY 20, with no automatic retries, increases or prompt cropping. The question list and snapshot hashes stayed unchanged. Execution has since completed under these limits.

The earlier CNY 2.113152 reservation, `(1048576 × 2 + 2000 × 8) / 1000000`, represented full context capacity, not actual input length. The final method counted the complete chat template using the official DeepSeek V4 offline tokenizer, `trust_remote_code=False`, `truncation=False`. Reserved input tokens were:

```text
max(ceil(full_offline_tokens * 1.25) + 512,
    full_request_utf8_bytes + 1024)
```

Maximum cost for 2,000 output tokens was added at recorded peak rates. No prompt field was cropped, compressed or dropped. Usage exceeding reservations, missing usage, failure or truncation would immediately stop execution and would not count as a valid answer.

Tokenizer source: https://api-docs.deepseek.com/zh-cn/quick_start/token_usage/ ; archive: https://cdn.deepseek.com/api-docs/deepseek_v4_tokenizer.zip . Only offline resources were downloaded; no API probe was sent. Offline counts for the historical 1,052 requests differed from server input counts by at most two tokens and stayed within reservations. Reservations for 75 distinct answer prompts ranged from CNY 0.105070 to 0.131766. Original reservations and the new audit are in `runs/eval-prepared-conv26-v1/input-budget-audit.json`; tokenizer hashes accompany the actual execution configuration.

Scheduling rotated capacities for each question: 5/10/20 in repetition 1, 10/20/5 in repetition 2 and 20/5/10 in repetition 3, using nine independent memory copies. Question order stayed the same. Active time sums each run's own question processing, excluding interleaved waiting; elapsed spans are stored separately.

Six offline tests passed, covering interleaving, intact full inputs, budget checks and explicit truncation flags. Fake-SDK data remained in temporary directories, separate from real results. Failed questions would be stored as `qNN.failed.json` with `valid_answer=false`; final scoring rejects failed or incomplete runs.
