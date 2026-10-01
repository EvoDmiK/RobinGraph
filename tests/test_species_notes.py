import json
import unittest
from unittest.mock import Mock, patch

from robingraph.generation import GeminiAnswerer, GeminiAnswerError
from robingraph.retrieval.species_notes import encyclopedia_excerpt, create_species_notes
from robingraph.retrieval.species_profile import create_species_flow
from tests.test_species_profile import LINEAGE


class SpeciesNotesTest(unittest.TestCase):
    def setUp(self):
        encyclopedia_excerpt.cache_clear()

    def test_article_is_unique_taxon_matched_revision_pinned_and_attributed(self):
        rows = {'results':{'bindings':[{'item':{'value':'http://www.wikidata.org/entity/Q1'},
            'article':{'value':'https://en.wikipedia.org/wiki/Mallard'}}]}}
        page = {'title':'Mallard', 'extract':'Male birds have green heads.',
                'revisions':[{'revid':123}], 'pageprops':{'wikibase_item':'Q1'}}
        with patch('robingraph.retrieval.species_notes._json_get', side_effect=[rows, {'query':{'pages':{'1':page}}}]):
            source = encyclopedia_excerpt('Anas platyrhynchos', 1)
        self.assertEqual('https://en.wikipedia.org/w/index.php?oldid=123', source['source_url'])
        self.assertEqual('CC BY-SA 4.0', source['license_name'])
        for invalid in [{**page, 'pageprops':{'wikibase_item':'Q2'}}, {**page, 'missing':''}, {**page, 'revisions':[]}]:
            encyclopedia_excerpt.cache_clear()
            with patch('robingraph.retrieval.species_notes._json_get', side_effect=[rows, {'query':{'pages':{'1':invalid}}}]):
                self.assertIsNone(encyclopedia_excerpt('Anas platyrhynchos', 1))
        encyclopedia_excerpt.cache_clear()
        with patch('robingraph.retrieval.species_notes._json_get', return_value={'results':{'bindings':rows['results']['bindings'] * 2}}) as get:
            self.assertIsNone(encyclopedia_excerpt('Anas platyrhynchos', 1))
            self.assertEqual(1, get.call_count)

    def test_notes_require_korean_and_actual_supporting_quote(self):
        excerpt = 'The adult male has a green head. Females are brown. The species feeds by dabbling.'
        good = {'appearance':[{'text':'성체 수컷의 머리는 녹색입니다.', 'quote':'The adult male has a green head.'}],
                'fun_facts':[{'text':'물 표면에서 먹이를 찾습니다.', 'quote':'The species feeds by dabbling.'}]}
        answerer = GeminiAnswerer('test')
        def document(value):
            return {'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]}
        with patch.object(answerer, '_request', return_value=document(good)) as request:
            result = answerer.species_notes('Anas platyrhynchos', excerpt)
            self.assertEqual('성체 수컷의 머리는 녹색입니다.', result['appearance'][0]['text'])
            self.assertNotIn('quote', result['appearance'][0])
            self.assertIn('sex, age, season', request.call_args.args[0])
        for item in [{'text':'아무 사실', 'quote':'A made up sentence absent from source.'},
                     {'text':'English only', 'quote':'The adult male has a green head.'},
                     {'text':'한글', 'quote':'too short'}]:
            with patch.object(answerer, '_request', return_value=document({'appearance':[item], 'fun_facts':[]})):
                with self.assertRaises(GeminiAnswerError):
                    answerer.species_notes('Anas platyrhynchos', excerpt)

    def test_cached_notes_keep_source_and_outage_preserves_card(self):
        source = {'text':'The adult male has a green head.', 'source_name':'Wikipedia · Mallard',
                  'source_url':'https://en.wikipedia.org/w/index.php?oldid=123', 'license_name':'CC BY-SA 4.0'}
        summarize = Mock(return_value={'appearance':[{'text':'성체 수컷은 녹색 머리를 가집니다.'}], 'fun_facts':[]})
        with patch('robingraph.retrieval.species_notes.encyclopedia_excerpt', return_value=source):
            notes = create_species_notes(summarize)
            self.assertEqual(notes(LINEAGE), notes(LINEAGE))
            self.assertEqual(1, summarize.call_count)
        flow = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=lambda _: [],
                                   notes=Mock(side_effect=TimeoutError('private details')))
        profile = flow.invoke('청둥오리')
        self.assertEqual(['basic','appearance','ecology','fun_facts'], [s['key'] for s in profile['sections']])
        self.assertEqual([], profile['sections'][-1]['items'])
        self.assertIn('아직 찾지 못했습니다', profile['sections'][-1]['empty_text'])
        self.assertNotIn('private', str(profile))
