"""Real workbook extract coverage and safe interpretation of compiled traits."""
from dataclasses import replace
from pathlib import Path
import json
import tempfile
from unittest import TestCase
from unittest.mock import patch

from robingraph.retrieval import birdbase as bb
from robingraph.retrieval.species_profile import LABELS, species_summary, species_sections
from tests.test_trait_mapping import lineage


def get_lineage(name):
    return lineage(next(e for e in bb.birdbase_index().values() if e['target_name'] == name))


class BirdbaseTraitsTests(TestCase):
    def test_all_11131_and_all_baseline_503_have_attributed_habitat(self):
        index = bb.birdbase_index()
        self.assertEqual(len(index), 11131)
        baseline = json.loads(Path('docs/verification/assets/2026-10-09-active-species-runtime-audit.json').read_text())
        missing = {s['scientific_name'] for s in baseline['species'] if not s['trait_names']}
        resolved = []
        for entry in index.values():
            values = bb.birdbase_traits(lineage(entry), [], LABELS)
            self.assertIn('habitat', {t['name'] for t in values})
            for t in values:
                self.assertTrue(t['display'])
                self.assertNotIn('확인 필요', t['display'])
                self.assertEqual(t['evidence_kind'], 'packaged_source_extract')
                self.assertIsNone(t['source_record_id'])
            if entry['target_name'] in missing: resolved.append(entry['target_name'])
        self.assertEqual(len(resolved), 503)

    def test_published_mass_summary_not_sample_mean_and_all_bounds_preserved(self):
        lin = get_lineage('Parus cinereus'); values = bb.birdbase_traits(lin, [], LABELS)
        mass = next(t for t in values if t['name'] == 'body_mass')
        self.assertEqual(mass['value'], 16.55)
        self.assertEqual(mass['summary_statistic'], 'literature_bounds_mean')
        self.assertEqual(mass['source_mass_bounds']['Unsexed MinMass'], 11)
        self.assertEqual(mass['source_mass_bounds']['Unsexed MaxMass'], 22.1)
        self.assertEqual(len(mass['source_mass_bounds']), 6)
        text = species_summary({'scientific_name': 'Parus cinereus'}, values)
        self.assertIn('문헌 범위값 평균', text)
        self.assertNotIn('표본 평균', text)
        basic = species_sections({'scientific_name': 'Parus cinereus'}, values, {})[0]['items']
        self.assertTrue(any('문헌 범위값 평균' in x['text'] for x in basic))

    def test_interpolated_diet_is_marked_in_both_structured_and_prose(self):
        e = next(e for e in bb.birdbase_index().values() if e['diet_literature'] == 0 and e['diet_category'] in bb.DIET_LABELS)
        values = bb.birdbase_traits(lineage(e), [], LABELS)
        diet = next(t for t in values if t['name'] == 'diet_category')
        self.assertTrue(diet['inferred'])
        self.assertIn('Diet_Lit=0', diet['source_note'])
        self.assertIn('(추정값)', species_summary({'scientific_name': e['target_name']}, values))
        self.assertIn('(추정값)', json.dumps(species_sections({}, values, {}), ensure_ascii=False))
        self.assertNotIn('diet_distribution', {t['name'] for t in values})

    def test_unknown_diet_and_missing_mass_never_become_zero_or_estimated(self):
        e = next(e for e in bb.birdbase_index().values() if e['body_mass'] is None and e['diet_category'] == 'No Information')
        values = bb.birdbase_traits(lineage(e), [], LABELS)
        self.assertEqual([t['name'] for t in values], ['habitat'])

    def test_existing_traits_never_overwritten(self):
        prior = {'name': 'body_mass', 'value': 123, 'inferred': False}
        result = bb.birdbase_traits(get_lineage('Parus cinereus'), [prior], LABELS)
        self.assertEqual([t for t in result if t['name'] == 'body_mass'], [prior])

    def test_revoked_source_changed_taxonomy_and_tamper_fail_closed(self):
        lin = get_lineage('Parus cinereus')
        with patch.object(bb, 'source_allowed', return_value=False):
            self.assertEqual(bb.birdbase_traits(lin, [], LABELS), [])
        self.assertEqual(bb.birdbase_traits(replace(lin, taxonomy_release='other'), [], LABELS), [])
        bb.birdbase_index.cache_clear()
        with patch.object(Path, 'read_bytes', return_value=b'{}'):
            self.assertEqual(bb.birdbase_index(), {})
        bb.birdbase_index.cache_clear()

    def test_registry_disabled_and_duplicate_source_rejected(self):
        records = json.loads(Path('config/source-registry.json').read_text())
        source = next(r for r in records if r['source_id'] == bb.SOURCE_ID)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'source-registry.json'
            for i, data in enumerate(([source], [{**source, 'enabled': False}], [source, source])):
                path.write_text(json.dumps(data))
                self.assertEqual(bb._registry_allowed(str(path), i, len(data)), i == 0)

    def test_mapping_requires_unique_explicit_avilist_name_and_family(self):
        import sys
        sys.path.insert(0, str(Path('scripts').resolve()))
        from build_birdbase_traits import build
        target = {'Taxon_rank': 'species', 'Scientific_name': 'Target species', 'Sequence': '1', 'Family': 'Targetidae', 'AvibaseID': 'avibase-12345678'}
        wrong_family = {'AviList v1 2025': 'Target species', 'Family AviList v1 2025': 'Otheridae'}
        with self.assertRaisesRegex(ValueError, 'family mismatch'):
            build([target], [wrong_family])
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            build([target], [wrong_family, wrong_family])
        with self.assertRaisesRegex(ValueError, 'sets differ'):
            build([target], [])
