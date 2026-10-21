import copy
import math
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch

from robingraph.embeddings import EmbeddingProfile
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval import taxon_name_vectors_neo4j as module
from robingraph.retrieval.taxon_name_vectors_neo4j import (
    Neo4jTaxonNameVectorRepository, TaxonNameVectorUnavailable, catalog_fingerprint)


CONTEXT = ("rg:concept-set:avilist-v2025b", "v2025b")
PROFILE = EmbeddingProfile("jinaai/jina-embeddings-v3", 3, True)
TAXA = {"avilist-taxon:v2025b:540": "Anas zonorhyncha", "avilist-taxon:v2025b:541": "Anas platyrhynchos",
        "avilist-taxon:v2025b:100": "Ardea cinerea"}
NAMES = {"avilist-taxon:v2025b:540": "흰뺨검둥오리", "avilist-taxon:v2025b:541": "청둥오리",
         "avilist-taxon:v2025b:100": "왜가리"}
VECTORS = {"흰뺨검둥오리": (1.0, 0.0, 0.0), "청둥오리": (0.0, 1.0, 0.0), "왜가리": (0.0, 0.0, 1.0),
           "청둥 오리": (0.0, 0.8, 0.6)}
WRITE_QUERIES = {module._CREATE_INDEX, module._CREATE_CONSTRAINT, module._UPSERT_ENTRIES, module._RETIRE_STALE,
                 module._SWITCH_CATALOG}


def inventory(names=NAMES):
    return [{"taxon_id": taxon_id, "scientific_name": TAXA[taxon_id], "display_name": name, "text": name}
            for taxon_id, name in names.items()]


class Result:
    def __init__(self, rows):
        self.rows = rows

    def data(self):
        return copy.deepcopy(self.rows)

    def consume(self):
        return None


class FakeGraph:
    """In-memory stand-in for the queries this module issues."""

    def __init__(self):
        self.index = None
        self.constraint = None
        self.taxa = dict(TAXA)
        # (concept_set_id, version) -> policy_status; there is no IngestState.
        self.concept_sets = [(CONTEXT, "allowed")]
        self.entries = {}
        self.catalog = None
        self.queries = []
        self.fail_on = None
        self.hits = None

    def state(self):
        return copy.deepcopy((self.index, self.constraint, self.entries, self.catalog))

    def restore(self, state):
        self.index, self.constraint, self.entries, self.catalog = state

    def run(self, query, read_only, **p):
        self.queries.append(query)
        if "IngestState" in query:
            raise AssertionError("IngestState must not be queried")
        self.params = getattr(self, "params", {})
        self.params[query] = p
        if read_only and query in WRITE_QUERIES:
            raise AssertionError("write query in a read transaction")
        if query is self.fail_on:
            raise RuntimeError("injected failure")
        if query is module._SHOW_INDEX:
            return Result([self.index] if self.index else [])
        if query is module._CREATE_INDEX:
            self.index = {"type": "VECTOR", "state": "ONLINE", "labelsOrTypes": ["TaxonNameVector"],
                          "properties": ["name_vector"],
                          "options": {"indexConfig": {"vector.dimensions": p["dimensions"],
                                                      "vector.similarity_function": "COSINE"}}}
            return Result([])
        if query is module._AWAIT_INDEX:
            return Result([])
        if query is module._SHOW_CONSTRAINT:
            return Result([self.constraint] if self.constraint else [])
        if query is module._CREATE_CONSTRAINT:
            self.constraint = {"type": "UNIQUENESS", "labelsOrTypes": ["TaxonNameVectorEntry"], "properties": ["key"]}
            return Result([])
        if query is module._ACTIVE_CONTEXT:
            return Result([{"concept_set_id": key[0], "taxonomy_release": key[1]} for key in self.allowed(p)])
        if query is module._ALLOWED_TAXA:
            ok = bool(self.allowed(p))
            return Result([{"taxon_id": r["taxon_id"]} for r in p["rows"]
                           if ok and self.taxa.get(r["taxon_id"]) == r["scientific_name"]])
        if query is module._EXISTING_ENTRIES:
            return Result([{"key": e["key"], "text_hash": e["text_hash"], "taxon_id": e["taxon_id"],
                            "scientific_name": e["scientific_name"], "vector": e.get("name_vector")}
                           for key, e in self.entries.items() if key in p["keys"]])
        if query is module._ACTIVE_KEYS:
            return Result([{"key": key} for key, e in self.entries.items() if "TaxonNameVector" in e["labels"]])
        if query is module._CATALOG:
            return Result([dict(self.catalog)] if self.catalog else [])
        if query is module._UPSERT_ENTRIES:
            written = 0
            for row in p["rows"]:
                if self.allowed(p) and self.taxa.get(row["taxon_id"]) == row["scientific_name"]:
                    self.entries[row["key"]] = {**row["properties"], "key": row["key"], "name_vector": list(row["vector"]),
                                                "labels": {"TaxonNameVectorEntry", "TaxonNameVector"},
                                                "linked_to": row["taxon_id"]}
                    written += 1
            return Result([{"written": written}])
        if query is module._RETIRE_STALE:
            retired = 0
            for key, entry in self.entries.items():
                if "TaxonNameVector" in entry["labels"] and key not in p["keys"]:
                    entry["labels"].discard("TaxonNameVector")
                    entry.pop("name_vector", None)
                    retired += 1
            return Result([{"retired": retired}])
        if query is module._SWITCH_CATALOG:
            self.catalog = {"fingerprint": p["fingerprint"], "model": p["model"], "dimensions": p["dimensions"],
                            "normalized": p["normalized"], "concept_set_id": p["concept_set_id"],
                            "taxonomy_release": p["release"], "count": p["count"]}
            return Result([])
        if query is module._SEARCH:
            if not self.allowed(p):
                return Result([])
            if self.hits is not None:
                return Result(self.hits)
            rows = []
            for entry in self.entries.values():
                if "TaxonNameVector" not in entry["labels"] or entry["catalog_fingerprint"] != p["fingerprint"]:
                    continue
                vector = entry["name_vector"]
                cosine = sum(a * b for a, b in zip(vector, p["vector"])) / (math.hypot(*vector) * math.hypot(*p["vector"]))
                rows.append({**{f: entry[f] for f in ("taxon_id", "scientific_name", "display_name", "text", "text_hash")},
                             "score": (1 + cosine) / 2})
            return Result(sorted(rows, key=lambda r: -r["score"])[:p["limit"]])
        raise AssertionError("unexpected query")


    def allowed(self, p):
        key = (p["concept_set_id"], p["release"])
        return [k for k, status in self.concept_sets if k == key and status == "allowed"]


