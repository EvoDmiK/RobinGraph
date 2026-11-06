# Backend report v2: condition-keeping follow-up, after root review (dev-claude, 2026-10-28)

v1 report items still hold except where this document changes them. The v1 patch is kept as `backend-followup.v1.patch`.

## Summary
- **What I did:** applied all 7 review items and root's contract review (msg_2d49503d032e, read and applied). Contract updated to **v2** (`contract.md`; v1 kept as `contract.v1.md`) and sent to UI `ctx_ee4535e24cd6` (msg_36e9cc088c2d) and root (msg_c62cc134a63a).
- **New patch vs the original baseline:** `/tmp/robingraph-followup-20261028/backend-followup.patch`.
  - sha256 `f8f13524cc25c02e4f06fc5e99a1acce00de5735274c81c058304ef8937e7337`
  - 10 files, +914/−9
  - Applies with `patch -p1` to a copy of the current root tree.
- **Tests, in the dev-claude worktree (after syncing the verification files):**
  - Command: `uv run --locked --extra test --extra tracing python -m unittest discover -s tests`
  - Result: **Ran 1359, OK, 0 failures, 0 errors, 40 skipped**. Run 3 times in a row, identical each time.
- **No TEST deploy, no Production change, no Git operation, no DB write.**

## Changes vs original baseline (the whole patch)

| File | Change |
|---|---|
| `src/robingraph/api/followup.py` (new) | Marker detection (a bare "그중/그중?" counts as a follow-up); sign/verify; addition parsing; merge; `info(plan, retained)`; `route_conflict`; scope labels in prompts |
| `src/robingraph/api/schemas.py` | `ChatRequest.followup_context`; `ChatFollowupPlan{conditions,taxon,scope:SpeciesScope}`; `ChatFollowupInfo{status,reason,root_question,added,plan,retained}`; `ChatResponse.followup_context` / `followup` (omitted when None) |
| `src/robingraph/api/services.py` | Follow-up branch (route/filter conflict check, base vs merged plan, retained plan); effective scope; token issue/keep; `_trace_payload` masks `followup_context` |
| `src/robingraph/api/drf/views.py` | `Cache-Control: no-store` whenever the response carries a `followup_context` (independent of feedback) |
| `src/robingraph/tracing.py` | Allowlist: reasons `followup_context_missing` / `followup_context_invalid`, stage `followup` |
| `src/robingraph/api/drf/openapi*.json` | Only the new properties, `ChatFollowupInfo` and `ChatFollowupPlan` |
| `tests/test_drf_parity.py` | The existing additive projection block now also pops the new models and fields; the migration oracle is unchanged |
| `tests/test_graph_diagnostics.py` | Root-trace output is compared with the token `[redacted]`; on/off body comparisons ignore only the token's value (signing time) and check that it is present |
| `tests/test_graph_followup.py` (new) | 19 tests (18 API, 1 tracing) |

- `tests/fixtures/drf_parity_golden.json` has been **restored to the baseline byte for byte** and is not in the patch.

## Review items

1. **Trace masking and no-store (msg_2d49503d032e §1):**
   - `_trace_payload` replaces `followup_context` with `"[redacted]"` in the route span's request inputs and response outputs.
   - The original question, root question and `graph_followup.canonical_plan` / `.added` / `.turn` are kept.
   - `ChatView` sets `Cache-Control: no-store` on every response that carries a token, even when feedback is unavailable.
   - Tests:
     - `FollowupTracingTest`, tracing on with a fake MLflow SDK: neither the input token nor the output token prefix appears in any recorded span call; `[redacted]`, both questions and the canonical plan do.
     - `test_followup_token_responses_are_never_cached_without_feedback`, tracing off: no-store is set on the base and follow-up responses.
     - `test_feedback_headers_are_kept_on_followups`: the RG603 headers are unchanged.
2. **Explicit intent and filters:**
   - On a follow-up question, an `intent` other than auto/profile, or any non-empty `filters` (profile name, observations, …), gives `route_conflict` clarify. The input token is kept and the handler is never called.
   - An empty `{"kind":"profile"}` filter is not a conflict.
   - A standalone question with an explicit intent still ignores the context. Test: `test_explicit_route_or_species_filter_is_not_dropped_for_the_context`.
