# Chat UI integrated verification — 2026-09-14

## Scope and provenance

- Branch: `robingraph-chat-ui-verified-retry-20260914`
- Verified product HEAD before this report-only commit: `880308f6a011c04284f55cab4cd0244fbc08abef`
- Comparison base: `335d59a4283dd99416f23f179f936e0ddcd172d0`
- Reviewed base: `687d6ce10079c60d17aaf07f0812552483bbb6ea`
- Source commits: `7ca20ad92be5c43cc921423af38b7bf45a9b7882` and `c7d85763286f2715f14c547598fb660b052aa38b`
- Integrated commits: `ac584f7a4bdebf2b4267a9cf434b1853c3250098` and `880308f6a011c04284f55cab4cd0244fbc08abef`
- Stable patch IDs matched source to integrated exactly: `8e51e68a385c4b828728b4c79e94f70a8aacd28e` and `e7cf2541535f8ed0120982620409ddc0ab364155`. There were no conflicts: `docs/chat-ui.md` auto-merged cleanly and no manual conflict-resolution delta was present.
- Orca Run/Task/Dispatch: `run_ba50eebff154` / `task_f51fa7658fb7` / `ctx_f411a3fe9bf6`; worker terminal `term_73827de9-7496-461e-8c41-86ae99cc23a0`.
- Launch metadata (`orca orchestration worker-show --dispatch ctx_f411a3fe9bf6 --json`) recorded requested and effective agent/model as `codex` / `gpt-5.6-sol`; effort was `null`.
- Prior source-run assignments (authoritative coordinator provenance from `run_223165b6ac47`): Claude frontend task `task_c1c2c9241420`, dispatch `ctx_3a6f14e5620f`, source `7ca20ad92be5c43cc921423af38b7bf45a9b7882`; the exact provider model was unavailable/unverified beyond the real commit trailer `Claude Sonnet 5`. GPT-5.6 Terra backend/CI/packaging task `task_53b1e639030d`, dispatch `ctx_84559ed17f4f`, source `c7d85763286f2715f14c547598fb660b052aa38b`; the Orca projection recorded `gpt-5.6-terra`.
- Current ownership boundary: frontend findings would route to Claude; FastAPI/CI/packaging findings would route to GPT-5.6 Terra. No blocker was found, so neither route was needed. This current Sol worker independently verified the integrated tree.

## Integrated diff review

The complete `335d59a4..HEAD` diff comprised 13 files, 1,926 insertions, and 7 deletions. I inspected all changed CI, packaging, FastAPI, HTML, CSS, JavaScript, Python/Node tests, and documentation. The implementation serves a fail-closed three-file UI bundle from both fixture and Neo4j app factories, packages it in the wheel, uses only same-origin `/health` and `/v1/answers`, renders dynamic values with text nodes, gates dispositions, sanitizes citation URLs, and never consumes backend `detail` in the UI error path.

No implementation or test fix was made during verification. The only non-blocking observation was setuptools' warning that the TOML-table form of `project.license` becomes unsupported after 2027-02-18; it did not affect this wheel or the requested contract.

## Required command results

Local tools were `uv 0.11.16`, CPython `3.12.13`, and Node `v26.0.0`.

| Command | Exit/result |
|---|---|
| `git status --short --branch` | `0`; initially clean: `## robingraph-chat-ui-verified-retry-20260914` |
| `git diff --check 335d59a4283dd99416f23f179f936e0ddcd172d0..HEAD` | `0`; no output |
| `git diff --name-only 335d59a4283dd99416f23f179f936e0ddcd172d0..HEAD -- tests/test_n8n_workflows.py` | `0`; empty output |
| `uv lock --check` | `0`; resolved 26 packages |
| `uv sync --locked --extra test` | `0`; built RobinGraph and installed 25 packages into a new `.venv` |
| `uv run --locked robingraph validate-fixture` | `0`; 10 taxa, 100 allowed observations, 2 allowed documents, 4 allowed chunks |
| `uv run --locked robingraph evaluate-fixture` | `0`; 15/15 gold questions passed |
| `uv run --locked --extra test python -m unittest discover -s tests -v` | `0`; 303 tests ran in 4.862s, 22 disposable-Neo4j opt-in tests skipped, all others passed |
| `node --test tests/frontend/chat_ui.test.js` | `0`; 30/30 passed, 0 failed/skipped |
| `uv build --wheel --out-dir "$wheel_dir"` followed by `unzip -Z1 "$wheel_path"` | `0`; 36 wheel entries; `robingraph/api/static/index.html`, `chat.js`, and `styles.css` all present |

