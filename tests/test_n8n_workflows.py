"""Static import and safety checks for the reviewed n8n workflow artifacts."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
FINAL = ROOT / "n8n" / "robingraph-operational-ingest.json"
REFERENCE = ROOT / "n8n" / "robingraph-reference-ingest.json"
KOREAN_VERNACULAR = ROOT / "n8n" / "robingraph-korean-vernacular-ingest.json"
WORKFLOWS = [
    ROOT / "n8n" / "candidates" / "claude-operational-ingest.json",
    ROOT / "n8n" / "candidates" / "terra-operational-ingest.json",
    FINAL,
    REFERENCE,
    KOREAN_VERNACULAR,
]


def load(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


class N8nWorkflowArtifactTest(unittest.TestCase):
    def test_every_workflow_has_import_shape_and_valid_connections(self) -> None:
        for path in WORKFLOWS:
            with self.subTest(path=path.name):
                workflow = load(path)
                self.assertTrue(workflow["id"])
                self.assertIs(workflow["active"], False)
                self.assertEqual("v1", workflow["settings"]["executionOrder"])
                nodes = workflow["nodes"]
                names = [item["name"] for item in nodes]
                ids = [item["id"] for item in nodes]
                self.assertEqual(len(names), len(set(names)))
                self.assertEqual(len(ids), len(set(ids)))
                self.assertIn("Manual Trigger", names)
                self.assertTrue(any("Schedule Trigger" in name for name in names))

                known = set(names)
                for source, outputs in workflow["connections"].items():
                    self.assertIn(source, known)
                    for branch in outputs["main"]:
                        for target in branch:
                            self.assertIn(target["node"], known)

    def test_final_collects_gbif_directly_with_bounded_pagination(self) -> None:
        workflow = load(FINAL)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        self.assertFalse(any(item["type"] == "n8n-nodes-base.ssh" for item in workflow["nodes"]))

        fetch = by_name["Fetch GBIF Korea Aves pages"]
        self.assertEqual("n8n-nodes-base.httpRequest", fetch["type"])
        self.assertTrue(fetch["parameters"]["url"].startswith("https://api.gbif.org/v1/occurrence/search?"))
        self.assertIn("license=CC0_1_0&license=CC_BY_4_0", fetch["parameters"]["url"])
        query = fetch["parameters"]["queryParameters"]["parameters"]
        query_names = [item["name"] for item in query]
        self.assertIn("country", query_names)
        self.assertIn("taxon_key", query_names)
        self.assertIn("event_date", query_names)
        self.assertIn("has_coordinate", query_names)
        self.assertNotIn("license", query_names)

        pagination = fetch["parameters"]["options"]["pagination"]["pagination"]
        self.assertEqual("updateAParameterInEachRequest", pagination["paginationMode"])
        self.assertTrue(pagination["limitPagesFetched"])
        self.assertGreater(pagination["maxRequests"], 0)
        self.assertGreaterEqual(pagination["requestInterval"], 200)
        self.assertIn("endOfRecords", pagination["completeExpression"])
        self.assertIn("$pageCount", pagination["parameters"]["parameters"][0]["value"])

        raw_hash = by_name["Hash each raw GBIF page"]
        self.assertEqual("n8n-nodes-base.crypto", raw_hash["type"])
        self.assertEqual("SHA256", raw_hash["parameters"]["type"])
        self.assertEqual("raw_sha256", raw_hash["parameters"]["dataPropertyName"])

    def test_final_uses_community_neo4j_load_and_fail_closed_paths(self) -> None:
        workflow = load(FINAL)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        connections = workflow["connections"]
        load_node = by_name["Atomic upsert to Neo4j"]
        self.assertEqual("n8n-nodes-neo4j.neo4j", load_node["type"])
        self.assertEqual("graphDb", load_node["parameters"]["resource"])
        self.assertEqual("executeQuery", load_node["parameters"]["operation"])
        body = load_node["parameters"]["cypherQuery"]
        self.assertIn("UNWIND $bird_taxa AS row", body)
        self.assertIn("SET taxon:BirdTaxon", body)
        self.assertIn("HAS_ACCEPTED_NAME", body)
        self.assertIn("PARENT_OF", body)
        self.assertIn("UNWIND $observations AS row", body)
        self.assertIn("MERGE (state:IngestState", body)

        verify_node = by_name["Verify Neo4j response counts"]
        self.assertIn("result['state.active_release']", verify_node["parameters"]["jsCode"])

        self.assertEqual(
            "Notify failure",
            connections["Quality gates passed?"]["main"][1][0]["node"],
        )
        self.assertEqual(
            "Advance n8n cursor",
            connections["Atomic load verified?"]["main"][0][0]["node"],
        )
        self.assertEqual(
            "Notify failure",
            connections["Atomic load verified?"]["main"][1][0]["node"],
        )
        self.assertEqual("Fail execution", connections["Notify failure"]["main"][0][0]["node"])
        self.assertEqual("n8n-nodes-base.stopAndError", by_name["Fail execution"]["type"])

    def test_final_keeps_secrets_out_and_uses_native_processing_nodes(self) -> None:
        workflow = load(FINAL)
        self.assertEqual(1, workflow["settings"]["concurrency"])
        self.assertTrue(any(item["type"] == "n8n-nodes-base.code" for item in workflow["nodes"]))
        notifications = [
            item for item in workflow["nodes"] if item["name"].startswith("Notify ")
        ]
        self.assertEqual(2, len(notifications))
        self.assertTrue(
            all(item["type"] == "n8n-nodes-base.discord" for item in notifications)
        )
        self.assertTrue(
            all(item["parameters"]["authentication"] == "webhook" for item in notifications)
        )
        self.assertFalse(any(item["type"] == "n8n-nodes-base.emailSend" for item in workflow["nodes"]))
        neo4j_node = next(
            item for item in workflow["nodes"]
            if item["type"] == "n8n-nodes-neo4j.neo4j"
        )
        self.assertEqual(["neo4jApi"], list(neo4j_node["credentials"]))
        serialized = json.dumps(workflow).lower()
        self.assertNotIn("-----begin private key-----", serialized)
        self.assertNotIn("bearer ", serialized)
        self.assertNotIn("password", serialized)
        self.assertNotIn("robingraph ingest ", serialized)

    def test_community_query_escaping_and_verification(self) -> None:
        from scripts.generate_n8n_operational_ingest import ASSESS_NEO4J, CYPHER_LITERAL_JS

        script = CYPHER_LITERAL_JS + r"""
const assert = require('node:assert/strict');
assert.equal(literal("O'Brien\\$run_id\n"), "'O\\'Brien\\\\$run_id\\u000a'");
assert.equal(literal({rows: [null, true, 12]}), '{rows:[null,true,12]}');
assert.throws(() => literal(Infinity));
assert.throws(() => literal({'bad`key': 1}));
const expected = {taxon_count: 2, taxon_link_count: 1, observation_count: 19,
  media_count: 11, quarantine_count: 0, source_release: 'release'};
const good = {loaded_taxa: 2, loaded_taxon_links: 1, loaded_observations: 19,
  loaded_media: 11, loaded_quarantine: 0, 'state.active_release': 'release'};
