# RG-013 intent evaluation set — report

## What was produced
- `tests/fixtures/jev_intent_eval.json`: object `{version, labels, cases[]}`. 120 unique questions (case-insensitive unique), ids `jev-001..120`.
  Each case has `id, split, question, label, name (optional), category`.
- Split: 64 calibration / 56 heldout, assigned alternately within each label, so every label appears in both splits (ecological_* have 5 cases: 3/2 and 3/2).
- Label counts: uncertain 19, subspecies 16, profile 12, taxonomy 11, observations/diet/habitat 8 each, evidence/activity/appearance/related 7 each, ecological_diet 5, ecological_habitat 5.
- Categories: reported, paraphrase, common_name, scientific, english, typo, ambiguous_name, ambiguous_reference, unsupported, absent_taxon, multi_intent.
- Includes the two reported cases (`청둥오리 아종 알려줘`, `흰뺨검둥오리 아종 알려줘`) -> subspecies. The two reported cases are split across sets: jev-001 (청둥오리) is calibration, jev-002 (흰뺨검둥오리) is heldout.

## Labeling method / honesty note
Labels were written by me (the model, Sonnet 5.5, `claude-sonnet-5-5`, the session's configured model) from the *meaning* of each question and the
allowed-label definitions, not by running the router. I read `species_questions.py` and the `app.py` regexes only to know which phrasings the deterministic routes
cover; I did NOT execute them against the set, call any API, or read secrets. So labels are single-annotator, not human-adjudicated. Recommend a human review of the
tricky cases below before treating heldout numbers as ground truth.

## Compatibility with deterministic routes (from reading code, not running)
- `species_questions.py` handles: `X(와/과) 비슷한/관련된 새`, `같은 속/과`, 먹이/서식지 비슷한 새 (ecological_*), diet, habitat, activity, appearance phrasings (`~알려줘/뭐야/어디서 살아/야행성이니/어떻게 생겼어`). Many of my common-name cases in those labels use exactly these shapes, so they should be answered deterministically (expect these to be "easy").
- `app.py` handles taxonomy (`X 분류 알려줘`, `X는 무슨 과/목…`) and profile (`X에 대해 알려줘`). `X 아종 알려줘` matches neither, so it has no deterministic route, and `subspecies` is not in `ChatIntent` (auto|taxonomy|profile|observations|evidence). The runner must therefore map the label `subspecies` (and activity/diet/etc.) onto whatever the router can emit; this mapping is the coordinator's job.
- Typos, English, scientific-name-only and paraphrase cases are intentionally outside the regexes to test the LLM fallback.

## Tricky ground truths
- Subspecies vs taxonomy: `X 아종 알려줘`/`아종 목록` -> subspecies (the user wants the subspecies list). `X는 무슨 아종/과/목` and "what family…" -> taxonomy. Rationale: the first asks for enumeration, the second for placement of the taxon.
- `흰뺨검둥오리`: the name denotes a species group whose scientific naming (Anas poecilorhyncha vs A. zonorhyncha) varies by source; I labeled by intent, not by whether data exists. Whether the system actually has subspecies data is out of scope for intent labeling.
- profile vs taxonomy: "소개해줘 / 어떤 새야 / Tell me about" -> profile (general); "분류/계통/무슨 과" -> taxonomy.
- observations vs evidence: sightings/locations/dates (eBird etc.) -> observations; "출처/근거/논문/citation" -> evidence. "어디서 관찰됐어?" is observations, not habitat (habitat = where it lives generally).
- related vs ecological_*: plain "비슷한/같은 속·과" -> related; "먹이가 비슷한" -> ecological_diet; "서식지가 비슷한" -> ecological_habitat.
- `부엉이`, `오리`, `기러기`, `갈매기`, `딱따구리`: umbrella names covering multiple species. `오리 아종`, `기러기 어디에 살아`, `갈매기 먹이`, `부엉이 분류` -> uncertain (should ask for clarification). Two debatable ones: `딱따구리 아종 알려줘` labeled subspecies (name flagged ambiguous_name) and `부엉이는 밤에 활동하니` labeled activity — both are generic enough to arguably be uncertain. I kept the intent label since the *intent* is clear and ambiguity is of the name; if the runner scores name resolution, these should be excluded or relabeled.
  Inconsistency to be aware of: that is a judgment call; please decide a policy for ambiguity vs. intent.
- `까치 아종`, `참새 아종별 분포`: intent=subspecies even though "분포" hints habitat; the main noun is subspecies.
- Multi-intent (`아종이랑 먹이도`, `분류하고 관찰 기록`, `서식지랑 생김새`, `diet and habitat`): single-label schema cannot express two intents, so labeled `uncertain` (system should not silently pick one). Alternative policy (accept either intent) is possible but not applied.
- Unsupported (weather, recipe, poem, price, greeting) and absent taxa (고양이, T. rex, 도도새, Canis lupus, 용): `uncertain`. NB: 도도새 is a real extinct bird that may legitimately be absent from the DB; the *intent* (habitat) is clear. I still labeled `uncertain` because the set treats "taxon not in scope" as abstain. This conflates intent with data availability; flagged as a concern.
- `그 새 아종 알려줘`: no referent in a single turn -> uncertain.
- Typos (`아존`, `분뷰`, `머거`, `알려조`, `알려져`, `비슷항`, `보여조`, `데이타`): intent still recoverable, so labeled with the intended intent.

## Confidence policy (suggested for the runner)
- Predict `uncertain` when model confidence < threshold OR the prediction is not in the allowed set. Choose the threshold on calibration only (e.g. maximize accuracy subject to wrong-answer rate on calibration), then freeze it and report heldout once. Do not tune prompts on heldout.
- A wrong confident label is worse than a false abstain: report separately (a) accuracy on non-uncertain labels, (b) false-answer rate on `uncertain` cases (predicting a concrete intent), (c) abstain rate on answerable cases.
- Score multi-label / ambiguous-name cases separately via `category`.

## Concerns / limits
- Sample is small (5–7 per label for several labels); per-label heldout rates are noisy (2–4 items).
- Single annotator, labels not verified by running the system; questions I wrote are stylistically close to each other and to the regexes.
- Ambiguity-vs-intent and absent-taxon-vs-intent conflation as described above.
- Species names used (mallard, magpie, great tit…) were not checked against the database contents.
- No code changed, no graphify update, no commits, no network calls. Documentation in Obsidian/repo docs per AGENTS.md was not written (out of the allowed ownership).
