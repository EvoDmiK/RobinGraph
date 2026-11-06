# TEST conservation-tier native audio colors

2026-11-02, actual TEST deployed CSS at https://robingraph-test.dove-nest.com/chat, Chromium headless shell CDP. No new JavaScript player or dependency. CSS custom properties are reset on every .species-card and overridden only by its own recognized risk class. This prevents a nested neutral card from inheriting another card's color.

## All-tier CSS fixture matrix

run-tier-browser.cjs creates native audio DOM fixtures using the deployed TEST stylesheet. The fixtures inject class names only; they do not represent real species recordings or change species data. LC, NT, VU, EN, CR and EW reuse their existing light badge surfaces and dark badge text for focus. EX reuses its light card surface #ecebf1 and dark card border #3b3b44, not the dark EX badge. DD, NE, unconfirmed, unknown class, no class and a no-class card nested inside CR all use neutral #f1f2ee/#20351d.

All 13 cases pass computed audio background, WebKit control-panel background, visible keyboard focus and outline-color checks. All seven recognized color tiers have independent colors on one screen; the nested fallback remains neutral despite its CR ancestor. The screenshot all-tier-native-audio-1440.png was opened and visually inspected. Empty fixture players have no source and consequently show disabled native controls. Raw DD/NE/unknown class fixtures may show the pre-existing base card texture; these are robustness cases, not claims that the production renderer assigns those raw card classes to verified species.

contrast-results.json computes relative-luminance contrast from actual computed CSS colors. Focus-to-panel contrast ranges from 9.35:1 to 12.90:1. Black-icon reference contrast ranges from 15.50:1 to 18.68:1. Native icon pixels were not sampled, so this is a CSS-color calculation and visual inspection, not a complete native-control accessibility audit.

## Actual API representatives

Actual GET profiles rendered without changing their conservation data: Passer montanus is LC with one recording and green variables; Aythya ferina is VU with no recording and gold variables; Platalea minor is also VU according to the current server response, with no recording and gold variables. The two VU profiles verify real card-variable selection only; no non-LC recording was invented or played.

## Actual natural chat and media

run-lc-playback-browser.cjs submits the natural sparrow question and uses the actual popup and native audio. All six checks pass: green LC tint, one front audio and no back duplicate, actual decoded playback, no visible error, keyboard source navigation/focus and playback stopping on leaving the front. Both 390x844 and 1280x800 reopening/layout checks pass, including focus outline and no horizontal overflow. Evidence: chat-browser-results.json and screenshots/actual-chat-audio-mobile-390.png plus actual-chat-audio-1280.png.

## Validation and limits

Local existing frontend regression tests: 334 passed, zero failures/skips. graphify update completed with the pre-existing SQL parser warning. No new trivial CSS test was added. The all-tier browser matrix provides the focused styling regression evidence.

Safari, Firefox, physical mobile and human listening confirmation were not performed. Internal native panel colors may remain platform-default where the WebKit pseudo-element is unsupported. No API/schema change, source metadata change, explicit DB mutation, Git operation or Production operation was performed. No raw tokens, credentials or full API responses saved. Verification Chromium processes exited.
