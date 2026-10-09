"""Guard translation identity and seasonal qualifiers across navigation paths."""
from copy import deepcopy
from dataclasses import asdict, replace
from pathlib import Path
import importlib.util
import json
import unittest
from unittest.mock import Mock, patch

from robingraph.retrieval.subspecies import subspecies_for, subspecies_metadata
from robingraph.retrieval.subspecies_ranges import range_reviews, reviewed_range
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


class RangeReviewTest(unittest.TestCase):
    def setUp(self):
        self.parent = LineageTaxon('parent', 'species', 'Struthio camelus', None, '타조')
        self.child = LineageTaxon('avilist-taxon:v2025b:6', 'subspecies', 'Struthio camelus syriacus', None)
        self.lineage = TaxonomyLineage('타조', 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b', (self.parent,self.child))
        self.raw = 'formerly Syrian and Arabian desert; extinct ca. 1966'
        self.row = dict(taxon=asdict(self.child), range_text=self.raw,
                        source_url='https://explore.avilist.org/data/avilist-2025b.json',source_name='AviList')

    def test_extinction_preserved_in_caption_and_full_description_shared_with_profile(self):
        repo=Mock();repo._run.return_value=[self.row]
        shown=subspecies_for(repo,lambda _:self.lineage,'타조')['subspecies'][0]
        self.assertIn('약 1966년 멸종',range_reviews()[self.child.taxon_id]['caption'])
        self.assertIn('과거',shown['description'])
        self.assertEqual(self.raw,shown['range_text'])
        self.assertIsNone(shown['korean_name'])
        self.assertEqual(shown,subspecies_metadata(repo,self.lineage)['display_taxon'])

    def test_changed_identity_release_source_and_missing_source_do_not_reuse_translation(self):
        for taxon,lin,raw,status in (
            ({**asdict(self.child),'scientific_name':'Wrong identity'},self.lineage,self.raw,'stale-review'),
            (asdict(self.child),replace(self.lineage,taxonomy_release='v2026'),self.raw,'stale-review'),
            (asdict(self.child),replace(self.lineage,concept_set_id='other'),self.raw,'stale-review'),
            (asdict(self.child),self.lineage,self.raw+' changed','stale-review'),
            ({**asdict(self.child),'taxon_id':'unknown'},self.lineage,self.raw,'pending-review'),
            (asdict(self.child),self.lineage,'','missing-source'),
        ):
            with self.subTest(status=status,taxon=taxon):
                review,actual=reviewed_range(taxon,lin,raw)
                self.assertIsNone(review);self.assertEqual(status,actual)

    def test_unreviewed_conflict_failed_or_invalid_records_cannot_be_served_as_korean(self):
        for status in ('pending-review','conflict','translation-failed','unexpected'):
            reviews=deepcopy(range_reviews());reviews[self.child.taxon_id]['status']=status
            with patch('robingraph.retrieval.subspecies_ranges.range_reviews',return_value=reviews):
                repo=Mock();repo._run.return_value=[self.row]
                shown=subspecies_for(repo,lambda _:self.lineage,'타조')['subspecies'][0]
                self.assertEqual('en',shown['description_language'])
                self.assertEqual(self.raw,shown['description'])
        reviews=deepcopy(range_reviews());reviews[self.child.taxon_id]['caption']=''
        with patch('robingraph.retrieval.subspecies_ranges.range_reviews',return_value=reviews):
            self.assertEqual((None,'invalid-review'),reviewed_range(asdict(self.child),self.lineage,self.raw))

    def test_long_seasonal_and_introduced_ranges_keep_qualifiers(self):
        reviews=range_reviews()
        mallard=reviews['avilist-taxon:v2025b:545']['description']
        for word in ('번식','월동','도입','교잡','바하칼리포르니아','쿠바'):
            self.assertIn(word,mallard)
        self.assertIn('도입',reviews['avilist-taxon:v2025b:8']['description'])
        self.assertIn('겨울',reviews['avilist-taxon:v2025b:11251']['description'])
        self.assertIn('가능성',reviews['avilist-taxon:v2025b:11259']['description'])

    def test_build_rejects_changed_source(self):
        spec=importlib.util.spec_from_file_location('build_ranges',Path(__file__).resolve().parents[1]/'scripts/build_subspecies_ranges.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        reviews=json.loads((Path(__file__).resolve().parents[1]/'data/review/subspecies-range-ko.json').read_text(encoding='utf-8'))
        with self.assertRaisesRegex(ValueError,'Snapshot changed'):
            module.build(b'[]',reviews)

    def test_candidate_translation_is_not_promoted_to_reviewed(self):
        spec=importlib.util.spec_from_file_location('build_ranges',Path(__file__).resolve().parents[1]/'scripts/build_subspecies_ranges.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        from hashlib import sha256
        row=['6','subspecies',None,None,None,'Struthio camelus syriacus',None,None,None,None,None,None,None,self.raw]
        content=json.dumps([row]).encode()
        source=dict(schema_version=1,reviewer='test',review_method='test',phrases={self.raw:dict(description='unreviewed candidate',caption='candidate')})
        with patch.object(module,'SOURCE_SHA256',sha256(content).hexdigest()):
            bundle,report,ledger=module.build(content,source)
        self.assertEqual('pending-review',bundle['reviews'][self.child.taxon_id]['status'])
        with patch('robingraph.retrieval.subspecies_ranges.range_reviews',return_value=bundle['reviews']):
            self.assertEqual((None,'pending-review'),reviewed_range(asdict(self.child),self.lineage,self.raw))
        self.assertEqual(1,report['counts']['pending-review'])
        self.assertEqual('pending-review',ledger[0]['status'])
