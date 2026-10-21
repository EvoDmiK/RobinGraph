"""Pure review-gate core for the AviList v2025b distribution TEST pilot.

The distribution itself is decided only by scripts/build_species_distribution.py;
this module recomputes it from the pinned inputs, binds every input, identity,
policy and target to a deterministic manifest, and checks a review record.
No network, file, PostgreSQL or Neo4j access happens here.

The SHA-256 digests detect local operator mistakes or edits to a prepared
package. They are not an authenticated signature: whoever can rewrite the
package can also recompute them.
"""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
import hashlib
import json
from typing import Any

PIPELINE_ID = 'avilist-distribution-pilot'
MANIFEST_SCHEMA_VERSION = 1
# Allowlist the CLI enforces before opening any connection; bound into the manifest.
TEST_TARGET = {
    'deployment_target': 'test',
    'postgres': {'host': '192.168.219.99', 'port': 5433, 'database': 'robingraph_test',
                 'username': 'robingraph_test_app', 'schema': 'ingest'},
    'neo4j': {'uri': 'bolt://192.168.219.98:7687', 'database': 'neo4j'},
    'api': {'base_url': 'http://127.0.0.1:8000'},
    'domain_projection': False,
}
APPROVAL_FIELDS = frozenset({'manifest_sha256', 'bundle_sha256', 'decision', 'reviewer', 'reviewer_type',
                             'reviewed_at', 'rationale', 'target'})
REVIEWER_TYPES = ('agent', 'human')
RANKS = frozenset({'order', 'family', 'genus', 'species', 'subspecies'})


class SourceVerificationError(ValueError):
    """The source snapshot or its declared provenance differs from the pinned release."""


class AmbiguousIdentityError(ValueError):
    """A species ID or scientific name does not identify exactly one AviList species row."""


