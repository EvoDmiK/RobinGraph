"""Actual pinned extract plus rejection/precedence contracts; no DB mocked as live."""
from copy import deepcopy
import json
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from robingraph.retrieval import avonet_ebird as ae
from robingraph.retrieval.species_profile import LABELS, trait_display
from robingraph.retrieval.reviewed_magpie import reviewed_magpie_traits
from tests.test_trait_mapping import context, lineage


def get_lineage(name):
    e = next(e for e in ae.supplement_index().values() if e['target_name'] == name)
    return lineage(e)


class AvonetEbirdTests(TestCase):
    def supplement(self, name, existing=None, ctx=None):
        return ae.supplement_traits(get_lineage(name), existing or [], ctx or context('avonet'), LABELS, trait_display)

    def test_real_extract_all_615_unique_id_records_and_187_empty_targets(self):
        index = ae.supplement_index()
        self.assertEqual(len(index), 615)
        self.assertEqual(len({e['avibase_id'] for e in index.values()}), 615)
        audit = json.loads(Path('docs/verification/assets/2026-10-09-active-species-runtime-audit.json').read_text())
        empty = {s['scientific_name'] for s in audit['species'] if not s['trait_names']}
        restored = []
        for e in index.values():
            traits = self.supplement(e['target_name'])
            self.assertGreater(len(traits), 0)
            self.assertLessEqual(len(traits), 13)
            self.assertTrue(all(t['taxonomy_alignment']['status'] == 'accepted' for t in traits))
            self.assertTrue(all(t['source_record_id'] is None for t in traits))
            self.assertTrue(all(t['evidence_kind'] == 'packaged_source_extract' for t in traits))
            if e['target_name'] in empty:
                restored.append(e['target_name'])
        self.assertEqual(len(restored), 187)

    def test_pinned_artifact_tampering_fails_closed(self):
        ae.supplement_index.cache_clear()
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            self.assertEqual(ae.supplement_index(), {})
        ae.supplement_index.cache_clear()
        self.assertEqual(len(ae.supplement_index()), 615)

    def test_inferred_magpie_never_replaces_measured_korean_mass(self):
        traits = self.supplement('Pica serica')
        mass = next(t for t in traits if t['name'] == 'body_mass')
        self.assertEqual(mass['value'], 217.5)
        self.assertTrue(mass['inferred'])
        self.assertEqual(mass['summary_statistic'], 'species_estimate')
        self.assertIn('Pica pica', mass['source_note'])
        merged = reviewed_magpie_traits(get_lineage('Pica serica'), traits)
        selected = [t for t in merged if t['name'] == 'body_mass']
        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]['value'], 220.64)
        self.assertEqual(selected[0]['summary_statistic'], 'sample_mean')
        self.assertFalse(selected[0]['inferred'])

    def test_morphology_total_is_not_claimed_as_mass_or_per_trait_sample_size(self):
        entries = list(ae.supplement_index().values())
        entry = next(e for e in entries if float(e['sample_size']) > 0 and e['mass_source'] != 'Inferred')
        traits = self.supplement(entry['target_name'])
        for trait in traits:
            self.assertNotIn('sample_size', trait)
            self.assertEqual(trait['source_morphology_sample_size'], int(float(entry['sample_size'])))
            self.assertIn('개별 형질의 유효 표본수나 체중 문헌의 표본수가 아닙니다', trait['source_note'])
        self.assertTrue(any(t['name'] == 'body_mass' for t in traits))
        self.assertTrue(any(t['name'] == 'habitat' for t in traits))
        self.assertTrue(any(t['unit'] == 'mm' for t in traits))

    def test_existing_verified_values_unchanged(self):
        old = {'name': 'body_mass', 'value': 999, 'inferred': False}
        traits = self.supplement('Stilpnia cucullata', [old])
        self.assertEqual([t for t in traits if t['name'] == 'body_mass'], [old])

    def test_other_taxonomy_or_bad_pin_or_missing_context_rejected(self):
        lin = get_lineage('Stilpnia cucullata')
        self.assertEqual(ae.supplement_traits(lin, [], None, LABELS, trait_display), [])
        ctx = context('avonet'); ctx.release.content_sha256 = 'wrong'
        self.assertEqual(ae.supplement_traits(lin, [], ctx, LABELS, trait_display), [])
        from dataclasses import replace
        for changed in [replace(lin, taxonomy_release='other'), replace(lin, taxonomy_source='other')]:
            self.assertEqual(ae.supplement_traits(changed, [], context('avonet'), LABELS, trait_display), [])

    def test_no_cross_concept_name_match_for_cinereus(self):
        self.assertNotIn('Parus cinereus', {e['target_name'] for e in ae.supplement_index().values()})

    def test_generation_rejects_duplicate_source_or_target_concepts(self):
        import sys
        sys.path.insert(0, str(Path('scripts').resolve()))
        from build_avonet_ebird_supplement import build
        row = {'Avibase.ID2': 'avibase-12345678', 'Species2': 'Old name', '_row': 2, 'Inference': 'NO'}
        target = {'Taxon_rank': 'species', 'Sequence': '1', 'AvibaseID': 'avibase-12345678', 'Scientific_name': 'New name'}
        self.assertEqual(len(build([target], [row], {'entries': []})['entries']), 1)
        self.assertEqual(build([target], [row, row], {'entries': []})['entries'], [])
        self.assertEqual(build([target, target], [row], {'entries': []})['entries'], [])
