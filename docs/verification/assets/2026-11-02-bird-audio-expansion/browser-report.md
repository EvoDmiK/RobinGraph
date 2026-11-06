# TEST recording expansion: partial playback verification

2026-11-02, actual https://robingraph-test.dove-nest.com/chat, Chromium headless CDP. No mocked media or server response. This report does not claim all14 recordings play successfully.

## Source and metadata

The reviewed catalog contains existing3 plus new11 =14 unique species. Uncertain Anas crecca, video Garrulus glandarius and cross-species substitutions for Pica serica/Parus cinereus are excluded. Offline independent comparison of pinned Commons metadata versus actual TEST API and rendered back-face attribution passes14/14 across13 checks per species: one recording, page-based ID, title, original media/source URL, creator, license and canonical secure license URL, DateTimeOriginal, original location/type, rendered metadata and unchanged LC palette. Upload date is not substituted for recording date. Streptopelia orientalis and Corvus corone retain missing locations; no inferred location was added. API-provided Korean names/display names are stored in coverage.json for user examples; names were not recalled or generated.

All14 actual GET profiles return one available recording; unsupported Treron sieboldii returns none with explicit no-recording text and a hidden empty front controls section. The API available status means a licensed linked record exists, not guaranteed CDN availability. All14 keep one front player, zero back duplicates, preload none and no autoplay; no recording request occurs before playback. Metadata checks use actual GET data mounted through the deployed renderer, not the natural chat route.

## Initial actual playback

The first batch attempts all14 with actual native control clicks. Seven decode successfully (including the MP3 Ardea cinerea), seven fail or time out. Exact first-pass results remain in browser-first-pass-results.json. The full-card batch may also have loaded photos, so extra image traffic could have contributed to request volume; that is a hypothesis, not a demonstrated cause.

A fresh native-audio-only diagnostic reproduces Chromium ORB for all seven failures. A single authorized Range diagnostic confirms Cuculus canorus HTTP429 with text/html and Retry-After600; its body starts with a Wikimedia HTML error page. It does not establish that all seven first failures had HTTP429. No browser security setting or URL was changed. Extra CDN requests were stopped.

## Controlled retry and remaining failures

After the conservative earliest retry time2026-11-02T08:13:03.962Z, root authorizes one retry pass for failed seven only. One native audio is used on about:blank with no images or profile requests, unchanged actual API URLs and20-second gaps. Fetch response-stage monitoring records status/Content-Type/Retry-After and aborts further requests if429 is observed. Five retry cases decode successfully: Cuculus canorus, Fulica atra, Hirundo rustica, Motacilla alba and Nycticorax nycticorax. HTTP206 and original OGG/MP3 MIME are observed, currentTime advances and readyState is4. Picus canus remains at time0/ready0 with ORB after an initial206 response; Corvus corone reports MediaError4/ORB without a visible final HTTP response. These two are not reported as successful.

One further authorized Range0-127 diagnostic for the remaining two immediately encounters Picus canus HTTP429/text-html/Retry-After600 at2026-11-02T08:18:43.767Z. Its128-byte signature is Wikimedia Error HTML, not Ogg. The stop rule applies immediately: no Corvus diagnostic request and no further playback retry are made. Corvus HTTP status/codec cause remains unconfirmed.

Unique coverage combines the initial successful seven and retry successful five without double counting:14 metadata passes,12 decoded-playback passes,2 unverified. Retry results are5 pass/2 fail; seven initially successful species were not retried. All14 species were attempted at least once. coverage.md lists every species with initial/retry/final status. slow-retry-results.json and remaining-two-range-diagnostic.json retain the partial failures.

## Natural chat, layout and skipped checks

A separate actual sparrow chat question creates its natural popup, verifies front-only playback, native decoded time, no visible errors, keyboard source navigation, focused back summary and pause/reset on leaving the front. All five checks pass. Both390x844 and1280x800 reopen/layout checks pass, with unchanged fit scale and no horizontal overflow. Evidence: chat-browser-results.json and screenshots/actual-chat-audio-mobile-390.png / actual-chat-source-back-390.png / actual-chat-audio-1280.png.

The aggregate14-species batch skips its final single-playback/DOM-removal/clear probes because its all-playbacks-success guard is false. They are not claimed as newly executed for this expansion. The unchanged UI lifecycle had passed on the preceding front-audio release; this run's natural chat independently covers source navigation and reopening. No new app code was added by this UI worker.

## Limits and artifacts

coverage.json and coverage.md provide the unique species table; independent-metadata-comparison.json provides original-source checks. Public audio/source URLs are preserved, while raw complete API responses, signed tokens and credentials are not stored. No app edit, explicit DB write, Git operation or Production action was performed. Verification Chromium processes exited. Human listening, physical mobile, physical swipe, Safari and Firefox were not performed. Non-LC colors were not newly fixture-tested because the app CSS is unchanged and actual recording species in this batch return LC.

Two files remain unverified for live playback; further scope/deployment decisions belong to root. No further CDN request is pending.

## Final released TEST support scope

Root narrows the final catalog to original3 plus new9 =12 verified-playback species. The source review remains original3 plus new11 =14 candidates, with Picus canus and Corvus corone pending rather than declared invalid or silently deleted from historical evidence. Historical14-source and2-unverified playback results above are preserved.

After the final12-species app/graph release, run-final-support-check.cjs makes15 HTTP basic-profile requests through POST /v1/chat with defer_enrichment=true and defer_discovery=true. This avoids the full GET profile's external photo-enrichment handler. No CDN, image or playback request is made. All15 assertions pass: supported12 return exactly one available recording each with unchanged audio/source URLs; pending Picus/Corvus return zero linked recordings/no_licensed_recording for the current release; previously unsupported Treron sieboldii also returns zero. All15 profiles mark enrichment_pending=true. Only selected metadata is saved, never signed tokens or full chat responses.

Receipt: final-support-http-results.json. coverage.json.publicSupport and coverage.md explicitly list supported12, new9, original3 and pending2, distinct from the original14-candidate playback review. No further CDN request was attempted after the scoped HTTP429 stop.
