import json
import math
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

from robingraph.retrieval.graph_questions import GRAPH_QUESTION_KINDS
from robingraph.retrieval.graph_semantic_router import (
    CONFIDENCE, MARGIN, PROTOTYPE_VERSION, PROTOTYPES, GraphSemanticRouter, KindCandidates, rank_kinds)

ROOT = Path(__file__).resolve().parents[1]
KIND_AXIS = {kind: index for index, kind in enumerate(GRAPH_QUESTION_KINDS)}


class FakeClient:
    """Deterministic 8-dim vectors: each prototype points at its kind's axis; queries are scripted."""

    def __init__(self, queries=None, model='jinaai/jina-embeddings-v3', dimensions=8, normalized=True):
        self.profile = SimpleNamespace(model=model, dimensions=dimensions, normalized=normalized)
        self.queries = dict(queries or {})
        self.prototype_kind = {text: kind for kind, text in PROTOTYPES}
        self.calls = []
        self.fail_on = None

    def embed_documents(self, texts):
        raise AssertionError('prototypes use the query task')

    def embed_query(self, text):
        self.calls.append(text)
        if self.fail_on is not None and len(self.calls) == self.fail_on:
            raise TimeoutError('graph client timeout')
        if text in self.queries:
            return self.queries[text]
        vector = [0.0] * 8
        vector[KIND_AXIS[self.prototype_kind[text]]] = 1.0
        return vector


