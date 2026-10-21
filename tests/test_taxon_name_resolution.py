import math
import threading
import unicodedata
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock

from robingraph.retrieval import taxon_name_resolution as module
from robingraph.retrieval.taxon_name_resolution import TaxonNameResolver, compact_korean_name, normalize_mention
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


CONTEXT = ("rg:concept-set:avilist-v2025b", "v2025b")
SPECIES = {
    "Ardea cinerea": ("avilist-taxon:v2025b:100", "왜가리"),
    "Ardea alba": ("avilist-taxon:v2025b:101", "중대백로"),
    "Egretta garzetta": ("avilist-taxon:v2025b:102", "쇠백로"),
    "Ciconia boyciana": ("avilist-taxon:v2025b:103", "황새"),
    "Pica serica": ("avilist-taxon:v2025b:104", "까치"),
}


def lineage(scientific_name, taxon_id, rank="species", context=CONTEXT):
    return TaxonomyLineage(
        query_scientific_name=scientific_name, taxonomy_source="AviList",
        taxonomy_release=context[1], concept_set_id=context[0],
        items=(LineageTaxon("avilist-taxon:v2025b:1", "order", "Pelecaniformes", None),
               LineageTaxon(taxon_id, rank, scientific_name, None)),
        resolved_query_scientific_name=scientific_name)


class FakeGraph:
    """Exact-only graph lookup over scientific and Korean names."""

    def __init__(self):
        self.calls = []
        self.overrides = {}

    def __call__(self, name):
        self.calls.append(name)
        if name in self.overrides:
            value = self.overrides[name]
            if isinstance(value, Exception):
                raise value
            return value
        for science, (taxon_id, korean) in SPECIES.items():
            if name.casefold() in (science.casefold(), korean):
                return lineage(science, taxon_id)
        return None


def inventory():
    return [{"taxon_id": taxon_id, "scientific_name": science, "display_name": korean, "text": f"{korean} {science}"}
            for science, (taxon_id, korean) in SPECIES.items()]


class FakeEmbeddings:
    """Deterministic vectors: each candidate name text maps to a fixed vector."""

    def __init__(self, documents, queries, dimensions=3):
        self.documents = documents
        self.queries = queries
        self.profile = SimpleNamespace(model="test-embed", dimensions=dimensions, normalized=False)
        self.document_calls = []
        self.query_calls = []

    def embed_documents(self, texts):
        self.document_calls.append(list(texts))
        return tuple(self.documents[text] for text in texts)

    def embed_query(self, text):
        self.query_calls.append(text)
        return self.queries[text]


def vectors(**by_korean):
    return {f"{korean} {science}": by_korean.get(korean, (0.0, 0.0, 1.0)) for science, (_, korean) in SPECIES.items()}


class ResolverCase(TestCase):
    def setUp(self):
        self.graph = FakeGraph()
        self.context = Mock(return_value=CONTEXT)
        self.load = Mock(side_effect=inventory)

    def resolver(self, embeddings=None):
        return TaxonNameResolver(self.graph, self.load, embeddings, active_context=self.context)


