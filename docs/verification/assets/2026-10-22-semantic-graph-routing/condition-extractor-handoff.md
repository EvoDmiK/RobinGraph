# RG-207 result: original-text condition extractor (Claude, dev-claude)

- Not done: no DB or API write, no TEST deploy, no Git operation. I did not read the holdout.
- Reference: root's latest `graph_questions.py`, staged byte-identical. My tree's older copy overwrote nothing.
- Model: `claude-opus-5-5`.

## Finished files (dev-claude, uncommitted)

| File | Kind | sha256 |
|---|---|---|
| `src/robingraph/retrieval/graph_condition_extractor.py` | new | `8088de213d40394a2d4f45e55a8d17277d4c3c1bb26d5859bcc3c9cabec0bb1a` |
| `tests/test_graph_condition_extractor.py` | new (17 tests) | `c9f4e2392bece5573775fdbfdd726d3313793786a68072ddff513878f0b31a67` |
| `scripts/eval_graph_questions.py` | edited (`--parser extractor` added) | `304085b261999c8606e09454209f0361bc9de6aebf9dfcffd07d94e7ece6cb94` |

- Evaluator patch against root's current file: `/tmp/rg207-eval.patch`. The regex raw/gated meaning is unchanged; tuning regex output is identical to before (15/39, false executions 4/84 raw, 3/84 gated).
- `graph_intent_schema.py`, the router and the embeddings files match root's integrated copies, and none of them changed. The schema gate was not changed.

## Contract as implemented
`extract_graph_intent(question, candidates=()) -> GraphIntent(source='extractor')`. It never raises; on an internal exception it returns `ambiguity=('other',)`, which gives clarify.

**Span consumption:**
- Characters are consumed by slot patterns first: negation, unsupported, korea scope, residence/outside, common/genus, habitat, the habitat-target relation, niche relation, rank, fruit/frugivore/tree fruit, specific plant, group, names.
- What remains may be consumed only by bounded fillers: bird nouns, 중/가운데/에서, question endings, particles. Fillers must match an unclaimed run within a token exactly, and they are never applied by substring.
- Everything else goes into `residual`, which gives clarify.
- Negation, season, quantity, conservation status, region, adverbs (주로/대부분) and Cypher fragments are not fillers.

**Clean not_graph:**
- With no graph cue (relation or diet: common, genus, niche, habitat-target relation, fruit, specific plant, or unsupported with a bird target), the result is `GraphIntent(None, source='extractor')`.
- A rank, habitat or scope alone is not a cue.