3. **Displayed plan vs retained plan:**
   - `followup.plan` is what this response ran or kept. `followup.retained` is what the returned token carries (the last success).
   - Applied but empty or insufficient → `plan` includes the addition and `retained` does not. Tested: scope korea vs all, same conditions.
   - `scope` is the effective species scope (`all|korea|outside|unknown`). An initial korea, outside or unknown scope is shown in `plan` and `retained`, and the rejection prompt names it (국내 기록 / 국외 분포 / 한국 분포 미확인). Test: `test_initial_species_scope_is_shown_in_every_followup_plan`.
   - The contract v2 "minimal display" section tells the UI what to show; sent to UI.
   - The "tokens differ per tab" guarantee was removed; isolation is per-tab memory, never persistent storage.
4. **Golden migration oracle:** restored to baseline. The new schema is projected out in `assert_same`, following the existing feedback/clarify pattern. The exact new-schema check passes separately in `OpenApiContractTest.test_component_schemas_match_the_pydantic_dtos` (component schemas vs live DTOs).
5. **Verification support files:** these are separate from the patch. They are not feature files and are synced from root `dev-codex` only so the suite can run.
   - **Backups:**
     - `/tmp/robingraph-followup-20261028/dev-claude-backup/pre-scripts-sync/scripts-data-before.tar.gz` (my `scripts/` and `data/`)
     - `n8n-before.tar.gz`
     - the earlier `dev-claude-backup/` (first task)
   - **Synced from root:**
     - all of `scripts/` (13 files were missing)
     - `data/eval/graph_questions/` (gates, holdout, question-families v1–v6, taxonomic-regression-v1, manifest)
     - `compose.local-test.yml`
     - `n8n/robingraph-avilist-pipeline-test.json`
   - My own `data/eval/taxon_traits/` and my other existing scripts are left as they were.
   - **Not synced:** UI (`api/static`, `tests/frontend`; dev-agy's files are stale here). The JS frontend tests are not part of the Python unittest suite, so they were **not run** here; UI version assertions are dev-agy's verification.
   - **Root comparison:** a pristine copy of the current root tree (no `.git`) gives Ran 1340, skipped 40, plus 7 failures/errors, all in `test_nas_release_package`, which needs a git worktree.
     - The same copy with my patch applied gives Ran 1359, skipped 40, and the same 7 git-only failures.
     - In the real dev-claude worktree, which has git, those 7 pass: **1359 OK, 40 skipped**.
     - 1359 − 1340 = my 19 new tests; the skip count is identical.
6. **Bare marker, signing, revalidation:**
   - "그중", "그중?", "그 중에서는?", "여기서" → `context_missing` without a token and `unresolved_addition` with one. Never routed as a new question.
   - A signing failure (`signing.dumps` raises) → the base answer stays answer with no token.
   - Correctly signed tokens with an invalid plan → `context_invalid`. Cases: unknown value `Moon`, empty conditions, an injection-like taxon, an unknown scope `s`, version 2, an extra condition key.
7. **Generic ranks and boundaries:** checked through the API with mocks.
   - Taxon at any rank: Turdus, Passeriformes, 까마귀속, 지빠귀과, `Turdus merula 중에서` (species; the active data decides the rank at execution).
   - Measures: wing length `미만`, body mass `초과`, tail length `이상`.
   - Diet: insects, nectar, tree fruit, `먹이 생태 범주가 잡식`.
   - Rejected, the same as the standalone extractor: ambiguous `부리 길이 20mm`, a number with no unit, bare `잡식성`, two habitats, a contradictory range, `무거운`.
   - Nothing new was built for this.

## Test results (exact)
- `uv run --locked --extra test --extra tracing python -m unittest discover -s tests -p test_graph_followup.py` → **Ran 19, OK**.
- `uv run --locked --extra test --extra tracing python -m unittest discover -s tests` → **Ran 1359, OK (skipped=40)**, 3 runs.
- Pristine root copy, same command: Ran 1340, skipped 40, 3 failures + 4 errors (`test_nas_release_package`, no `.git` in the copy).
  - With the patch applied: Ran 1359, skipped 40, the same 3 + 4.
- A flake I caused and fixed: the old diagnostics tests compared whole chat bodies between tracing-off and tracing-on runs. A signed token embeds its signing second, so the tokens could differ. The comparison now checks the token's presence instead of its value.
- **Mock vs real:** all follow-up tests are mock/unit. The only real TEST API check is the read-only v1 probe; TEST still runs baseline code.

## Remaining
- Root/Codex refactoring review. Private extractor names are imported in `followup.py`, as noted in v1.
- After review: plan the TEST deployment and real end-to-end follow-up check with dev-agy (UI must consume v2 `plan`/`retained`).