class GraphFirstTests(ResolverCase):
    def test_exact_graph_hit_returns_scientific_name_without_embedding(self):
        embeddings = FakeEmbeddings({}, {})
        result = self.resolver(embeddings).resolve("왜가리")
        self.assertEqual(result, {"mention": "왜가리", "status": "matched", "method": "graph_exact",
                                  "canonical_name": "Ardea cinerea", "taxon_id": "avilist-taxon:v2025b:100",
                                  "concept_set_id": CONTEXT[0], "taxonomy_release": CONTEXT[1],
                                  "candidates": []})
        self.assertEqual((embeddings.document_calls, embeddings.query_calls), ([], []))
        self.load.assert_not_called()

    def test_scientific_name_is_matched_and_not_compacted(self):
        result = self.resolver().resolve("  Ardea   cinerea ")
        self.assertEqual((result["status"], result["method"], result["canonical_name"]),
                         ("matched", "graph_exact", "Ardea cinerea"))
        self.assertEqual(self.graph.calls, ["Ardea cinerea"])

    def test_korean_spacing_is_removed_only_for_name_shaped_input(self):
        result = self.resolver(FakeEmbeddings({}, {})).resolve("중대 백로")
        self.assertEqual((result["status"], result["method"], result["taxon_id"]),
                         ("matched", "graph_normalized", "avilist-taxon:v2025b:101"))
        self.assertEqual(self.graph.calls, ["중대 백로", "중대백로"])
        self.assertEqual(compact_korean_name("Ardea cinerea"), None)
        self.assertEqual(compact_korean_name("왜가리와 중대백로 비교해줘 그리고 쇠백로도"), None)
        self.assertEqual(compact_korean_name("왜가리 정보 알려줘?"), None)

    def test_nfc_normalization(self):
        decomposed = unicodedata.normalize("NFD", "왜가리")
        self.assertNotEqual(decomposed, "왜가리")
        self.assertEqual(normalize_mention(decomposed), "왜가리")
        result = self.resolver().resolve(decomposed)
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["mention"], decomposed)  # returned unmodified

    def test_mention_is_returned_unmodified(self):
        for mention in ("  중대 백로 ", "없는새", "가" * (module.MAX_MENTION_CHARS + 1)):
            self.assertEqual(self.resolver().resolve(mention)["mention"], mention)

    def test_bounded_and_invalid_input_never_queries(self):
        for mention in ("", "   ", None, 12, "가" * (module.MAX_MENTION_CHARS + 1)):
            result = self.resolver().resolve(mention)
            self.assertEqual((result["status"], result["method"], result["taxon_id"], result["concept_set_id"]),
                             ("not_found", "none", None, None))
        self.assertEqual(self.graph.calls, [])

    def test_graph_miss_without_embedding_client_is_unavailable(self):
        result = self.resolver().resolve("없는새")
        self.assertEqual((result["status"], result["method"], result["taxon_id"], result["candidates"]),
                         ("unavailable", "none", None, []))
        self.load.assert_not_called()


class AvailabilityTests(ResolverCase):
    def test_missing_or_invalid_active_context_is_unavailable(self):
        for value in (None, ("only",), ("", "v2025b"), RuntimeError("secret neo4j://host")):
            self.context.side_effect = value if isinstance(value, Exception) else None
            self.context.return_value = None if isinstance(value, Exception) else value
            result = self.resolver().resolve("왜가리")
            self.assertEqual((result["status"], result["taxon_id"], result["canonical_name"]), ("unavailable", None, None))
            self.assertNotIn("secret", repr(result))

    def test_graph_outage_is_unavailable_without_details(self):
        self.graph.overrides["왜가리"] = RuntimeError("bolt://user:password@host")
        result = self.resolver().resolve("왜가리")
        self.assertEqual((result["status"], result["method"], result["taxon_id"], result["taxonomy_release"]),
                         ("unavailable", "none", None, None))
        self.assertNotIn("password", repr(result))

    def test_exact_hit_from_another_release_is_not_a_match(self):
        self.graph.overrides["왜가리"] = lineage("Ardea cinerea", "avilist-taxon:v2025b:100", context=("cs", "v2024"))
        self.assertEqual(self.resolver().resolve("왜가리")["status"], "unavailable")


