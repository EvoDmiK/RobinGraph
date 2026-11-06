# TEST native audio card-color verification

2026-11-02, actual https://robingraph-test.dove-nest.com/chat in Chromium headless shell CDP. Actual sparrow chat response and native media controls; no response/media mock or local style override.

Only native audio CSS changed: reuse existing LC card badge background #e3f2c4, preserve light-scheme native controls and add a dark #233d1c focus outline. No custom player, JavaScript change or dependency was added.

Computed audio background and WebKit control-panel background both equal rgb(227,242,196). The native play/pause icon, timeline, volume and menu retain their default dark controls on the light green background. Actual native-control click advances decoded audio to 0.440288 seconds with readyState=4 and no visible media error. Source-button keyboard navigation still opens/focuses the attributed back and stops/resets playback. All six natural-flow checks pass.

Both 390x844 mobile emulation and 1280x800 desktop retain original reopen scale, collapsed fitting details and no horizontal overflow. Keyboard focus is visible at both widths: solid outline rgb(35,61,28). Both viewport checks pass. Screenshots were opened and visually compared: before-native-gray-390.png is the earlier actual TEST gray native player; actual-chat-audio-mobile-390.png is the new green player in playback; actual-chat-audio-1280.png shows the green player with focus outline. Dynamic photo content may differ between before/after because the actual image provider can return a different photo.

Evidence: chat-browser-results.json and run-color-browser.cjs. Local existing chat regression tests: 334 pass, 0 fail/skip. New trivial CSS-only tests were not added. graphify update exited successfully with the pre-existing SQL parser dependency warning.

The WebKit native panel pseudo-element is browser-specific. Safari and Firefox were not run; their native internal panel may keep platform-default colors, though standard outer background, color-scheme and focus styling remain available. No physical mobile, human listening confirmation or physical swipe test was performed. No raw tokens/credentials/full API responses were saved. Verification Chromium exited. No Git, deployment or Production operation was performed by this UI worker.