""" + "const verify = new Function('$', '$input', " + json.dumps(ASSESS_NEO4J) + ");" + r"""
const check = value => verify(() => ({first: () => ({json: expected})}),
  {first: () => ({json: value})})[0].json.load_ok;
assert.equal(check(good), true);
assert.equal(check({...good, loaded_observations: 18}), false);
assert.equal(check({...good, 'state.active_release': 'old'}), false);
assert.equal(check({error: 'connection failed'}), false);
assert.equal(check({}), false);
"""
        subprocess.run(['node', '-e', script], check=True, capture_output=True, text=True)

    def test_nas_api_deployment_maps_existing_credentials(self) -> None:
        from scripts.deploy_n8n_operational_ingest import build_deployment

        payload = build_deployment(
            load(FINAL),
            {"id": "neo4j-id", "name": "Neo4j"},
            {"id": "discord-id", "name": "Nesty API 키"},
            "guild-id",
            "channel-id",
        )
        by_name = {item["name"]: item for item in payload["nodes"]}
        load_node = by_name["Atomic upsert to Neo4j"]
        self.assertEqual("n8n-nodes-neo4j.neo4j", load_node["type"])
        self.assertEqual("neo4j-id", load_node["credentials"]["neo4jApi"]["id"])
        self.assertNotIn("concurrency", payload["settings"])
        for name in ("Notify success", "Notify failure"):
            self.assertEqual("channel-id", by_name[name]["parameters"]["channelId"]["value"])
            self.assertEqual("discord-id", by_name[name]["credentials"]["discordBotApi"]["id"])

    def test_reference_workflow_collects_only_approved_pinned_sources(self) -> None:
        workflow = load(REFERENCE)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        self.assertFalse(any(item["type"] == "n8n-nodes-base.ssh" for item in workflow["nodes"]))

        build = by_name["Build reference configuration"]["parameters"]["jsCode"]
        points = json.loads((ROOT / "config" / "collection-points.json").read_text(encoding="utf-8"))
        enabled = {
            item["collection_point_id"]: item
            for item in points["collection_points"]
            if item["enabled"] and item["license_policy_status"] == "allowed"
            and item["collection_point_id"] not in ("traits-avonet", "korean-vernacular-wikidata-species-labels")
        }
        self.assertEqual(
            {
                "taxonomy-avilist-v2025b",
                "taxonomy-checklistbank-release",
                "traits-eltontraits-v1",
            },
            set(enabled),
        )
        for item in enabled.values():
            self.assertIn(item["endpoint_uri"], build)
            if item["expected_sha256"]:
                self.assertIn(item["expected_sha256"], build)

        serialized = json.dumps(workflow)
        for blocked in (
            "api.gbif.org/v1/species/match",
            "species.nibr.go.kr/api-list",
            "nie-ecobank.kr/data/api",
            "api.iucnredlist.org/api/v4",
            "discovery.ucl.ac.uk/id/eprint/10144437",
        ):
            self.assertNotIn(blocked, serialized)

        avi_fetch = by_name["Fetch AviList snapshot"]
        elton_fetch = by_name["Fetch EltonTraits snapshot"]
        self.assertEqual("text", avi_fetch["parameters"]["options"]["response"]["response"]["responseFormat"])
        self.assertEqual("file", elton_fetch["parameters"]["options"]["response"]["response"]["responseFormat"])
        self.assertFalse(by_name["Hash AviList snapshot"]["parameters"]["binaryData"])
        self.assertEqual("={{ $json.data }}", by_name["Hash AviList snapshot"]["parameters"]["value"])
        self.assertTrue(by_name["Hash EltonTraits snapshot"]["parameters"]["binaryData"])
        for name in ("Hash AviList snapshot", "Hash EltonTraits snapshot"):
            self.assertEqual("SHA256", by_name[name]["parameters"]["type"])
        elton_extract = by_name["Extract EltonTraits TSV"]
        self.assertEqual("csv", elton_extract["parameters"]["operation"])
        self.assertEqual("\t", elton_extract["parameters"]["options"]["delimiter"])
        self.assertEqual("latin1", elton_extract["parameters"]["options"]["encoding"])

    def test_reference_workflow_is_claim_first_batched_and_fail_closed(self) -> None:
        workflow = load(REFERENCE)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        connections = workflow["connections"]
        self.assertEqual(1, workflow["settings"]["concurrency"])
        self.assertIn("AviList SHA-256 mismatch", by_name["Assemble claims and quality gates"]["parameters"]["jsCode"])
        self.assertIn("Exact trait mapping ratio", by_name["Assemble claims and quality gates"]["parameters"]["jsCode"])
        self.assertIn("taxonomy_batch_size", by_name["Prepare taxonomy batches"]["parameters"]["jsCode"])
        self.assertIn("trait_claim_batch_size", by_name["Prepare trait batches"]["parameters"]["jsCode"])

        taxonomy_query = by_name["Upsert AviList taxonomy batch"]["parameters"]["cypherQuery"]
        self.assertIn("MERGE (taxon:Taxon", taxonomy_query)
        self.assertIn("HAS_ACCEPTED_NAME", taxonomy_query)
        self.assertIn("PARENT_OF", taxonomy_query)
        self.assertIn("ExternalIdentifier", taxonomy_query)
        trait_query = by_name["Upsert EltonTraits batch"]["parameters"]["cypherQuery"]
        self.assertIn("TraitClaim", trait_query)
        self.assertIn("TaxonMappingClaim", trait_query)
        self.assertIn("TaxonMappingCandidate", trait_query)
        self.assertIn("SUPPORTED_BY", trait_query)
        finalize_query = by_name["Finalize active reference releases"]["parameters"]["cypherQuery"]
        self.assertIn("ExternalTaxonConcept:BirdTaxon", finalize_query)
        self.assertIn("MERGE (taxonomy_state:IngestState", finalize_query)
        self.assertIn("run.status = 'succeeded'", finalize_query)

        for gate in (
            "Reference quality gates passed?",
            "Ingestion run started?",
            "Taxonomy load verified?",
            "Trait load verified?",
            "Reference release finalized?",
        ):
            self.assertEqual("Notify reference failure", connections[gate]["main"][1][0]["node"])
        self.assertEqual(
            "Fail reference execution",
            connections["Notify reference failure"]["main"][0][0]["node"],
        )

    def test_snapshot_binaries_are_not_fanned_out_or_merged_into_rows(self) -> None:
        cases = [
            (REFERENCE, 'EltonTraits', 'Extract EltonTraits TSV', 'Normalize EltonTraits'),
            (ROOT / 'n8n/robingraph-avonet-ingest.json', 'AVONET', 'Extract AVONET species sheet', 'Normalize AVONET species'),
        ]
        for path, source, extract, normalize in cases:
            with self.subTest(source=source):
                workflow=load(path)
                nodes={n['name']:n for n in workflow['nodes']}
                chain=[f'Fetch {source} snapshot', f'Hash {source} snapshot', f'Restore {source} snapshot binary', extract, normalize]
                for previous,following in zip(chain,chain[1:]):
                    self.assertEqual(workflow['connections'][previous]['main'],[[{'node':following,'type':'main','index':0}]])
                self.assertNotIn(f'Join {source} hash and rows',nodes)
                restore=nodes[chain[2]]['parameters']['jsCode']
                self.assertIn('.first()',restore)
                self.assertIn('binary: item.binary' if source!='AVONET' else 'binary:item.binary',restore)

    def test_reference_code_nodes_and_cypher_expressions_parse_as_javascript(self) -> None:
        workflow = load(REFERENCE)
        checked = 0
        for item in workflow["nodes"]:
            if item["type"] == "n8n-nodes-base.code":
                script = item["parameters"]["jsCode"]
            elif item["type"] == "n8n-nodes-neo4j.neo4j":
                expression = item["parameters"]["cypherQuery"]
                self.assertTrue(expression.startswith("={{"))
                script = expression.removeprefix("={{").removesuffix("}}").strip()
            else:
                continue
            subprocess.run(
                ["node", "--check"],
                input=script,
                check=True,
                capture_output=True,
                text=True,
            )
            checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_reference_nas_deployment_maps_all_credentials(self) -> None:
        from scripts.deploy_n8n_reference_ingest import build_deployment

        payload = build_deployment(
            load(REFERENCE),
            {"id": "neo4j-id", "name": "Neo4j"},
            {"id": "discord-id", "name": "Nesty API 키"},
            "guild-id",
            "channel-id",
        )
        self.assertNotIn("concurrency", payload["settings"])
        neo4j_nodes = [item for item in payload["nodes"] if item["type"] == "n8n-nodes-neo4j.neo4j"]
        from scripts.generate_n8n_reference_ingest import REFERENCE_LABELS
        self.assertEqual(5 + len(REFERENCE_LABELS), len(neo4j_nodes))
        self.assertTrue(
            all(item["credentials"]["neo4jApi"]["id"] == "neo4j-id" for item in neo4j_nodes)
        )
        by_name = {item["name"]: item for item in payload["nodes"]}
        for name in ("Notify reference success", "Notify reference failure"):
            self.assertEqual("channel-id", by_name[name]["parameters"]["channelId"]["value"])
            self.assertEqual("discord-id", by_name[name]["credentials"]["discordBotApi"]["id"])

    def test_korean_vernacular_workflow_uses_the_approved_wikidata_source_only(self) -> None:
        workflow = load(KOREAN_VERNACULAR)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        self.assertFalse(any(item["type"] == "n8n-nodes-base.ssh" for item in workflow["nodes"]))

        points = json.loads((ROOT / "config" / "collection-points.json").read_text(encoding="utf-8"))
        point = next(
            item
            for item in points["collection_points"]
            if item["collection_point_id"] == "korean-vernacular-wikidata-species-labels"
        )
        self.assertTrue(point["enabled"])
        self.assertEqual("allowed", point["license_policy_status"])

        build = by_name["Build Korean vernacular configuration"]["parameters"]["jsCode"]
        self.assertIn(point["endpoint_uri"], build)
        self.assertIn("wd:Q5113", build)
        self.assertIn("wd:Q7432", build)
        self.assertIn('LANG(?itemLabel) = \\"ko\\"', build)

        serialized = json.dumps(workflow)
        for blocked in ("species.nibr.go.kr", "nie-ecobank.kr", "api.iucnredlist.org"):
            self.assertNotIn(blocked, serialized)

        fetch = by_name["Fetch Wikidata Korean bird labels"]
        self.assertEqual("n8n-nodes-base.httpRequest", fetch["type"])
        self.assertEqual(
            "application/sparql-results+json",
            fetch["parameters"]["headerParameters"]["parameters"][0]["value"],
        )
        self.assertEqual("text", fetch["parameters"]["options"]["response"]["response"]["responseFormat"])
        self.assertEqual("SHA256", by_name["Hash Wikidata response"]["parameters"]["type"])

    def test_korean_vernacular_workflow_never_touches_reference_taxonomy_state_or_gbif_taxa(self) -> None:
        workflow = load(KOREAN_VERNACULAR)
        by_name = {item["name"]: item for item in workflow["nodes"]}
        connections = workflow["connections"]
        self.assertEqual(1, workflow["settings"]["concurrency"])

        state_query = by_name["Read active taxonomy and Korean dataset state"]["parameters"]["cypherQuery"]
        self.assertIn("OPTIONAL MATCH (taxState:IngestState {id: 'reference-taxonomy'})", state_query)
        self.assertIn("OPTIONAL MATCH (koreanState:IngestState {id: 'korean-vernacular-names'})", state_query)
        self.assertIn("coalesce(koreanState.last_successful_run_id, '')", state_query)

        resolve_query = by_name["Resolve active concept set and match candidates"]["parameters"]["cypherQuery"]
        self.assertIn("MATCH (state:IngestState {id: 'reference-taxonomy'})", resolve_query)
        self.assertIn("Taxon:BirdTaxon", resolve_query)
        self.assertNotIn("SET state", resolve_query)
        self.assertNotIn("ExternalTaxonConcept", resolve_query)

        batch_query = by_name["Upsert Korean vernacular names batch"]["parameters"]["cypherQuery"]
        # The dataset id is content-addressed and folded into every written
        # node's id: identical Wikidata content across runs MERGEs the same
        # immutable nodes, different content never overwrites another
        # snapshot's node in place.
        self.assertIn(
            "MERGE (vernacular:VernacularName {id: row.taxon_id + ':vernacular:ko:wikidata:' + $wikidata_dataset_id}",
            batch_query,
        )
        self.assertIn(
            "MERGE (record:SourceRecord {id: 'wikidata-record:' + qid + ':' + $wikidata_dataset_id})", batch_query
        )
        self.assertIn("UNWIND row.qids AS qid", batch_query)
        self.assertIn("vernacular.language = 'ko'", batch_query)
        self.assertIn("VernacularNameCandidate", batch_query)
        self.assertNotIn("ExternalTaxonConcept", batch_query)
        self.assertNotIn("TaxonConceptSet {id: $taxonomy_concept_set_id}", batch_query)
        # Re-checked on every batch, not just once at Start: a mid-run
        # taxonomy switch stops matching further taxa instead of writing
        # against a superseded concept set.
        self.assertIn(
            "MATCH (state:IngestState {id: 'reference-taxonomy'}) WHERE state.active_concept_set_id = $concept_set_id",
            batch_query,
        )

        start_query = by_name["Start Korean vernacular ingestion run"]["parameters"]["cypherQuery"]
        self.assertIn(
            "MATCH (state:IngestState {id: 'reference-taxonomy'}) WHERE state.active_concept_set_id = $concept_set_id",
            start_query,
        )

        finalize_query = by_name["Finalize Korean vernacular active release"]["parameters"]["cypherQuery"]
        self.assertIn("MERGE (state:IngestState {id: 'korean-vernacular-names'})", finalize_query)
        self.assertIn("state.active_dataset_id = $wikidata_dataset_id", finalize_query)
        # Optimistic concurrency: a concurrent run that already advanced
        # korean-vernacular-names past what this run captured must block
        # this run's activation rather than being clobbered by it.
        # The state is MERGEd (and its unique-key lock acquired) *before*
        # reading the current run id. Without this order, two first-ever
        # executions can both see an absent state as '', pass the comparison,
        # and have the later transaction overwrite the first activation.
        self.assertIn("WHERE currentRunId = $expected_prior_run_id", finalize_query)
        self.assertIn(
            "MERGE (state:IngestState {id: 'korean-vernacular-names'}) ON CREATE SET state.last_successful_run_id = '' WITH run, state, coalesce(state.last_successful_run_id, '') AS currentRunId",
            finalize_query,
        )
        self.assertLess(
            finalize_query.index("MERGE (state:IngestState {id: 'korean-vernacular-names'})"),
            finalize_query.index("WHERE currentRunId = $expected_prior_run_id"),
        )
        self.assertIn(
            "MATCH (taxState:IngestState {id: 'reference-taxonomy'}) WHERE taxState.active_concept_set_id = $concept_set_id",
            finalize_query,
        )
        self.assertIn("reference-taxonomy", finalize_query)

        for gate in (
            "Korean vernacular quality gates passed?",
            "Korean vernacular ingestion run started?",
            "Korean vernacular load verified?",
            "Korean vernacular release finalized?",
        ):
            self.assertEqual("Notify Korean vernacular failure", connections[gate]["main"][1][0]["node"])
        self.assertEqual(
            "Fail Korean vernacular execution",
            connections["Notify Korean vernacular failure"]["main"][0][0]["node"],
        )

    def test_korean_vernacular_code_nodes_and_cypher_expressions_parse_as_javascript(self) -> None:
        workflow = load(KOREAN_VERNACULAR)
        checked = 0
        for item in workflow["nodes"]:
            if item["type"] == "n8n-nodes-base.code":
                script = item["parameters"]["jsCode"]
            elif item["type"] == "n8n-nodes-neo4j.neo4j":
                expression = item["parameters"]["cypherQuery"]
                self.assertTrue(expression.startswith("={{"))
                script = expression.removeprefix("={{").removesuffix("}}").strip()
            else:
                continue
            subprocess.run(["node", "--check"], input=script, check=True, capture_output=True, text=True)
            checked += 1
        self.assertGreaterEqual(checked, 15)

    def test_korean_vernacular_nas_deployment_maps_all_credentials(self) -> None:
        from scripts.deploy_n8n_reference_ingest import build_deployment

        payload = build_deployment(
            load(KOREAN_VERNACULAR),
            {"id": "neo4j-id", "name": "Neo4j"},
            {"id": "discord-id", "name": "Nesty API 키"},
            "guild-id",
            "channel-id",
        )
        self.assertNotIn("concurrency", payload["settings"])
        neo4j_nodes = [item for item in payload["nodes"] if item["type"] == "n8n-nodes-neo4j.neo4j"]
        from scripts.generate_n8n_korean_vernacular_ingest import KOREAN_VERNACULAR_LABELS

        self.assertEqual(5 + len(KOREAN_VERNACULAR_LABELS), len(neo4j_nodes))
        self.assertTrue(all(item["credentials"]["neo4jApi"]["id"] == "neo4j-id" for item in neo4j_nodes))
        by_name = {item["name"]: item for item in payload["nodes"]}
        for name in ("Notify Korean vernacular success", "Notify Korean vernacular failure"):
            self.assertEqual("channel-id", by_name[name]["parameters"]["channelId"]["value"])
            self.assertEqual("discord-id", by_name[name]["credentials"]["discordBotApi"]["id"])

    def test_korean_vernacular_deployment_succeeds_without_a_discord_credential(self) -> None:
        """Discord is optional for this pipeline (docs/n8n/korean-vernacular-ingest.md):
        deploying with no Discord credential configured must not raise --
        unlike the reference workflow, whose notifications are mandatory
        (see test_reference_deployment.test_reference_requires_notification_credentials_before_deployment)."""

        from scripts.deploy_n8n_reference_ingest import DISCORD_REQUIRED, build_deployment

        self.assertFalse(DISCORD_REQUIRED.get("korean-vernacular", True))
        payload = build_deployment(
            load(KOREAN_VERNACULAR),
            {"id": "neo4j-id", "name": "Neo4j"},
            None,
            "guild-id",
            "channel-id",
            discord_required=False,
        )
        by_name = {item["name"]: item for item in payload["nodes"]}
        for name in ("Notify Korean vernacular success", "Notify Korean vernacular failure"):
            node = by_name[name]
            self.assertEqual("n8n-nodes-base.discord", node["type"])
            self.assertNotIn("credentials", node)
            self.assertEqual("continueRegularOutput", node["onError"])

    def test_korean_vernacular_deploy_script_is_registered(self) -> None:
        from scripts.deploy_n8n_reference_ingest import WORKFLOWS as DEPLOY_WORKFLOWS

        source_path, env_var = DEPLOY_WORKFLOWS["korean-vernacular"]
        self.assertEqual(KOREAN_VERNACULAR, source_path)
        self.assertEqual("ROBINGRAPH_N8N_KOREAN_VERNACULAR_WORKFLOW_ID", env_var)

    def test_korean_vernacular_license_gate_approves_wikidata_and_denies_unreviewed_nibr(self) -> None:
        from scripts.generate_n8n_korean_vernacular_ingest import (
            COLLECTION_POINT_ID,
            load_wikidata_collection_point,
            require_collection_point_approved,
        )

        approved = load_wikidata_collection_point()
        self.assertEqual(COLLECTION_POINT_ID, approved["collection_point_id"])
        self.assertEqual("allowed", approved["license_policy_status"])
        self.assertEqual("allowed", approved["source"]["license_policy_status"])
        self.assertEqual(
            "https://creativecommons.org/publicdomain/zero/1.0/", approved["source"]["license_uri"]
        )

        # korea-nibr-species is still enabled=false / license_policy_status="review_required"
        # in the project's real config/collection-points.json (see docs/decisions/0002 and
        # docs/data-source-decision-input.md). This is a live check against that current
        # config, not an invented denial: if a future ADR approves NIBR and someone flips its
        # enabled/license_policy_status fields, this assertion should be revisited alongside
        # that change, not silenced.
        with self.assertRaisesRegex(RuntimeError, "not approved"):
            require_collection_point_approved("korea-nibr-species")

        with self.assertRaisesRegex(RuntimeError, "unknown collection point"):
            require_collection_point_approved("does-not-exist")

    def test_korean_vernacular_classify_wikidata_rows_handles_duplicates_and_conflicts(self) -> None:
        from scripts.generate_n8n_korean_vernacular_ingest import CLASSIFY_WIKIDATA_ROWS_JS

        script = CLASSIFY_WIKIDATA_ROWS_JS + r"""
