# Taxonomic trait generalization: Claude handoff (stage-by-stage)

- **Owner:** Claude (dev-claude, `/Users/kimdove/orca/workspaces/RobinGraph/dev-claude`, branch dev-claude). All changes are uncommitted.
- **Not done:** no commit, push, deploy, DB write, or change to the fixed RG-205 holdout of 40. I did not read the holdout or gates.
- **TEST access** was read-only: Neo4j sessions with `default_access_mode=READ_ACCESS`, and only MATCH/RETURN queries. No credentials were printed.
- **Contracts:**
  - `/tmp/taxonomic-trait-contract.md`: scope; approved by root with corrections;
  - `/tmp/taxonomic-trait-api-contract.md`: the exact graph kind enum and response fields.
- **Status:** **stage 1 only is complete** (the user's exact question and rank boundaries). Stages 2–4 are not done. This is **not** a claim of full support.

## Baseline and preservation
- **`graph_questions.py` and `tests/test_graph_questions.py`** are based on root's latest copies (`385a31df…`, `ea9e7c85…`).
  - My older uncommitted copies were not lost. They are backed up at `/tmp/taxonomic-trait-backup-dev-claude/`: `graph_questions.py.old` (`0025a7fe…`) and `test_graph_questions.py.old` (`0e64b90c…`).
- **Staging:** an rsync copy of root's dev-codex tree (no `.git` or `.venv`) with my files overlaid, at `/private/tmp/claude-501/-Users-kimdove-orca-workspaces-RobinGraph-dev-claude/928becd3-da81-48f1-a657-792b375dbaa2/scratchpad/stagett`.

## Stage 1: exact user question and rank boundaries
### Files (sha256)
| File | sha256 | Change |
|---|---|---|
| `src/robingraph/retrieval/graph_questions.py` | `f305c0bd6e6b1e7ff65604e681ea243869354bb576cd93d887bfabfbda600050` | Adds the `taxon_traits` kind, `TraitCondition`, `GraphQuestion.conditions`, the `TRAIT_CONDITIONS` allowlist, `TAXON_BY_NAME_QUERY`, `TAXON_TRAITS_QUERY`, `CATALOG_TRAITS_QUERY`, the handler and validators. Legacy kinds are unchanged. |
| `src/robingraph/retrieval/graph_intent_schema.py` | `c05d269e615ea93d476b70e8097001e371e5f53cb83921b601a0a0d5836395d0` | Adds `GraphIntent.conditions` and the taxon_traits rule. The rank becomes a taxon surface (`bad_taxon` replaces `rank_not_order`). Adds `KIND_FAMILIES`. Gold `conditions` is optional (`OPTIONAL_FIELDS`), so the fixed gold files stay valid. |
| `src/robingraph/retrieval/graph_condition_extractor.py` | `0f1879d00e7cd66c8aba5d87d8aa8e2bcdaa5adff6dbaf59fcd59218d94a55df` | `_claim_taxon` (any rank, whole-token stem, no modifier absorption); fruit criteria become conditions; order_fruit is kept for the established order shape; sibling candidates get no kind_tie. |
| `src/robingraph/retrieval/graph_semantic_router.py` | `85a36933dccf68d73c991b61f5fe702bf1654749d88d197683b3ae296b1aa4dc` | Unchanged. |
| `tests/test_taxon_traits.py` | `6a4aa876fd00e1f38fd22ef292bdcec6b3d86f09bf3cd8707141de1a1e9e1650` | New, 23 tests. |
| `tests/test_graph_semantic_router.py` | `57c7e45f9acac4e9507837bcb946e5289c1798533c93e38d84b0aee930f3b4f4` | Prototype-kind assertion excludes taxon_traits, which has no prototypes yet; documented as the order_fruit sibling. |
| `tests/test_graph_questions.py` | `ea9e7c858a78011c12f888e1856cf584396509aa97941693d334d98504392ae2` | Root's copy, unchanged. |

- **Diff against root's current copies:** `/tmp/taxonomic-trait-stage1.patch` (sha256 `ab4cd0ba36cde566cb3131d71ce6438d2ee26cf560089a5ea7ecfff5a71f2491`). 5 files, +769 / −36.
- **Shared files needing root:** none. Root confirmed that `ChatGraphResult.payload` is a dict and that chat.js renders generically.

### Commands and actual results
1. **Focused set in staging** (`PYTHONPATH=src:tests .venv/bin/python -m unittest tests.test_taxon_traits tests.test_graph_questions tests.test_graph_questions_api tests.test_graph_semantic_api tests.test_graph_condition_extractor tests.test_graph_intent_schema tests.test_graph_semantic_router tests.test_semantic_chat`):
   - result: **Ran 134, OK**;
   - before the change the same set without test_taxon_traits gave 111 OK.
2. **Full staging run** (`python -m unittest discover -s tests`), log at `/tmp/taxonomic-trait-stage1-full-staging.txt`:
   - result: **Ran 1145, failures=3, errors=4, skipped=39**;
   - all 7 are `test_nas_release_package`, which needs git; staging has no `.git`. This is the same environment failure as in RG-207 and was not "fixed".
3. **Tuning evaluation, in-sample** (`scripts/eval_graph_questions.py --gold data/eval/graph_questions/tuning.jsonl --parser extractor --json /tmp/taxonomic-trait-stage1-tuning-extractor.json`):
   - unchanged: valid 84/84, leaks 0, kind 67/67, coverage 39/39, false execution 0/84, condition-loss executions 0, disposition 84/84;
   - all-slots-exact went from 66/67 to **65/67**.
   - The slot changes are both on non-executing items:
     - T-052 kind went from order_fruit+negation to taxon_traits+negation (still clarify);
     - T-056 `오리과` is now a taxon span rather than residual (still clarify because of negation).
4. **Real TEST, read-only** (`docker --context orbstack exec -i -e ROBINGRAPH_DEPLOY_TARGET=test robingraph-api-test python - < /tmp/taxonomic-trait-probes/probe_stage1.py`):
   - my three modules are injected into the container process; the repository `_run` is forced to READ_ACCESS; the resolver is the plain graph `resolve_species`, not the active embedding resolver;
   - results: `/tmp/taxonomic-trait-stage1-test-readonly.json`.

   | Question | Gate/kind | Result |
   |---|---|---|
   | **`까마귀과면서 열매를 먹는 새는 어떤 종이 있어?`** | answer / taxon_traits | **answer**: family Corvidae, coverage scoped 135 / evaluable 100 / matched 76; 20 items with has_more; 319 ms on the first call |
   | Corvidae면서 … | answer | the same 76/100 (121 ms) |
   | 까마귀속이면서 … / Corvus 중에서 … | answer | genus Corvus 30/39 |
   | 까마귀면서 … / Corvus corone 중에서 … | answer | species itself: **empty** (evaluable 1, matched 0: an Elton fruit claim exists and is not above 0) |
   | Corvus corone cornix면서 … | answer | subspecies: **insufficient_data**, "아종 단위로 직접 연결된 먹이 구성 자료가 그래프에 없어 … 부모 종의 자료로 대체하지 않았습니다" |
   | 까마귀과 중 열매 섭식 새 | answer | Frugivore 4/121 |
   | 직박구리과 / Pycnonotidae | answer | fruit share 72/81; Frugivore 72/143 |
   | 수리과 (fruit share / Frugivore) | answer | 5/165 and 1/201, small but nonzero |
   | 앵무새면서 … | answer | an order label without the 목 suffix: Psittaciformes 228/269, rank taken from the data |
   | 열매를 먹는 새는 어떤 종이 있어? | answer | whole catalog 2551/7067 (360 ms) |
   | 초승달가슴새류 / 화식조 | answer → insufficient | `ambiguous` (family+genus / species+higher label); no trait query |
   | 용용과면서 … | clarify | unknown name stays residual |
   | 겨울에만 까마귀과면서 … | clarify | the modifier is residual |
   | 까마귀과면서 감나무 열매 … | insufficient_data | specific plant, as before |
   | 참새목/Passeriformes/비둘기목 … | order_fruit | unchanged legacy path |

5. **Legacy parity on real TEST** (`probe_parity.py`, results in `/tmp/taxonomic-trait-stage1-parity.json`):
   - `order_fruit` versus `taxon_traits` for Passeriformes (fruit_share), Columbiformes (frugivore) and Psittaciformes (tree_fruit_share);
   - the **item ids and every evidence path text are identical**, along with status and has_more;
   - with scope `korea`, the ids are also identical.
6. `graphify update .` in dev-claude: the code graph is updated.

### Stage 1 limits
- The TEST probe used the plain graph resolver. The active-mode `graph_resolve_species` (matched only) is only reached when a Korean name is neither a pinned label nor a sourced species name.
- Root's real API path in active mode and the UI were not run.
- The router has no taxon_traits prototypes, so only the order_fruit sibling is treated as compatible.
  - A router top of habitat_shared_diet or another kind on a taxon_traits question would still add kind_tie (clarify).
  - This matters for the multi-condition questions of stage 4 and must be measured with Jina then.
- Stage 1 conditions are fruit only. Habitat, numeric and other fields give clarify today; they are never dropped.

## Next stages (not started)
- **Stage 2:** homonyms, subspecies, no data, conflicting conditions, numeric units, unsupported-word omission.
- **Stage 3:** full-catalog name and scientific-name extraction check (all labels, sourced names, and the active inventory taxa from root's `inventory.json`).
- **Stage 4:** the condition lexicon for all 15 fields, multi-condition AND (`까마귀과 중 숲에 살고 열매 먹는 새`), taxon_traits router prototypes, the new separate `data/eval/taxon_traits/` tuning set, and regression checks on the literature and profile routes.

---
# Update: stage 1 addendum, stages 2–3, Jina integration (same session)
The status line above is superseded: stages 1–3 and the router integration are done **in dev-claude**. Root's real-API, DB-oracle and blind-44 verification is still pending, so this is **not acceptance**.

## Current files (sha256)
| File | sha256 |
|---|---|
| `src/robingraph/retrieval/graph_questions.py` | `21315a10afd931ec9992ec273023ff16048ba0b721aacc3f5a21ec7ff1487414` |
| `src/robingraph/retrieval/graph_intent_schema.py` | `dd949e3a16f9afbf6f71755dbbce38c46b0e898d4ea9823323d364c7dba6323f` (= root integrated) |
| `src/robingraph/retrieval/graph_condition_extractor.py` | `280a3c41424785a086786ae9fb05d8633357a05964d5b87831a93b79aa10d6db` |
| `src/robingraph/retrieval/graph_semantic_router.py` | `85a36933dccf68d73c991b61f5fe702bf1654749d88d197683b3ae296b1aa4dc` (unchanged) |
| `tests/test_taxon_traits.py` | `1d9e5dbeff12d243c895b66ea655b5cd0e383e54eabfda6c1dbc5cc9eaca6f9b` (34 tests) |
| `tests/test_graph_condition_extractor.py` | `b08f979d402c9a5e9048cd3770157ab5b033adad9d282a39254fa0525819ad0c` (= root integrated) |
| `tests/test_graph_semantic_router.py` | `57c7e45f9acac4e9507837bcb946e5289c1798533c93e38d84b0aee930f3b4f4` (= root integrated) |
| `tests/test_graph_intent_schema.py`, `tests/test_graph_questions.py` | unchanged (`b4166c63…`, `ea9e7c85…`) |

- **Patches:**
  - full, against root's pre-integration copies: `/tmp/taxonomic-trait-stage3.patch` (`b51b5920…`);
  - **delta against root's integrated snapshot** (`integrated-source.json`): `/tmp/taxonomic-trait-delta-after-integration.patch` (`7998ad45…`), covering `graph_questions.py`, `graph_condition_extractor.py` and `test_taxon_traits.py` only.
- **What the delta changes:**
  - **(a)** router kind_tie applies only to kinds the router has prototypes for;
  - **(b)** an explicit residual claim (e.g. `국내에 사는`) after a linked taxon also holds;
  - **(c)** a range shows one measurement once in the evidence paths;
  - the tests that go with these.

## Stage 1 addendum: label rank conflict (from Writer's finding)
- **Rule:** a pinned Korean label whose explicit 목/과/속 ending contradicts its own rank gives `insufficient_data` with `taxon_resolution=label_rank_conflict` and "학명으로 다시 질문해 주세요". No trait query runs.
- **The 7 such labels:** 물까마귀과→genus Cinclus, 군함조과→genus Fregata, 사다새과→genus Pelecanus, 장다리물떼새과→genus Recurvirostra, 팔색조속→family Pittidae, 카구속→family Rhynochetidae, 논병아리목→family Podicipedidae.
  - 논병아리목 has the order shape, so it takes the legacy `_order` path, which also holds it.
- **Still allowed:** a suffix-less label such as 앵무새 → order. The scientific name always works: `Cinclus` → genus, empty 0/4 on TEST.
- **Not done:** no label file edit and no DB write.

## Stage 2: whole-catalog names
- `/tmp/taxonomic-trait-probes/stage2_names.py` was run offline against root's `inventory.json` (33,684 active taxa plus 1,201 distinct Korean display names, 2 templates, **69,770 questions**). Results are in `/tmp/taxonomic-trait-stage2-names.json`.
  - **Extraction:** 0 failures. Every taxon span equals the name, with no residual.
  - **Resolution:** 69,604 resolved to the exact inventory id and rank. 12 held as `label_rank_conflict` (6 labels × 2). 12 `ambiguous` (the 6 homonyms × 2). 142 legacy `order_fruit` surfaces: `_order` resolves 70 of 71 and holds 논병아리목.
  - 0 wrong resolutions.
- **Fix found:** `Somateria mollissima v-nigrum`, a hyphenated epithet, is now allowed in all three scientific-name patterns.
- **In-repo test:** `WholeLexiconNames` runs every pinned label and sourced name, Korean and scientific, through both templates.
- **Root's own audit:** `catalog-fruit-parse-audit.json`, 34,891 surfaces, 0 failures. That is the shared evidence, so I did not repeat it.

## Stage 3: 15-field lexicon, AND, numeric boundaries
- **Surfaces** come only from `species_profile.VALUES`/`LABELS` and `HABITATS`.
  - The qualified form `<trait label>이/가 <value>인` works for each categorical field.
  - A bare value works only when it is unique across traits (육식, 씨앗 섭식, 수생 초식, 나무 위 생활, 개방형 …).
  - 잡식, 사체 섭식 and a bare `부리 길이` are ambiguous, so they clarify.
- **Diet shares:** `<VALUES key> 먹는` (물고기, 씨앗, 꽃꿀, 사체, 무척추동물 …) means a share above 0.
  - 곤충/벌레/어류/곡식/꿀/고기/잎 stay `unsupported`: there is no data key for them.
- **Numbers:**
  - a measure word plus a whole number plus a unit (g/kg/그램/킬로그램/mm/cm/m …) plus 이상/이하/초과/미만/넘는/보다 큰·작은 …;
  - ranges are `N~M unit` or `N unit 이상 M unit 이하`;
  - kg→g and cm/m→mm are converted.
  - **Signs, separators, exponents and decimal points touching the number make the phrase residual.** Tested on: -1g, −1g, +1g, .5g, 1,000g, 1e3g, 100 with no unit, NaN, Infinity, 1.5.3g, `100g인` with no operator.
  - A wrong dimension (체중 30cm), lower > upper, two lower bounds, or contradictory categories (숲+습지) give ambiguity → clarify.
- **Whole catalog:** a clear condition with no taxon (`숲에 사는 새 알려줘`, `숲에 살고 열매를 먹는 새는?`) is taxon_traits over the whole catalog, as root decided.
  - The old RG-207 test listing `숲에 사는 새 알려줘` as not_graph was updated with a comment.
- **Taxon followed by unreadable words:** with an explicit scope link (`까마귀과 중 큰 새`, `…면서 야행성인`, `… 중 철새`, `… 중 국내에 사는`), the question **clarifies**. It is never sent to other routes with the condition dropped.
  - Without a link (`까마귀과 새는 몇 종이야?`, `까마귀과의 특징 알려줘`, `참새목 중에서 어떤 새가 있어?`), it stays not_graph on the existing routes.
- **Tests:** `FieldLexicon` (all 15 fields, AND, ranges, number boundaries, ambiguity/unsupported/contradiction, route boundaries) and `MultiConditionExecution` (per-pipeline parameters, paths, measurement recheck).

## Jina integration (real TEST router, read-only embedding calls)
- **v1** (`/tmp/taxonomic-trait-router-v1-probe.json`): 33 of my taxon_traits questions (not the blind set). 32 answer; **1 blocked**: `직박구리과면서 열매를 먹는 새는?`, router top specific_fruit 0.945, margin 0.187 → kind_tie → clarify.
  - Most taxon_traits questions were below threshold: top 0.50–0.85, margins 0.004–0.096.
- **Cause:** the router has no taxon_traits prototypes, so its top is only the nearest of the 7 modelled kinds.
- **Fix:** `extract_graph_intent` adds kind_tie only when the rule kind is one the router models (`_ROUTED_KINDS`, taken from `PROTOTYPES`).
  - The 7 old kinds are unchanged.
  - No threshold or prototype was changed.
  - Embeddings still never add or remove slots.
- **v2** (`/tmp/taxonomic-trait-router-v2-probe.json`): **33/33 answer**. Classify p95 is 732 ms; the first call includes the cold prototype load.

## Real TEST DB, read-only (`probe_stage3.py`, results in `/tmp/taxonomic-trait-stage3-test-readonly.json`)
28 questions, all executed with no error:

| Question | Result |
|---|---|
| 까마귀과 숲+열매 | 47/96 |
| catalog 숲+열매 | 1775/6898, 482 ms |
| 숲에 사는 새 (catalog) | 5595/9796 |
| 까마귀과 체중 ≥500 g | 18/117 |
| 까마귀과 체중 ≤1 kg | 116/117 |
| 체중 100–200 g (catalog) | 880/9563 |
| 까마귀과 날개 ≥30 cm | 24/119 |
| 잡식, trophic_niche | 97/121 |
| 잡식, trophic_level | 88/121 |
| 참새목 육식 | 3490/5995 |
| 까마귀과 물고기 | 7/100 |
| 까마귀과 씨앗+숲 | 23/96 |
| 까마귀과 개방형 | 25/121 |
| 까마귀과 나무 위 생활 | 72/121 |
| 까마귀과 Frugivore+숲 | 4/120 |
| 까마귀과 FruiNect | 4/100 |
| 까마귀과 숲+≥300 g+열매 (three conditions, two pipelines) | 8/94 |
| catalog >100 g+숲 | 1297/9491 |
| catalog 습지+물고기 | 172/6898 |
| 까마귀 (species itself) 숲 | empty 0/1 |
| Corvus corone cornix 숲 | insufficient_data, subspecies with no direct claim |
| 까마귀과 부리 너비 ≤10 mm | 33/118 |
| 까마귀과 꼬리 >20 cm | 21/118 |
| 수생 초식 | 82/9870 |
| 까마귀과 사막 | 6/120 |
| 직박구리과 열매 | 72/81 |

- `-1g` and `숲이랑 습지` clarify.
- Latency: 60–480 ms per query. Catalog queries take 220–480 ms.

## Commands and results (latest)
- **Focused set** in staging (test_taxon_traits, graph_questions, graph_questions_api, graph_semantic_api, condition_extractor, intent_schema, semantic_router, semantic_chat, embeddings): **Ran 156, OK**.
- **Tuning evaluation (in-sample):**
  - unchanged: 84/84 valid, kind 67/67, coverage 39/39, false execution 0/84, condition-loss 0, disposition 84/84;
  - all-slots 65/67, the same two non-executing items as in stage 1.
  - Evidence: `/tmp/taxonomic-trait-stage3-tuning-extractor.json`.
- **Full staging run:** not repeated, as root asked. The earlier run showed only the 7 known `.git` environment failures. Root does the final real-worktree full run.
- `graphify update .`: done.

## Limits and not done
- **Blind set and real API:** I did not read the blind 44 or `independent-*.json`. The real API path, active-mode resolver and UI are root's.
- **Phrasing coverage:** a natural phrasing outside the VALUES vocabulary (e.g. "나무 위에서 생활하는", "몸무게가 1킬로 넘는") gives clarify, which is safe but means low recall. Gains need blind-set evidence, not guessed synonyms.
- **Question-level scope:** 국내 기록 + taxon_traits gives clarify (the scope slot is not allowed). The request `species_scope` is applied as before.
- **Router and tuning:** there are no taxon_traits router prototypes and no new taxon_traits tuning file yet. The router only marks out-of-family conflicts for its 7 kinds.

---
# Update: measurement label forms (root's blind 44: 42 pass / 2 safe holds)
- **The 2 holds:** a display label `X (Y)` written in words: `부리 길이 콧구멍 기준이 5mm 이상인`, `다리 길이 부척이 10mm 이상인`. Neither threshold was lost; the phrases were held.
  - These cases are now feedback, so they no longer count as blind. Root records the 42/44 first-run result separately from the later regression pass.
- **Fix:** a general rule, not those two strings. Measurement surfaces come from `species_profile.LABELS`:
  - `X (Y)`, `X Y` and `X(Y)` all name the field;
  - a bare base `X` is used only when one field has it: `다리 길이` → tarsus, while `부리 길이` (culmen or nares) stays ambiguous → clarify;
  - the short everyday forms 몸무게, 날개 길이, 부척 길이 and 부리 전체 길이 are kept.
  - A partial qualifier (`부리 길이 콧구멍이`) still clarifies.
- **Tests:** `MeasureLabelForms`: both blind phrasings, the bracket/word variants, shared or partial labels holding, and every measured field read by its display label.
- **Results:**
  - focused staging set: **Ran 159, OK**;
  - tuning evaluation unchanged: false execution 0/84, disposition 84/84.
- **Not run yet:** a real TEST DB probe for these two phrasings. Root's oracle covers it.

## Current hashes (supersede the table above)
| File | sha256 |
|---|---|
| `src/robingraph/retrieval/graph_questions.py` | `21315a10afd931ec9992ec273023ff16048ba0b721aacc3f5a21ec7ff1487414` |
| `src/robingraph/retrieval/graph_intent_schema.py` | `dd949e3a16f9afbf6f71755dbbce38c46b0e898d4ea9823323d364c7dba6323f` (= root integrated) |
| `src/robingraph/retrieval/graph_condition_extractor.py` | `0f6af2fa28d6dde7d3e086c279716327962229b65b84be9041564f444948b342` |
| `src/robingraph/retrieval/graph_semantic_router.py` | `85a36933dccf68d73c991b61f5fe702bf1654749d88d197683b3ae296b1aa4dc` (unchanged) |
| `tests/test_taxon_traits.py` | `580f38c5f07e14cfb50844cfaa6d72a4243b66f550c4c03ccaa410fd6c9b628b` (37 tests) |
| `tests/test_graph_condition_extractor.py` / `test_graph_semantic_router.py` | `b08f979d…` / `57c7e45f…` (= root integrated) |

- **Delta against root's integrated snapshot** (dev-codex: `cce6cfe5…` / `05862e70…` / `39830847…`): `/tmp/taxonomic-trait-delta-after-integration.patch` (`b7e266b1…`). 3 files, +225 / −12. It contains:
  1. router kind_tie only for kinds the router models (Jina 1/33 → 0/33 false hold);
  2. an explicit residual claim after a linked taxon holds;
  3. a range path is shown once;
  4. the measurement label forms;
  5. the tests for 1–4.

---
# Code freeze (root request)
- Root has integrated the 3 deltas: `graph_questions.py 21315a10`, `graph_condition_extractor.py 0f6af2fa`, `test_taxon_traits.py 580f38c5`. Current candidate: `1768d40f4b1e`.
- Claude: **no further code change, feature, prototype or tuning file** until root asks for a required fix. Only comments or factual corrections to this handoff are allowed, and any change will be shared first.
- Not yet run by root: the blind-44 regression rerun, numeric boundaries 17, the full Python suite, and the old 40-question holdout. Public TEST is still on the old snapshot.

---
# Required fix: CT-013 primary_lifestyle wording (freeze lifted for this fix only)
- **Evidence (root):** `dev-codex/docs/verification/assets/2026-10-22-taxonomic-coverage/natural/independent-api-natural.json`.
  - 19/20 passed. CT-013 `동박새과 중 나무 위에서 생활하는 새는?` gave clarify (`supported_query_not_executed`, `original_conditions_changed_or_lost`).
- **Cause, a general defect:** the lifestyle vocabulary had only the display values `나무 위 생활 / 공중 생활 / 지상 생활`. The everyday form `X에서 생활하는` of the same value was not read.
- **Minimal fix** (`graph_condition_extractor.py` only):
  1. Each display value ending in ` 생활` also gets the surface `X에서 생활`. This is derived from the existing values (Insessorial, Aerial, Terrestrial); no synonym is invented.
  2. The condition link `_LINK` accepts `하면서 / 하며 / 하고`, so lifestyle conditions combine with AND.
- **Still held:** 물/땅/나무에서 생활하는 (not the vocabulary; Aquatic's value is `수생`), negation, a season word, and an extra word such as 큰.
- **Backup of the frozen versions:** `/tmp/taxonomic-trait-backup-dev-claude/graph_condition_extractor.py.0f6af2fa`, `test_taxon_traits.py.580f38c5`.

## Files and hashes
| File | sha256 |
|---|---|
| `src/robingraph/retrieval/graph_condition_extractor.py` | `17765013bcd524314fc37c540df89645344285e05ac0ca7681ea214b3dca879b` (was 0f6af2fa) |
| `tests/test_taxon_traits.py` | `7c6665d7f1bd79ffb326d73924b2c4c4d6683aa43a8af59a16f96cb5ade6b286` (was 580f38c5; +`LifestylePhrasing`, 3 tests) |
| `graph_questions.py` / `graph_intent_schema.py` / `graph_semantic_router.py` | unchanged (`21315a10` / `dd949e3a` / `85a36933`) |

- **Patch against the frozen versions:** `/tmp/taxonomic-trait-lifestyle.patch` (`e0f38cd5…`), 2 files, +33 / −1.
- At the time of writing, dev-codex already holds the same two hashes (`17765013`, `7c6665d7`).

## Commands and results
- **Focused set in staging** (test_taxon_traits, graph_questions(_api), graph_semantic_api, condition_extractor, intent_schema, semantic_router, semantic_chat, embeddings): **Ran 162, OK**.
- **Tuning evaluation (extractor):** unchanged. False execution 0/84, disposition 84/84, all-slots 65/67. Evidence: `/tmp/taxonomic-trait-lifestyle-tuning-extractor.json`.
- **Parser gate on `claude-review-cases.json`:** 20/20 agree. CT-011 and CT-016 reach their insufficient outcome in the handler.
- **Real TEST DB, read-only** (`/tmp/taxonomic-trait-probes/probe_lifestyle.py`, results in `/tmp/taxonomic-trait-lifestyle-test-readonly.json`):

  | Question | Result |
  |---|---|
  | CT-013 동박새과 나무 위에서 생활 | answer 129/129 (scoped 147), the same as the display wording `나무 위 생활을 하는` (129/129) |
  | 칼새목 공중에서 생활 | 366/390 |
  | 꿩과 지상에서 생활 | 159/171 |
  | Picidae 나무 위에서 생활하며 + 무척추동물 | 146/160 |

  Latency 70–115 ms.
- `graph_questions.py`, the DB and the deployment are untouched. The code freeze is back in force after this fix.
