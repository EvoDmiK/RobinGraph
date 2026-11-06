# TEST front-face recording controls verification

Date: 2026-11-02. Target: https://robingraph-test.dove-nest.com/chat. Chromium headless shell, CDP input. Actual TEST API and actual media; no response or media mocks. No human listening confirmation, physical mobile device, Safari or Firefox.

## Actual profile API plus deployed renderer

run-front-audio-browser.cjs loads actual GET profiles for Passer montanus, Hypsipetes amaurotis, Anas platyrhynchos and unsupported Treron sieboldii, then mounts the deployed card/popup renderer. This phase is explicitly renderer integration, not a natural chat interaction.

Supported species each have one native audio only in the front face and none in the back. All supplied title, creator, license, source and optional recording metadata are retained in the back. Before playback there are zero requests to the recording URLs, preload is none, autoplay is false and players are paused. Native control clicks successfully decode actual clips: sparrow time 0.529915s / decoded 20731 bytes, bulbul 0.305637s / 4370 bytes and mallard 0.315625s / 8359 bytes. All have readyState 4 and no media error. Popup closing pauses and resets every recording. Starting another recording stops the old one. Source navigation, DOM removal and conversation clear also pause/reset real media.

Unsupported Treron sieboldii has no front audio and its empty controls section is hidden. Back-face no-confirmed-recording text remains explicit. Ten aggregated checks and three playback/close/layout checks pass. Evidence: browser-results.json.

## Natural chat interaction and source navigation

run-natural-front-browser.cjs submits the actual sparrow question and opens the naturally generated popup. Its native player is visible in the front, immediately after the photo area; there is one front audio and zero back audio. Clicking the native control advances decoded playback. No error status is visible (hidden error fallback text is not treated as an error).

Focusing the small source button and pressing native Enter switches to the back, opens recording metadata and moves focus to its summary. Active audio stops and resets to time zero on this transition. The original audio remains one DOM element; metadata is not duplicated into the visible front. All five natural-flow checks pass.

At 390x844 and 1280x800, expanding distribution/source metadata, closing and reopening restores the front and collapsed toggles. Fit scale returns to its baseline: mobile 0.833333, desktop 0.780693. Neither document nor dialog overflows horizontally. Both viewport checks pass. Evidence: chat-browser-results.json.

## Visual evidence and limits

The screenshots actual-chat-audio-mobile-390.png, actual-chat-source-back-390.png and actual-chat-audio-1280.png were opened and visually inspected: player below photo, small source link, attributed back metadata, no duplicate player. Metadata includes an overseas location exactly as supplied; no domestic recording claim was generated.

Unit tests cover the photo-unavailable/deferred path, error presentation and URL trust boundary. Live external-provider failure was not induced. This round does not add a physical swipe test; existing frontend gesture regression checks passed before TEST deployment. No raw full API responses, signed tokens or credentials were saved. No code edit, explicit DB mutation, Git operation or deployment was performed during browser verification. Both verification Chromium processes exited.
