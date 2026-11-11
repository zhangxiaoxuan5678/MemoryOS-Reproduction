# Public evidence for the completed experiment

These files were copied from the original frozen snapshot and real execution logs. Packaging did not generate new model answers or alter the original evidence contents. `manifest.json` records file SHA-256 hashes.

| File | Purpose |
|---|---|
| questions.json | The 25 fixed generation questions, containing only IDs and question text |
| selection-manifest.json | Original indices, category counts, source-data and question-list hashes |
| build_input/ | The complete losslessly converted dialogue and 215 pages, for restoring build inputs |
| scoring_only/references.json | Reference answers and evidence, for offline scoring only |
| scores.json | Overall, category, per-run and per-question simplified F1 |
| verification.json / status.json | Independent verification of 225 answers, 450 requests, tokens, timing and the snapshot |
| evaluation-config.json | Actual execution parameters and budget settings, without credentials |
| algorithm-audit.json / input-budget-audit.json | Offline checks of the original algorithm and pre-request cost reservations |
| evaluation-raw.zip | Complete per-question results, the 450-request/response ledger, nine run copies and scoring support files |
| snapshot.zip | The shared 215-page memory snapshot, integrity checks, output-limit changes and profile diagnostics |
| build-ledger.zip / build-verification.json | The cumulative 1,052-call construction ledger, budget/configuration records and acceptance checks |

The ZIP files preserve raw evidence without filling the working tree with long prompts and repeated memory text. They contain neither embedding weights nor `.env`. Model outputs, public-dataset conversations and profiles are study materials. API request/response IDs and timestamps support verification and cannot authenticate an account.

From the repository root, run:

```sh
python3 -B eval/verify_submission.py
```

This reads the archives directly, verifies hashes and recomputes the original repository F1 statistics. It uses only the Python standard library, needs no key, third-party dependencies or network, and does not extract archives over local run directories.

Original execution commit IDs remain in the configuration and manifests. The safe publication copy excludes old upstream Git objects. Those IDs identify provenance and are not necessarily available for checkout in this published repository. The original local research history has been retained.
