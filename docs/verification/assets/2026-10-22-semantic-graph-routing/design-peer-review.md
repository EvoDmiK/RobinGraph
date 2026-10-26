# RG-204 design check (Claude, read-only)

- Inputs:
  - the RG-204 plan (`docs/work-log/2026-10-22-semantic-graph-routing-backlog.md`);
  - `/tmp/rg204-claude-interfaces.md`;
  - root's draft wiring in dev-codex: `services.py` 822–870, `cli.py` 245–300 and 363–364, `drf/application.py` 94–129;
  - the `graph_intent_schema.py` gate;
  - the test names in `tests/test_graph_semantic_api.py`.
- Not done: no code change, no test run, no DB, TEST or Jina call. I did not read the holdout.
- **This is a design consistency check, not verification that RG-204 is complete at runtime.**

## Key limitation (must be kept in the record)
- The schema gate (`validate_intent` / `execution_gate`) can only block conditions that are recorded in `negation` / `residual` / `unsupported` / `ambiguity`.
- If the extractor never records a condition (unextracted residual text), the gate cannot detect it. For example, with `해외에만 있는 청둥오리`, an extractor that drops the leading condition would get an `answer` from the gate.
- Two things are therefore required for safety:
  - the RG-207 extractor's span-coverage check: every content character is consumed or goes into residual;
  - its holdout verification.
- The name resolver (`matched` only) is a second safeguard, not a replacement.
- RG-206/207 are unfinished: the router is an untested draft and the extractor does not exist. **The core of RG-204 is therefore unverified.**

## Passed (consistent in design and code)

| Principle | Evidence |
|---|---|
| Embeddings only produce kind candidates | Candidates go only into `extract_graph_intent(question, candidates)` (cli.py:260–272). The service uses only `execution_gate`/`to_graph_question` |
| Only fixed templates run | Execution is `to_graph_question` → the existing `graph_question_answer`. No path builds Cypher |
| Explicit intents preserved | The new path runs only for `request.intent in ("auto","profile")` (services.py:836–837). taxonomy, observations and evidence are not touched |
| Single-species routes preserved | `not single_species` condition; the same_genus overlap still goes to the related route (services.py:870) |
| All 4 scopes preserved | `request.species_scope` goes to the handler unchanged. Question-level scope is `korea` only, and order_fruit+korea gives clarify |
| Filters preserved | After the semantic step, the existing ProfileChatFilters name check is applied |
| Name ID check | `graph_resolve_species` accepts only `matched` and rechecks canonical, taxon_id, concept_set and release (cli.py:282–299). It is used only in active mode (cli.py:364); off/shadow keep the old resolver |
| off / shadow / active | off makes no call. shadow only writes to tracing; the result and DB reads are unchanged. active runs only when the gate and the conversion pass. An invalid mode fails at construction (services.py:648) |
| Failure handling | In active, a handler exception gives clarify with the "do not read this as no data" warning. In shadow, an exception keeps the old answer |
| Rollback | Set `ROBINGRAPH_GRAPH_INTENT_MODE=off` and restart to return to the old path |
| Observability | Only status, top, margin, timing, call counts, model, version, kind and disposition. Logs carry only the exception type. No question text |
| Interface match | The cli closure matches the interfaces doc: `classify`, `KindCandidates.top`, `candidates=()` when there is no client |

## Risks: at most 3 to fix

### 1. (High) Active mode can take over existing auto routes
**Cause:**
- The gate applies `negation/residual/ambiguity → clarify` (graph_intent_schema.py:152) before `kind is None → not_graph` (line 156).
- The new path also runs for **every auto question without a single-species match** (services.py:836–837).
- So if the extractor records residual for a non-graph question such as `참새목 관찰 기록 보여줘` or `기후변화가 철새에 미치는 영향은?`:
  - active returns clarify;
  - the existing semantic/Jev routes for observations, evidence and taxonomy are never reached (services.py:850–857).
- `unsupported` with kind None (e.g. 잡아먹는) is also cut off as clarify. Any existing evidence-route answer it had would be lost (not checked).