class FakeTx:
    def __init__(self, graph, read_only):
        self.graph, self.read_only = graph, read_only

    def run(self, query, **parameters):
        return self.graph.run(query, self.read_only, **parameters)


class FakeSession:
    def __init__(self, graph):
        self.graph = graph
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.closed = True

    def run(self, query, **parameters):
        return self.graph.run(query, False, **parameters)

    def execute_read(self, function):
        return function(FakeTx(self.graph, True))

    def execute_write(self, function):
        snapshot = self.graph.state()
        try:
            return function(FakeTx(self.graph, False))
        except Exception:
            self.graph.restore(snapshot)
            raise


class FakeDriver:
    def __init__(self, graph):
        self.graph = graph
        self.sessions = []
        self.closed = False

    def session(self, database):
        session = FakeSession(self.graph)
        self.sessions.append(session)
        return session

    def close(self):
        self.closed = True


class Embeddings:
    def __init__(self, profile=PROFILE, vectors=VECTORS):
        self.profile = profile
        self.vectors = vectors
        self.document_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        return tuple(self.vectors[text] for text in texts)

    def embed_query(self, text):
        raise AssertionError("indexing must not embed queries")


class RepositoryCase(TestCase):
    def setUp(self):
        self.graph = FakeGraph()
        self.driver = FakeDriver(self.graph)
        patcher = patch.object(module.GraphDatabase, "driver", return_value=self.driver)
        self.driver_factory = patcher.start()
        self.addCleanup(patcher.stop)
        self.repository = Neo4jTaxonNameVectorRepository(Neo4jSettings("bolt://x", "u", "p", "neo4j"))

    def apply(self, names=NAMES, embeddings=None):
        embeddings = embeddings or Embeddings()
        return self.repository.index_names(inventory(names), embeddings, CONTEXT, dry_run=False), embeddings

    def writes(self):
        return [q for q in self.graph.queries if q in WRITE_QUERIES]


