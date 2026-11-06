# Real-browser check: answer notices (TEST, 2026-10-28)

- **Target:** https://robingraph-test.dove-nest.com/chat, the real TEST API.
  - Release `notice-ui-dc72ada65dbf-46b2cc`; served `chat.js` sha256 `35ee4383c8bc…` (matches the deploy).
- **Browser:** Chromium headless shell over CDP.
- **Script:** `run-notice-browser.cjs`, a copy of the reviewed `run-test-browser.cjs` that keeps its helpers (connect, waitForIdle with `aria-busy != "true"`, keyboard submit). No new framework or dependency.
- **Evidence:** `browser-results.json` and `screenshots/`.
- **Tokens:** no raw token or header values are logged. Requests record only `has_followup_context`, and the response keeps only limitations/warnings counts and text. Token-pattern scan of the evidence: 0.
- **Not run:** physical mobile, Safari, Firefox.

## Results (one question per viewport: "숲에 사는 열매 먹는 새")
| Check | 390x844 (tap) | 1280x800 (keyboard Enter) |
|---|---|---|
| answer / graph_query, first request has no context | pass | pass |
| last assistant message has exactly one `.graph-query-notes` | pass | pass |
| collapsed by default (items not visible), summary `안내 및 유의사항 (5)` | pass | pass |
| no `.warnings` list outside the card | pass | pass |
| expands on interaction (tap on summary / Enter, focus on summary) | pass | pass |
| no duplicate items | pass | pass |
| DOM items equal the real response's `payload.limitations + warnings`, trimmed and unique, in order. Raw 5 + 5 = 10 → 5 unique | pass | pass |
| items wrap, no item overflow, notes inside the viewport, no page horizontal scroll | pass (5/5 items wrap) | pass (4/5 wrap) |
| feedback buttons rendered alongside (3; none clicked) | pass | pass |

## Screenshots (3 per viewport; the chat scrolled to the notes)
- `mobile_390x844-1-collapsed.png`, `-2-expanded-top.png`, `-3-expanded-end.png`
- `desktop_1280x800-1-collapsed.png`, `-2-expanded-top.png`, `-3-expanded-end.png`

## Harness notes (no app issue)
- The first run reported 2 failures, and both were bugs in my test code:
  - **Collapsed check:** a closed `<details>` in Chromium still returns layout boxes from `getClientRects`, so I switched to `checkVisibility()`. The screenshot showed the panel visually collapsed.
  - **Enter key:** the CDP Enter key event carried no `text: "\r"`, so no keypress was generated and the summary was not activated.
- After fixing both, one re-run passed everything. I did not loop.
- **Requests:** 2 runs × 2 viewports, read-only questions. No feedback writes.