const assert = require('node:assert/strict');
const bindings = [
  {item: {value: 'http://www.wikidata.org/entity/Q25348'}, taxonName: {value: 'Anas platyrhynchos'}, itemLabel: {value: '청둥오리'}},
  {item: {value: 'http://www.wikidata.org/entity/Qdup'}, taxonName: {value: 'Anas platyrhynchos'}, itemLabel: {value: '청둥오리'}},
  {item: {value: 'http://www.wikidata.org/entity/Qa'}, taxonName: {value: 'Anas zonorhyncha'}, itemLabel: {value: '흰뺨검둥오리'}},
  {item: {value: 'http://www.wikidata.org/entity/Qb'}, taxonName: {value: 'Anas zonorhyncha'}, itemLabel: {value: '다른이름'}},
  {item: {value: 'http://www.wikidata.org/entity/Qc'}, taxonName: {value: ''}, itemLabel: {value: '이름없음'}},
  {item: {value: ''}, taxonName: {value: 'No qid'}, itemLabel: {value: '값'}},
];
const {clean, conflicted, malformedRowCount} = classifyWikidataRows(bindings);
assert.equal(malformedRowCount, 2);
assert.equal(clean.length, 1);
assert.equal(clean[0].taxon_name, 'Anas platyrhynchos');
assert.equal(clean[0].korean_name, '청둥오리');
assert.deepEqual(clean[0].qids, ['Q25348', 'Qdup']);
assert.equal(conflicted.length, 2);
assert.ok(conflicted.every(row => row.taxon_name === 'Anas zonorhyncha' && row.reason_code === 'conflicting_korean_labels'));
const repeat = classifyWikidataRows(bindings);
assert.deepEqual(repeat, {clean, conflicted, malformedRowCount});
"""
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_korean_vernacular_classify_wikidata_rows_quarantines_cross_taxon_homonyms(self) -> None:
        """The HIGH-severity bug this fixes: the same Korean label attached
        to two genuinely different scientific names must never both come
        back "clean" -- even though each looks unambiguous when checked in
        isolation per taxon name. Both must be quarantined; neither wins."""

        from scripts.generate_n8n_korean_vernacular_ingest import CLASSIFY_WIKIDATA_ROWS_JS

        script = CLASSIFY_WIKIDATA_ROWS_JS + r"""
