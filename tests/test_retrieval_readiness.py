"""Offline contracts for audit metadata; no live DB or embeddings."""
import hashlib
import json
import unittest
from unittest.mock import patch

from scripts.audit_retrieval_readiness import main, summarize_manifest


def row(**changes):
    value = dict(document_id='fixture-doc-a', chunk_id='fixture-chunk-a', text='private text',
                 content_hash=hashlib.sha256(b'private text').hexdigest(),
                 source_record_hash='source-hash', source_id='fixture-document',
                 source_url='https://example.invalid/source', document_labels=['Fixture'], embedding_allowed=True)
    value.update(changes)
    return value


class RetrievalReadinessTests(unittest.TestCase):
    def test_frozen_manifest_has_no_text_and_is_order_independent(self):
        rows = [row(), row(chunk_id='fixture-chunk-b')]
        result = summarize_manifest(rows)
        self.assertEqual(result, summarize_manifest(list(reversed(rows))))
        self.assertEqual(1, result['synthetic_documents'])
        self.assertNotIn('private text', json.dumps(result))

    def test_changed_text_without_new_hash_is_excluded(self):
        result = summarize_manifest([row(text='changed')])
        self.assertEqual([], result['records'])
        self.assertEqual(1, result['invalid_content_hashes'])

    def test_fixture_label_does_not_turn_pmc_article_into_synthetic_data(self):
        result = summarize_manifest([row(document_id='pmc-pilot:article',
                                         source_url='https://pmc.ncbi.nlm.nih.gov/',
                                         document_labels=['Fixture', 'PmcPilot'])])
        self.assertEqual(1, result['pmc_pilot_documents'])
        self.assertEqual(0, result['synthetic_documents'])

    def test_unknown_corpus_is_not_silently_classified_as_reviewed_literature(self):
        result = summarize_manifest([row(document_id='new-document', source_url='https://example.org/')])
        self.assertEqual(1, result['unclassified_documents'])
        self.assertEqual(0, result['pmc_pilot_documents'])

    def test_non_test_target_fails_before_opening_database(self):
        with patch.dict('os.environ', {'ROBINGRAPH_DEPLOY_TARGET': 'prod'}), \
             patch('scripts.audit_retrieval_readiness.GraphDatabase.driver') as driver:
            with self.assertRaises(SystemExit):
                main()
            driver.assert_not_called()
