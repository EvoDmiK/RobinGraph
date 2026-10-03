from dataclasses import replace
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock

from fastapi.testclient import TestClient
from robingraph.api.app import create_app
from robingraph.retrieval.name_relations import NameRelationRepository, manifest_digest, validate_manifest, RELATIONS_QUERY
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


def manifest():
    return {"policy_status": "allowed", "reviewed_at": "2026-10-03", "records": [
        {"id": "chicken", "entity_id": "chicken", "name": "닭", "entity_kind": "domestic_form",
         "relation_type": "domesticated_from", "scientific_name": "Gallus gallus", "search_terms": ["닭"],
         "note": "가축형과 야생종의 정보를 구분합니다.",
         "sources": [{"title": "Reviewed source", "url": "https://example.org/chicken"}]}]}


class NameRelationsTest(unittest.TestCase):
    def setUp(self):
        self.manifest = manifest()
        self.context = NS(dataset=NS(id="dataset"), release=NS(id="release", metadata={"manifest": self.manifest},
                          content_sha256=manifest_digest(self.manifest)), cursor={"concept_set_id": "concept", "taxonomy_release": "v1"})
        self.repo = Mock()
        self.repo._active_concept_set.return_value = ("concept", "v1")
        self.row = {"usage_id": "u", "source_record_id": "release:chicken", "relation_type": "domesticated_from",
                    "scientific_name": "Gallus gallus", "taxon_id": "t"}
        self.repo._run.return_value = [self.row]
        self.lineage = TaxonomyLineage("Gallus gallus", "AviList", "v1", "concept",
                                      (LineageTaxon("t", "species", "Gallus gallus", None, "적색야계"),))
        self.repo.lineage_for_scientific_name.return_value = self.lineage
        self.reader = NameRelationRepository(self.repo, lambda: self.context)

    def test_domestic_lookup_has_explicit_relation_sources_and_no_profile_traits(self):
        result = self.reader.for_name(" 닭 ")
        self.assertTrue(result["is_search_term"])
        self.assertEqual("domestic_form", result["relations"][0]["entity_kind"])
        self.assertIn("야생종", result["summary"])
        self.assertNotIn("traits", result)
        self.assertEqual("https://example.org/chicken", result["relations"][0]["sources"][0]["url"])
        self.assertIn("target:Taxon:BirdTaxon", RELATIONS_QUERY)
        self.assertEqual("dataset", self.repo._run.call_args.kwargs["dataset_id"])

    def test_reverse_lookup_keeps_canonical_species_search(self):
        self.assertFalse(self.reader.for_name("Gallus gallus")["is_search_term"])

    def test_no_active_or_stale_overlay_fails_closed(self):
        self.context = None
        self.assertIsNone(self.reader.for_name("닭"))
        self.repo._run.assert_not_called()
        self.setUp()
        self.context.cursor["concept_set_id"] = "old"
        self.assertIsNone(self.reader.for_name("닭"))
        self.repo._run.assert_not_called()

    def test_revoked_or_tampered_evidence_is_rejected(self):
        self.manifest["policy_status"] = "blocked"
        with self.assertRaises(ValueError): self.reader.for_name("닭")
        self.setUp()
        self.manifest["records"][0]["note"] = "changed"
        with self.assertRaises(ValueError): self.reader.for_name("닭")

    def test_missing_edge_and_changed_target_are_not_silently_accepted(self):
        self.repo._run.return_value = []
        with self.assertRaises(ValueError): self.reader.for_name("닭")
        self.repo._run.return_value = [{**self.row, "scientific_name": "Another taxon"}]
        with self.assertRaises(ValueError): self.reader.for_name("닭")

    def test_ambiguous_common_name_preserves_all_reviewed_targets(self):
        second = {**self.manifest["records"][0], "id": "second", "scientific_name": "Other species"}
        self.manifest["records"].append(second)
        self.context.release.content_sha256 = manifest_digest(self.manifest)
        self.repo._run.return_value = [self.row, {**self.row, "source_record_id": "release:second", "taxon_id": "t2", "scientific_name": "Other species"}]
        self.repo.lineage_for_scientific_name.side_effect = [self.lineage, replace(self.lineage, items=(LineageTaxon("t2", "species", "Other species", None),))]
        self.assertEqual(2, len(self.reader.for_name("닭")["relations"]))

    def test_taxonomy_change_during_lookup_is_rejected(self):
        self.repo.lineage_for_scientific_name.return_value = replace(self.lineage, concept_set_id="new")
        with self.assertRaises(ValueError): self.reader.for_name("닭")

    def test_invalid_or_unlicensed_sources_rejected(self):
        for url in ("javascript:alert(1)", "http://example.org", "https://user:password@example.org"):
            data = manifest()
            data["records"][0]["sources"][0]["url"] = url
            with self.assertRaises(ValueError): validate_manifest(data)

    def test_parameterized_query_does_not_interpolate_hostile_name(self):
        self.repo._run.return_value = []
        hostile = "' MATCH (n) DETACH DELETE n //"
        self.reader.for_name(hostile)
        self.assertNotIn(hostile, self.repo._run.call_args.args[0])
        self.assertEqual(hostile, self.repo._run.call_args.kwargs["name"])

    def test_chat_prompts_for_related_wild_taxon_without_fetching_domestic_profile(self):
        profile = Mock()
        client = TestClient(create_app(species_profile_handler=profile, name_relations_handler=self.reader.for_name))
        for question in ("닭", "닭에 대해 알려줘"):
            result = client.post("/v1/chat", json={"question": question}).json()
            self.assertEqual("clarify", result["disposition"])
            self.assertEqual("name_relations", result["result"]["kind"])
        profile.assert_not_called()

    def test_explicit_evidence_and_scientific_filter_are_not_rerouted(self):
        reader = Mock(return_value={"is_search_term": True, "relations": [self.row], "summary": "choose"})
        client = TestClient(create_app(name_relations_handler=reader))
        client.post("/v1/chat", json={"question": "닭", "intent": "evidence"})
        client.post("/v1/chat", json={"question": "닭", "intent": "taxonomy", "filters": {"kind": "taxonomy", "scientific_name": "Gallus gallus"}})
        reader.assert_not_called()

    def test_endpoint_unavailable_blank_and_safe_errors(self):
        client = TestClient(create_app(name_relations_handler=Mock(side_effect=RuntimeError("password-secret"))))
        response = client.get("/v1/taxa/name-relations", params={"name": "닭"})
        self.assertEqual(503, response.status_code)
        self.assertNotIn("password-secret", response.text)
        self.assertEqual(422, client.get("/v1/taxa/name-relations", params={"name": "  "}).status_code)

    def test_known_domestic_term_never_falls_back_to_wild_profile_on_outage(self):
        profile = Mock()
        client = TestClient(create_app(species_profile_handler=profile, name_relations_handler=Mock(side_effect=ValueError("unavailable"))))
        result = client.post("/v1/chat", json={"question":"닭에 대해 알려줘"}).json()
        self.assertEqual("abstain", result["disposition"])
        profile.assert_not_called()

    def test_auto_evidence_filters_and_explicit_taxonomy_question(self):
        reader = Mock(return_value={"is_search_term": True, "relations": [self.row], "summary": "choose"})
        client = TestClient(create_app(name_relations_handler=reader))
        client.post("/v1/chat", json={"question":"닭", "filters":{"kind":"evidence"}})
        reader.assert_not_called()
        result = client.post("/v1/chat", json={"question":"닭은 무슨 과야?", "intent":"taxonomy", "filters":{"kind":"taxonomy","name":"닭"}}).json()
        self.assertEqual("clarify", result["disposition"])
        self.assertEqual("닭", reader.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