**Literature and observation requests (root's new case):**
- If the text has an unclaimed request word (논문, 문헌, 연구, 기사, 출처, 인용, 관찰 기록, 관찰, 사진, 영상), the result is clean not_graph, so the existing evidence/observations/Jev routes decide.
- If it reads as a second, independent request (`…알려주고`, `그리고`, `논문도`), the word stays residual, which gives clarify.

**Conflicts (root's feedback):** the extractor never picks the first of several values. Each of these gives ambiguity, i.e. clarify:
- differing diet criteria (e.g. frugivore + tree fruit);
- same and different niche at once;
- two specific plants;
- two kinds of request (common + genus, and so on);
- several ranks or habitats.

**Names:**
- A name is an original-text span: a token before 와/과/랑/이랑/하고/처럼, checked against batchim grammar (와/랑 after a vowel, 과/이랑 after a consonant), or the token right before a relation cue.
- A spaced name is joined **only when its compact form matches a source-checked name from `taxonomy_lineage.sourced_korean_names()`** (850 KOS names), so `청둥 오리` and `흰뺨 검둥 오리` work.
- Free merging is not allowed. `여름에만 청둥오리` and `큰 오리` stay separate: the leading word becomes residual and the result clarifies.
- Group words (오리, 기러기 …) give `name_ambiguous`.
- The real species identity is checked again by root's CLI resolver: `matched` only, with ID and context rechecked.

**Specific plants:** a word before 열매 that ends in a particle or modifier ending, or is an adverb or season word, is residual, not a plant (`겨울에 열매` → residual, clarify).

**Candidates:**
- A confident top kind that disagrees adds only `kind_tie`, which gives clarify. Slots are never added or removed.
- A broken `top` property is caught inside the try block and gives clarify.

**Over 200 characters:** if a graph cue exists, the result is `ambiguity=('other',)`, i.e. clarify. With no cue, it is clean not_graph. The API cap is 2000 characters.

## Tests (unit, fixtures; no DB or network)
- `tests/test_graph_condition_extractor.py`, 17 tests:
  1. all 84 tuning questions: dispositions match, 0 false executions, 0 condition-loss executions, `validate_intent` passes, `source='extractor'`;
  2. the **504 order_fruit matrix forms + 84 specific-plant variants**, checked against expected `GraphQuestion` values rather than the parser;
  3. the 6 other kinds × 12 endings;
  4. the 10 original user and root-probe questions;
  5. 15 questions with no graph cue (single species, observations, literature, taxonomy, Korea alone) → clean None;
  6. literature/observation requests → clean None, and 2 compound requests → clarify;
  7. 4 Cypher injection forms → never answer;
  8. 18 blocking words × 3 templates → never answer, with residual/negation/ambiguity present;
  9. 5 negation forms → clarify;
  10. 5 specific-plant cases → insufficient, never relaxed;
  11. unsupported relations and missing or ambiguous parts;
  12. sourced spaced names;
  13. spans and evidence;
  14. conflicts;
  15. long questions;
  16. candidates `kind_tie` only, plus a broken candidates object;
  17. never raising.
- Staging (root's latest code plus these files): graph, API and semantic chat focused set (extractor, schema, router, graph_questions, graph_questions_api, graph_semantic_api, semantic_chat, embeddings) → **122 OK**.
- dev-claude: extractor + schema + router + embeddings → **55 OK**.
- Staging full run, done once on an earlier version of the extractor (name logic changed since): 1121 ran, failures are only the same 7 `test_nas_release_package` cases that need git (no `.git` in staging). Root's real-worktree full run is the next step.

## Tuning evaluation (in-sample; not holdout)
- Command: `PYTHONPATH=src python scripts/eval_graph_questions.py --parser extractor --json …`
- Evidence: `/tmp/rg207-extractor-tuning.json`

| Metric | regex baseline (gated) | extractor |
|---|---|---|
| kind accuracy | 20/67 | **67/67** |
| all slots exact | 17/67 | 66/67 |
| coverage | 15/39 | **39/39** |
| false execution | 3/84 | **0/84** |
| appropriate hold | 42/45 | 45/45 |
| condition-loss execution | 2 | **0** |
| disposition accuracy | 24/84 | 84/84 |

- Parser latency: p50 0.046 ms, p95 0.079 ms (local, rules only).
- Remaining slot differences are all on non-executing items, where the extractor is more conservative than the gold:
  - T-052 kind None → order_fruit + negation (clarify);
  - T-053 `오리는` residual;
  - T-069 `청둥오리를` residual.
- Router `kind_tie` simulation with tuning leave-one-out candidates at 0.80/0.06: one disposition changed, T-039 insufficient → clarify. Both are non-executing; no coverage loss.

## Limitations and unverified items
- **These are tuning numbers.** The rules were written while looking at tuning, so there is overfitting risk. The real verdict is root's holdout run (the G1 gates).
- Region names, seasons, quantities and conservation words are not in a lexicon; they are caught because they are unconsumed and become residual. A new filler or slot pattern could swallow such a word, so patterns must not be widened carelessly. The blocking-word tests guard this.
- `과일` (a general word for fruit) is deliberately not recognised and stays residual.
- 직박구리-type questions about a target species' own traits keep the existing data limits of the graph handler (directly linked TraitClaims only).
- Whole-route latency in shadow/active mode, the real API, and TEST deployment are RG-208 and root's.
