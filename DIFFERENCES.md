# Differences from the original upstream commit

Upstream baseline: `587ed7755c7aed179965792830ff1b5ad9a6fa92`.

This document records changes in the order they were introduced. Statements about a phase occurring before evaluation describe the historical workflow. The completed evaluation is reported in [EVALUATION_RESULTS.md](EVALUATION_RESULTS.md).

## Initial construction changes

1. **API configuration.** Removed hard-coded third-party endpoints and the import-time global client. Configuration loads from the root `.env`, with environment variables taking priority. All stages use the same configured model. Keys are not stored in the repository.
2. **Embeddings.** Retained `all-MiniLM-L6-v2` and the original encoding parameters, adding lazy loading and instance caching. The model revision and file hashes are recorded separately.
3. **Complete dialogue conversion.** A separate pure converter pairs utterances within each session, avoiding overwrites across sessions or consecutive turns by the same speaker. One-sided pages are retained. All 419 utterances in `conv-26` form 215 pages. Normal two-sided pages still use the original User content for topic summaries; an Assistant-only page uses that side's content as the topic input.
4. **Construction execution.** Limited the build to one sample with frozen inputs, without reading questions or reference answers. Retained original capacities, heat/topic thresholds, prompts, temperatures and page contents. Added topic-structure validation so failures cannot silently discard pages.
5. **Runtime controls.** Explicitly disabled thinking for DeepSeek flash and disabled SDK automatic retries. Added transactional checkpoints, response replay, raw-page coverage and hash acceptance checks. The published snapshot is read-only.
6. **Construction budget.** Set a cumulative limit of 1,200 new requests and CNY 10, using recorded rates of CNY 2 per million input tokens and CNY 8 per million output tokens. Initially, each request reserved costs for 1,048,576 input and 2,000 output tokens. Requests exceeding remaining funds were not sent. Reservations were released only after complete usage was known; an unknown outcome retained its reservation and stopped execution.
7. **Context reservation.** The model context was documented as 1M at the time. The input reservation used `2^20` to cover both decimal and binary interpretations. These program limits rely on the verified published prices; they do not replace provider billing or protect against future price changes.
8. **Scope at this stage.** Construction did not change retrieval deduplication, sorting or scoring and did not run formal evaluation. The fixed 25 questions and references were prepared separately and were not read during construction.

Fault-injection logs came from a temporary fake SDK and were excluded from the real construction ledger. Real requests, usage, errors and source hashes were saved in the corresponding run directories.

## Authorized metadata-summary limit change: 100 to 300

The initial build stopped at page 68 because a metadata summary reached the 100-token limit. The checkpoint for the first 67 pages did not contain the truncated content. The user explicitly authorized one resend of request 333 and a shared metadata-summary limit of 300. This was a runtime correction common to every group, not an experimental variable.

Previously successful pages and responses were reused. Original logs and `config.json` were retained; the revised configuration was saved separately as `config-meta300.json`. The final snapshot preserves the actual history in which the first 67 pages used the earlier limit.

The resend authorization allowed only `max_tokens` to change from 100 to 300 in the request fingerprint. All other fields had to match. The new request counted against the original cumulative request and monetary budgets. Any later truncation still stopped execution without an automatic retry.

## Authorized profile-merge limit change: 2,000 to 4,000

Offline diagnosis found synonymous redundancy and continued profile growth; the evidence was retained. The user then explicitly requested raising only the long-term profile-merge output limit to 4,000, without changing prompts, the algorithm or deduplication. Offline comparison confirmed identical messages and temperature. Other limits stayed unchanged, including the 300-token metadata limit.

Profile-merge requests reserved 4,000 output tokens plus 1,048,576 input tokens, or CNY 2.129152 at the recorded peak rates. Other request reservations were unchanged. The CNY 10 / 1,200-request cumulative budget was not reset. Request 408 received one explicitly authorized resend; a later truncation again required a stop.

This shared runtime adjustment did not resolve profile redundancy, information accumulation or conflicting prompt-length requirements. All evaluation groups had to use the same completed snapshot rather than rebuild different profiles.

## Authorized profile-merge limit change: 4,000 to 16,000

At the time of the change, the official Chat Completions documentation specified `max_tokens` from 1 to 393216, supporting an explicit 16,000-token output limit for the configured `deepseek-flash`. No API probe request was sent. Historical sources: [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion/) and [model/pricing documentation](https://api-docs.deepseek.com/zh-cn/quick_start/pricing/). These describe the basis for that execution decision, not a guarantee of future service limits.

Only `gpt_update_profile` changed to `max_tokens=16000`. Prompts, temperature and the merge algorithm were unchanged; profiles were neither compressed nor deduplicated. The pre-request reservation for this call became 1,048,576 input and 16,000 output tokens, or CNY 2.225152 at the recorded peak rates. The original cumulative CNY 10 / 1,200-request limits remained. Request 697 received one authorized resend. Other output limits were unchanged; truncation or insufficient budget still stopped execution.

The adjustment was not an experimental variable and did not solve redundancy. Original logs, successive configurations and diagnostics were retained. Publication of the final snapshot required acceptance of all 215 pages / 419 utterances, with correction and diagnostic evidence attached. Every group then loaded that same complete snapshot.

## Final snapshot

Construction completed all 215 pages / 419 utterances and passed independent coverage and hash checks. It used 1,052 requests and 524,744 tokens, with an estimated CNY 2.089654 at peak, uncached rates. The largest actual profile-merge output was 7,223 tokens. Higher limits allowed execution to finish but did not establish that redundancy was resolved.

The read-only snapshot's provenance contains all limit changes and redundancy diagnostics. `STUDY_SNAPSHOT.json` pins the same complete snapshot for every group. No evaluation had run at the point this snapshot was published.

## Formal evaluation preparation

The only controlled variable was `queue_capacity=5/10/20`, with 10 taken from the upstream entry point. Each group used three runs of 25 questions. The original retrieval algorithm, duplicate pages and `id(page)` tie handling were retained; no deduplication or stable sorting was added. New fields recorded observations and isolated the run copies.

Keyword extraction and answer generation made separate requests, with no shared or cached outputs across repetitions. Simplified F1 called the upstream function directly. Sample SD was computed from the three run means. FAISS/OMP used one thread as a shared environment setting, not an experimental variable. Preparation itself generated no real evaluation answers or F1 scores.

## Evaluation scheduling and budget controls

After evaluation authorization, the retrieval algorithm and prompts remained unchanged. Execution interleaved capacities question by question and rotated the starting capacity across repetitions. Nine independent copies were used, without reusing generated answers.

Full input was counted using the official offline tokenizer, with a 25% / 512-token margin. The full UTF-8 request byte count plus 1,024 provided an additional reservation floor, and maximum output cost was added. Offline checks covered the historical 1,052 requests and 75 full answer prompts. No experimental prompt was truncated.

The evaluation had a separate 450-request / CNY 20 budget, with no automatic retries or budget increases. Errors and truncated outputs would be marked separately rather than silently scored. The completed results, including the absence of these failures, are in [EVALUATION_RESULTS.md](EVALUATION_RESULTS.md).
