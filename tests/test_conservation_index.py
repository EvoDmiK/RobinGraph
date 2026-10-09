"""Fail closed when public assessment evidence does not match AviList concepts."""
from copy import deepcopy
from hashlib import sha256
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from xml.etree import ElementTree as ET
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build_conservation_index', ROOT / 'scripts/build_conservation_index.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


class ConservationIndexTest(unittest.TestCase):
    def setUp(self):
        self.avilist = [['1', 'species', None, None, None, 'Anas platyrhynchos',
                         'Linnaeus, 1758', None, None, None, None, None, None,
                         None, None, 'LC', 'https://datazone.birdlife.org/species/factsheet/22680186']]
        self.citation = ('BirdLife International. 2025. Anas platyrhynchos. '
                         'The IUCN Red List of Threatened Species 2025: e.T22680186A281835571. '
                         'https://dx.doi.org/10.2305/IUCN.UK.2025-2.RLTS.T22680186A281835571.en')
        self.core = [['22680186', 'Anas platyrhynchos Linnaeus, 1758', 'ANIMALIA',
                      'CHORDATA', 'AVES', 'ANSERIFORMES', 'ANATIDAE', 'Anas',
                      'platyrhynchos', 'Linnaeus, 1758', 'species', '', 'accepted',
                      '22680186', self.citation, 'https://www.iucnredlist.org/species/22680186/281835571']]
        self.distributions = [['22680186', '', 'Global', self.citation, '', 'Least Concern', 'Present']]
        self.eml = ET.fromstring(f'''<eml><dataset><title>{builder.TITLE}</title>
            <creator><organizationName>{builder.PUBLISHER}</organizationName></creator>
            <pubDate>2026-07-28</pubDate><licensed><identifier>CC-BY-4.0</identifier></licensed>
            <intellectualRights><para><ulink url="http://creativecommons.org/licenses/by/4.0/legalcode"/></para></intellectualRights>
            </dataset><additionalMetadata><metadata><gbif><citation>IUCN (2026). Version 2026-1.
            https://doi.org/10.15468/0qnb58</citation></gbif></metadata></additionalMetadata></eml>''')
        ns = builder.NAMESPACE['a']
        self.descriptor = ET.Element(f'{{{ns}}}archive')
        for tag, rowtype, filename, fields in (
            ('core', builder.DWC + 'Taxon', 'taxon.txt', builder.CORE_FIELDS),
            ('extension', builder.GBIF + 'Distribution', 'distribution.txt', builder.DISTRIBUTION_FIELDS),
        ):
            element = ET.SubElement(self.descriptor, f'{{{ns}}}{tag}', {
                'rowType': rowtype, 'fieldsTerminatedBy': '\\t',
                'ignoreHeaderLines': '0', 'encoding': 'utf-8'})
            files = ET.SubElement(element, f'{{{ns}}}files')
            ET.SubElement(files, f'{{{ns}}}location').text = filename
            ET.SubElement(element, f'{{{ns}}}' + ('id' if tag == 'core' else 'coreid'), {'index': '0'})
            for index, field in enumerate(fields, 1):
                ET.SubElement(element, f'{{{ns}}}field', {'index': str(index), 'term': field})

    def source_bytes(self):
        content = io.BytesIO()
        with ZipFile(content, 'w') as archive:
            archive.writestr('eml.xml', ET.tostring(self.eml))
            archive.writestr('meta.xml', ET.tostring(self.descriptor))
            for name, rows in (('taxon.txt', self.core), ('distribution.txt', self.distributions)):
                archive.writestr(name, ''.join('\t'.join(row) + '\n' for row in rows))
        return content.getvalue()

    def build(self):
        taxonomy = json.dumps(self.avilist).encode()
        archive = self.source_bytes()
        with patch.object(builder, 'AVILIST_SHA256', sha256(taxonomy).hexdigest()), \
                patch.object(builder, 'SOURCE_SHA256', sha256(archive).hexdigest()):
            return builder.build_index(taxonomy, archive)

    def assert_excluded(self, reason, count=1):
        index = self.build()
        self.assertEqual({}, index['taxa'])
        self.assertEqual({reason: count}, index['coverage']['excluded_reasons'])

    def test_exact_identity_produces_individual_assessment_and_release_provenance(self):
        index = self.build()
        record = index['taxa']['avilist-taxon:v2025b:1']
        self.assertEqual('LC', record['category'])
        self.assertEqual(22680186, record['sis_id'])
        self.assertEqual(281835571, record['assessment_id'])
        self.assertEqual(2025, record['assessment_year'])
        self.assertEqual('exact', record['authority_match_method'])
        self.assertEqual('2026-1', index['source']['release'])
        self.assertEqual('2026-07-28', index['source']['published_at'])
        self.assertEqual('CC BY 4.0', index['source']['license_name'])
        self.assertEqual(1, index['coverage']['mapped_species'])
        self.assertEqual({}, index['coverage']['excluded_reasons'])
        self.assertEqual(index, self.build())

    def test_changed_pinned_bytes_are_rejected_before_parsing(self):
        archive = self.source_bytes()
        with self.assertRaisesRegex(ValueError, 'AviList snapshot changed'):
            builder.build_index(b'[]', archive)
        taxonomy = json.dumps(self.avilist).encode()
        with patch.object(builder, 'AVILIST_SHA256', sha256(taxonomy).hexdigest()):
            with self.assertRaisesRegex(ValueError, 'IUCN GBIF snapshot changed'):
                builder.build_index(taxonomy, archive)

    def test_license_must_explicitly_be_cc_by_4(self):
        for field, replacement in (('dataset/licensed/identifier', 'CC-BY-NC-4.0'),
                                   ('dataset/licensed/identifier', '')):
            with self.subTest(value=replacement):
                self.eml.find(field).text = replacement
                with self.assertRaisesRegex(ValueError, 'license must be explicit'):
                    self.build()
        self.eml.find('dataset/licensed/identifier').text = 'CC-BY-4.0'
        self.eml.find('dataset/intellectualRights/para/ulink').set('url', 'https://example.org/license')
        with self.assertRaisesRegex(ValueError, 'license must be explicit'):
            self.build()

    def test_source_publisher_and_release_must_match(self):
        for field, replacement in (('dataset/creator/organizationName', 'Other publisher'),
                                   ('additionalMetadata/metadata/gbif/citation', 'Version 2025-2.')):
            original = self.eml.find(field).text
            self.eml.find(field).text = replacement
            with self.assertRaises(ValueError):
                self.build()
            self.eml.find(field).text = original

    def test_descriptor_schema_and_row_width_must_match(self):
        core = self.descriptor.find('a:core', builder.NAMESPACE)
        core.find('a:field', builder.NAMESPACE).set('term', 'http://example.org/unverified')
        with self.assertRaisesRegex(ValueError, 'archive fields'):
            self.build()
        core.find('a:field', builder.NAMESPACE).set('term', builder.CORE_FIELDS[0])
        self.core[0].append('extra')
        with self.assertRaisesRegex(ValueError, 'row width'):
            self.build()

    def test_descriptor_identity_column_cannot_move(self):
        self.descriptor.find('a:core/a:id', builder.NAMESPACE).set('index', '1')
        with self.assertRaisesRegex(ValueError, 'identity column'):
            self.build()

    def test_ne_never_inherits_a_matching_source_grade(self):
        self.avilist[0][15] = 'NE'
        self.assert_excluded('avilist_ne_requires_concept_review')

    def test_empty_birdlife_reference_is_not_repaired_with_name_only_match(self):
        self.avilist[0][16] = ''
        self.assert_excluded('missing_birdlife_exact_link')

    def test_changed_scientific_name_is_not_mapped_through_same_sis_id(self):
        self.avilist[0][5] = 'Anas changed'
        self.assert_excluded('scientific_name_mismatch')

    def test_invalid_or_shared_birdlife_links_fail_closed(self):
        self.avilist[0][16] = 'https://example.org/22680186'
        self.assert_excluded('invalid_or_ambiguous_birdlife_exact_link')
        self.setUp()
        other = deepcopy(self.avilist[0]); other[0] = '2'; other[5] = 'Anas other'
        self.avilist.append(other)
        self.assert_excluded('invalid_or_ambiguous_birdlife_exact_link', 2)

    def test_duplicate_avilist_identity_fails_closed(self):
        self.avilist.append(deepcopy(self.avilist[0]))
        self.assert_excluded('ambiguous_avilist_identity', 2)

    def test_duplicate_source_sis_fails_closed(self):
        self.core.append(deepcopy(self.core[0]))
        self.assert_excluded('duplicate_source_sis_id')

    def test_duplicate_source_binomial_fails_closed(self):
        other = deepcopy(self.core[0]); other[0] = '99'; other[13] = '99'
        self.core.append(other)
        self.assert_excluded('ambiguous_source_identity')

    def test_nonaccepted_or_nonbird_or_infraspecific_source_is_not_used(self):
        for index, value in ((12, 'synonym'), (4, 'MAMMALIA'), (10, 'subspecies')):
            original = self.core[0][index]; self.core[0][index] = value
            self.assert_excluded('no_accepted_source_bird_species')
            self.core[0][index] = original

    def test_authority_space_and_case_normalization_preserves_parentheses_and_year(self):
        self.avilist[0][6] = ' LINNAEUS,   1758 '
        self.assertEqual(1, self.build()['coverage']['mapped_species'])
        for authority in ('(Linnaeus, 1758)', 'Linnaeus, 1759', ''):
            self.avilist[0][6] = authority
            self.assert_excluded('authority_mismatch')

    def test_single_author_omitted_initials_preserves_raw_authorship(self):
        for initials in ('C', 'J-FÉ', 'A. J. D.'):
            with self.subTest(initials=initials):
                self.avilist[0][6] = f'Linnaeus, {initials}, 1758'
                record = next(iter(self.build()['taxa'].values()))
                self.assertEqual('single_author_initials_omitted', record['authority_match_method'])
                self.assertEqual(self.avilist[0][6], record['authority'])
                self.assertEqual('Linnaeus, 1758', record['assessment_authority'])
        self.avilist[0][6] = '(Linnaeus, C, 1758)'
        self.core[0][9] = '(Linnaeus, 1758)'
        self.assertEqual(1, self.build()['coverage']['mapped_species'])

    def test_omitted_initials_never_changes_year_parentheses_author_or_multi_author(self):
        for avilist, assessment in (
            ('Linnaeus, C, 1758', 'Linnaeus, 1759'),
            ('(Linnaeus, C, 1758)', 'Linnaeus, 1758'),
            ('Linnaeus, C, 1758', '(Linnaeus, 1758)'),
            ('Linnaeus, C, 1758', 'Other, 1758'),
            ('Linnaeus, c, 1758', 'Linnaeus, 1758'),
            ('Linnaeus, C1, 1758', 'Linnaeus, 1758'),
            ('Linnaeus; Other, C, 1758', 'Linnaeus; Other, 1758'),
            ('Linnaeus & Other, C, 1758', 'Linnaeus & Other, 1758'),
            ('Linnaeus et al., C, 1758', 'Linnaeus et al., 1758'),
            ('Linnaeus, C; Other, AB, 1758', 'Linnaeus & Other, 1758'),
            (' , C, 1758', ' , 1758'),
            ('Linnaeus, ..., 1758', 'Linnaeus, 1758'),
        ):
            with self.subTest(avilist=avilist, assessment=assessment):
                self.avilist[0][6] = avilist; self.core[0][9] = assessment
                self.assert_excluded('authority_mismatch')
        self.avilist[0][6] = 'Linnaeus & Other, 1758'
        self.core[0][9] = 'Linnaeus & Other, 1758'
        record = next(iter(self.build()['taxa'].values()))
        self.assertEqual('exact', record['authority_match_method'])

    def test_only_one_global_assessment_is_eligible(self):
        original = deepcopy(self.distributions)
        self.distributions[0][2] = 'Europe'
        self.assert_excluded('missing_or_ambiguous_global_assessment')
        self.distributions = original + deepcopy(original)
        self.assert_excluded('missing_or_ambiguous_global_assessment')

    def test_category_and_assessment_ids_must_be_supported_and_agree(self):
        self.distributions[0][5] = 'Possibly Extinct'
        self.assert_excluded('unsupported_source_category')
        self.distributions[0][5] = 'Least Concern'
        self.core[0][15] = 'https://www.iucnredlist.org/species/99/281835571'
        self.assert_excluded('assessment_identity_or_citation_mismatch')
        self.core[0][15] = 'https://www.iucnredlist.org/species/22680186/281835571'
        self.distributions[0][3] = 'Different citation'
        self.assert_excluded('assessment_identity_or_citation_mismatch')

    def test_missing_or_conflicting_citation_year_is_not_filled_from_dataset_release(self):
        for citation in (self.citation.replace('Species 2025:', 'Species unknown:'),
                         self.citation.replace('IUCN.UK.2025-', 'IUCN.UK.2024-')):
            self.core[0][14] = citation; self.distributions[0][3] = citation
            record = next(iter(self.build()['taxa'].values()))
            self.assertNotIn('assessment_year', record)

    def test_dd_is_preserved_and_taxonomy_cr_qualifier_is_not_fabricated_in_source(self):
        self.avilist[0][15] = 'DD'; self.distributions[0][5] = 'Data Deficient'
        record = next(iter(self.build()['taxa'].values()))
        self.assertEqual('DD', record['category'])
        self.assertEqual(self.citation, record['assessment_citation'])
        self.avilist[0][15] = 'CR (PEW)'; self.distributions[0][5] = 'Critically Endangered'
        record = next(iter(self.build()['taxa'].values()))
        self.assertEqual('CR', record['category'])
        self.assertEqual('CR (PEW)', record['taxonomy_category_raw'])
        self.assertNotIn('qualifier', record)

    def test_packaged_index_has_consistent_coverage_and_no_ne_or_invented_flags(self):
        index = json.loads((ROOT / 'src/robingraph/retrieval/conservation_index.json').read_text(encoding='utf-8'))
        self.assertEqual(builder.SOURCE_SHA256, index['source']['snapshot_sha256'])
        self.assertEqual(builder.AVILIST_SHA256, index['taxonomy_snapshot_sha256'])
        coverage = index['coverage']
        self.assertEqual(len(index['taxa']), coverage['mapped_species'])
        self.assertEqual(coverage['active_species'], coverage['mapped_species'] + sum(coverage['excluded_reasons'].values()))
        records = list(index['taxa'].values())
        self.assertEqual(len(records), len({record['sis_id'] for record in records}))
        for key, record in index['taxa'].items():
            with self.subTest(taxon=key):
                self.assertRegex(key, r'^avilist-taxon:v2025b:[1-9][0-9]*$')
                self.assertIn(record['category'], builder.CATEGORIES.values())
                self.assertNotEqual('NE', record['taxonomy_category_raw'])
                self.assertNotIn('qualifier', record)
                self.assertEqual(record['authority_match_method'], builder._authority_match(record['authority'], record['assessment_authority']))
        self.assertNotIn('Pica serica', {record['scientific_name'] for record in records})
        self.assertNotIn('Pica pica', {record['scientific_name'] for record in records})


if __name__ == '__main__':
    unittest.main()
