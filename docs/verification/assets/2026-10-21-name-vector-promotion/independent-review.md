# Independent review: TEST → Production name-vector promotion operator (task_314bc6959251)

Reviewer: Claude (dev-claude), read-only. No DB connections, writes, DDL, restarts, or Git changes were made.
Date: 2026-10-21

## Code reviewed (sha256)
| File | sha256 |
|---|---|
| dev-codex `src/robingraph/retrieval/taxon_name_vectors_neo4j.py` (HEAD 9c7f40a) | e843a1274e6d7f32dfee38f19236b196877a1f2b09b5430e262d6129868a505d (= `module_sha256` in the TEST export) |
| dev-codex `scripts/index_taxon_name_vectors.py` | ad507ed34fb85ba57254c75902cbb0369e877e602533fa62de0cd30aaacf217e |
| dev-codex `src/robingraph/embeddings/__init__.py` | 5e936e92d1edc621a708296e433179aa8539770ef67003bb519f668fc3bd967d |
| dev-codex `tests/test_taxon_name_vectors_neo4j.py` | b6fb86e0d723ce84ed595f503cb3adeff0cfcebc7992f3d8d65af440efc6f793 |
| dev-codex `tests/test_index_taxon_name_vectors.py` | 9bf0414362447123a6db711944bc8ad4dd464285c97c53478117a5271af0c3f9 |
| **final** `/tmp/rg-name-promotion/common.py` | 07a17f950c9eb868a2d2991d49f26cc9a47ed555245bfdbd406caa776dc9a156 (earlier revisions reviewed: 6469660…, 05c975e…, 76da668…) |
| **final** `/tmp/rg-name-promotion/promote.py` | 0c8162dc94e179ca000ec84c13899a8e31295dad1ba3b6ecc0d72a30ead9a7ea (earlier: 2136c00…, 6aac6c0…, 8745829…) |
| TEST export `.../name-vector-promotion-20261021-ad361c90/test-export.json` (file) | c4ce73cb263382bd47a2903dc6c0ac3afc5cd67a1896758474df21f4e81d4e5f; canonical digest b755c2a0ae35… matches the summary `export_sha256` |

There is no `src/` diff between `770495a` (the deployed Production image commit) and `9c7f40a`, so the Production runtime code is the same as the code reviewed.

## Commands and results
1. `.venv/bin/python -m unittest tests.test_taxon_name_vectors_neo4j tests.test_index_taxon_name_vectors tests.test_embeddings tests.test_taxon_name_resolution` (dev-codex): **61 tests OK** (offline/mock).
2. Mock harness `harness.py`: renormalization drift through `_vector` is ≤5.6e-17 per component. index_names reuses destination entries that have the same key and text_hash without calling `embed_documents` (B1). The operator closes this by requiring an empty destination.
3. Mock harness `harness_common.py` / `harness_apply.py` against the **actual TEST export** (read only; no DB):
   - `validate_source` accepts the export: 855 vectors, 512 dims, max |norm−1| 1.1e-16, no duplicate texts. The 3 self-query names (Anas platyrhynchos, Anas zonorhyncha, Nestor notabilis) are present.
   - Rejected negative cases: NaN vector, 511 dims, profile model/dims, context release, link to a foreign/fixture taxon, missing link, an inventory row dropped, edited inventory text, an active entry removed, a foreign active fixture entry, catalog count, target=prod.
   - Destination guards: context mismatch, module hash mismatch, and a non-empty destination are all rejected.
   - End-to-end `apply_source` with the real `index_names` against an in-memory fake Neo4j: state verified, count 855, cache_calls 1, reused 0, embedded 855, max diff 2.8e-17. Rerunning against a non-empty destination is rejected, a stale baseline digest is rejected, and a missing PINNED identity is rejected.
4. `harness_wrap.py`: the apply NAS wrapper is rebuilt from the real promote.py template. It is 10.46 MB and parses. BACKUP_CODE, PAYLOAD and EXPECTED round-trip exactly, OPERATION appears 3 times, and the source literal equals the export.
5. `python -O` on the common.py header raises `Optimized execution is forbidden`.

