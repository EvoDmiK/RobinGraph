"""Review-gate core tests.

Most cases use a tiny synthetic AviList/KOS fixture with the builder's pinned
hashes patched to the fixture: they check the gate logic, not real species data.
Only RealSnapshotTest reads the pinned AviList v2025b snapshot, when present.
"""
from contextlib import contextmanager
import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import build_species_distribution as builder  # noqa: E402
from robingraph.ingest.avilist_pipeline import (  # noqa: E402
    AmbiguousIdentityError, ApprovalError, SourceVerificationError, canonical_bytes, prepare_manifest,
    validate_approval,
)

SNAPSHOT = Path(os.getenv('ROBINGRAPH_AVILIST_SNAPSHOT', '/tmp/rg-avilist-pipeline/avilist-2025b.json'))
GENERATOR = (ROOT / 'scripts' / 'build_species_distribution.py').read_bytes()


def row(sequence, rank, name, range_text=None):
    return [sequence, rank, None, None, None, name, None, None, None, None, None, None, None, range_text]


FIXTURE_ROWS = [
    row('1', 'order', 'Anseriformes'),
    row('10', 'species', 'Anas platyrhynchos', 'North America, Eurasia including Korea'),
    row('11', 'subspecies', 'Anas platyrhynchos conboschas'),
    row('20', 'species', 'Fixtura insularis', 'South Island (New Zealand)'),
    row('30', 'species', 'Fixtura borealis', 'Siberia'),
]
NAMES = {
    'taxonomy_release': builder.TAXONOMY_RELEASE, 'concept_set_id': builder.CONCEPT_SET_ID,
    'source_sha256': builder.KOS_SHA256, 'source_title': 'KOS fixture', 'source_url': 'https://example.invalid/kos',
    'source_download_url': 'https://example.invalid/kos.xlsx',
    'labels': {builder.taxon_id('30'): {'source_sheet': '공식목록', 'source_title': 'KOS fixture',
                                        'scientific_name': 'Fixtura borealis', 'category': '가-1',
                                        'source_row': 7, 'source_scientific_name': 'Fixtura borealis'}},
}
NAMES_BYTES = json.dumps(NAMES, ensure_ascii=False).encode()


def encode(rows):
    return json.dumps(rows).encode()


@contextmanager
def pinned(content):
    """Pin the builder to a fixture snapshot, as if it were the reviewed release."""
    sha = hashlib.sha256(content).hexdigest()
    with mock.patch.object(builder, 'AVILIST_SHA256', sha), \
            mock.patch.dict(builder.AVILIST_SOURCE, {'sha256': sha}), \
            mock.patch.object(builder, 'REVIEWED_OUTSIDE', (('20', 'Fixtura insularis', 'South Island (New Zealand)'),)):
        yield


def build(content):
    # The bundle shares builder.AVILIST_SOURCE, which `pinned` restores in place on exit.
    return copy.deepcopy(builder.build(content, json.loads(NAMES_BYTES), builder.sha256(NAMES_BYTES),
                                       builder.sha256(GENERATOR)))


def approval_for(manifest, bundle, **changes):
    record = {'manifest_sha256': hashlib.sha256(canonical_bytes(manifest)).hexdigest(),
              'bundle_sha256': hashlib.sha256(canonical_bytes(bundle)).hexdigest(),
              'decision': 'approved', 'reviewer': 'claude-agent', 'reviewer_type': 'agent',
              'reviewed_at': '2026-10-19T14:00:00+09:00', 'rationale': 'TEST regeneration of existing bundle',
              'target': 'test'}
    record.update(changes)
    return record


class CanonicalBytesTest(unittest.TestCase):
    def test_key_order_independent_and_rejects_nan(self):
        self.assertEqual(canonical_bytes({'b': 1, 'a': '한'}), canonical_bytes({'a': '한', 'b': 1}))
        self.assertEqual(canonical_bytes({'a': '한'}), '{"a":"한"}'.encode())
        with self.assertRaises(ValueError):
            canonical_bytes({'a': float('nan')})