class IndexTests(RepositoryCase):
    def test_connection_is_lazy_and_closed(self):
        self.driver_factory.assert_not_called()
        self.repository.index_names(inventory(), Embeddings(), CONTEXT)
        self.driver_factory.assert_called_once()
        self.assertTrue(all(session.closed for session in self.driver.sessions))
        self.repository.close()
        self.assertTrue(self.driver.closed)

    def test_dry_run_reads_only_with_zero_model_calls(self):
        embeddings = Embeddings()
        report = self.repository.index_names(inventory(), embeddings, CONTEXT)
        self.assertEqual(report, {"dry_run": True, "inventory": 3, "reused": 0, "to_embed": 3, "embedded": 0,
                                  "stale": 0, "schema": "absent", "constraint": "absent", "catalog_current": False})
        self.assertEqual((embeddings.document_calls, self.writes(), self.graph.index, self.graph.constraint),
                         ([], [], None, None))

    def test_apply_creates_schema_links_species_and_switches_catalog(self):
        report, embeddings = self.apply()
        self.assertEqual((report["schema"], report["constraint"], report["embedded"], report["reused"],
                          report["catalog_current"]), ("created", "created", 3, 0, True))
        for entry in self.graph.entries.values():
            self.assertAlmostEqual(math.hypot(*entry["name_vector"]), 1.0)
        self.assertEqual(len(embeddings.document_calls), 1)
        active = [e for e in self.graph.entries.values() if "TaxonNameVector" in e["labels"]]
        self.assertEqual(sorted(e["linked_to"] for e in active), sorted(TAXA))
        self.assertEqual(self.graph.catalog["fingerprint"],
                         catalog_fingerprint(sorted(inventory(), key=lambda r: r["taxon_id"]),
                                             ("jinaai/jina-embeddings-v3", 3, True), CONTEXT))
        self.assertEqual(self.graph.taxa, TAXA)  # taxa are never mutated

    def test_second_apply_is_idempotent_and_reuses_vectors(self):
        self.apply()
        before = {k: e["name_vector"] for k, e in self.graph.entries.items()}
        report, embeddings = self.apply()
        self.assertEqual(embeddings.document_calls, [])
        self.assertEqual((report["reused"], report["embedded"], report["stale"], report["schema"]), (3, 0, 0, "compatible"))
        self.assertEqual({k: e["name_vector"] for k, e in self.graph.entries.items()}, before)
        self.assertEqual(self.graph.queries.count(module._CREATE_INDEX), 1)
        self.assertEqual(self.graph.queries.count(module._CREATE_CONSTRAINT), 1)

    def test_changed_text_embeds_only_that_name_and_removed_name_is_retired(self):
        self.apply()
        changed = {"avilist-taxon:v2025b:540": "흰뺨검둥오리", "avilist-taxon:v2025b:541": "청둥 오리"}
        report, embeddings = self.apply(changed)
        self.assertEqual(embeddings.document_calls, [["청둥 오리"]])
        self.assertEqual((report["reused"], report["embedded"], report["stale"]), (1, 1, 1))
        retired = [e for e in self.graph.entries.values() if e["taxon_id"] == "avilist-taxon:v2025b:100"]
        self.assertEqual(len(retired), 1)
        self.assertNotIn("TaxonNameVector", retired[0]["labels"])
        self.assertNotIn("name_vector", retired[0])
        self.assertEqual(self.graph.catalog["count"], 2)

    def test_taxon_or_context_mismatch_fails_before_any_write_or_embedding(self):
        cases = []
        bad_name = inventory()
        bad_name[0] = {**bad_name[0], "scientific_name": "Anas wrongii"}
        cases.append((bad_name, CONTEXT))
        cases.append((inventory(), ("rg:concept-set:avilist-v2026a", "v2026a")))
        for rows, context in cases:
            for dry_run in (True, False):
                embeddings = Embeddings()
                with self.assertRaises(TaxonNameVectorUnavailable):
                    self.repository.index_names(rows, embeddings, context, dry_run=dry_run)
                self.assertEqual((embeddings.document_calls, self.writes()), ([], []))

    def test_supplied_context_is_checked_against_allowed_concept_set_without_ingest_state(self):
        self.apply()
        self.assertEqual(self.graph.params[module._ACTIVE_CONTEXT], {"concept_set_id": CONTEXT[0], "release": CONTEXT[1]})
        self.assertEqual(self.graph.params[module._ALLOWED_TAXA]["concept_set_id"], CONTEXT[0])
        for name in ("_ACTIVE_CONTEXT", "_ALLOWED_TAXA", "_UPSERT_ENTRIES", "_SEARCH"):
            self.assertNotIn("IngestState", getattr(module, name))
        before = self.graph.state()
        for concept_sets in ([], [(CONTEXT, "revoked")], [(CONTEXT, "allowed"), (CONTEXT, "allowed")],
                             [(("rg:concept-set:avilist-v2026a", "v2026a"), "allowed")]):
            self.graph.concept_sets = concept_sets
            for dry_run in (True, False):
                embeddings = Embeddings()
                with self.assertRaises(TaxonNameVectorUnavailable):
                    self.repository.index_names(inventory(), embeddings, CONTEXT, dry_run=dry_run)
                self.assertEqual(embeddings.document_calls, [])
        self.assertEqual(self.graph.state(), before)

    def test_failure_inside_write_rolls_back_atomically(self):
        self.apply()
        before = self.graph.state()
        self.graph.fail_on = module._SWITCH_CATALOG
        with self.assertRaises(RuntimeError):
            self.apply({"avilist-taxon:v2025b:540": "흰뺨검둥오리"})
        self.assertEqual(self.graph.state(), before)

    def test_taxon_revoked_between_plan_and_write_rolls_back(self):
        self.apply()
        before = self.graph.state()
        original = self.graph.run

        def revoke_on_write(query, read_only, **p):
            if query is module._ALLOWED_TAXA and not read_only:
                self.graph.taxa.pop("avilist-taxon:v2025b:100", None)
            return original(query, read_only, **p)

        self.graph.run = revoke_on_write
        embeddings = Embeddings()
        with self.assertRaises(TaxonNameVectorUnavailable):
            self.repository.index_names(inventory(), embeddings, CONTEXT, dry_run=False)
        self.assertEqual(self.graph.state(), before)

    def test_empty_inventory_never_retires_active_entries(self):
        self.apply()
        before = self.graph.state()
        for dry_run in (True, False):
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.index_names([], Embeddings(), CONTEXT, dry_run=dry_run)
        self.assertEqual(self.graph.state(), before)

    def test_incompatible_constraint_fails_before_embedding(self):
        self.graph.constraint = {"type": "UNIQUENESS", "labelsOrTypes": ["TaxonNameVectorEntry"], "properties": ["id"]}
        embeddings = Embeddings()
        with self.assertRaises(TaxonNameVectorUnavailable):
            self.repository.index_names(inventory(), embeddings, CONTEXT, dry_run=False)
        self.assertEqual((embeddings.document_calls, self.writes()), ([], []))

    def test_incompatible_schema_fails_without_ddl_or_embedding(self):
        for config in ({"vector.dimensions": 1024, "vector.similarity_function": "COSINE"},
                       {"vector.dimensions": 3, "vector.similarity_function": "EUCLIDEAN"}):
            self.graph.index = {"type": "VECTOR", "state": "ONLINE", "labelsOrTypes": ["TaxonNameVector"],
                                "properties": ["name_vector"], "options": {"indexConfig": config}}
            embeddings = Embeddings()
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.index_names(inventory(), embeddings, CONTEXT, dry_run=False)
            self.assertEqual((embeddings.document_calls, self.writes()), ([], []))

    def test_invalid_input_and_vectors_fail_before_writes(self):
        duplicate = inventory() + [inventory()[0]]
        for rows in (duplicate, "x", [{"taxon_id": "a"}], inventory() * 400, []):
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.index_names(rows, Embeddings(), CONTEXT, dry_run=False)
        for bad in ((float("nan"), 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0), (1.7e308, 1.7e308, 1.7e308)):
            embeddings = Embeddings(vectors={**VECTORS, "왜가리": bad})
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.index_names(inventory(), embeddings, CONTEXT, dry_run=False)
        for profile in (None, SimpleNamespace(model="m", dimensions=None, normalized=True)):
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.index_names(inventory(), Embeddings(profile=profile), CONTEXT, dry_run=False)
        self.assertEqual(self.writes(), [])


