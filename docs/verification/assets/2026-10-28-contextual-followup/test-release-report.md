# TEST release report: condition-keeping follow-up (dev-claude, 2026-10-28)

## Result
- **Deployment:** the approved final root snapshot is deployed to TEST only. `state=verified`, container `healthy`, no rollback needed.
- **Live API acceptance:** 29 cases + 5 header/trace checks: **29 pass, 0 fail, 1 no_data** (expected vs actual; see `live/evaluation.json`). 30 evaluated keys in total.
- **MLflow 33 readback:** 29/29 traces read; signed tokens in any span field: none; all traces tagged `validation_phase=followup_acceptance`, `automated_test=true`.
- **Not changed:** Production, NAS app, DBs, n8n, Neo4j, MLflow experiment 50, and Git.

## Gate and source
- I prepared and then waited at the gate.
  - The first prepare (`159a52fc4b8c…`, baseline UI) was **not deployed**, per the coordinator.
  - The final gate approval is msg_a6b4ae937683: UI v2 reviewed, Node 331 tests and backend 56 tests pass, root source frozen.
- **Re-prepared root source** (`/Users/kimdove/orca/workspaces/RobinGraph/dev-codex`) and deployed with `--expect-source-sha256`:
  - `source_sha256`: `69b19f6f5fed1d9def1bb2e98f088d92bf32b216670edb6d749bf5da80bd89bf` (235 files)
  - snapshot: `/tmp/robingraph-followup-20261028/snapshot-69b19f6f5fed`
  - `src/robingraph/api/followup.py` (root's Ponytail refactor): `80d47cc72cce65173d6a938ff64b56a90d46c3cd86cc04eb24388fe0ce1285ef`
  - `src/robingraph/api/static/chat.js` (final UI v2): `ff13a283ab784b2e8cc4c4f3d77611b71b0aabb4c48c09718aaeb14d96aa5afb`
  - base revision (`git rev-parse`, read-only): `318e7731fda8b85560b7e8d464b0f4f2c92439d1` (uncommitted source snapshot)
- **Image:**
  - `robingraph-api:test-followup-69b19f6f5fed`, id `sha256:4c3a532d0f71be6d31bc411db28503a0107bfd0cbe033be72dcb376c6d646a48`, arm64
  - label `org.robingraph.test.source-sha256=69b19f6f…`
- **Release:**
  - new: `/Users/kimdove/robingraph-test/releases/followup-69b19f6f5fed-f80a69` (`RELEASE.json` = `/tmp/robingraph-followup-20261028/test-release.json`)
  - previous (kept for rollback): `/Users/kimdove/robingraph-test/releases/chat-feedback-2e822237c9dc-2377c8`, image `robingraph-api:test-chat-feedback-2e822237c9dc`

## Deploy steps (`deploy_followup_test.py deploy`, log `deploy.log`, exit 0)
1. **Preflight:**
   - current release is under `releases/`;
   - container env `ROBINGRAPH_DEPLOY_TARGET=test`, `MLFLOW_EXPERIMENT_ID=33` (robingraph-test), tracing on, active/semantic;
   - the stable Django key exists (checked, never printed or generated).
2. **Snapshot:** copied and re-hashed; the digest equals the approved SHA.
3. **Build:** `docker build --platform linux/arm64` from the snapshot (log `/Users/kimdove/robingraph-test/followup-build.log`).
4. **Isolated fixture smoke:** `--network none --read-only`. `/health` mode is fixture, and `/openapi.json` contains `ChatFollowupInfo`. Passed.
5. **New release:** a copy of the current release with all source folders and top-level files replaced from the snapshot. All 235 file hashes were re-verified in the release.
6. **`.env.nas.test` comparison:** the only changed key is `ROBINGRAPH_IMAGE`. `compose.nas.yml` and `compose.mac-test.yml` are identical. The DB, Neo4j, n8n, MLflow and signing key settings are preserved.
7. **Switch and start:** atomic `current` symlink switch, then `manage.sh start`. Health became healthy and `manage.sh verify` passed: health, openapi and lineage all ok. Automatic rollback was armed but not triggered.

## Live API acceptance (`verify_followup_live.py`; evidence in `live/responses.json`)
- Requests went to `https://robingraph-test.dove-nest.com/v1/chat`.
- **Raw tokens are never written to files.** The evidence records only `token_returned`, `token_unchanged` and the first 12 characters of the sha256. A pattern scan of `responses.json`, `trace-readback.json` and `evaluation.json` found 0 signed values.
- **Real API vs mock:** every row below is a real TEST API call against real TEST Neo4j data. Expired-token handling was **not verified live**, because it needs one hour, an unchangeable signing time, or access to the key. It is covered only by the unit test (`_MAX_AGE` patch).

| Case | Real result | Verdict |
|---|---|---|
| chain.base: 숲에 사는 열매 먹는 새 | answer, 1775 of 6898 evaluable, token issued | pass |
| chain.korea: 그중 한국에서 볼 수 있는 새는? | answer, 48 of 410; executed conditions = base 2; `plan.scope=korea`; KOS/AviList korea_record warning; new token | pass |
| chain.number: 그 새들 중 체중 100g 이상인 새는? | answer, 10 of 410; plan = 숲 + 열매 + 체중 100g 이상, scope korea (conditions accumulated) | pass |
| rank.order: 그중 참새목 새는? | answer, 1115 of 3983 | pass |
| rank.family: 그중 직박구리과 새는? | answer, 47 of 81 | pass |
| rank.genus: 그중 Turdus 새는? | answer, 51 of 60 | pass |
| rank.species: 그중 Hypsipetes amaurotis에 속하는 새 | insufficient_data: "Hypsipetes amaurotis의 서식 환경, 먹이 구성 자료가 그래프에 없어…"; plan applied; token kept (last success) | **no_data** (contract held; not counted as an answer) |
| indep.wetland: 습지에 사는 새 알려줘 → 그중 물고기 먹는 새는? | answer 590 of 9796 → answer 172 of 6898 | pass |
| indep.seed (scope korea): 참새목 중 씨앗 먹는 새 → 그중 숲에 사는 새는? | 88 of 165 → 35 of 164; plan scope korea and taxon 참새목 kept | pass |
| indep.order_fruit: 참새목 중 열매를 먹고 사는 새는? → 그중 날개 길이 100mm 미만인 새는? | order_fruit answer → taxon_traits 1015 of 3978 (열매 + 접은 날개 길이 100mm 미만) | pass |
| ctx.missing / ctx.forged / ctx.garbage | clarify `context_missing` / `context_invalid` / `context_invalid`, no token | pass |
| ctx.scope_mismatch (token from all, sent with outside) | clarify `context_scope_mismatch`, no token | pass |
| ctx.bare: 그중? | clarify `unresolved_addition`, input token kept | pass |
| add.negation / unresolved / multiple / conflict / duplicate | `unsupported_addition` / `unresolved_addition` / `multiple_additions` / `conflicting_condition` / `duplicate_condition`; token kept; prompts list the kept conditions | pass |
| add.route_conflict (profile filter 직박구리) | clarify `route_conflict`, token kept, filter not dropped | pass |
| empty.followup: 참새목 중 숲에 사는 새 → 그중 체중 5000g 이상인 새는? | empty (0 of 5760); `plan` includes 체중 5000g 이상, `retained` = 숲 only; token unchanged | pass |
| empty.next_uses_retained: 그중 한국에서 볼 수 있는 새는? | answer 109 of 239; plan = 참새목 + 숲 + korea, without 5000g | pass |
| new.standalone_graph (with context): 습지에 사는 새 알려줘 | answer; no `followup`; its own new token | pass |
| new.other_kind (with context): 까치와 같은 속인 새 | answer (Pica); no `followup`, no token | pass |
| headers.no_store_with_token | every token response has `Cache-Control: no-store` | pass |
| headers.feedback_kept | every response has `X-RobinGraph-Trace-Id` and a feedback token (RG603) | pass |

## MLflow 33 trace readback (`readback_followup_live.py`; evidence in `live/trace-readback.json`)
- `MlflowClient` against experiment 33 (name `robingraph-test` confirmed). Read-only, except the validation tags.
- For all 29 traces:
  - experiment 33;
  - the root input question equals the question sent;
  - the request `followup_context` is `[redacted]` exactly when a context was sent;
  - the response `followup_context` is `[redacted]` exactly when a token was returned;
  - no Django signed-value pattern (`.eJ…` follow-up / `eyJ…:` feedback) appears in any span input, output or attribute.
- Follow-up traces carry `graph_followup.status`, `.reason`, `.root_question`, `.added`, `.turn` and `.canonical_plan`. For example, chain.number has turn 2, added `체중 100g 이상`, and the canonical plan conditions plus `species_scope=korea`.
- Tags `validation_phase=followup_acceptance` and `automated_test=true` were set on all 29 traces.
- No trace deleted. Experiment 50 (Production) not used.

## Deviations and notes
- **First live attempt:** Cloudflare returned 403 to the default Python urllib user agent. No request reached the app. I added an explicit User-Agent and re-ran.
- **One token on the terminal:** while diagnosing the 403, a manual `curl` printed one base-question follow-up token to my terminal output. It was not written to any file or report. It is a 1-hour, plan-only capability with no credentials.
- **MLflow client:** my worktree venv has only the skinny tracing client, so the readback ran with `uv run --extra tracing --with mlflow==3.14.0`. Readback used the saved responses (no re-posting).
- **Answer text:** with a Korea scope the answer text still says "전체 조류 범위…". Korea is conveyed by the warning and `followup.plan.scope` (known limit, unchanged).

## Not verified / follow-ups
- Expired-token rejection on live TEST (unit-tested only).
- Real browser checks: handed to UI dispatch `ctx_1cc08b1cdd41`, notified at healthy (msg_4fe98bb55ae3); root notified (msg_d71da708c753).
- **Rollback, if needed:** atomically switch `/Users/kimdove/robingraph-test/current` to `releases/chat-feedback-2e822237c9dc-2377c8`, then run `manage.sh start`. Not performed and not needed.
- **Files:** `deploy_followup_test.py`, `verify_followup_live.py`, `readback_followup_live.py`, `deploy.log`, `test-release.json`, `test-release-prepare.json`, `live/`.
