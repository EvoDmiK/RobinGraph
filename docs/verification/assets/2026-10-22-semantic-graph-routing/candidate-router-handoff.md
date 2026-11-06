# RG-206 result: graph kind candidate router (Claude, dev-claude)

- Not done: no DB access, deploy or Git operation. RG-207 was not started. I did not read the holdout.
- TEST access was embedding calls to Jina only. The patched modules were loaded into a single process; the container image was not changed.
- Model: `claude-opus-5-5`.

## Finished files (dev-claude, uncommitted)

| File | Kind | sha256 |
|---|---|---|
| `src/robingraph/retrieval/graph_semantic_router.py` | new | `85a36933dccf68d73c991b61f5fe702bf1654749d88d197683b3ae296b1aa4dc` |
| `tests/test_graph_semantic_router.py` | new | `c07b909116a0353a733f78fb9c972d10348d7c64e71c0c50a2d58671ff3d8fe1` |
| `src/robingraph/embeddings/__init__.py` | shared, edited (root-approved `embed_queries`) | `d7e8807d915dd7e809dbc3262bc7b2ea8816e368654f204acba6aff00df1715c` |
| `tests/test_embeddings.py` | shared, edited (2 tests added) | `3c314f31738184febcafc99fa229f0629c9f7b711d8e7f73f51171c7a2de1bb4` |

- The patch is against root's current files: `/tmp/rg206-embed_queries.patch`. Before patching, my files and root's were confirmed byte-identical (`cmp`).
- `embed_queries`:
  - reuses the document batching (`_embed_many`) with the query task;
  - `embed_documents` and `embed_query` behave exactly as before;
  - it is not added to the `EmbeddingClient` Protocol, so existing fake and Protocol clients are unaffected.

## Router contract (the cli closure root already wired still works)
- **`classify(question) -> KindCandidates`.** It never raises. Fields:
  - `candidates` (top 3), `margin`, `status` (`ok` / `below_threshold` / `unavailable`);
  - `prototype_version`, `model`, `elapsed_ms`;
  - `embedding_calls`: query embedding attempts;
  - `prototype_calls`: cache load attempts, counted even on failure;
  - `prototype_requests` (**new**): client method calls;
  - `prototype_batches` (**new**): HTTP batches implied by the client's batch_size, or None when unknown.
- **Prototypes:**
  - 45 answerable or insufficient-data **tuning** questions;
  - **embedded with the query task**: `embed_queries` when it is callable, otherwise an `embed_query` loop for fake or old clients.
- **Cache:**
  - the key is `(PROTOTYPE_VERSION, model, dimensions, normalized)`, and the profile is validated (model name, positive integer dimensions, boolean `normalized`);
  - a failed or partial load (count or dimension mismatch, non-finite values) is never cached and is retried on the next call.
- **Thresholds:** confidence 0.80 in [0,1], margin 0.06 in [0,2]. bool, NaN and inf are rejected at construction.
- **Errors:** `_profile_key` runs inside the try block, so a profile property error also gives unavailable.

## Tests (unit, fake clients)
- dev-claude: `PYTHONPATH=src:tests .venv/bin/python -m unittest test_graph_semantic_router test_embeddings test_graph_intent_schema` → **38 OK**.
- Router tests cover:
  - prototypes being tuning-only and answerable;
  - nearest neighbour per kind;
  - ok, below_threshold, warm and cold counts;
  - the batch path (1 method call = 2 batches);
  - batch failure and short batches not being cached;
  - cache key changes on model/normalized;
  - failure counts;
  - abnormal vectors (NaN, inf, zero, wrong dimensions, bool, str, None) and profiles;
  - never raising (profile exception, empty question);
  - threshold and prototype checks in the constructor.
- Embedding tests cover:
  - `embed_queries` sends the query task with batches of `[2, 1]` items;
  - an empty input makes no HTTP call;
  - documents still use the passage task;
  - count and dimension mismatches raise `EmbeddingResponseError`.