class ApprovalError(ValueError):
    """The review record is missing, malformed, not approved or bound to other content."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode('utf-8')


def _digest(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _builder():
    # Same import the CLI uses; requires the repository root on sys.path.
    from scripts import build_species_distribution
    return build_species_distribution


def _verify_source(builder, avilist_bytes: bytes, bundle: Mapping[str, Any]) -> None:
    if builder.sha256(avilist_bytes) != builder.AVILIST_SHA256:
        raise SourceVerificationError('AviList snapshot hash differs from the pinned release')
    source = bundle.get('sources', {}).get(builder.AVILIST_SOURCE['id'])
    if source != builder.AVILIST_SOURCE:
        raise SourceVerificationError('Bundle AviList source metadata differs from the pinned release')
    expected = (builder.TAXONOMY_RELEASE, builder.CONCEPT_SET_ID, builder.AVILIST_SHA256)
    actual = (bundle.get('taxonomy_release'), bundle.get('concept_set_id'),
              bundle.get('inputs', {}).get('avilist_sha256'))
    release = builder.TAXONOMY_RELEASE
    if (actual != expected or not source['url'].endswith(f"/avilist-{release.removeprefix('v')}.json")
            or f'/{release}/' not in source['landing_url']):
        raise SourceVerificationError('Bundle release, concept set or source URL differs from the pinned version')
    if (source['license_name'], source['license_url']) != ('CC BY 4.0', 'https://creativecommons.org/licenses/by/4.0/'):
        raise SourceVerificationError('AviList license is not the reviewed CC BY 4.0 grant')


def _identify_species(builder, avilist_bytes: bytes, bundle: Mapping[str, Any]) -> list[list[str]]:
    """Exact (taxon_id, scientific_name) pairs; checked before the builder so bad rows fail explicitly."""
    try:
        rows = json.loads(avilist_bytes)
    except (UnicodeDecodeError, ValueError) as error:
        raise AmbiguousIdentityError('AviList snapshot is not JSON') from error
    if not isinstance(rows, list):
        raise AmbiguousIdentityError('AviList snapshot is not a row list')
    sequences, by_sequence, by_name, parent = set(), {}, {}, None
    for index, row in enumerate(rows):
        if not isinstance(row, list) or len(row) < 14:
            raise AmbiguousIdentityError(f'AviList row {index} is not a list of at least 14 columns')
        sequence, rank, name = row[0], row[1], row[5]
        if rank not in RANKS:
            raise AmbiguousIdentityError(f'AviList row {index} has unexpected rank {rank!r}')
        if not isinstance(sequence, str) or not sequence.isdigit() or sequence in sequences:
            raise AmbiguousIdentityError(f'AviList row {index} has a missing, malformed or duplicate ID {sequence!r}')
        if not isinstance(name, str) or not name.strip() or name != name.strip():
            raise AmbiguousIdentityError(f'AviList row {sequence} has no exact scientific name')
        sequences.add(sequence)
        if rank == 'subspecies':
            if parent is None or not name.startswith(parent + ' '):
                raise AmbiguousIdentityError(f'Subspecies {name} is not under its current parent species row')
            continue
        # A higher rank ends the current species; a later subspecies needs a new species row.
        parent = None
        if rank != 'species':
            continue
        if name in by_name:
            raise AmbiguousIdentityError(f'Scientific name {name} names more than one species')
        by_sequence[sequence], by_name[name], parent = name, sequence, name
    identities = {builder.taxon_id(sequence): name for sequence, name in by_sequence.items()}
    for section in ('taxa', 'unknown_audit', 'rejected_korea_text'):
        for tid, entry in bundle.get(section, {}).items():
            if identities.get(tid) != entry.get('scientific_name'):
                raise AmbiguousIdentityError(f'{section} entry {tid} does not match exactly one species row')
    return sorted(([tid, name] for tid, name in identities.items()), key=lambda item: int(item[0].rsplit(':', 1)[1]))


def prepare_manifest(avilist_bytes: bytes, ko_names_bytes: bytes, generator_bytes: bytes,
                     bundle: Mapping[str, Any]) -> dict[str, Any]:
    """Recompute the bundle with the real builder and bind it to a deterministic manifest."""
    builder = _builder()
    _verify_source(builder, avilist_bytes, bundle)
    identities = _identify_species(builder, avilist_bytes, bundle)
    names = json.loads(ko_names_bytes)
    rebuilt = builder.build(avilist_bytes, names, builder.sha256(ko_names_bytes), builder.sha256(generator_bytes))
    if canonical_bytes(rebuilt) != canonical_bytes(bundle):
        raise SourceVerificationError('Bundle differs from the builder output for these inputs')
    if len(identities) != bundle['counts']['active_species']:
        raise AmbiguousIdentityError('Species identity count differs from the bundle')
    if bundle['sources']['kos-2025-v2.1']['sha256'] != builder.KOS_SHA256:
        raise SourceVerificationError('KOS label snapshot differs from the pinned list')
    return {
        'schema_version': MANIFEST_SCHEMA_VERSION,
        'pipeline_id': PIPELINE_ID,
        'source': {**builder.AVILIST_SOURCE, 'version': builder.TAXONOMY_RELEASE},
        'inputs': {'avilist_sha256': builder.sha256(avilist_bytes),
                   'ko_names_sha256': builder.sha256(ko_names_bytes),
                   'generator_sha256': builder.sha256(generator_bytes),
                   'kos_sha256': builder.KOS_SHA256},
        'taxonomy': {'release': builder.TAXONOMY_RELEASE, 'concept_set_id': builder.CONCEPT_SET_ID,
                     'species_count': len(identities), 'species_identity_sha256': _digest(identities)},
        'policy_sha256': _digest({'policy': bundle['policy'], 'scope_note': bundle['scope_note'],
                                  'reviewed_outside': [list(item) for item in builder.REVIEWED_OUTSIDE],
                                  'outside_review': builder.OUTSIDE_REVIEW}),
        # The REVIEWED_OUTSIDE list is the builder's agent review, not an independent human review.
        'outside_review_basis': 'agent',
        'target': TEST_TARGET,
        'bundle_sha256': _digest(bundle),
        'counts': bundle['counts'],
        'review': {'required': True, 'reviewer_types': list(REVIEWER_TYPES), 'target': 'test'},
    }


def validate_approval(manifest: Mapping[str, Any], bundle: Mapping[str, Any], approval: Mapping[str, Any]) -> None:
    """Fail closed unless `approval` approves exactly this manifest and bundle for TEST."""
    if not isinstance(approval, Mapping) or set(approval) != APPROVAL_FIELDS:
        raise ApprovalError('Approval record has missing or unexpected fields')
    if manifest.get('pipeline_id') != PIPELINE_ID or manifest.get('target') != TEST_TARGET:
        raise ApprovalError('Manifest is not a TEST pilot manifest')
    if approval['manifest_sha256'] != _digest(manifest):
        raise ApprovalError('Approval is bound to a different manifest')
    if approval['bundle_sha256'] != _digest(bundle) or manifest.get('bundle_sha256') != approval['bundle_sha256']:
        raise ApprovalError('Approval is bound to a different bundle')
    if approval['decision'] != 'approved':
        raise ApprovalError('Review decision is not approved')
    if approval['target'] != 'test':
        raise ApprovalError('Approval target is not TEST')
    if approval['reviewer_type'] not in REVIEWER_TYPES:
        raise ApprovalError('Unknown reviewer type')
    for field in ('reviewer', 'rationale'):
        if not isinstance(approval[field], str) or not approval[field].strip():
            raise ApprovalError(f'Approval {field} is empty')
    reviewed_at = approval['reviewed_at']
    try:
        parsed = datetime.fromisoformat(reviewed_at) if isinstance(reviewed_at, str) else None
    except ValueError:
        parsed = None
    if parsed is None or parsed.utcoffset() is None:
        raise ApprovalError('reviewed_at must be a timezone-qualified ISO timestamp')