const assert = require('node:assert/strict');
const bindings = [
  {item: {value: 'http://www.wikidata.org/entity/Q1'}, taxonName: {value: 'Species A'}, itemLabel: {value: '동명이인'}},
  {item: {value: 'http://www.wikidata.org/entity/Q2'}, taxonName: {value: 'Species B'}, itemLabel: {value: '동명이인'}},
  {item: {value: 'http://www.wikidata.org/entity/Q3'}, taxonName: {value: 'Species C'}, itemLabel: {value: '고유이름'}},
];
const {clean, conflicted} = classifyWikidataRows(bindings);
assert.deepEqual(clean.map(row => row.taxon_name), ['Species C']);
const homonyms = conflicted.filter(row => row.reason_code === 'ambiguous_korean_name_across_taxa');
assert.equal(homonyms.length, 2);
assert.deepEqual(homonyms.map(row => row.taxon_name).sort(), ['Species A', 'Species B']);
assert.ok(homonyms.every(row => row.korean_name === '동명이인'));
"""
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_korean_vernacular_classify_matches_reports_missing_and_ambiguous_taxa(self) -> None:
        from scripts.generate_n8n_korean_vernacular_ingest import CLASSIFY_MATCHES_JS

        script = CLASSIFY_MATCHES_JS + r"""