- Staging copy (root's latest code plus these 4 files):
  - focused run (router, embeddings, birdsnest, embedding_flow): OK;
  - `test_graph_semantic_api` hit an ImportError in my run because `asgi_client` was missing from the path. Re-run with `PYTHONPATH=src:tests`, it is included in the full run below.
  - Full run: 1105 tests, 7 failed, 39 skipped. **All 7 are `test_nas_release_package`, which needs `git rev-parse HEAD`; the staging copy has no `.git`.** That is an environment difference, not an app defect, and I changed nothing for it. A full run in the real worktree is root's step.

## Real TEST Jina measurements
- Setup: `robingraph-api-test`, `ROBINGRAPH_DEPLOY_TARGET=test`, `jinaai/jina-embeddings-v3`, 512 dims, normalized, batch_size 32, graph client with 2 s timeout and 0 retries.
- Evidence: `/tmp/rg206-router-probe.json`. Scripts are in the scratchpad (`probe_loo.py`, `probe_router.py`, `probe_cold.py`).

| Item | Result |
|---|---|
| cold classify (batch path) | 2125 ms. prototype_calls 1, prototype_requests 1, prototype_batches 2, embedding_calls 1, **3 real HTTP requests** |
| cold HTTP per request (3 runs) | 32-text batch 1258/1133/1147 ms, 13-text batch 595/550/547 ms, query 211/207/206 ms. Whole cold load 1930–2107 ms |
| warm classify (84 tuning questions) | p50 210.5 ms, p95 222.8 ms, max 250.4 ms; **1 HTTP request per question**; prototype_calls 0 |
| recovery (first HTTP simulated as timeout) | failed: unavailable, prototype_calls 1, requests 1, embedding_calls 0. Next call: ok, prototype reload 2184 ms |
| per-text fallback cold (no embed_queries) | 9614 ms, 45 prototype requests + 1 query = 46 HTTP requests |
| batch vs single query vectors | minimum cosine 0.999999 |

### Threshold evidence: leave-one-out on tuning, excluding the question itself from the prototypes

| Prototype task | LOO top-1 |
|---|---|
| passage | 41/67 |
| **query** | **53/67** |

Sweep, query task:

| confidence / margin | confident | correct | wrong |
|---|---|---|---|
| 0.80 / 0.04 | 40 | 35 | 5, including 2 answerable (T-015, T-030) |
| **0.80 / 0.06 (chosen)** | **30** | **28** | **2: T-039 specific_fruit→order_fruit (insufficient), T-045 contrastive clarify. 0 answerable errors** |
| 0.85 / 0.06 | 29 | 27 | same 2 |

- Why 0.80/0.06: a candidate can only add `kind_tie`, which turns a result into clarify. So a confident wrong candidate does not cause a false execution; it costs coverage. 0.80/0.06 had zero confident errors on answerable questions.
- Most of the router's confusion is between contrastive pairs: same vs different diet, specific vs general fruit, korea vs general same genus. **The extractor's rules have to settle these.** The router is only an auxiliary check.

## Limitations and unverified items
- The thresholds come from the tuning set itself (leave-one-out, selected after a sweep), so there is selection bias. **Holdout verification of their effect happens after RG-207 is integrated.**
- Cold load headroom: the 32-text batch at 1.13–1.26 s leaves about 0.75 s under the 2 s timeout. If the provider slows down, a cold load can fail. That fails closed and is retried on the next request; only that request gets an unavailable result. If needed, root can consider a smaller prototype batch or preloading at startup.
- Route p95 ≤ 1500 ms: the router alone has warm p95 222.8 ms. The whole route has not been measured, because the extractor and the real API path do not exist yet.
- The `embed_queries` change to the shared embeddings module still needs root's integration and a full run in the real worktree.
- RG-207 (`graph_condition_extractor.py`) does not exist yet, so the cli's shadow/active modes still cannot start.