**Fix (extractor contract, mine):**
- Record residual, negation and unsupported only when at least one graph cue has been consumed (rank, diet, habitat, genus or taxonomy relation, specific plant).
- With no graph cue, return a clean `GraphIntent(None)`, i.e. not_graph.
- Tuning T-052/T-054 (kind None + negation) have graph cues, so they still clarify.

**Root test to add:** in active + auto mode, a non-graph question without a single species (observations or evidence wording) reaches the existing route.

### 2. (Medium) Shadow and active always add an embedding call and up to 2 s to the request path
**Cause:**
- `graph_intent_handler` calls `router.classify` first (cli.py:262), synchronously, for every auto non-single-species question.
- In shadow the result does not change, but on a provider outage latency rises by up to 2 s on each of those requests.
- An embedding call is also made for non-graph questions, so G2 "graph query embedding ≤ 1" is met per question, but the cost grows across all auto traffic.

**Fix (root's closure + my extractor):**
- Run the extractor first with rules only (no cost).
- Call `router.classify` only when a graph cue exists, then re-run `extract_graph_intent(question, candidates)`.
- With no cue: 0 embedding calls, and the not_graph from risk 1 is kept.

### 3. (Medium) Active drops a legacy regex match whenever the extractor says not_graph, and does not check the source
**Cause:**
- services.py:849 overwrites with `graph_question = to_graph_question(...)`. When the extractor returns not_graph, a question the regex already answers (user_failure / the 664 forms) goes to the existing single-species/Jev routes.
- Until RG-207 meets G1 on the holdout, active can regress the "user_failure regression 0" gate.
- The service also accepts any GraphIntent from the handler. An intent marked `source='regex_fullmatch'` or `'gold'` would skip the scalar evidence check.

**Fix (root):**
- (a) Turn active on only after RG-207 passes G1 on the holdout. Before that, shadow only.
- (b) Decide explicitly what happens on not_graph with a legacy match. My recommendation: use `from_graph_question(question, legacy)` plus `execution_gate`. This keeps the T-064 block, but T-040 and T-080 remain regex false executions.
- (c) In active, accept only `interpreted.source == "extractor"`; anything else gives clarify.

## Unverified
- Runtime:
  - shadow and active **cannot start** while `graph_condition_extractor.py` is missing: the import fails in cli.py:250 when the mode is not off;
  - only off can run.
- RG-206 router thresholds: Jina leave-one-out was not run; the thresholds are placeholders.
- RG-207 extractor quality: holdout G1 kind, slots, coverage and false-execution figures.
- Real latency: warm p95 ≤ 1500 ms and the cold prototype load.
- Real TEST API and browser checks: no new deploy.
- How predation and co-occurrence questions are answered by the existing routes today, and whether the new path's unsupported → clarify would regress that (risk 1).
- Root's API tests: I only read the names (15 + 11 + 10 reported). I did not run them.

## Re-check after root's fixes (read-only)

Root's fixes, confirmed in the code:
- **cli.py 263–280:** the rules-based `extract_graph_intent(question)` runs first, then `execution_gate`.
  - If the result is not_graph, there are 0 embedding calls and the request goes back to the existing auto route.
  - `classify` is called only when a graph cue exists. This settles risk 2.
- **services.py 843 and 851–856:** active accepts only `source == "extractor"`. When the extractor says not_graph but the regex matched, the answer is clarify. Active is not allowed until the gates pass. This settles risk 3.

Extractor contract additions, mine for RG-207, settling risk 1:
1. With no graph cue, return a clean `GraphIntent(None, source="extractor")`: no residual, negation, unsupported or ambiguity.
2. Candidates can only add `ambiguity=("kind_tie",)`. They never add or remove a slot, and never turn a non-answer into answer. So if the first call is not_graph, the second gives the same result.
3. With the same question and `candidates=()`, the output is deterministic and never raises.

Remaining limitation: original-text consumption and the extractor are not implemented, so RG-204 is not complete at runtime. This record covers the design check only.
