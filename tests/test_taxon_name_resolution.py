import unicodedata
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

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



class ResolverCase(TestCase):
    def setUp(self):
        self.graph = FakeGraph()
        self.context = Mock(return_value=CONTEXT)
        self.load = Mock(side_effect=inventory)

    def resolver(self, embeddings=None, search=None):
        return TaxonNameResolver(self.graph, self.load, embeddings, active_context=self.context,
                                 candidate_search=search if search is not None else Mock(return_value=[]))


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


class PersistentVectorSuggestionTests(ResolverCase):
    def client(self, mention="왜가리아", vector=(1.0, 0.0, 0.0)):
        return FakeEmbeddings({}, {mention: vector})

    def hits(self, scores):
        return [{**entry, "score": score} for entry, score in zip(inventory(), scores)]

    def test_searches_persistent_index_with_one_query_vector_and_no_document_embedding(self):
        client = self.client()
        search = Mock(return_value=self.hits([.9, .8, .7, .6]))
        resolver = self.resolver(client, search)
        for _ in range(2):
            result = resolver.resolve("왜가리아")
            self.assertEqual((result["status"], result["method"], result["taxon_id"]), ("candidates", "vector", None))
            self.assertEqual(len(result["candidates"]), 3)
            self.assertEqual(result["candidates"][0]["score"], .9)
        self.assertEqual(client.document_calls, [])
        self.assertEqual(client.query_calls, ["왜가리아", "왜가리아"])
        self.assertEqual(search.call_count, 2)
        self.assertEqual(search.call_args.args, ((1.0, 0.0, 0.0), client.profile, CONTEXT, inventory()))
        self.assertEqual(search.call_args.kwargs, {"limit": 10})
        self.assertFalse(hasattr(resolver, "_cache"))

    def test_missing_index_adapter_is_unavailable_without_bulk_embedding(self):
        client = self.client()
        result = TaxonNameResolver(self.graph, self.load, client, self.context).resolve("왜가리아")
        self.assertEqual(result["status"], "unavailable")
        self.assertEqual((client.query_calls, client.document_calls), ([], []))

    def test_database_outage_is_unavailable_not_memory_fallback(self):
        client = self.client()
        result = self.resolver(client, Mock(side_effect=RuntimeError("password=secret"))).resolve("왜가리아")
        self.assertEqual(result["status"], "unavailable")
        self.assertNotIn("secret", repr(result))
        self.assertEqual(client.document_calls, [])

    def test_floor_and_stable_ties_preserve_suggestion_policy(self):
        result = self.resolver(self.client(), Mock(return_value=list(reversed(self.hits([.3, .3, .249, .2]))))).resolve("왜가리아")
        self.assertEqual([c["display_name"] for c in result["candidates"]], ["왜가리", "중대백로"])
        self.assertEqual(self.resolver(self.client(), Mock(return_value=self.hits([.249]))).resolve("왜가리아")["status"], "not_found")

    def test_every_candidate_is_reverified_by_active_graph(self):
        self.graph.overrides["Ardea cinerea"] = None
        self.graph.overrides["Ardea alba"] = lineage("Ardea alba", "wrong-id")
        self.graph.overrides["Egretta garzetta"] = lineage("Egretta garzetta", "avilist-taxon:v2025b:102", rank="subspecies")
        self.graph.overrides["Ciconia boyciana"] = lineage("Ciconia boyciana", "avilist-taxon:v2025b:103", context=("other", "old"))
        result = self.resolver(self.client(), Mock(return_value=self.hits([.9, .8, .7, .6, .5]))).resolve("왜가리아")
        self.assertEqual([c["display_name"] for c in result["candidates"]], ["까치"])

    def test_foreign_stale_duplicate_and_malformed_hits_fail_closed(self):
        good = self.hits([.9])[0]
        for hits in ([{**good, "text": "changed"}], [{**good, "taxon_id": "foreign"}], [good, good],
                     [None], "invalid", [{**good, "score": float("nan")}], [{**good, "score": True}],
                     [{**good, "score": 1.01}], self.hits([.9]) * 11):
            result = self.resolver(self.client(), Mock(return_value=hits)).resolve("왜가리아")
            self.assertEqual((result["status"], result["candidates"]), ("unavailable", []), hits)

    def test_context_and_embedding_profile_changes_during_search_fail_closed(self):
        self.context.side_effect = [CONTEXT, ("changed", "old")]
        search = Mock(return_value=self.hits([.9]))
        self.assertEqual(self.resolver(self.client(), search).resolve("왜가리아")["status"], "unavailable")
        search.assert_not_called()
        self.context.side_effect = None
        client = self.client()
        def changed(*args, **kwargs):
            client.profile.model = "changed"
            return self.hits([.9])
        self.assertEqual(self.resolver(client, Mock(side_effect=changed)).resolve("왜가리아")["status"], "unavailable")

    def test_bad_query_vectors_are_rejected_before_database_search(self):
        for bad in ((float("nan"), 0, 0), (0, 0, 0), (1, 0), (True, 0, 0), "abc", (float("inf"), 0, 0), (1.7e308,) * 3):
            search = Mock()
            self.assertEqual(self.resolver(self.client(vector=bad), search).resolve("왜가리아")["status"], "unavailable")
            search.assert_not_called()

    def test_invalid_profile_or_inventory_fails_before_query_embedding(self):
        for profile in (None, SimpleNamespace(model="m", dimensions=True, normalized=False), SimpleNamespace(model="", dimensions=3, normalized=False)):
            client = self.client()
            client.profile = profile
            self.assertEqual(self.resolver(client).resolve("왜가리아")["status"], "unavailable")
            self.assertEqual(client.query_calls, [])
        for bad in ([], None, "invalid", inventory() * 2, [{"taxon_id": "a"}], inventory() * 201):
            client = self.client()
            self.load.side_effect = None
            self.load.return_value = bad
            self.assertEqual(self.resolver(client).resolve("왜가리아")["status"], "unavailable")
            self.assertEqual(client.query_calls, [])

    def test_whole_sentences_are_never_embedded_or_searched(self):
        for mention in ("왜가리아에 대해 알려줘?", "왜가리아 정보 좀 자세히 알려주세요", "가" * 41):
            client = self.client()
            search = Mock()
            self.assertEqual(self.resolver(client, search).resolve(mention)["status"], "not_found")
            search.assert_not_called()
            self.assertEqual(client.query_calls, [])

    def test_cheondung_spelling_fallback_still_uses_index_scores_and_compacted_query(self):
        self.load.side_effect = None
        self.load.return_value = [{"taxon_id": "mallard", "scientific_name": "Anas platyrhynchos", "display_name": "청둥오리", "text": "청둥오리"},
                                  {"taxon_id": "scoter", "scientific_name": "Melanitta americana", "display_name": "검둥오리", "text": "검둥오리"}]
        for entry in self.load.return_value:
            self.graph.overrides[entry["scientific_name"]] = lineage(entry["scientific_name"], entry["taxon_id"])
        hits = [{**e, "score": s} for e, s in zip(self.load.return_value, [.2138, .2201])]
        client = self.client("천둥오리")
        search = Mock(return_value=hits)
        resolver = self.resolver(client, search)
        for mention in ("천둥오리", "천둥 오리"):
            result = resolver.resolve(mention)
            self.assertEqual(result["mention"], mention)
            self.assertEqual(result["status"], "candidates")
            self.assertIsNone(result["taxon_id"])
            self.assertEqual([(c["display_name"], c["score"]) for c in result["candidates"]], [("청둥오리", .2138)])
        self.assertEqual(client.query_calls, ["천둥오리", "천둥오리"])
        self.assertEqual(client.document_calls, [])


