"""Pure license policy decisions shared by the fixture loader and the graph loader.

License status is decided per record (`license_policy_status`) and, for documents,
further narrowed by per-document tri-state flags (`fulltext_storage_allowed`,
`chunk_storage_allowed`, `embedding_allowed`). A document's metadata is never
withheld because of those flags -- only the derived chunk/embedding content is.
A chunk therefore requires both its own `allowed` status and its parent
document's chunk permission; nothing here is specific to any one taxon,
document, or source.
"""

from __future__ import annotations

from typing import Any


ALLOWED = "allowed"


def record_allowed(record: dict[str, Any]) -> bool:
    """True when a taxonomy or observation record may enter the retrieval corpus."""

    return record.get("license_policy_status") == ALLOWED


def document_metadata_allowed(document: dict[str, Any]) -> bool:
    """True when a document's title/citation metadata may be shown at all."""

    return document.get("license_policy_status") == ALLOWED


def document_fulltext_allowed(document: dict[str, Any]) -> bool:
    """True when the document's full text may be retained beyond metadata."""

    return document_metadata_allowed(document) and bool(document.get("fulltext_storage_allowed"))


def document_chunk_allowed(document: dict[str, Any]) -> bool:
    """True when chunks derived from this document may be indexed and cited."""

    return document_fulltext_allowed(document) and bool(document.get("chunk_storage_allowed"))


def document_embedding_allowed(document: dict[str, Any]) -> bool:
    """True when chunks derived from this document may be embedded."""

    return document_chunk_allowed(document) and bool(document.get("embedding_allowed"))


def chunk_allowed(chunk: dict[str, Any], document: dict[str, Any] | None) -> bool:
    """True when a chunk may enter the retrieval corpus.

    Requires the chunk's own status to be allowed *and* its parent document to
    permit chunk storage. A missing parent document (e.g. an orphaned or
    unresolved `document_id`) is always denied.
    """

    if document is None:
        return False
    return record_allowed(chunk) and document_chunk_allowed(document)


def chunk_embedding_allowed(chunk: dict[str, Any], document: dict[str, Any] | None) -> bool:
    """True when a chunk may be embedded, independent of chunk-index eligibility."""

    if document is None:
        return False
    return chunk_allowed(chunk, document) and document_embedding_allowed(document)
