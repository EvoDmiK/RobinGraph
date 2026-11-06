# Graph question gold sets (RG-205)

Parser-level gold for the seven fixed graph question kinds. The schema is defined in
`src/robingraph/retrieval/graph_intent_schema.py` (`SCHEMA_VERSION = rg205-v1`).

| File | Author | Use |
|---|---|---|
| `tuning.jsonl` | `agent:claude-opus-5-5`; root/Codex semantic review (`agent_reviewed`, **not** human) | prototypes, thresholds and rules may be tuned on it |
| `holdout.jsonl` | root/Codex (separate author, `agent_draft`) | frozen before RG-206/207; never used for tuning; implementers do not read it |
| `manifest.json` | generated | counts, sha256, contributors |

These are **not** the 664 generated regex regression subcases in `tests/test_graph_questions.py`,
and they are not the synthetic `data/eval/v1` fixture. Only records whose `review_status` is
`human_reviewed` may be described as human-reviewed; a third-party review is requested separately.

## Record
`{id, split, question, expected, categories, provenance{author, created, review_status, reviewers}, notes}`

`expected` (missing optional fields default to `[]` / `null`; unknown fields are rejected):

| Field | Form |
|---|---|
| kind | one of the 7 kinds, or null |
| disposition | `answer`, `insufficient_data`, `clarify`, `unsupported`, `not_graph` |
| species, negation, residual | list of surface strings copied from the question |
| rank, group, specific_plant | surface string (rank may also be `["order", surface]`) |
| diet | `fruit_share`, `tree_fruit_share`, `frugivore`, `niche` (or `[code, surface]`) |
| habitat | AVONET code (`Forest` …) or `target` (the target species' own habitat) |
| relation | `same`, `different` |
| scope | `korea` only; absent means the request `species_scope` is kept |
| unsupported | `co_occurrence`, `evolutionary_distance`, `predation`, `ranking`, `other` |
| ambiguity | `kind_tie`, `name_ambiguous`, `relation_unclear`, `group_unresolved`, `other` |

Every surface must occur in the question, and the disposition must equal the execution gate's
result for the record, or the record is reported as invalid and not scored.

`unsupported` and `not_graph` are evaluation labels only; the API keeps clarify/abstain.
The same-genus overlap (`직박구리와 같은 속 새 알려줘`), which the service keeps on its existing
related route, is a service-level case and is not in this parser-level set.

## Evaluate (parser only; no network or DB)
```
PYTHONPATH=src python scripts/eval_graph_questions.py --gold data/eval/graph_questions/tuning.jsonl --json report.json
# holdout (root): also reject questions already in tuning or the regex tests
PYTHONPATH=src python scripts/eval_graph_questions.py --gold data/eval/graph_questions/holdout.jsonl \
    --leak-against data/eval/graph_questions/tuning.jsonl tests/test_graph_questions.py --json holdout-report.json
python scripts/eval_graph_questions.py --write-manifest data/eval/graph_questions
```
Explicit intents, filters and the request `species_scope` are checked by root's mock and real-API tests.

Exit code 1 means invalid or leaked records (a reproduction failure), not a quality verdict.