class ScopedRecallTests(ResolverCase):
    def test_scope_ranking_recovers_candidate_below_global_top_ten(self):
        rows = [{'taxon_id': f'taxon:{i}', 'scientific_name': f'Example species{i}',
                 'display_name': f'검증이름{i}', 'text': f'검증이름{i}'} for i in range(11)]
        self.load = Mock(return_value=rows)
        self.graph.overrides[rows[-1]['scientific_name']] = lineage(rows[-1]['scientific_name'], rows[-1]['taxon_id'])
        def search(*args, limit, eligible_taxon_ids=None):
            ranked = [{**row, 'score': .9-i*.01} for i, row in enumerate(rows)]
            if eligible_taxon_ids is not None:
                ranked = [r for r in ranked if r['taxon_id'] in eligible_taxon_ids]
            return ranked[:limit]
        search = Mock(side_effect=search)
        with patch.object(module, 'scope_matches', side_effect=lambda taxon, *args: taxon['taxon_id'] == rows[-1]['taxon_id']):
            result = self.resolver(FakeEmbeddings({}, {'오타이름': (1.,0.,0.)}), search).resolve('오타이름', 'korea')
        self.assertEqual(result['status'], 'candidates')
        self.assertEqual([r['taxon_id'] for r in result['candidates']], ['taxon:10'])
        self.assertEqual(search.call_args.kwargs, {'limit': 10, 'eligible_taxon_ids': ['taxon:10']})
        self.assertEqual(len(search.call_args.args[3]), 11)  # full catalog remains intact

    def test_empty_scope_never_calls_repository_or_backfills_other_scope(self):
        search = Mock()
        with patch.object(module, 'scope_matches', return_value=False):
            result = self.resolver(FakeEmbeddings({}, {'오타이름': (1.,0.,0.)}), search).resolve('오타이름', 'outside')
        self.assertEqual(result['candidates'], [])
        search.assert_not_called()


    def test_outside_candidate_uses_english_name_from_verified_graph(self):
        from dataclasses import replace
        value = lineage('Ardea cinerea', 'avilist-taxon:v2025b:100')
        self.graph.overrides['Ardea cinerea'] = replace(value, items=(*value.items[:-1],
            replace(value.items[-1], korean_name='왜가리', english_name='Grey Heron')))
        search = Mock(return_value=[{**inventory()[0], 'score': .8}])
        with patch.object(module, 'scope_matches', return_value=True):
            result = self.resolver(FakeEmbeddings({}, {'왜가리아': (1.,0.,0.)}), search).resolve('왜가리아', 'outside')
        self.assertEqual(result['candidates'][0]['display_name'], 'Grey Heron')


