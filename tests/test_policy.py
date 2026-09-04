"""Unit tests for the license policy engine (robingraph.policy).

These use small synthetic records rather than the committed fixture so they
can exercise document/chunk permission combinations (fulltext denied, chunk
denied, embedding denied) that do not currently exist in the fixture data
without needing to change data owned by the fixture generator.
"""

from __future__ import annotations

import unittest

from robingraph import policy


def _document(**overrides: object) -> dict[str, object]:
    base = {
        "document_id": "doc-1",
        "license_policy_status": "allowed",
        "fulltext_storage_allowed": True,
        "chunk_storage_allowed": True,
        "embedding_allowed": True,
    }
    base.update(overrides)
    return base


def _chunk(**overrides: object) -> dict[str, object]:
    base = {"chunk_id": "chunk-1", "document_id": "doc-1", "license_policy_status": "allowed"}
    base.update(overrides)
    return base


class PolicyTest(unittest.TestCase):
    def test_fully_allowed_document_permits_metadata_chunks_and_embedding(self) -> None:
        document = _document()
        self.assertTrue(policy.document_metadata_allowed(document))
        self.assertTrue(policy.document_fulltext_allowed(document))
        self.assertTrue(policy.document_chunk_allowed(document))
        self.assertTrue(policy.document_embedding_allowed(document))

    def test_fulltext_denied_document_keeps_metadata_but_blocks_chunks_and_embedding(self) -> None:
        document = _document(fulltext_storage_allowed=False)
        self.assertTrue(policy.document_metadata_allowed(document))
        self.assertFalse(policy.document_fulltext_allowed(document))
        self.assertFalse(policy.document_chunk_allowed(document))
        self.assertFalse(policy.document_embedding_allowed(document))

    def test_chunk_storage_denied_blocks_chunks_but_keeps_metadata(self) -> None:
        document = _document(chunk_storage_allowed=False)
        self.assertTrue(policy.document_metadata_allowed(document))
        self.assertTrue(policy.document_fulltext_allowed(document))
        self.assertFalse(policy.document_chunk_allowed(document))
        self.assertFalse(policy.document_embedding_allowed(document))

    def test_embedding_denied_still_permits_chunk_indexing(self) -> None:
        document = _document(embedding_allowed=False)
        self.assertTrue(policy.document_chunk_allowed(document))
        self.assertFalse(policy.document_embedding_allowed(document))

    def test_denied_document_blocks_metadata_and_everything_derived(self) -> None:
        document = _document(license_policy_status="denied")
        self.assertFalse(policy.document_metadata_allowed(document))
        self.assertFalse(policy.document_fulltext_allowed(document))
        self.assertFalse(policy.document_chunk_allowed(document))
        self.assertFalse(policy.document_embedding_allowed(document))

    def test_chunk_eligible_requires_both_its_own_status_and_document_permission(self) -> None:
        allowed_document = _document()
        chunk_blocked_document = _document(chunk_storage_allowed=False)

        self.assertTrue(policy.chunk_allowed(_chunk(), allowed_document))
        self.assertFalse(policy.chunk_allowed(_chunk(license_policy_status="denied"), allowed_document))
        self.assertFalse(policy.chunk_allowed(_chunk(), chunk_blocked_document))
        self.assertFalse(policy.chunk_allowed(_chunk(), None))

    def test_chunk_embedding_eligible_requires_document_embedding_permission(self) -> None:
        embedding_denied_document = _document(embedding_allowed=False)
        self.assertTrue(policy.chunk_allowed(_chunk(), embedding_denied_document))
        self.assertFalse(policy.chunk_embedding_allowed(_chunk(), embedding_denied_document))
        self.assertTrue(policy.chunk_embedding_allowed(_chunk(), _document()))

    def test_taxonomy_and_observation_records_follow_license_policy_status_only(self) -> None:
        self.assertTrue(policy.record_allowed({"license_policy_status": "allowed"}))
        for status in ("denied", "review_required", "restricted"):
            self.assertFalse(policy.record_allowed({"license_policy_status": status}))


if __name__ == "__main__":
    unittest.main()
