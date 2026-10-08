"""Selection-policy regressions; scoring and real checked-name identity stay intact."""
from dataclasses import asdict
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from tests.test_similar_species import FakeRepository, HABITAT, LINEAGE, TARGET, candidate, ecology
from robingraph.api.app import create_app
from robingraph.retrieval.similar_species import NAMES_QUERY, similar_species
from robingraph.retrieval.taxonomy_lineage import sourced_korean_names


KNOWN_IDS = [f"avilist-taxon:v2025b:{number}" for number in (306, 310, 320, 321)]


def checked_candidate(index, *, genus=False, family=True):
    taxon_id = KNOWN_IDS[index]
    return candidate(taxon_id, sourced_korean_names()[taxon_id]["scientific_name"], family, genus)


class NameRepository(FakeRepository):
    def __init__(self, candidates, evidence=(), overrides=None, corrupt=None):
        super().__init__(candidates, list(evidence))
        self.overrides = overrides or {}
        self.corrupt = corrupt

    def _run(self, query, **params):
        if query != NAMES_QUERY:
            return super()._run(query, **params)
        self.calls.append((query, params))
        names = sourced_korean_names()
        rows = [{"taxon_id": taxon_id,
                 "english_name": names[taxon_id]["english_name"] if taxon_id in names else "English " + taxon_id,
                 # Raw graph Korean labels must never establish priority.
                 "korean_name": "검증하지 않은 그래프 번역",
                 "korean_name_status": "machine-translated",
                 **self.overrides.get(taxon_id, {})}
                for taxon_id in params["taxon_ids"]]
        return self.corrupt(rows) if self.corrupt else rows


