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

    @staticmethod
    def document(value):
        return {'candidates':[{'content':{'parts':[{'text':json.dumps(value)}]}}]}

    def test_article_is_unique_taxon_matched_revision_pinned_and_attributed(self):
        rows = {'results':{'bindings':[{'item':{'value':'http://www.wikidata.org/entity/Q1'},
            'article':{'value':'https://en.wikipedia.org/wiki/Mallard'}}]}}
        page = {'title':'Mallard', 'extract':'Male birds have green heads.',
                'revisions':[{'revid':123}], 'pageprops':{'wikibase_item':'Q1'}}
        with patch('robingraph.retrieval.species_notes._json_get', side_effect=[rows, {'query':{'pages':{'1':page}}}]):
            source = encyclopedia_excerpt('Anas platyrhynchos', 1)
        self.assertEqual('https://en.wikipedia.org/w/index.php?oldid=123', source['source_url'])
        self.assertEqual('CC BY-SA 4.0', source['license_name'])
        self.assertEqual('Anas platyrhynchos', source['source_scientific_name'])
        self.assertEqual('Anas platyrhynchos', source['source_scope'])
        self.assertEqual('encyclopedia_taxon', source['source_scope_kind'])
        self.assertEqual({'status':'article_identity_only', 'method':'scientific_name_article_identity',
                          'wikidata_id':'Q1'}, source['taxonomy_alignment'])
        self.assertIn('별도로 검증하지', source['source_note'])
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
            self.assertIn('one subspecies, population', request.call_args.args[0])
            self.assertIn('historical broader species concept', request.call_args.args[0])
            self.assertIn('뺨의 흰색 무늬', request.call_args.args[0])
            self.assertIn('날개의 흰색 띠', request.call_args.args[0])
        for item in [{'text':'아무 사실', 'quote':'A made up sentence absent from source.'},
                     {'text':'English only', 'quote':'The adult male has a green head.'},
                     {'text':'한글', 'quote':'too short'}]:
            with patch.object(answerer, '_request', return_value=document({'appearance':[item], 'fun_facts':[]})):
                with self.assertRaises(GeminiAnswerError):
                    answerer.species_notes('Anas platyrhynchos', excerpt)

    def test_natural_bird_wording_requires_no_rewrite_and_preserves_qualifications(self):
        quote = 'In winter, adult males of the northern subspecies have white cheek patches and two pale wing bars.'
        text = '북부 아종의 성체 수컷은 겨울에 뺨에 흰색 무늬가 있고 날개에 옅은 색 띠가 두 개 있습니다.'
        answerer = GeminiAnswerer('test')
        with patch.object(answerer, '_request', return_value=self.document({
                'appearance':[{'text':text, 'quote':quote}], 'fun_facts':[]})) as request:
            self.assertEqual(text, answerer.species_notes('Example species', quote)['appearance'][0]['text'])
            self.assertEqual(1, request.call_count)

    def test_literal_plumage_is_rewritten_once_against_identical_source_quotes(self):
        quote = 'This bird has a grey back, a black hood, white cheek patches and a white wing bar.'
        behavior = 'The adult birds hide seeds in bark crevices during autumn.'
        draft = {'appearance':[
            {'text':'이 새는 회색 등, 검은색 후드, 흰색 뺨 패치, 흰색 날개 바를 가지고 있습니다.', 'quote':quote},
            {'text':'등은 회색입니다.', 'quote':quote}],
            'fun_facts':[{'text':'성체는 가을에 나무껍질 틈에 씨앗을 숨깁니다.', 'quote':behavior}]}
        repaired = json.loads(json.dumps(draft))
        repaired['appearance'][0]['text'] = '등은 회색이고 머리 부분은 검으며, 뺨에는 흰색 무늬가 있고 날개에는 흰색 띠가 있습니다.'
        answerer = GeminiAnswerer('test')
        with patch.object(answerer, '_request', side_effect=[self.document(draft), self.document(repaired)]) as request:
            result = answerer.species_notes('Parus cinereus', quote + ' ' + behavior)
        self.assertEqual(repaired['appearance'][0]['text'], result['appearance'][0]['text'])
        self.assertEqual(draft['fun_facts'][0]['text'], result['fun_facts'][0]['text'])
        self.assertEqual(2, request.call_count)
        self.assertEqual('species_notes_language_repair', request.call_args.kwargs['operation'])
        repair_input = json.loads(request.call_args.args[0].split('\n', 1)[1])
        self.assertEqual([0], repair_input['repair_appearance_indices'])
        self.assertEqual(quote, repair_input['notes']['appearance'][0]['quote'])

    def test_wording_repair_rejects_changed_quotes_extra_facts_and_still_literal_output(self):
        quote = 'Adult males have a black hood and a white wing bar.'
        other = 'Adult females have brown feathers and no white wing bar.'
        draft = {'appearance':[{'text':'성체 수컷은 검은 후드와 흰 날개 바가 있습니다.', 'quote':quote}],
                 'fun_facts':[]}
        natural = {'appearance':[{'text':'성체 수컷은 머리 부분이 검고 날개에 흰색 띠가 있습니다.', 'quote':quote}],
                   'fun_facts':[]}
        changed_quote = json.loads(json.dumps(natural)); changed_quote['appearance'][0]['quote'] = other
        extra_item = json.loads(json.dumps(natural)); extra_item['appearance'].append(natural['appearance'][0])
        changed_facts = json.loads(json.dumps(natural)); changed_facts['fun_facts'].append({'text':'성체 암컷은 갈색입니다.', 'quote':other})
        for invalid in (draft, changed_quote, extra_item, changed_facts):
            with self.subTest(invalid=invalid):
                answerer = GeminiAnswerer('test')
                with patch.object(answerer, '_request', side_effect=[self.document(draft), self.document(invalid)]) as request:
                    with self.assertRaises(GeminiAnswerError):
                        answerer.species_notes('Example species', quote + ' ' + other)
                self.assertEqual(2, request.call_count)

    def test_unsupported_source_is_rejected_before_any_language_repair(self):
        answerer = GeminiAnswerer('test')
        bad = {'appearance':[{'text':'검은 후드가 있습니다.', 'quote':'A fabricated head color description.'}], 'fun_facts':[]}
        with patch.object(answerer, '_request', return_value=self.document(bad)) as request:
            with self.assertRaises(GeminiAnswerError):
                answerer.species_notes('Example species', 'Adult males have blue feathers and a pale bill.')
        self.assertEqual(1, request.call_count)

    def test_cached_notes_keep_source_and_outage_preserves_card(self):
        source = {'text':'The adult male has a green head.', 'source_name':'Wikipedia · Mallard',
                  'source_url':'https://en.wikipedia.org/w/index.php?oldid=123', 'license_name':'CC BY-SA 4.0',
                  'source_scientific_name':'Anas platyrhynchos', 'source_scope':'Anas platyrhynchos',
                  'source_scope_kind':'encyclopedia_taxon',
                  'taxonomy_alignment':{'status':'article_identity_only', 'method':'scientific_name_article_identity'}}
        summarize = Mock(return_value={'appearance':[{'text':'성체 수컷은 녹색 머리를 가집니다.'}], 'fun_facts':[]})
        with patch('robingraph.retrieval.species_notes.encyclopedia_excerpt', return_value=source):
            notes = create_species_notes(summarize)
            self.assertEqual(notes(LINEAGE), notes(LINEAGE))
            self.assertEqual(1, summarize.call_count)
            self.assertEqual(source['taxonomy_alignment'], notes(LINEAGE)['appearance'][0]['taxonomy_alignment'])
            self.assertEqual(source['source_scientific_name'], notes(LINEAGE)['appearance'][0]['source_scientific_name'])
        flow = create_species_flow(lambda _: LINEAGE, lambda _: [], photos=lambda _: [],
                                   notes=Mock(side_effect=TimeoutError('private details')))
        profile = flow.invoke('청둥오리')
        self.assertEqual(['basic','appearance','ecology','fun_facts'], [s['key'] for s in profile['sections']])
        self.assertEqual([], profile['sections'][-1]['items'])
        self.assertIn('아직 찾지 못했습니다', profile['sections'][-1]['empty_text'])
        self.assertNotIn('private', str(profile))