class VectorSuggestionTests(ResolverCase):
    def embeddings(self, query=(1.0, 0.0, 0.0), **by_korean):
        return FakeEmbeddings(vectors(**by_korean), {"왜가리아": query})

    def test_cosine_ranking_returns_verified_candidates_not_a_match(self):
        embeddings = self.embeddings(왜가리=(0.9, 0.1, 0.0), 중대백로=(0.7, 0.3, 0.0), 쇠백로=(0.6, 0.6, 0.0),
                                     황새=(0.95, 0.0, 0.2))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual((result["status"], result["method"], result["canonical_name"], result["taxon_id"]),
                         ("candidates", "vector", None, None))
        self.assertEqual((result["concept_set_id"], result["taxonomy_release"]), CONTEXT)
        # cosine to (1,0,0): 왜가리 .994, 황새 .979, 중대백로 .919, 쇠백로 .707 (below floor)
        self.assertEqual([c["display_name"] for c in result["candidates"]], ["왜가리", "황새", "중대백로"])
        self.assertEqual(set(result["candidates"][0]), {"taxon_id", "scientific_name", "display_name", "score"})
        self.assertGreaterEqual(min(c["score"] for c in result["candidates"]), module.SUGGESTION_COSINE_FLOOR)
        self.assertEqual(embeddings.query_calls, ["왜가리아"])
        self.assertEqual(len(embeddings.document_calls), 1)
        # every suggested scientific name was re-resolved through the graph
        for candidate in result["candidates"]:
            self.assertIn(candidate["scientific_name"], self.graph.calls)

    def test_below_floor_is_not_found(self):
        embeddings = self.embeddings(query=(0.0, 1.0, 0.0), 왜가리=(1.0, 0.2, 0.0))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual((result["status"], result["method"], result["candidates"]), ("not_found", "none", []))

    def test_floor_is_suggestion_only_at_calibrated_level(self):
        self.assertEqual(module.SUGGESTION_COSINE_FLOOR, 0.25)
        embeddings = self.embeddings(왜가리=(0.3, math.sqrt(1 - 0.09), 0.0), 황새=(0.249, math.sqrt(1 - 0.249 ** 2), 0.0))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual((result["status"], result["method"], result["canonical_name"], result["taxon_id"]),
                         ("candidates", "vector", None, None))
        self.assertEqual([(c["display_name"], c["score"]) for c in result["candidates"]], [("왜가리", 0.3)])

    def test_below_calibrated_floor_has_no_candidate(self):
        embeddings = self.embeddings(왜가리=(0.249, math.sqrt(1 - 0.249 ** 2), 0.0), 황새=(0.2, math.sqrt(0.96), 0.0))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual((result["status"], result["method"], result["candidates"], result["taxon_id"]),
                         ("not_found", "none", [], None))

    def test_sentences_and_long_mentions_are_never_embedded(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        resolver = self.resolver(embeddings)
        for mention in ("왜가리아에 대해 알려줘?", "왜가리아 정보 좀 자세히 알려주세요", "가" * (module.MAX_VECTOR_MENTION_CHARS + 1),
                        "what is the bird called heron"):
            result = resolver.resolve(mention)
            self.assertEqual((result["status"], result["method"], result["candidates"]), ("not_found", "none", []), mention)
        self.assertEqual((embeddings.document_calls, embeddings.query_calls), ([], []))
        self.load.assert_not_called()

    def test_ties_sort_by_taxon_id(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0), 중대백로=(2.0, 0.0, 0.0), 쇠백로=(3.0, 0.0, 0.0),
                                     황새=(4.0, 0.0, 0.0))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual([c["taxon_id"] for c in result["candidates"]],
                         ["avilist-taxon:v2025b:100", "avilist-taxon:v2025b:101", "avilist-taxon:v2025b:102"])

    def test_revoked_rank_changed_or_mismatched_candidates_are_excluded(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0), 중대백로=(0.99, 0.01, 0.0), 쇠백로=(0.98, 0.02, 0.0),
                                     황새=(0.97, 0.03, 0.0), 까치=(0.96, 0.04, 0.0))
        self.graph.overrides["Ardea cinerea"] = None  # revoked
        self.graph.overrides["Ardea alba"] = lineage("Ardea alba", "avilist-taxon:v2025b:101", rank="subspecies")
        self.graph.overrides["Egretta garzetta"] = lineage("Egretta garzetta", "avilist-taxon:v2025b:999")
        self.graph.overrides["Ciconia boyciana"] = lineage("Ciconia boyciana", "avilist-taxon:v2025b:103",
                                                           context=("cs", "v2024"))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual([c["display_name"] for c in result["candidates"]], ["까치"])
        for excluded in ("100", "101", "102", "103", "999"):
            self.assertNotIn(f"avilist-taxon:v2025b:{excluded}", repr(result))

    def test_active_context_change_during_suggestion_is_unavailable(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        self.context.side_effect = [CONTEXT, ("rg:concept-set:avilist-v2026a", "v2026a")]
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual((result["status"], result["candidates"]), ("unavailable", []))

    def test_malformed_vectors_are_unavailable(self):
        bad_vectors = ((float("nan"), 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0), ("1", 0.0, 0.0), (True, 0.0, 0.0),
                       "abc", (float("inf"), 0.0, 0.0), (1.7e308, 1.7e308, 1.7e308), (1.0, 0.0, 0.0, 0.0))
        for bad in bad_vectors:
            for target in ("query", "document"):
                self.graph.calls.clear()
                embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
                if target == "query":
                    embeddings.queries["왜가리아"] = bad
                else:
                    embeddings.documents["황새 Ciconia boyciana"] = bad
                result = self.resolver(embeddings).resolve("왜가리아")
                self.assertEqual((result["status"], result["candidates"], result["taxon_id"]),
                                 ("unavailable", [], None), (bad, target))

    def test_huge_finite_coordinates_do_not_overflow_cosine(self):
        embeddings = self.embeddings(query=(1e300, 0.0, 0.0), 왜가리=(1e308, 1e307, 0.0), 황새=(1e-300, 0.0, 0.0))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual(result["status"], "candidates")
        self.assertEqual([c["display_name"] for c in result["candidates"]], ["황새", "왜가리"])
        for candidate in result["candidates"]:
            self.assertTrue(math.isfinite(candidate["score"]) and -1.0 <= candidate["score"] <= 1.0)

    def test_missing_or_invalid_profile_fails_closed_before_embedding(self):
        profiles = (None, SimpleNamespace(model="m", normalized=True),
                    SimpleNamespace(model="m", dimensions=None, normalized=True),
                    SimpleNamespace(model="m", dimensions=True, normalized=True),
                    SimpleNamespace(model="m", dimensions=0, normalized=True),
                    SimpleNamespace(model="m", dimensions="3", normalized=True),
                    SimpleNamespace(model="", dimensions=3, normalized=True),
                    SimpleNamespace(model=None, dimensions=3, normalized=True),
                    SimpleNamespace(model="m", dimensions=3, normalized=None),
                    SimpleNamespace(model="m", dimensions=3, normalized="yes"))
        for profile in profiles:
            embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
            embeddings.profile = profile
            result = self.resolver(embeddings).resolve("왜가리아")
            self.assertEqual((result["status"], result["candidates"]), ("unavailable", []), profile)
            self.assertEqual((embeddings.document_calls, embeddings.query_calls), ([], []))

    def test_real_client_profile_shape_is_accepted(self):
        from robingraph.embeddings import EmbeddingProfile
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        embeddings.profile = EmbeddingProfile("jinaai/jina-embeddings-v3", 3, True)
        self.assertEqual(self.resolver(embeddings).resolve("왜가리아")["status"], "candidates")

    def test_wrong_document_count_and_embedding_outage_are_unavailable(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        embeddings.embed_documents = Mock(return_value=((1.0, 0.0, 0.0),))
        self.assertEqual(self.resolver(embeddings).resolve("왜가리아")["status"], "unavailable")
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        embeddings.embed_query = Mock(side_effect=RuntimeError("https://embed.internal token=abc"))
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("token", repr(result))

    def test_duplicate_or_invalid_inventory_is_unavailable(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        duplicate_id = inventory() + [{**inventory()[0], "scientific_name": "Other name"}]
        duplicate_name = inventory() + [{**inventory()[0], "taxon_id": "avilist-taxon:v2025b:555"}]
        missing_field = [{k: v for k, v in inventory()[0].items() if k != "text"}]
        oversized = inventory() * 0 + [{**inventory()[0], "taxon_id": f"id:{i}", "scientific_name": f"Name {i}"}
                                       for i in range(module.MAX_INVENTORY + 1)]
        for bad in (duplicate_id, duplicate_name, missing_field, oversized, "not a list", None, []):
            self.load.side_effect = None
            self.load.return_value = bad
            self.assertEqual(self.resolver(embeddings).resolve("왜가리아")["status"], "unavailable")

    def test_at_most_three_candidates(self):
        embeddings = self.embeddings(**{korean: (1.0, 0.01 * i, 0.0) for i, (_, korean) in enumerate(SPECIES.values())})
        result = self.resolver(embeddings).resolve("왜가리아")
        self.assertEqual(len(result["candidates"]), module.MAX_SUGGESTIONS)

    def test_name_vectors_are_cached_per_context_and_bounded(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        resolver = self.resolver(embeddings)
        resolver.resolve("왜가리아")
        resolver.resolve("왜가리아")
        self.assertEqual(len(embeddings.document_calls), 1)
        self.assertEqual(len(embeddings.query_calls), 2)
        self.context.return_value = ("rg:concept-set:avilist-v2026a", "v2026a")
        resolver.resolve("왜가리아")
        self.assertEqual(len(embeddings.document_calls), 2)
        self.assertLessEqual(len(resolver._cache), module.CACHE_MAX_ENTRIES)

    def test_cache_eviction_respects_bound(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        resolver = self.resolver(embeddings)
        original = module.CACHE_MAX_ENTRIES
        module.CACHE_MAX_ENTRIES = 3
        try:
            resolver.resolve("왜가리아")
            self.assertEqual(len(resolver._cache), 3)
        finally:
            module.CACHE_MAX_ENTRIES = original

    def test_concurrent_cold_cache_embeds_inventory_once(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        original = embeddings.embed_documents
        started, release = threading.Event(), threading.Event()

        def slow_embed(texts):
            started.set()
            self.assertTrue(release.wait(5))
            return original(texts)

        embeddings.embed_documents = slow_embed
        resolver = self.resolver(embeddings)
        results = []
        threads = [threading.Thread(target=lambda: results.append(resolver.resolve("왜가리아"))) for _ in range(8)]
        for thread in threads:
            thread.start()
        self.assertTrue(started.wait(5))
        # every other thread is now blocked on the in-flight fill, not embedding
        release.set()
        for thread in threads:
            thread.join(5)
        self.assertEqual(len(results), 8)
        self.assertEqual({r["status"] for r in results}, {"candidates"})
        self.assertEqual(len(embeddings.document_calls), 1)
        self.assertEqual(len(embeddings.query_calls), 8)

    def test_failed_fill_is_not_cached_and_next_call_retries(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        original = embeddings.embed_documents
        embeddings.embed_documents = Mock(side_effect=[RuntimeError("down"), original(list(embeddings.documents))])
        resolver = self.resolver(embeddings)
        self.assertEqual(resolver.resolve("왜가리아")["status"], "unavailable")
        self.assertEqual(len(resolver._cache), 0)
        self.assertEqual(resolver.resolve("왜가리아")["status"], "candidates")

    def test_concurrent_resolution_is_consistent(self):
        embeddings = self.embeddings(왜가리=(1.0, 0.0, 0.0))
        resolver = self.resolver(embeddings)
        results = []
        threads = [threading.Thread(target=lambda: results.append(resolver.resolve("왜가리아"))) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual({r["status"] for r in results}, {"candidates"})
        self.assertEqual(len(resolver._cache), len(SPECIES))