class SimilarSpeciesKoreanPriorityTest(TestCase):
    def setUp(self):
        self.enterContext(patch("robingraph.retrieval.similar_species.read_traits", return_value=[HABITAT]))
        self.enterContext(patch("robingraph.retrieval.similar_species.phylogenetic_relations", return_value={}))

    def evaluate(self, candidates, evidence=(), **kwargs):
        repo = NameRepository(candidates, evidence, **kwargs)
        result = similar_species(repo, Mock(), lambda _: LINEAGE, TARGET.scientific_name)
        return result, repo

    def items(self, result):
        return result["groups"][0]["items"]

    def test_four_verified_names_take_three_by_score_and_keep_score_evidence(self):
        known = [checked_candidate(i, genus=i < 2) for i in range(4)]
        english = candidate("english-winner", "AAA English", True, True)
        result, _ = self.evaluate(known + [english], [ecology(known[0]["taxon_id"]), ecology(known[2]["taxon_id"]), ecology("english-winner")])
        items = self.items(result)
        self.assertEqual(KNOWN_IDS[:3], [p["taxon_id"] for p in items])
        self.assertEqual([80, 60, 40], [p["similarity_score"] for p in items])
        self.assertEqual([1, 2, 3], [p["similarity_rank"] for p in items])
        self.assertTrue(all(p["korean_name"] and p["korean_name_status"] == "source-reference" for p in items))
        self.assertTrue(all(p["similarity_reasons"] and p["korean_name_source_url"].startswith("https://") for p in items))
        self.assertEqual("korean_name_then_weighted_score", result["ranking"]["priority"])
        self.assertEqual(5, result["ranking"]["scanned_count"])
        self.assertTrue(result["groups"][0]["has_more"])

    def test_one_or_two_verified_names_fill_remaining_places_with_best_english(self):
        english = [candidate("e1", "AAA first", True, True), candidate("e2", "AAA second", True), candidate("e3", "AAA third", True)]
        for count in (1, 2):
            with self.subTest(verified_count=count):
                result, _ = self.evaluate(english + [checked_candidate(i) for i in range(count)], [ecology("e1"), ecology("e2")])
                items = self.items(result)
                self.assertEqual(KNOWN_IDS[:count] + ["e1", "e2"][:3-count], [p["taxon_id"] for p in items])
                self.assertTrue(all(p["korean_name"] for p in items[:count]))
                self.assertTrue(all(p["korean_name"] is None and p["english_name"] for p in items[count:]))
                self.assertEqual(3, len({p["taxon_id"] for p in items}))

    def test_no_verified_names_preserves_score_top_three_and_raw_labels_get_no_priority(self):
        result, _ = self.evaluate([candidate("e4", "Fourth bird", True), candidate("e2", "Second bird", True, True),
                                  candidate("e3", "Third bird", True), candidate("e1", "First bird", True, True)],
                                 [ecology("e1"), ecology("e3")])
        items = self.items(result)
        self.assertEqual(["e1", "e2", "e3"], [p["taxon_id"] for p in items])
        self.assertEqual([80, 60, 40], [p["similarity_score"] for p in items])
        self.assertTrue(all(p["korean_name"] is None for p in items))

    def test_verified_candidate_outside_original_top_three_is_selected(self):
        english = [candidate(f"e{i}", f"AAA bird{i}", True, True) for i in range(4)]
        result, repo = self.evaluate(english + [checked_candidate(0)])
        self.assertEqual([KNOWN_IDS[0], "e0", "e1"], [p["taxon_id"] for p in self.items(result)])
        self.assertEqual([20, 60, 60], [p["similarity_score"] for p in self.items(result)], "Display rank intentionally prioritizes checked Korean names")
        name_ids = next(params["taxon_ids"] for query, params in repo.calls if query == NAMES_QUERY)
        self.assertIn(KNOWN_IDS[0], name_ids)

    def test_checked_id_requires_matching_scientific_and_english_names(self):
        english = [candidate(f"e{i}", f"AAA bird{i}", True, True) for i in range(3)]
        for mismatch in ("scientific", "english"):
            with self.subTest(mismatch=mismatch):
                known = checked_candidate(0)
                overrides = {}
                if mismatch == "scientific":
                    known["scientific_name"] = "Different species"
                else:
                    overrides[KNOWN_IDS[0]] = {"english_name": "Different English name"}
                result, _ = self.evaluate(english + [known], overrides=overrides)
                self.assertEqual(["e0", "e1", "e2"], [p["taxon_id"] for p in self.items(result)])
                fallback, _ = self.evaluate([known], overrides=overrides)
                self.assertEqual(1, len(self.items(fallback)))
                self.assertIsNone(self.items(fallback)[0]["korean_name"])
                self.assertIsNone(self.items(fallback)[0]["korean_name_status"])
                self.assertTrue(self.items(fallback)[0]["english_name"])

    def test_zero_score_verified_name_is_not_eligible_or_name_queried(self):
        zero = checked_candidate(0, family=False)
        result, repo = self.evaluate([zero, candidate("eligible", "Eligible bird", True)])
        self.assertEqual(["eligible"], [p["taxon_id"] for p in self.items(result)])
        self.assertEqual(1, result["ranking"]["eligible_count"])
        name_ids = next(params["taxon_ids"] for query, params in repo.calls if query == NAMES_QUERY)
        self.assertNotIn(KNOWN_IDS[0], name_ids)

    def test_equal_score_order_is_stable_inside_each_name_priority_group(self):
        known = [checked_candidate(i) for i in range(2)]
        english = [candidate("z", "AAA same", True), candidate("a", "AAA same", True)]
        first, _ = self.evaluate(known + english)
        second, _ = self.evaluate(list(reversed(known + english)))
        expected = KNOWN_IDS[:2] + ["a"]
        self.assertEqual(expected, [p["taxon_id"] for p in self.items(first)])
        self.assertEqual(expected, [p["taxon_id"] for p in self.items(second)])

    def test_name_lookup_is_bounded_to_eligible_reference_intersection_and_score_top_three(self):
        english = [candidate(f"e{i:03d}", f"AAA bird{i:03d}", True, True) for i in range(100)]
        known = [checked_candidate(i) for i in range(4)]
        result, repo = self.evaluate(english + known)
        calls = [params for query, params in repo.calls if query == NAMES_QUERY]
        self.assertEqual(1, len(calls))
        self.assertEqual(set(KNOWN_IDS) | {"e000", "e001", "e002"}, set(calls[0]["taxon_ids"]))
        self.assertEqual(7, len(calls[0]["taxon_ids"]))
        self.assertEqual(104, result["ranking"]["scanned_count"])
        self.assertEqual(104, result["ranking"]["eligible_count"])

    def test_duplicate_or_unrequested_name_projection_fails_closed(self):
        for corrupt in (lambda rows: rows + [dict(rows[0])],
                        lambda rows: rows + [{"taxon_id": "not-requested", "english_name": "Foreign bird"}]):
            with self.subTest(corrupt=corrupt):
                with self.assertRaisesRegex(ValueError, "name projection"):
                    self.evaluate([checked_candidate(0), candidate("english", "AAA bird", True)], corrupt=corrupt)

    def test_chat_calls_name_priority_positions_recommendations_instead_of_score_ranks(self):
        relations, _ = self.evaluate([checked_candidate(0)] + [
            candidate(f"e{i}", f"AAA bird{i}", True, True) for i in range(3)])
        profile = {"taxon": asdict(TARGET), "lineage": asdict(LINEAGE), "traits": [], "warnings": []}
        handler = Mock(return_value=relations)
        client = TestClient(create_app(species_profile_handler=lambda _: profile, similar_species_handler=handler))
        response = client.post("/v1/chat", json={"question": "청둥오리와 비슷한 새 알려줘"})
        self.assertEqual(200, response.status_code)
        answer = response.json()
        self.assertEqual("answer", answer["disposition"])
        handler.assert_called_once_with("청둥오리")
        self.assertIn("추천 1 흑기러기: 20점", answer["answer_text"])
        self.assertNotIn("1위", answer["answer_text"])
        self.assertEqual([20, 60, 60], [item["peer"]["similarity_score"]
                                     for item in answer["result"]["question_answer"]["items"]])
        self.assertEqual("korean_name_then_weighted_score", answer["result"]["question_answer"]["relations"]["ranking"]["priority"])
