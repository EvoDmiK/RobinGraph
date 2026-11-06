# Pre-MLflow review of the 496-question scorer (Claude, read-only)

- **Read:**
  - `dev-codex/docs/verification/assets/2026-10-22-taxonomic-coverage/verify-api.py`;
  - `verify-db-evidence.py` and `independent-cases.json` (counts only) in the same folder.
- **Not done:** no app, DB, deploy or dataset change, and no scorer run.
- **Overall:** the scorer is deterministic and mock-free, and it compares the taxon and the conditions strictly. The three points below are what could still hide a regression in the MLflow re-evaluation.

## 1. verify-api alone does not judge result correctness (most important)
- **What it passes:**
  - for `query`, any of `answer`, `empty` or `insufficient_data`;
  - the items, `coverage`, `has_more` and the per-item condition evidence are never checked.
- **Where correctness is checked:** only in `verify-db-evidence.py`, which recomputes ancestry from parent edges plus the claim guard.
  - It checks status, `coverage == {scoped, evaluable, matched}`, membership, pagination, scope and support for each item.
- **Risk:** if MLflow scores only with the verify-api contract, any of these passes as success:
  - a wrong filter, such as a dropped AND condition or a wrong threshold direction;
  - a scope widened to the order;
  - an `insufficient_data` that should have been `answer`.
- **Check needed:** run the DB-evidence checks per question as a second deterministic scorer in the same run, read-only.
  - Do this at least for the 432 broad cases plus the `query`/`empty` cases in the natural sets.
  - Alternatively, store the oracle values in a separate run artifact, not the dataset, and compare against them.

## 2. Hold and insufficient pass criteria are loose
- **`hold`:** passes when `disposition != 'clarify'` but `status == 'insufficient_data'`.
  - A question with an unsupported word could run as taxon_traits with that word dropped. If it then lands on insufficient (`evaluable=0`, or a resolution failure), the scorer still passes it.
- **`insufficient`:** passes on any insufficient result, whatever the reason. The subspecies text check is the only exception.
  - Example: a homonym (나팔새류) or a rank-conflict label coming back as `not_found` would pass, and so would a subspecies whose taxon resolution failed.
- **Check needed:**
  - For `hold`: require `disposition == 'clarify'`, or `insufficient_data` that carries no executed `conditions`.
  - For `insufficient`: check the reason:
    - `payload.taxon_resolution` (ambiguous / label_rank_conflict / not_found);
    - for a subspecies, `coverage.evaluable == 0` plus the taxon rank `subspecies`;
    - for a specific plant, the `no_plant_level_diet` limitation.
- **Coverage note:** all 432 broad cases are `query`. The hold and insufficient paths are covered only by the 44 + 20 natural sets: 14 holds and 4 insufficient cases. Report the hold and insufficient metrics separately so this small sample stays visible.

## 3. Cause of each run and its latency are not recorded
- **What is missing:** each row has only the response and elapsed time. It does not record `selected_intent`, `route_method`, `result.kind` or the graph-intent trace (router status/top).
  - A passing response could have come from another route.
  - When the router hits its 2 s timeout it falls back to rules (`unavailable`), and that difference between runs is invisible.
- **Latency:** the first call includes the cold prototype load (about 2 s on TEST). An average over the whole run mixes cold and warm.
- **Not covered:** only `species_scope='all'` is exercised. Within the top 20, only subset is checked, not the ordering rule (Korean name first, then name, then id).
  - The scope and ordering choices are not regression-tested.
- **Check needed:**
  - log `selected_intent / route_method / disposition / result.kind` and `graph_intent.status/top` per question;
  - aggregate latency separately for the first (cold) call and warm calls (p50/p95);
  - if a run compares against the previous run's per-question result, it should see those fields change too.
- **Also:** the existing script ends with `assert not failures`, so it stops a run halfway. The MLflow version should record every question and only judge the aggregate at the end.