Distinction: everything above is offline (mock/fixture/actual-export file). Nothing was run against a real TEST or Production DB or model endpoint. The embedding probe and the self-queries ran only against fakes, so the cosine checks were trivially satisfied in the mock.

## Final-revision additions verified (mock)
- `validate_source` now requires `feature_count`, exactly one schema row and one constraint row, the recorded index compatible and ONLINE at the source dims, and a compatible constraint. Because the post-apply check calls validate_source(after), Production must end with an ONLINE 512-dim cosine index. Mock negatives were rejected: index dims 1024, index POPULATING, feature_count 856, and a stray destination feature node. In total 16/16 source negatives and 4/4 destination negatives were rejected.
- The operator and validation sha256 values are pinned in plan.json and re-checked by `--apply`. The remote wrappers carry a `__debug__` guard. The wrapper substitution was rebuilt from the final template: 10.46 MB, it parses, and every placeholder round-trips exactly.
- **Note:** the existing export `name-vector-promotion-20261021-ad361c90` predates `feature_count` and `operator_sha256`. The current code fails closed on it (KeyError and missing receipt field), so `--plan` must be re-run to produce a fresh export and plan.json before `--apply`. For the mock run, the harness added the fields in memory only, so its digest differs from b755c2a0 by design.

## Verdict
**No blocker** for `--plan` or `--apply` at the hashes above. The guards cover:
- fixture or foreign taxa mixing in (exact inventory, links and labels)
- unrelated graph and PG state (taxa properties and ingest_state digests are compared before and after)
- exact equality of inventory, context, profile and module hash
- index dimensions (repository `_index_state` plus ONLINE search)
- empty-destination compare-and-swap
- copy precision (<1e-12)
- target identity (env, docker inspect, `.env.nas.prod`, pinned identity)

## Non-blocking recommendations
1. **N4:** if a post-commit check fails (search, snapshot or diff), the data is already committed but the NAS `receipt.json` is never written. Only `production-before.json` exists, and the lock is released. Treat any nonzero exit from `--apply` as "committed – unverified" and inspect before retrying. A rerun is refused anyway because the destination is no longer empty. Optionally, wrap the post-commit checks so they write a partial receipt.
2. If the data transaction fails, the DDL (constraint and vector index) is auto-committed before it and remains as empty schema. Recovery needs separate approval, as the root notes.
3. The identity pin proves "unchanged since plan" combined with `bolt://neo4j:7687`, db `robingraph`, and container env equal to `.env.nas.prod`. The PG host and user are not independently pinned to known-good values.
4. The `.env.nas.prod` comparison fails closed spuriously if values are quoted, or if `NEO4J_DATABASE` is omitted from the file (compose defaults it to `neo4j`).
5. If the vector index has not yet reflected the write when the self-query runs right after commit, it fails post-commit. That is the same case as item 1.

## Final rerun on the refreshed source packet (frozen operator)
- Export `/Users/kimdove/robingraph-test/backups/name-vector-promotion-20261021-06a7a825/test-export.json`: file sha256 257c17e72eef832a03c273cea25d706e8e66c43deb013206d763cf50f720f9be. Its canonical digest a46d0bb4b3a1573c29ace2e7b91cada00333ff5c5f7fe783661d61fd637b4a1d equals the summary `export_sha256`. feature_count, schema and constraint are present, so no in-memory adaptation was needed.
- Rerun results:
  - validate_source OK (855 vectors, 512 dims)
  - 16/16 source negatives and 4/4 destination negatives rejected
  - mock apply_source verified (cache_calls 1, reused 0, embedded 855, max diff 2.8e-17)
  - rerun, stale baseline and missing pin all rejected
  - wrapper rebuild exact (10,464,392 bytes)
  - module unittests: 61 OK
- The ad361c90 note above is superseded: the fresh export and plan path exist. `--plan` must still be run once with the frozen operator so that plan.json records operator_sha256 and validation_sha256 before `--apply`.
- Clearance applies only to common.py 07a17f95…a156 and promote.py 723736e12636372ae205fc5f7f6c94ab6a140833e06988c4ecab1f688a753648 (final redaction edit reviewed: the identity is read from the private 600 production-before.json, checked against destination_identity_sha256 in the receipt, and pinned before any DB access; wrapper rebuild re-verified). Any later edit voids it.