class BatchClient(FakeClient):
    """Adds the batch query method; one call stands for ceil(n / batch_size) HTTP batches."""

    def __init__(self, *args, batch_size=32, short=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = SimpleNamespace(batch_size=batch_size)
        self.batch_calls = 0
        self.short = short

    def embed_queries(self, texts):
        self.batch_calls += 1
        if self.fail_on == 'batch':
            raise TimeoutError('graph client timeout')
        vectors = tuple(FakeClient.embed_query(self, text) for text in texts)
        return vectors[:-1] if self.short else vectors


def toward(kind, other=None, weight=0.0):
    vector = [0.0] * 8
    vector[KIND_AXIS[kind]] = 1.0
    if other:
        vector[KIND_AXIS[other]] = weight
    return vector


class PrototypeTests(TestCase):
    def test_prototypes_are_answerable_tuning_questions_only(self):
        tuning = {}
        for line in (ROOT / 'data/eval/graph_questions/tuning.jsonl').read_text(encoding='utf-8').splitlines():
            row = json.loads(line)
            tuning[row['question']] = row['expected']
        for kind, text in PROTOTYPES:
            with self.subTest(text=text):
                self.assertEqual(kind, tuning[text]['kind'])
                self.assertIn(tuning[text]['disposition'], ('answer', 'insufficient_data'))
        # taxon_traits has no prototypes yet: it is order_fruit's sibling (KIND_FAMILIES), never a kind_tie with it.
        self.assertEqual(set(GRAPH_QUESTION_KINDS) - {'taxon_traits', 'shared_diet'}, {kind for kind, _ in PROTOTYPES})
        self.assertEqual(len(PROTOTYPES), len({text for _, text in PROTOTYPES}))

    def test_rank_kinds_uses_the_nearest_prototype_per_kind(self):
        prototypes = (('same_genus', (1.0, 0.0)), ('same_genus', (0.0, 1.0)), ('order_fruit', (0.6, 0.8)))
        self.assertEqual([('same_genus', 1.0), ('order_fruit', 0.8)], rank_kinds((0.0, 1.0), prototypes))


class ClassifyTests(TestCase):
    def test_retrieval_returns_ranked_examples_even_when_kind_margin_is_small(self):
        client = BatchClient({'q': toward('same_genus', 'common_taxonomy', 1.0)})
        router = GraphSemanticRouter(client)
        self.assertEqual('below_threshold', router.classify('q').status)
        examples = router.retrieve('q', limit=4)
        self.assertEqual(4, len(examples))
        self.assertTrue(all(e['kind'] in ('same_genus', 'common_taxonomy') for e in examples))
        self.assertTrue(all((e['kind'], e['question']) in PROTOTYPES for e in examples))
        self.assertTrue(all(e['score'] > 0 for e in examples))
        self.assertEqual(1, client.batch_calls)
        client.fail_on = len(client.calls) + 1
        self.assertEqual([], router.retrieve('q'))

    def test_confident_candidate_and_warm_cache_counts(self):
        client = FakeClient({'q': toward('same_genus')})
        router = GraphSemanticRouter(client)
        cold = router.classify('q')
        self.assertEqual(('ok', 'same_genus', 1.0), (cold.status, cold.top, cold.candidates[0][1]))
        self.assertEqual((1, 1, len(PROTOTYPES), len(PROTOTYPES)),
                         (cold.embedding_calls, cold.prototype_calls, cold.prototype_requests, cold.prototype_batches))
        self.assertEqual((PROTOTYPE_VERSION, 'jinaai/jina-embeddings-v3'), (cold.prototype_version, cold.model))
        warm = router.classify('q')
        self.assertEqual((1, 0, 0), (warm.embedding_calls, warm.prototype_calls, warm.prototype_requests))
        self.assertEqual(len(PROTOTYPES) + 2, len(client.calls))
        self.assertLessEqual(len(cold.candidates), 3)

    def test_batch_client_loads_prototypes_in_one_method_call(self):
        client = BatchClient({'q': toward('same_genus')})
        router = GraphSemanticRouter(client)
        cold = router.classify('q')
        self.assertEqual(('ok', 'same_genus'), (cold.status, cold.top))
        self.assertEqual((1, 1, 1, 2), (cold.embedding_calls, cold.prototype_calls, cold.prototype_requests,
                                        cold.prototype_batches))
        self.assertEqual(1, client.batch_calls)
        warm = router.classify('q')
        self.assertEqual((1, 0, 0, None), (warm.embedding_calls, warm.prototype_calls, warm.prototype_requests,
                                           warm.prototype_batches))

    def test_batch_failure_or_short_batch_is_counted_and_not_cached(self):
        for client in (BatchClient({'q': toward('same_genus')}), BatchClient({'q': toward('same_genus')}, short=True)):
            if not client.short:
                client.fail_on = 'batch'
            with self.subTest(short=client.short):
                router = GraphSemanticRouter(client)
                failed = router.classify('q')
                self.assertEqual(('unavailable', 0, 1, 1), (failed.status, failed.embedding_calls,
                                                            failed.prototype_calls, failed.prototype_requests))
                client.fail_on, client.short = None, False
                recovered = router.classify('q')
                self.assertEqual(('ok', 1, 2), (recovered.status, recovered.prototype_calls, client.batch_calls))

    def test_low_score_or_small_margin_is_below_threshold_without_a_top(self):
        cases = {'weak': toward('same_genus', 'order_fruit', 1.0 / math.tan(math.acos(CONFIDENCE) + 0.05)),
                 'close': toward('same_genus', 'korea_same_genus', 0.95)}
        router = GraphSemanticRouter(FakeClient(cases))
        for question in cases:
            with self.subTest(question=question):
                result = router.classify(question)
                self.assertEqual('below_threshold', result.status)
                self.assertIsNone(result.top)
                self.assertTrue(result.candidates)
        self.assertLess(router.classify('close').margin, MARGIN)

    def test_cache_key_follows_version_model_dimensions_and_normalized(self):
        client = FakeClient({'q': toward('order_fruit')})
        router = GraphSemanticRouter(client)
        router.classify('q')
        client.profile = SimpleNamespace(model=client.profile.model, dimensions=8, normalized=False)
        self.assertEqual(1, router.classify('q').prototype_calls)
        client.profile = SimpleNamespace(model='other-model', dimensions=8, normalized=False)
        self.assertEqual(1, router.classify('q').prototype_calls)
        self.assertEqual(0, router.classify('q').prototype_calls)

    def test_failed_prototype_load_is_counted_and_never_cached(self):
        client = FakeClient({'q': toward('order_fruit')})
        client.fail_on = 3
        router = GraphSemanticRouter(client)
        failed = router.classify('q')
        self.assertEqual(('unavailable', (), None), (failed.status, failed.candidates, failed.top))
        self.assertEqual((0, 1, 3), (failed.embedding_calls, failed.prototype_calls, failed.prototype_requests))
        client.fail_on = None
        recovered = router.classify('q')
        self.assertEqual(('ok', 1, len(PROTOTYPES)), (recovered.status, recovered.prototype_calls,
                                                     recovered.prototype_requests))

    def test_query_failure_counts_the_attempt(self):
        client = FakeClient({'q': toward('order_fruit')})
        router = GraphSemanticRouter(client)
        self.assertTrue(router.warm())
        client.fail_on = len(client.calls) + 1
        failed = router.classify('q')
        self.assertEqual(('unavailable', 1, 0), (failed.status, failed.embedding_calls, failed.prototype_calls))

    def test_abnormal_vectors_and_profiles_fail_closed(self):
        bad_vectors = ([float('nan')] + [0.0] * 7, [float('inf')] + [0.0] * 7, [0.0] * 8, [1.0] * 7, [True] + [0.0] * 7,
                       ['1'] + [0.0] * 7, 'abcdefgh', None)
        for vector in bad_vectors:
            with self.subTest(vector=vector):
                result = GraphSemanticRouter(FakeClient({'q': vector})).classify('q')
                self.assertEqual(('unavailable', ()), (result.status, result.candidates))
        for profile in (SimpleNamespace(model='', dimensions=8, normalized=True),
                        SimpleNamespace(model='m', dimensions=True, normalized=True),
                        SimpleNamespace(model='m', dimensions=0, normalized=True),
                        SimpleNamespace(model='m', dimensions=8, normalized='yes'),
                        SimpleNamespace(model='m', dimensions=8)):
            with self.subTest(profile=profile):
                client = FakeClient({'q': toward('order_fruit')})
                client.profile = profile
                result = GraphSemanticRouter(client).classify('q')
                self.assertEqual(('unavailable', 0, 0), (result.status, result.embedding_calls, result.prototype_calls))

    def test_never_raises_on_broken_clients_or_inputs(self):
        class Exploding:
            @property
            def profile(self):
                raise RuntimeError('profile unavailable')
        self.assertEqual('unavailable', GraphSemanticRouter(Exploding()).classify('q').status)
        self.assertFalse(GraphSemanticRouter(Exploding()).warm())
        router = GraphSemanticRouter(FakeClient())
        for question in (None, '', '   ', 3):
            with self.subTest(question=question):
                self.assertEqual(('unavailable', 0), (router.classify(question).status,
                                                       router.classify(question).embedding_calls))
        self.assertIsNone(KindCandidates(candidates=(('same_genus', 0.9),), status='below_threshold').top)

    def test_constructor_rejects_bad_thresholds_and_prototypes(self):
        for kwargs in ({'confidence': 1.01}, {'confidence': -0.1}, {'confidence': float('nan')},
                       {'confidence': True}, {'margin': 2.5}, {'margin': float('inf')},
                       {'prototypes': ()}, {'prototypes': (('same_genus', 'a'),)},
                       {'prototypes': (('same_genus', 'a'), ('free_cypher', 'b'))},
                       {'prototypes': (('same_genus', 'a'), ('order_fruit', ' '))}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    GraphSemanticRouter(FakeClient(), **kwargs)
        GraphSemanticRouter(FakeClient(), confidence=1.0, margin=2.0)
