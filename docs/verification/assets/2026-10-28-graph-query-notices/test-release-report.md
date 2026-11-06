# TEST release report: answer-notice dedup/visual UI (dev-claude, 2026-10-28)

## Result
- Root's final UI integration is deployed to **TEST only**: `state=verified`, container `healthy`, no rollback.
- **Real API:** 2 calls, 8 of 8 checks pass (`live/evaluation.json`).
- **Not changed:** Production, NAS app, DB, n8n, Neo4j, MLflow experiment 50, app code and Git.

## Gate and source
- **Prepare only, before approval:**
  - The dry-run prepare hashed root to `69b19f6f5fed…`, identical to the release already on TEST, because the UI was not integrated yet.
  - I reported status (msg_47949cb66f1f) and waited at the gate.
- **Approval:** msg_2fbf1bf9c445 ("최종 UI 통합본 TEST 배포 승인").
  - Root UI tests: 333 pass, 0 fail, 0 skip.
  - Root source frozen; the 69b19f6 snapshot was not to be used.
- **Re-prepared from `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex`** and deployed with `--expect-source-sha256`:
  - `source_sha256`: `dc72ada65dbff3b6283851b105b21209fd099b7d904abfa58ea615f5b28d9594` (235 files)
  - snapshot: `snapshot-dc72ada65dbf`
  - Only 2 files differ from the previous release (69b19f6):
    - `src/robingraph/api/static/chat.js`: `35ee4383c8bc80d828a1a213d1efb2b5250accaa71895ea129120dea09421d6a`
    - `src/robingraph/api/static/styles.css`: `dd08f595777916e49174b94adef05786591b32afc191e6566837b58c9ebd7dc1`
  - `followup.py` is unchanged (`80d47cc7…`).
  - base revision (read-only `git rev-parse`): `318e7731fda8…`, an uncommitted snapshot.
- **Image:** `robingraph-api:test-notice-ui-dc72ada65dbf`, id `sha256:0e0bd708cca7a2cef74eda20dc62f7fcc05183deee931bc8b05bb9c788640280`, arm64.
- **Release:**
  - new: `/Users/kimdove/robingraph-test/releases/notice-ui-dc72ada65dbf-46b2cc` (receipt `test-release.json`)
  - previous, kept for rollback: `releases/followup-69b19f6f5fed-f80a69` (`robingraph-api:test-followup-69b19f6f5fed`)

## Deploy steps
- Script: `deploy_notice_ui_test.py`, log `deploy.log`, exit 0.
- It is the reviewed `deploy_followup_test.py` with only names changed: work path, image prefix, release prefix, smoke container, build log and temp symlink (7-line diff).
- Steps:
  1. **Preflight:** env target test; MLflow 33; tracing on; active mode; stable Django key present (checked, never printed or generated).
  2. **Snapshot:** re-hashed and checked against the approved SHA.
  3. **Build:** ARM64 (log `/Users/kimdove/robingraph-test/notice-ui-build.log`).
  4. **Smoke:** `--network none --read-only` fixture smoke passed.
  5. **Release:** all 235 file hashes re-verified in the new release.
  6. **Switch and start:** atomic `current` switch, then `manage.sh start`. The container became healthy and `manage.sh verify` passed.
- **Preservation check:**
  - In `.env.nas.test`, the only changed key is `ROBINGRAPH_IMAGE`.
  - `compose.nas.yml` and `compose.mac-test.yml` are identical.
  - The live `/static/chat.js` sha256 equals `35ee4383c8bc…`.
- **Healthy notifications:** root msg_7e8f9580ebe8, UI dispatch `ctx_7d1368d8a9cd` msg_236ff2fcdb00.

## Real API check (`verify_notice_ui_live.py`, real TEST API and Neo4j)
| Case | Result |
|---|---|
| 숲에 사는 열매 먹는 새 | answer, follow-up token issued, `no-store`, trace and feedback headers present, 5 warnings, no duplicates |
| 그중 한국에서 볼 수 있는 새는? (with the previous token) | answer, `followup.status=applied`, plan = 숲 + 열매 with `scope=korea`, new token, KOS/AviList korea_record warning added (6 warnings, no duplicates), `no-store`, headers present |

- Trace ids: `tr-15c914c3e87d…`, `tr-7f27946c4ddc…`.
- **Tokens:** follow-up and feedback token values are not written anywhere; only a 12-character sha256 prefix and presence flags are recorded. A pattern scan of the evidence found 0 signed values, and no token was printed to the terminal.
- **Script fix:** the first run reported `feedback_headers_kept=false` because of a bug in my script. Cloudflare lowercases `x-robingraph-*` header names, and the script used a case-sensitive dict. I switched to the case-insensitive `HTTPMessage` lookup and re-ran (2 more POSTs): 8 of 8 pass.
- Server-side API warnings have no duplicates. The visual notice dedup itself is UI behaviour and needs the real browser check.

## Not verified / follow-ups
- **Real browser check:** by the UI owner, after root sends a new dispatch.
- **MLflow trace readback:** not run for this deploy. It was not requested, and there were no backend changes.
- **No full Python re-run:** per the brief; app code was not changed here.
- **Rollback, if needed:** atomically switch `/Users/kimdove/robingraph-test/current` to `releases/followup-69b19f6f5fed-f80a69`, then run `manage.sh start`. Not performed.
