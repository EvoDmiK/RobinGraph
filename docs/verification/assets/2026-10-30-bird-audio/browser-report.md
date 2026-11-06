# Bird recording TEST browser verification

2026-10-30, actual https://robingraph-test.dove-nest.com/chat, Chromium headless shell CDP. No mocked API response or mocked audio. Browser emulation is not a physical mobile-device test; audio was not confirmed by human listening.

## Actual profile API and existing renderer

run-audio-browser.cjs loads actual GET /v1/taxa/profile data for Passer montanus, Hypsipetes amaurotis and Anas platyrhynchos, then mounts the existing deployed card/popup renderer. This first phase is renderer integration, not a natural chat interaction. Each species has one available recording; Treron sieboldii has none and shows explicit no-confirmed-recording text. All original supplied creator/title/license and optional metadata values match the rendered text. No unsupported metadata was invented.

Before any play gesture, all three controls have preload=none, autoplay=false and paused=true; no recording URL network request occurred. Native control clicks decode actual media: sparrow currentTime 0.535s/decodedBytes 21287, bulbul 0.362s/4816, mallard 0.325s/8671, all readyState=4 and no media error. Closing each popup pauses and resets currentTime=0. Real-media lifecycle probes also verify single playback across cards, DOM-removal cleanup and conversation-clear cleanup. The initial flip probe was not relied on because the first audio was already stopped by the single-playback probe; the natural chat phase below verifies active playback stopping on a real face transition.

## Actual natural chat interaction

run-chat-audio-browser.cjs submits the actual chat question asking about the sparrow, uses the naturally generated popup, flips to its back and expands the recording section. A native-control click starts decoded playback. visibleErrors is empty (hidden error status text exists in DOM but is not visible). Enter while the recording is actively playing changes to the front face and pauses/resets the recording. All four checks pass.

The same natural popup is tested at 390x844 and 1280x800: expand distribution and audio details, close, reopen. Front face restored, all fitting toggles closed, original scale restored (mobile 0.833333, desktop 0.785639), dialog inside horizontal viewport, no document horizontal overflow. Both viewport checks pass. Screenshots actual-chat-audio-mobile-390.png and actual-chat-audio-1280.png were visually inspected.

## Scope and evidence

browser-results.json contains the API/renderer/media-lifecycle phase. chat-browser-results.json contains the natural chat and mobile/desktop reopening phase. Actual recording metadata is preserved in evidence, but full API responses, feedback/followup tokens and authentication data are not stored. No code edit, server restart, deployment, Git operation or explicit DB mutation was performed by this verification. Existing application tracing may record the chat interaction normally.

No physical mobile, Safari, Firefox or human listening confirmation. Provider-failure UI behavior and hostile URL rejection were tested separately in Node tests, not by disrupting an external live provider. Verification Chromium processes were terminated.