class PrepareManifestFixtureTest(unittest.TestCase):
    def setUp(self):
        self.content = encode(FIXTURE_ROWS)

    def prepare(self, content=None, bundle=None):
        content = content or self.content
        with pinned(content):
            return prepare_manifest(content, NAMES_BYTES, GENERATOR, bundle or build(content))

    def test_same_inputs_give_identical_manifest(self):
        first, second = self.prepare(), self.prepare()
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        self.assertEqual(first['pipeline_id'], 'avilist-distribution-pilot')
        self.assertEqual(first['target']['deployment_target'], 'test')
        self.assertEqual(first['target']['neo4j']['database'], 'neo4j')
        self.assertEqual(first['target']['api']['base_url'], 'http://127.0.0.1:8000')
        self.assertEqual(first['taxonomy']['species_count'], 3)
        self.assertEqual(first['source']['license_name'], 'CC BY 4.0')
        self.assertEqual(first['outside_review_basis'], 'agent')

    def test_changed_source_fails_closed(self):
        with pinned(self.content):
            bundle = build(self.content)
            changed = self.content.replace(b'Siberia', b'Siberia ')
            with self.assertRaises(SourceVerificationError):
                prepare_manifest(changed, NAMES_BYTES, GENERATOR, bundle)

    def test_tampered_bundle_fails_closed(self):
        with pinned(self.content):
            bundle = build(self.content)
        tampered = copy.deepcopy(bundle)
        tampered['taxa'][builder.taxon_id('20')]['status'] = 'korea'
        with self.assertRaises(SourceVerificationError):
            self.prepare(bundle=tampered)
        relicensed = copy.deepcopy(bundle)
        relicensed['sources']['avilist-v2025b']['license_name'] = 'CC0'
        with self.assertRaises(SourceVerificationError):
            self.prepare(bundle=relicensed)

    def test_changed_local_inputs_fail_closed(self):
        with pinned(self.content):
            bundle = build(self.content)
            with self.assertRaises(SourceVerificationError):
                prepare_manifest(self.content, NAMES_BYTES, GENERATOR + b'\n', bundle)

    def test_duplicate_species_id_or_name_fails_closed(self):
        # The builder keys species by ID and would silently keep the last duplicate row.
        duplicate_id = FIXTURE_ROWS + [row('40', 'species', 'Fixtura altera', 'Siberia'),
                                       row('40', 'species', 'Fixtura tertia', 'Siberia')]
        duplicate_name = FIXTURE_ROWS + [row('40', 'species', 'Fixtura borealis', 'Siberia')]
        for rows in (duplicate_id, duplicate_name):
            with self.subTest(rows=rows[-1][:6]), self.assertRaises(AmbiguousIdentityError):
                self.prepare(content=encode(rows))


    def test_malformed_rows_fail_before_builder(self):
        with pinned(self.content):
            bundle = build(self.content)
        species = FIXTURE_ROWS[1]
        cases = {
            'not_json': b'not json',
            'not_list': b'{}',
            'row_not_list': encode(FIXTURE_ROWS + ['40']),
            'short_row': encode(FIXTURE_ROWS + [row('40', 'species', 'Fixtura brevis')[:13]]),
            'unexpected_rank': encode(FIXTURE_ROWS + [row('40', 'tribe', 'Fixturini')]),
            'integer_id': encode(FIXTURE_ROWS + [row(40, 'species', 'Fixtura altera')]),
            'non_digit_id': encode(FIXTURE_ROWS + [row('4a', 'species', 'Fixtura altera')]),
            'duplicate_id_across_ranks': encode(FIXTURE_ROWS + [row('1', 'genus', 'Fixtura')]),
            'blank_name': encode(FIXTURE_ROWS + [row('40', 'species', ' ')]),
            'padded_name': encode(FIXTURE_ROWS + [row('40', 'species', 'Fixtura altera ')]),
            'orphan_subspecies': encode([FIXTURE_ROWS[0], row('11', 'subspecies', 'Anas platyrhynchos conboschas')]),
            'wrong_parent': encode(FIXTURE_ROWS + [row('31', 'subspecies', 'Anas platyrhynchos domestica')]),
            'no_space_prefix': encode([species, row('11', 'subspecies', 'Anas platyrhynchosa minor')]),
            'subspecies_after_genus': encode([species, row('12', 'genus', 'Fixtura'),
                                              row('13', 'subspecies', 'Anas platyrhynchos minor')]),
        }
        for name, content in cases.items():
            # Bind the bundle to this snapshot so only the row structure can fail.
            claimed = copy.deepcopy(bundle)
            sha = hashlib.sha256(content).hexdigest()
            claimed['sources']['avilist-v2025b']['sha256'] = claimed['inputs']['avilist_sha256'] = sha
            with self.subTest(name), pinned(content), \
                    mock.patch.object(builder, 'build', side_effect=AssertionError('builder reached')), \
                    self.assertRaises(AmbiguousIdentityError):
                prepare_manifest(content, NAMES_BYTES, GENERATOR, claimed)


class ValidateApprovalTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        content = encode(FIXTURE_ROWS)
        with pinned(content):
            cls.bundle = build(content)
            cls.manifest = prepare_manifest(content, NAMES_BYTES, GENERATOR, cls.bundle)

    def test_exact_approval_passes(self):
        validate_approval(self.manifest, self.bundle, approval_for(self.manifest, self.bundle))
        validate_approval(self.manifest, self.bundle, approval_for(self.manifest, self.bundle, reviewer_type='human'))

    def test_missing_or_malformed_approval_is_rejected(self):
        good = approval_for(self.manifest, self.bundle)
        cases = {
            'empty': {},
            'extra_field': {**good, 'signature': 'x'},
            'missing_field': {key: value for key, value in good.items() if key != 'rationale'},
            'rejected': {**good, 'decision': 'rejected'},
            'production': {**good, 'target': 'production'},
            'unknown_reviewer_type': {**good, 'reviewer_type': 'bot'},
            'blank_reviewer': {**good, 'reviewer': ' '},
            'blank_rationale': {**good, 'rationale': ''},
            'naive_time': {**good, 'reviewed_at': '2026-10-19T14:00:00'},
            'bad_time': {**good, 'reviewed_at': 'yesterday'},
        }
        for name, approval in cases.items():
            with self.subTest(name), self.assertRaises(ApprovalError):
                validate_approval(self.manifest, self.bundle, approval)

    def test_tampered_manifest_or_bundle_is_rejected(self):
        approval = approval_for(self.manifest, self.bundle)
        manifest = copy.deepcopy(self.manifest)
        manifest['counts']['korea'] += 1
        with self.assertRaises(ApprovalError):
            validate_approval(manifest, self.bundle, approval)
        retargeted = copy.deepcopy(self.manifest)
        retargeted['target']['postgres']['host'] = '192.168.219.1'
        with self.assertRaises(ApprovalError):
            validate_approval(retargeted, self.bundle, approval_for(retargeted, self.bundle))
        bundle = copy.deepcopy(self.bundle)
        bundle['counts']['outside'] += 1
        with self.assertRaises(ApprovalError):
            validate_approval(self.manifest, bundle, approval)
        with self.assertRaises(ApprovalError):
            validate_approval(self.manifest, bundle, approval_for(self.manifest, bundle))


@unittest.skipUnless(SNAPSHOT.exists(), f'pinned AviList snapshot not present at {SNAPSHOT}')
class RealSnapshotTest(unittest.TestCase):
    """Pinned AviList v2025b bytes with the repository KOS bundle; no network or DB."""

    def test_rebuild_matches_installed_bundle_and_is_deterministic(self):
        content = SNAPSHOT.read_bytes()
        names = (ROOT / 'src/robingraph/retrieval/species_ko_names.json').read_bytes()
        bundle = builder.build(content, json.loads(names), builder.sha256(names), builder.sha256(GENERATOR))
        installed = json.loads((ROOT / 'src/robingraph/retrieval/species_distribution.json').read_bytes())
        self.assertEqual(canonical_bytes(bundle), canonical_bytes(installed))
        first = prepare_manifest(content, names, GENERATOR, bundle)
        second = prepare_manifest(content, names, GENERATOR, installed)
        self.assertEqual(canonical_bytes(first), canonical_bytes(second))
        self.assertEqual(first['taxonomy']['species_count'], 11131)
        rows = json.loads(content)
        self.assertEqual({len(item) for item in rows}, {26})
        self.assertTrue(all(isinstance(item[0], str) for item in rows))
        self.assertEqual({item[1] for item in rows}, {'order', 'family', 'genus', 'species', 'subspecies'})
        self.assertEqual(first['inputs']['avilist_sha256'], builder.AVILIST_SHA256)
        validate_approval(first, bundle, approval_for(first, bundle))


if __name__ == '__main__':
    unittest.main()