No test rerun was needed after a failure: every executed verification check passed on its first actual run.

## Loopback HTTP smoke

Started `uv run --locked robingraph serve-fixture --host 127.0.0.1 --port 8765`, used ordinary `curl` HTTP requests only, and terminated the Uvicorn process with Ctrl-C. Results:

| Request | Result |
|---|---|
| `curl http://127.0.0.1:8765/health` | `200`; `status=ok`, `mode=fixture`, taxonomy release `fixture-avlist-2025` |
| `curl http://127.0.0.1:8765/` | `200`; 2,790-byte HTML |
| `curl http://127.0.0.1:8765/chat` | `200`; byte-identical to `/` |
| `curl http://127.0.0.1:8765/static/chat.js` | `200`; 14,867 bytes |
| `curl http://127.0.0.1:8765/static/styles.css` | `200`; 6,444 bytes |
| `curl -H 'Content-Type: application/json' -d '{"question":"2025년 1월 fixture 호수에서 흰뺨검둥오리가 관찰됐나?"}' http://127.0.0.1:8765/v1/answers` | `200`; `disposition=answer`, citation/evidence `fixture-occ-001` |
| `curl -H 'Content-Type: application/json' -d '{"question":"말똥가리의 정확한 관찰 좌표를 알려줘."}' http://127.0.0.1:8765/v1/answers` | `200`; `disposition=abstain`, warning `sensitive_coordinates_withheld` |
| Empty and missing `question` JSON bodies | both `422`; bounded FastAPI validation bodies |

The frontend contract maps both 400 and 422 to distinct fixed generic messages and ignores response `detail`. A separate real `init` → form `submit` → fetch-response → rendered-error probe exercised 12 adversarial 400/422 payload cases (credential-like strings, internal URLs/paths, control bytes, and a 20,000-character value); all rendered only the fixed message. A post-termination `curl --max-time 1` failed with exit `7`, proving the loopback server stopped.

## Focused contract evidence

- CI: `.github/workflows/ci.yml` contains an independent `frontend-contract` job whose only test command is `node --test tests/frontend/chat_ui.test.js`. The suite imports only Node built-ins (`node:test`, `node:assert/strict`, `node:fs`, `node:path`) and `chat.js`; CI performs no npm install and invokes no browser, Playwright, Selenium, CDP, Puppeteer, Cypress, or jsdom.
- Deterministic contrast tests parse the actual `styles.css` declarations and passed all eight theme/purpose cases. Exact ratios were: send light `5.987:1`, send dark `8.311:1`, answer light `9.942:1`, answer dark `6.607:1`, abstain light `8.484:1`, abstain dark `5.998:1`, clarify light `8.484:1`, and clarify dark `5.998:1`.
- The real registered keydown path passed: plain Enter and post-composition Enter prevented default and called `form.requestSubmit()` once; composing Enter did not submit; Shift+Enter did not submit in either composition state.
- An additional 68-assertion TestClient matrix covered missing bundles, one-asset-missing partial bundles, zero-byte assets, and forced read failure. In every case, five UI routes returned only `503 Chat UI is temporarily unavailable.`, while `/health` and `/v1/answers` remained `200`.
- Adversarial arbitrary 400/422 details did not affect helper output or the actual rendered error path; the source assertion also proved the HTTP branch never reads `context.detail`.

## Limitations and prohibited-action confirmation

- Neo4j opt-in tests were not run. No disposable, explicitly non-operational service and its test-only connection contract were provided; per scope, the 22 guarded tests remain locally unverified. No NAS or operational Neo4j endpoint was accessed.
- Remote GitHub Actions were not triggered or queried; only the checked-in workflow and local commands were verified.
- No browser or browser tooling was used. No `.env`, credentials, secrets, NAS, deployment, push, pull request, or n8n behavior was accessed or changed. `tests/test_n8n_workflows.py` remained untouched.

Verdict: every required non-Neo4j check passed with no blocker; the integrated chat UI verification contract is satisfied locally for product HEAD `880308f6a011c04284f55cab4cd0244fbc08abef`.