const assert = require('node:assert/strict');
const resolved = [
  {taxon_name: 'Anas platyrhynchos', korean_name: '청둥오리', qids: ['Q25348'], matched_taxon_ids: ['species:anas-platyrhynchos']},
  {taxon_name: 'Nonexistent species', korean_name: '없는이름', qids: ['Q0'], matched_taxon_ids: []},
  {taxon_name: 'Ambiguous species', korean_name: '모호', qids: ['Q7'], matched_taxon_ids: ['a', 'b']},
];
const {writeRows, candidates} = classifyMatches(resolved);
assert.equal(writeRows.length, 1);
assert.equal(writeRows[0].taxon_id, 'species:anas-platyrhynchos');
assert.equal(writeRows[0].korean_name, '청둥오리');
assert.equal(candidates.length, 2);
assert.equal(candidates[0].reason_code, 'no_matching_avilist_taxon');
assert.equal(candidates[1].reason_code, 'ambiguous_avilist_taxon_match');
"""
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_korean_vernacular_assemble_gates_fails_closed_without_active_concept_set(self) -> None:
        from scripts.generate_n8n_korean_vernacular_ingest import ASSEMBLE_GATES_JS

        script = ASSEMBLE_GATES_JS + r"""
const assert = require('node:assert/strict');
const config = {run_id: 'run-1', pipeline_id: 'korean-vernacular-names'};
const noPriorState = {concept_set_id: 'rg:concept-set:avilist-v2025b', taxonomy_release: 'v2025b', expected_prior_run_id: ''};

// Missing active reference-taxonomy concept set must fail closed -- checked
// directly against the dedicated state-read result now, not inferred from
// resolvedRows being empty (which is also legitimately empty whenever there
// are zero clean candidates, a different case entirely).
const missingState = assembleGates(
  config,
  {source_sha256: 'abc', fetch_ok: true, malformed_row_count: 0, distinct_taxon_name_count: 1, clean_candidates: [{taxon_name: 'X', korean_name: 'Y', qids: ['Q1']}], conflicted_candidates: []},
  {concept_set_id: null, taxonomy_release: null, expected_prior_run_id: ''},
  []
);
assert.equal(missingState.ready_to_load, false);
assert.match(missingState.failure_reason, /Active AviList reference-taxonomy concept set is not available/);

// Empty Wikidata response: nothing parsed at all must also fail closed, not
// silently report success with zero everything.
const emptyResponse = assembleGates(
  config,
  {source_sha256: 'abc', fetch_ok: true, malformed_row_count: 0, distinct_taxon_name_count: 0, clean_candidates: [], conflicted_candidates: []},
  noPriorState,
  []
);
assert.equal(emptyResponse.ready_to_load, false);
assert.match(emptyResponse.failure_reason, /No Korean vernacular candidates parsed/);

// Any malformed row fails the run closed, even though a clean candidate was
// also parsed -- a partial parse failure is not treated as "good enough".
const malformedPresent = assembleGates(
  config,
  {source_sha256: 'abc', fetch_ok: true, malformed_row_count: 3, distinct_taxon_name_count: 1, clean_candidates: [{taxon_name: 'Anas platyrhynchos', korean_name: '청둥오리', qids: ['Q25348']}], conflicted_candidates: []},
  noPriorState,
  [{taxon_name: 'Anas platyrhynchos', korean_name: '청둥오리', qids: ['Q25348'], matched_taxon_ids: ['species:anas-platyrhynchos']}]
);
assert.equal(malformedPresent.ready_to_load, false);
assert.match(malformedPresent.failure_reason, /3 malformed Wikidata row\(s\) were rejected/);
assert.doesNotMatch(malformedPresent.failure_reason, /No Korean vernacular candidates parsed/);

// A real match succeeds, produces exactly one write row, and carries the
// content-addressed dataset id / activation token through for Start/Batch/Finalize.
const matched = assembleGates(
  config,
  {
    source_sha256: 'abc', fetch_ok: true, malformed_row_count: 0,
    wikidata_dataset_id: 'wikidata-dataset:taxon-labels:sha256-abc', source_release: 'wikidata-snapshot:2026-09-11:sha256-abc',
    distinct_taxon_name_count: 1, clean_candidates: [{taxon_name: 'Anas platyrhynchos', korean_name: '청둥오리', qids: ['Q25348']}], conflicted_candidates: [],
  },
  {concept_set_id: 'rg:concept-set:avilist-v2025b', taxonomy_release: 'v2025b', expected_prior_run_id: 'prior-run-7'},
  [{taxon_name: 'Anas platyrhynchos', korean_name: '청둥오리', qids: ['Q25348'], matched_taxon_ids: ['species:anas-platyrhynchos']}]
);
assert.equal(matched.ready_to_load, true);
assert.equal(matched.write_row_count, 1);
assert.equal(matched.candidate_count, 0);
assert.equal(matched.concept_set_id, 'rg:concept-set:avilist-v2025b');
assert.equal(matched.wikidata_dataset_id, 'wikidata-dataset:taxon-labels:sha256-abc');
assert.equal(matched.expected_prior_run_id, 'prior-run-7');