class SearchTests(RepositoryCase):
    def setUp(self):
        super().setUp()
        self.apply()
        self.graph.queries.clear()

    def test_search_is_read_only_and_converts_score_to_cosine(self):
        hits = self.repository.search((0.0, 8.0, 6.0), PROFILE, CONTEXT, inventory(), limit=2)
        self.assertEqual(self.graph.params[module._SEARCH]["vector"], [0.0, 0.8, 0.6])  # unit query
        self.assertEqual([h["display_name"] for h in hits], ["청둥오리", "왜가리"])
        self.assertAlmostEqual(hits[0]["score"], 0.8)
        self.assertAlmostEqual(hits[1]["score"], 0.6)
        self.assertEqual(set(hits[0]), {"taxon_id", "scientific_name", "display_name", "text", "score"})
        self.assertEqual(self.writes(), [])
        self.assertNotIn(module._AWAIT_INDEX, self.graph.queries)

    def test_opposite_vector_gives_negative_cosine(self):
        hits = self.repository.search((-1.0, 0.0, 0.0), PROFILE, CONTEXT, inventory(), limit=1)
        self.assertAlmostEqual(hits[0]["score"], 0.0)  # both others are orthogonal
        self.graph.hits = [{"taxon_id": "avilist-taxon:v2025b:540", "scientific_name": "Anas zonorhyncha",
                            "display_name": "흰뺨검둥오리", "text": "흰뺨검둥오리",
                            "text_hash": module._text_hash("흰뺨검둥오리"), "score": 0.0}]
        self.assertEqual(self.repository.search((-1.0, 0.0, 0.0), PROFILE, CONTEXT, inventory())[0]["score"], -1.0)

    def test_stale_foreign_and_malformed_hits_are_dropped(self):
        good = {"taxon_id": "avilist-taxon:v2025b:541", "scientific_name": "Anas platyrhynchos",
                "display_name": "청둥오리", "text": "청둥오리", "text_hash": module._text_hash("청둥오리"), "score": 0.9}
        self.graph.hits = [
            {**good, "taxon_id": "avilist-taxon:v2025b:999"},
            {**good, "text_hash": "0" * 64},
            {**good, "display_name": "청둥"},
            {**good, "score": 1.5}, {**good, "score": float("nan")}, {**good, "score": True},
            good, {**good, "score": 0.5},
        ]
        hits = self.repository.search((0.0, 1.0, 0.0), PROFILE, CONTEXT, inventory())
        self.assertEqual([(h["taxon_id"], round(h["score"], 6)) for h in hits], [("avilist-taxon:v2025b:541", 0.8)])

    def test_stale_catalog_or_schema_fails_closed(self):
        changed = inventory({"avilist-taxon:v2025b:540": "흰뺨검둥오리"})
        other_profile = EmbeddingProfile("other-model", 3, True)
        for args in ((PROFILE, CONTEXT, changed), (other_profile, CONTEXT, inventory()),
                     (PROFILE, ("rg:concept-set:avilist-v2026a", "v2026a"), inventory())):
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.search((1.0, 0.0, 0.0), *args)
        self.graph.index["state"] = "POPULATING"
        with self.assertRaises(TaxonNameVectorUnavailable):
            self.repository.search((1.0, 0.0, 0.0), PROFILE, CONTEXT, inventory())
        self.graph.index = None
        with self.assertRaises(TaxonNameVectorUnavailable):
            self.repository.search((1.0, 0.0, 0.0), PROFILE, CONTEXT, inventory())
        self.assertEqual(self.writes(), [])

    def test_missing_revoked_or_duplicated_concept_set_fails_search(self):
        for concept_sets in ([], [(CONTEXT, "revoked")], [(CONTEXT, "allowed"), (CONTEXT, "allowed")]):
            self.graph.concept_sets = concept_sets
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.search((1.0, 0.0, 0.0), PROFILE, CONTEXT, inventory())
        self.assertNotIn(module._SEARCH, self.graph.queries)
        self.assertEqual(self.writes(), [])

    def test_invalid_query_vector_profile_or_limit_never_queries(self):
        for vector, profile, limit in (((0.0, 0.0, 0.0), PROFILE, 5), ((1.0, 0.0), PROFILE, 5),
                                       ((float("inf"), 0.0, 0.0), PROFILE, 5), ((1.0, 0.0, 0.0), None, 5),
                                       ((1.0, 0.0, 0.0), PROFILE, 0), ((1.0, 0.0, 0.0), PROFILE, 51),
                                       ((1.0, 0.0, 0.0), PROFILE, True)):
            with self.assertRaises(TaxonNameVectorUnavailable):
                self.repository.search(vector, profile, CONTEXT, inventory(), limit=limit)
        self.assertEqual(self.graph.queries, [])