class LatinSpellingSupportTests(ResolverCase):
    def test_one_edit_boundaries(self):
        for value,name in [('Keaa','Kea'),('Nestor notabilix','Nestor notabilis'),
                           ('Okarito Kiwx','Okarito Kiwi'),('Kea','Keaa'),('Kxea','Kexa')]:
            if len(value) >= 4:
                self.assertTrue(module._one_latin_edit(value,name),(value,name))
        for value,name in [('Kea','Kea'),('Kex','Kea'),('Kezz','Kea'),('bird','Kea'),('Kea?','Kea')]:
            self.assertFalse(module._one_latin_edit(value,name),(value,name))

    def test_outside_spelling_candidate_preserves_real_cosine_and_requires_graph(self):
        from dataclasses import replace
        row={'taxon_id':'fixture:kea','scientific_name':'Nestor notabilis','display_name':'Kea','text':'Kea Nestor notabilis'}
        self.load=Mock(return_value=[row])
        base=lineage(row['scientific_name'],row['taxon_id'])
        self.graph.overrides[row['scientific_name']]=replace(base,items=(*base.items[:-1],replace(base.items[-1],english_name='Kea')))
        search=Mock(return_value=[{**row,'score':.1}])
        embeddings=FakeEmbeddings({}, {'Keaa':(1.,0.,0.),'Kezz':(1.,0.,0.)})
        resolver=self.resolver(embeddings,search)
        with patch.object(module,'scope_matches',return_value=True):
            result=resolver.resolve('Keaa','outside')
            self.assertEqual(result['status'],'candidates')
            self.assertEqual(result['candidates'][0]['display_name'],'Kea')
            self.assertEqual(result['candidates'][0]['score'],.1)
            embeddings.query_calls.clear()
            all_result=resolver.resolve('Keaa','all')
            self.assertEqual(all_result['status'],'candidates')
            self.assertEqual(all_result['candidates'][0]['display_name'],'Kea')
            self.assertEqual(embeddings.query_calls,['Keaa'])
            self.assertEqual(resolver.resolve('Kezz','outside')['status'],'not_found')
            self.graph.overrides[row['scientific_name']]=None
            self.assertEqual(resolver.resolve('Keaa','outside')['status'],'not_found')