// A failed or malformed Wikidata fetch (non-200, or a body that is not a
// well-formed SPARQL results document) must fail closed with a specific
// reason -- never be reported as an innocuous "zero candidates found",
// which would look like nothing was wrong.
const fetchFailed = assembleGates(
  config,
  {
    source_sha256: null, fetch_ok: false, malformed_row_count: 0,
    fetch_failure_reason: 'Wikidata SPARQL endpoint returned HTTP 500',
    distinct_taxon_name_count: 0, clean_candidates: [], conflicted_candidates: [],
  },
  noPriorState,
  []
);
assert.equal(fetchFailed.ready_to_load, false);
assert.match(fetchFailed.failure_reason, /Wikidata SPARQL endpoint returned HTTP 500/);
assert.doesNotMatch(fetchFailed.failure_reason, /No Korean vernacular candidates parsed/);
"""
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_korean_vernacular_normalize_computes_idempotent_content_addressed_dataset_id(self) -> None:
        """Two runs (the literal "run it twice" adversarial case): byte-
        identical Wikidata content must compute the exact same dataset id
        and source_release, so re-running MERGEs the same immutable nodes
        instead of a new run's hash overwriting an old one's in place.
        Different content must compute a different id. A failed or
        malformed fetch must compute no id at all (nothing to anchor an
        identity to, and nothing that should ever reach Start/Batch)."""

        from scripts.generate_n8n_korean_vernacular_ingest import NORMALIZE_WIKIDATA

        well_formed_body = json.dumps(
            {
                "head": {"vars": ["item", "taxonName", "itemLabel"]},
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q25348"},
                            "taxonName": {"value": "Anas platyrhynchos"},
                            "itemLabel": {"value": "청둥오리"},
                        }
                    ]
                },
            }
        )
        different_body = json.dumps(
            {
                "head": {"vars": ["item", "taxonName", "itemLabel"]},
                "results": {
                    "bindings": [
                        {
                            "item": {"value": "http://www.wikidata.org/entity/Q99"},
                            "taxonName": {"value": "Some other species"},
                            "itemLabel": {"value": "다른이름"},
                        }
                    ]
                },
            }
        )
        script = (
            "const assert = require('node:assert/strict');\n"
            "const config = {retrieved_at: '2026-09-11T00:00:00.000Z'};\n"
            "const hash = 'deadbeef'.repeat(8);\n"
            "const hash2 = 'cafebabe'.repeat(8);\n"
            f"const wellFormedBody = {json.dumps(well_formed_body)};\n"
            f"const differentBody = {json.dumps(different_body)};\n"
            "function run(fetchedEnvelope, sha) {\n"
            "  const impl = new Function('$', '$input', " + json.dumps(NORMALIZE_WIKIDATA) + ");\n"
            "  const hashedItem = {...fetchedEnvelope, raw_sha256: sha};\n"
            "  return impl(\n"
            "    (name) => {\n"
            "      if (name === 'Build Korean vernacular configuration') return {first: () => ({json: config})};\n"
            "      if (name === 'Hash Wikidata response') return {first: () => ({json: hashedItem})};\n"
            "      throw new Error('unexpected node: ' + name);\n"
            "    },\n"
            "    {first: () => ({json: hashedItem})}\n"
            "  )[0].json;\n"
            "}\n"
            "const runA = run({statusCode: 200, data: wellFormedBody}, hash);\n"
            "const runB = run({statusCode: 200, data: wellFormedBody}, hash);\n"
            "assert.equal(runA.wikidata_dataset_id, runB.wikidata_dataset_id);\n"
            "assert.equal(runA.source_release, runB.source_release);\n"
            "assert.ok(runA.wikidata_dataset_id.startsWith('wikidata-dataset:taxon-labels:sha256-'));\n"
            "const runDifferentContent = run({statusCode: 200, data: differentBody}, hash2);\n"
            "assert.notEqual(runDifferentContent.wikidata_dataset_id, runA.wikidata_dataset_id);\n"
            "const failed = run({statusCode: 500, data: 'Internal Server Error'}, null);\n"
            "assert.equal(failed.wikidata_dataset_id, null);\n"
            "assert.equal(failed.source_release, null);\n"
            "assert.equal(failed.fetch_ok, false);\n"
            "const malformed = run({statusCode: 200, data: '<html>not sparql</html>'}, hash2);\n"
            "assert.equal(malformed.wikidata_dataset_id, null);\n"
            "assert.equal(malformed.fetch_ok, false);\n"
        )
        subprocess.run(["node", "-e", script], check=True, capture_output=True, text=True)

    def test_korean_vernacular_verify_finalize_detects_lost_optimistic_concurrency_race(self) -> None:
        """Adversarial case: a concurrent stale writer. Simulates the exact
        Neo4j response shape when the FINALIZE_STATEMENT's
        `WHERE currentRunId = $expected_prior_run_id` guard was not
        satisfied (either a competing run already activated a newer
        snapshot, or the reference-taxonomy concept set changed mid-run):
        the query returns no matching row, so the community Neo4j node's
        response is missing the expected fields entirely. VERIFY_FINALIZE
        must treat that as a failure, never as a false "succeeded"."""

        from scripts.generate_n8n_korean_vernacular_ingest import VERIFY_FINALIZE

        script = VERIFY_FINALIZE.replace(
            "$('Assemble Korean vernacular quality gates').first().json",
            "expected",
        ) + ""
        harness = (
            "const assert = require('node:assert/strict');\n"
            "const expected = {run_id: 'run-2', source_release: 'wikidata-snapshot:2026-09-11:sha256-abc', "
            "wikidata_dataset_id: 'wikidata-dataset:taxon-labels:sha256-abc', "
            "loaded_vernacular_names: 5, loaded_candidates: 1};\n"
            "function verifyFinalize(response) {\n"
            "  const impl = new Function('$', '$input', " + json.dumps(VERIFY_FINALIZE) + ");\n"
            "  return impl(\n"
            "    (name) => { if (name === 'Assemble Korean vernacular quality gates') return {first: () => ({json: expected})}; throw new Error('unexpected'); },\n"
            "    {first: () => ({json: response})}\n"
            "  )[0].json;\n"
            "}\n"
            # Lost the race: Neo4j's WHERE guard excluded every row, so the
            # response the community node hands back carries none of the
            # expected activation fields.
            "const lostRace = verifyFinalize({});\n"
            "assert.equal(lostRace.finalize_ok, false);\n"
            "assert.match(lostRace.failure_reason, /lost the optimistic-concurrency race|active concept set changed/);\n"
            # Won cleanly: every field matches this run's own expectations.
            "const won = verifyFinalize({finalized_run_id: 'run-2', run_status: 'succeeded', "
            "active_release: expected.source_release, active_dataset_id: expected.wikidata_dataset_id});\n"
            "assert.equal(won.finalize_ok, true);\n"
            # A stale/wrong dataset id sneaking through (should be
            # impossible given the query, but verified defensively) must
            # still be rejected by the JS-side check, not just trusted.
            "const wrongDataset = verifyFinalize({finalized_run_id: 'run-2', run_status: 'succeeded', "
            "active_release: expected.source_release, active_dataset_id: 'wikidata-dataset:taxon-labels:sha256-someone-elses'});\n"
            "assert.equal(wrongDataset.finalize_ok, false);\n"
        )
        subprocess.run(["node", "-e", harness], check=True, capture_output=True, text=True)

    @unittest.skipUnless(
        os.environ.get("ROBINGRAPH_NEO4J_INTEGRATION_TESTS") == "1",
        "Opt in to run the Korean vernacular Cypher contract against Neo4j",
    )
    def test_korean_vernacular_neo4j_statements_are_idempotent_and_reject_homonym_ambiguity(self) -> None:
        """Live (opt-in) integration test covering three adversarial cases
        against a real Neo4j: (1) running the exact same batch/finalize
        sequence twice produces the same node count, not duplicates
        (idempotence across two runs); (2) once a second, different
        snapshot is activated, the taxon's old dataset-scoped name stops
        resolving through the read path (retirement without an explicit
        delete); (3) two different taxa sharing one Korean label never both
        resolve via `lineage_for_korean_name` -- it returns None for
        either, exactly like the tests in test_taxonomy_lineage_neo4j.py,
        but proven here against a real query execution instead of a mock.
        """

        from neo4j import GraphDatabase

        from robingraph.graph.settings import Neo4jSettings
        from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
        from scripts.generate_n8n_korean_vernacular_ingest import (
            BATCH_STATEMENT,
            FINALIZE_STATEMENT,
            START_STATEMENT,
        )

        marker = "n8n-korean-vernacular-integration-test"
        concept_set_id = f"concept-set:{marker}"
        taxon_a = f"taxon:{marker}:a"
        taxon_b = f"taxon:{marker}:b"
        run_1 = f"run-1:{marker}"
        run_2 = f"run-2:{marker}"
        dataset_1 = f"wikidata-dataset:taxon-labels:sha256-{marker}-1"
        dataset_2 = f"wikidata-dataset:taxon-labels:sha256-{marker}-2"

        driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        )
        database = os.environ.get("NEO4J_DATABASE", "neo4j")

        def start_batch_finalize(run_id, dataset_id, source_release, rows, expected_prior_run_id):
            with driver.session(database=database) as session:
                session.run(
                    "MATCH (state:IngestState {id: 'reference-taxonomy'}) "
                    "WHERE state.active_concept_set_id = $concept_set_id RETURN 1"
                ).consume()
                start = session.run(
                    START_STATEMENT,
                    concept_set_id=concept_set_id,
                    run_id=run_id,
                    pipeline_id="korean-vernacular-names",
                    retrieved_at="2026-09-11T00:00:00Z",
                    source_release=source_release,
                    wikidata_dataset_id=dataset_id,
                    source_sha256="0" * 64,
                    taxonomy_release=marker,
                    write_row_count=len(rows),
                    candidate_count=0,
                    wikidata_landing_uri="https://www.wikidata.org/wiki/Wikidata:WikiProject_Taxonomy",
                    sparql_endpoint="https://query.wikidata.org/sparql",
                    wikidata_license_uri="https://creativecommons.org/publicdomain/zero/1.0/",
                ).single(strict=True)
                self.assertEqual(run_id, start["started_run_id"])
                batch = session.run(
                    BATCH_STATEMENT,
                    run_id=run_id,
                    concept_set_id=concept_set_id,
                    wikidata_dataset_id=dataset_id,
                    batch_index=0,
                    batch_count=1,
                    rows=rows,
                    candidates=[],
                    source_release=source_release,
                    retrieved_at="2026-09-11T00:00:00Z",
                    source_sha256="0" * 64,
                ).single(strict=True)
                self.assertEqual(len(rows), batch["loaded_vernacular_names"])
                finalize = session.run(
                    FINALIZE_STATEMENT,
                    run_id=run_id,
                    concept_set_id=concept_set_id,
                    expected_prior_run_id=expected_prior_run_id,
                    loaded_vernacular_names=len(rows),
                    loaded_candidates=0,
                    source_release=source_release,
                    wikidata_dataset_id=dataset_id,
                    taxonomy_release=marker,
                ).single(strict=True)
                self.assertEqual(run_id, finalize["finalized_run_id"])
                self.assertEqual(dataset_id, finalize["active_dataset_id"])

        # This test temporarily repoints the two shared singleton IngestState
        # nodes ('reference-taxonomy', 'korean-vernacular-names') at
        # throwaway marker-scoped data. Both are captured here and restored
        # verbatim in `finally` -- including deleting them again if they
        # did not exist before -- so this test is safe to run against a
        # Neo4j instance that already has real active state, not only an
        # empty throwaway database.
        with driver.session(database=database) as session:
            prior_states = {
                row["id"]: dict(row["props"])
                for row in session.run(
                    "MATCH (state:IngestState) WHERE state.id IN ['reference-taxonomy', 'korean-vernacular-names'] "
                    "RETURN state.id AS id, properties(state) AS props"
                )
            }

        try:
            with driver.session(database=database) as session:
                session.run(
                    "MERGE (cs:TaxonConceptSet {id: $id}) "
                    "MERGE (state:IngestState {id: 'reference-taxonomy'}) "
                    "SET state.active_concept_set_id = $id, state.active_release = $release "
                    "MERGE (a:Taxon:BirdTaxon {id: $taxon_a}) "
                    "SET a.scientific_name = 'Marker species A', a.rank = 'species' "
                    "MERGE (a)-[:IN_CONCEPT_SET]->(cs) "
                    "MERGE (b:Taxon:BirdTaxon {id: $taxon_b}) "
                    "SET b.scientific_name = 'Marker species B', b.rank = 'species' "
                    "MERGE (b)-[:IN_CONCEPT_SET]->(cs)",
                    id=concept_set_id,
                    release=marker,
                    taxon_a=taxon_a,
                    taxon_b=taxon_b,
                ).consume()

                # --- (1) Idempotence across two runs with identical content ---
                rows_v1 = [
                    {"taxon_id": taxon_a, "taxon_name": "Marker species A", "korean_name": "마커이름", "qids": ["Q1"]}
                ]
                start_batch_finalize(run_1, dataset_1, "release-1", rows_v1, "")
                start_batch_finalize(run_1, dataset_1, "release-1", rows_v1, "")  # re-run, same content
                count_after_rerun = session.run(
                    "MATCH (v:VernacularName {dataset_id: $dataset_id}) RETURN count(v) AS n", dataset_id=dataset_1
                ).single(strict=True)["n"]
                self.assertEqual(1, count_after_rerun)

                # --- (2) Retirement: species A gets no name in the new snapshot ---
                start_batch_finalize(run_2, dataset_2, "release-2", [], run_1)
                with Neo4jTaxonomyLineageRepository(
                    Neo4jSettings(
                        uri=os.environ["NEO4J_URI"],
                        username=os.environ["NEO4J_USERNAME"],
                        password=os.environ["NEO4J_PASSWORD"],
                        database=database,
                    )
                ) as repository:
                    # Retired: the old snapshot's name is no longer active.
                    self.assertIsNone(repository.lineage_for_korean_name("마커이름"))

                    # --- (3) Homonym ambiguity across two distinct taxa ---
                    dataset_3 = f"wikidata-dataset:taxon-labels:sha256-{marker}-3"
                    run_3 = f"run-3:{marker}"
                    homonym_rows = [
                        {"taxon_id": taxon_a, "taxon_name": "Marker species A", "korean_name": "동명이인", "qids": ["Q1"]},
                        {"taxon_id": taxon_b, "taxon_name": "Marker species B", "korean_name": "동명이인", "qids": ["Q2"]},
                    ]
                    start_batch_finalize(run_3, dataset_3, "release-3", homonym_rows, run_2)
                    self.assertIsNone(repository.lineage_for_korean_name("동명이인"))
        finally:
            with driver.session(database=database) as session:
                session.run(
                    "MATCH (node) WHERE node.id CONTAINS $marker DETACH DELETE node", marker=marker
                ).consume()
                for state_id in ("reference-taxonomy", "korean-vernacular-names"):
                    if state_id in prior_states:
                        session.run(
                            "MATCH (state:IngestState {id: $id}) SET state = $props",
                            id=state_id,
                            props=prior_states[state_id],
                        ).consume()
                    else:
                        session.run(
                            "MATCH (state:IngestState {id: $id}) DETACH DELETE state", id=state_id
                        ).consume()
            driver.close()

    @unittest.skipUnless(
        os.environ.get("ROBINGRAPH_NEO4J_INTEGRATION_TESTS") == "1",
        "Opt in to run the n8n Cypher contract against Neo4j",
    )
    def test_native_neo4j_statement_executes_atomically(self) -> None:
        from neo4j import GraphDatabase
        from robingraph.graph.settings import Neo4jSettings
        from robingraph.retrieval.operational import OperationalObservationQuery
        from robingraph.retrieval.operational_neo4j import Neo4jOperationalObservationRepository
        from scripts.generate_n8n_operational_ingest import NEO4J_STATEMENT

        run_id = "n8n-native-workflow-integration-test"
        observation_id = f"gbif-observation:{run_id}"
        parameters = {
            "run_id": run_id,
            "pipeline_id": f"gbif-occurrence-kr-aves:{run_id}",
            "retrieved_at": "2026-09-07T00:00:00Z",
            "source_release": "gbif-live-integration-test",
            "source_count": 1,
            "taxon_count": 2,
            "taxon_link_count": 1,
            "quarantine_count": 0,
            "event_date_end": "2026-09-07",
            "bird_taxa": [
                {
                    "id": f"gbif-taxon:family-{run_id}",
                    "external_key": f"family-{run_id}",
                    "provider": "GBIF Backbone",
                    "rank": "family",
                    "scientific_name": "Corvidae",
                    "canonical_name": "Corvidae",
                    "authorship": None,
                    "taxonomic_status": "accepted",
                    "vernacular_name_raw": None,
                    "source_uri": f"https://example.invalid/species/family-{run_id}",
                    "retrieved_at": "2026-09-07T00:00:00Z",
                },
                {
                    "id": f"gbif-taxon:{run_id}",
                    "external_key": run_id,
                    "provider": "GBIF Backbone",
                    "rank": "species",
                    "scientific_name": "Pica serica",
                    "canonical_name": "Pica serica",
                    "authorship": "Gould, 1845",
                    "taxonomic_status": "accepted",
                    "vernacular_name_raw": "Oriental Magpie",
                    "source_uri": f"https://example.invalid/species/{run_id}",
                    "retrieved_at": "2026-09-07T00:00:00Z",
                },
            ],
            "taxon_links": [
                {
                    "id": f"family-{run_id}->species-{run_id}",
                    "parent_id": f"gbif-taxon:family-{run_id}",
                    "child_id": f"gbif-taxon:{run_id}",
                }
            ],
            "observations": [
                {
                    "id": observation_id,
                    "external_id": run_id,
                    "occurrence_id": run_id,
                    "event_id": None,
                    "external_taxon_id": f"gbif-taxon:{run_id}",
                    "external_taxon_key": run_id,
                    "scientific_name": "Pica serica",
                    "scientific_name_raw": "Pica serica",
                    "taxon_rank": "species",
                    "observed_at": "2026-09-01T12:00:00Z",
                    "event_date_precision": "instant",
                    "count": 1,
                    "basis": "human_observation",
                    "lat": 37.5,
                    "lon": 127.0,
                    "coordinate_uncertainty_m": 10,
                    "geodetic_datum": "WGS84",
                    "sensitivity": "public",
                    "place_id": f"gbif-place:{run_id}",
                    "place_name": "integration test place",
                    "dataset_id": f"gbif-dataset:{run_id}",
                    "dataset_key": run_id,
                    "publisher_key": None,
                    "license_uri": f"https://example.invalid/license/{run_id}",
                    "source_record_key": f"gbif:integration:{run_id}",
                    "source_release": "gbif-live-integration-test",
                    "raw_uri": f"https://example.invalid/occurrence/{run_id}",
                    "raw_sha256": "0" * 64,
                    "source_updated_at": None,
                    "retrieved_at": "2026-09-07T00:00:00Z",
                    "issues": [],
                }
            ],
            "media": [],
            "quarantine": [],
        }
        driver = GraphDatabase.driver(
            os.environ["NEO4J_URI"],
            auth=(os.environ["NEO4J_USERNAME"], os.environ["NEO4J_PASSWORD"]),
        )
        try:
            with driver.session(database=os.environ.get("NEO4J_DATABASE", "neo4j")) as session:
                result = session.run(NEO4J_STATEMENT, **parameters).single(strict=True)
                self.assertEqual(2, result["loaded_taxa"])
                self.assertEqual(1, result["loaded_taxon_links"])
                self.assertEqual(1, result["loaded_observations"])
                self.assertEqual(0, result["loaded_media"])
                self.assertEqual(0, result["loaded_quarantine"])
                self.assertEqual(parameters["source_release"], result["state.active_release"])
                with Neo4jOperationalObservationRepository(
                    Neo4jSettings(
                        uri=os.environ["NEO4J_URI"],
                        username=os.environ["NEO4J_USERNAME"],
                        password=os.environ["NEO4J_PASSWORD"],
                        database=os.environ.get("NEO4J_DATABASE", "neo4j"),
                    )
                ) as repository:
                    observations = repository.search_observations(
                        OperationalObservationQuery(taxon_key=run_id)
                    )
                self.assertEqual(1, len(observations))
                self.assertEqual(observation_id, observations[0].observation_id)
                self.assertEqual(f"gbif-evidence:{run_id}", observations[0].citation.evidence_id)
                session.run(
                    "MATCH (node) WHERE node.id CONTAINS $marker DETACH DELETE node",
                    marker=run_id,
                ).consume()
        finally:
            driver.close()


if __name__ == "__main__":
    unittest.main()
