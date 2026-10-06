from dataclasses import asdict, replace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from robingraph.api.app import create_app
from robingraph.retrieval.similar_species import (
    CANDIDATES_QUERY, ECOLOGY_QUERY, METHOD, similar_species,
)
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage


FAMILY = LineageTaxon('family', 'family', 'Anatidae', None)
GENUS = LineageTaxon('genus', 'genus', 'Anas', None)
TARGET = LineageTaxon('target', 'species', 'Anas platyrhynchos', None, '청둥오리')
LINEAGE = TaxonomyLineage(TARGET.scientific_name, 'AviList', 'v2025b', 'active', (FAMILY, GENUS, TARGET))
SOURCE = {'source_url':'https://example.org/taxonomy', 'source_name':'AviList'}
HABITAT = {'name':'habitat','value':'Wetland','inferred':False,'source_url':'https://example.org/target',
           'source_name':'AVONET','citation':'target row','dataset_id':'avonet','release':'2022'}


class FakeRepository:
    def __init__(self, candidates, ecology):
        self.candidates = candidates
        self.ecology = ecology
        self.calls = []

    def _korean_dataset_id(self):
        return 'active-korean'

    def _run(self, query, **params):
        self.calls.append((query,params))
        if 'snapshot_uri AS source_url' in query:
            return [SOURCE]
        if query == CANDIDATES_QUERY:
            return self.candidates
        if 'UNWIND $categories' in query:
            return self.ecology
        if 'WHERE peer.id IN $taxon_ids' in query:
            return [{'taxon_id':taxon_id,'korean_name':None,'english_name':None}
                    for taxon_id in params['taxon_ids']]
        raise AssertionError('Unexpected query')


def candidate(taxon_id, scientific_name, family=False, genus=False):
    return {'taxon_id':taxon_id,'scientific_name':scientific_name,
            'same_family':family,'same_genus':genus}


def ecology(taxon_id):
    return {'taxon_id':taxon_id,'trait_name':'habitat','value':'Wetland','dataset_id':'avonet',
            'release':'2022','source_url':f'https://example.org/{taxon_id}','citation':f'{taxon_id} row'}


class SimilarSpeciesTest(TestCase):
    @patch('robingraph.retrieval.similar_species.read_traits',return_value=[HABITAT])
    def test_full_active_pool_ranks_genus_family_ecology_and_deterministic_ties(self, traits):
        rows = [candidate('outside','Outside alba'),candidate('family-b','Family beta',True),
                candidate('genus','Genus alpha',True,True),candidate('family-a','Family alpha',True),
                candidate('zero','Zero alba')]
        repository = FakeRepository(rows,[ecology('outside'),ecology('family-b'),ecology('family-a')])
        result = similar_species(repository,Mock(),lambda _:LINEAGE,TARGET.scientific_name)
        self.assertEqual(METHOD,result['ranking']['method'])
        self.assertEqual('active_species',result['ranking']['candidate_scope'])
        self.assertEqual(5,result['ranking']['scanned_count'])
        self.assertEqual(4,result['ranking']['eligible_count'])
        self.assertEqual(['genus','family-a','family-b'],[p['taxon_id'] for p in result['groups'][0]['items']])
        self.assertEqual([60,40,40],[p['similarity_score'] for p in result['groups'][0]['items']])
        self.assertTrue(result['groups'][0]['has_more'])
        self.assertEqual(['same_family','same_genus'],[r['key'] for r in result['groups'][0]['items'][0]['similarity_reasons']])
        self.assertEqual('https://example.org/family-a',result['groups'][0]['items'][1]['similarity_reasons'][-1]['source_url'])
        self.assertEqual('https://example.org/target',result['groups'][0]['items'][1]['similarity_reasons'][-1]['target_source_url'])
        self.assertEqual(1,traits.call_count)
        self.assertNotIn('LIMIT',CANDIDATES_QUERY)
        self.assertNotIn('LIMIT',ECOLOGY_QUERY)
        for clause in ('origin.inferred=false','claim.inferred=false',
                       'originEvidence.source_record_id=origin.source_record_id',
                       'evidence.source_record_id=claim.source_record_id',
                       'claim.source_release=origin.source_release'):
            self.assertIn(clause,ECOLOGY_QUERY)

    @patch('robingraph.retrieval.similar_species.read_traits',return_value=[])
    def test_no_trait_bonus_and_genus_requires_verified_family(self, _traits):
        repository=FakeRepository([candidate('good','Good bird',True,True),
                                   candidate('broken','Broken bird',False,True),
                                   candidate('family','Family bird',True)],[])
        result=similar_species(repository,Mock(),lambda _:LINEAGE,'청둥오리')
        self.assertEqual(['good','family'],[p['taxon_id'] for p in result['groups'][0]['items']])
        self.assertEqual([60,20],[p['similarity_score'] for p in result['groups'][0]['items']])
        self.assertEqual(2,result['ranking']['eligible_count'])
        self.assertFalse(any('UNWIND $categories' in query for query,_ in repository.calls))

    @patch('robingraph.retrieval.similar_species.read_traits',return_value=[])
    def test_winner_beyond_first_twelve_is_scored_before_top_three(self, _traits):
        rows=[candidate(f'f{i}',f'Family {i:02}',True) for i in range(12)]
        rows.append(candidate('late-genus','Late genus',True,True))
        repository=FakeRepository(rows,[])
        result=similar_species(repository,Mock(),lambda _:LINEAGE,'청둥오리')
        self.assertEqual('late-genus',result['groups'][0]['items'][0]['taxon_id'])
        self.assertEqual(13,result['ranking']['scanned_count'])
        self.assertEqual(13,result['ranking']['eligible_count'])

    @patch('robingraph.retrieval.similar_species.read_traits',return_value=[HABITAT])
    def test_duplicate_evidence_scores_once_and_bad_provenance_fails_closed(self, _traits):
        repository=FakeRepository([candidate('peer','Peer bird')],[ecology('peer'),ecology('peer')])
        result=similar_species(repository,Mock(),lambda _:LINEAGE,'청둥오리')
        self.assertEqual(20,result['groups'][0]['items'][0]['similarity_score'])
        self.assertEqual(1,len(result['groups'][0]['items'][0]['similarity_reasons']))
        for changed in ({**ecology('peer'),'dataset_id':'stale'},
                        {**ecology('peer'),'release':'old'},
                        {**ecology('peer'),'source_url':'javascript:bad'}):
            repository.ecology=[changed]
            with self.assertRaises(ValueError):
                similar_species(repository,Mock(),lambda _:LINEAGE,'청둥오리')

    def test_api_generic_uses_ranking_explicit_genus_uses_taxonomy_and_checks_release(self):
        profile={'taxon':asdict(TARGET),'lineage':{'concept_set_id':'active','taxonomy_release':'v2025b'},
                 'traits':[],'sections':[],'warnings':[]}
        ranking={'taxon':asdict(TARGET),'concept_set_id':'active','taxonomy_release':'v2025b',
                 'ranking':{'method':METHOD,'limit':3},'groups':[{'rank':'similarity','label':'그래프 유사도 상위 3종',
                   'source_url':SOURCE['source_url'],'source_name':SOURCE['source_name'],
                   'items':[{'rank':'species','scientific_name':'Anas acuta','korean_name':'고방오리',
                             'similarity_score':80.5,'similarity_rank':1,'similarity_reasons':[
                                 {'key':'same_family','label':'같은 과','points':30,**SOURCE},
                                 {'key':'same_genus','label':'같은 속','points':50,**SOURCE}]}]}]}
        taxonomy={'taxon':asdict(TARGET),'concept_set_id':'active','taxonomy_release':'v2025b',
                  'groups':[{'rank':'genus','label':'같은 속의 새','source_url':SOURCE['source_url'],
                             'source_name':SOURCE['source_name'],'items':[{'rank':'species','scientific_name':'Anas acuta'}]}]}
        similar=Mock(return_value=ranking); related=Mock(return_value=taxonomy)
        client=TestClient(create_app(species_profile_handler=lambda _:profile,
                                     similar_species_handler=similar,related_species_handler=related))
        generic=client.post('/v1/chat',json={'question':'청둥오리와 비슷한 종은 어떤게 있니?'}).json()
        self.assertEqual('answer',generic['disposition'])
        self.assertIn('80.5점',generic['answer_text'])
        self.assertEqual(METHOD,generic['result']['question_answer']['relations']['ranking']['method'])
        similar.assert_called_once_with('청둥오리')
        explicit=client.post('/v1/chat',json={'question':'청둥오리와 같은 속의 새는?'}).json()
        self.assertEqual('answer',explicit['disposition'])
        related.assert_called_once_with('청둥오리')
        similar.return_value={**ranking,'taxonomy_release':'old'}
        stale=client.post('/v1/chat',json={'question':'청둥오리와 비슷한 종은 어떤게 있니?'}).json()
        self.assertEqual('abstain',stale['disposition'])
        self.assertEqual(200,client.get('/v1/taxa/similar',params={'name':'청둥오리'}).status_code)
        self.assertEqual(422,client.get('/v1/taxa/similar',params={'name':' '}).status_code)

    @patch('robingraph.retrieval.similar_species.phylogenetic_relations')
    @patch('robingraph.retrieval.similar_species.read_traits', return_value=[HABITAT])
    def test_weighted_closeness_for_any_species_and_release_is_passed(self, _traits, phylogeny):
        for name in ('Anas zonorhyncha', 'Nycticorax nycticorax', 'Parus major'):
            target = replace(TARGET, scientific_name=name)
            lineage = replace(LINEAGE, items=(FAMILY, GENUS, target))
            reason = {'key':'phylogenetic_clade', 'label':'공통 조상 관계', 'points':0,
                      'shared_ancestor_depth':7, **SOURCE}
            phylogeny.return_value = {'close': reason,
                                     'eco': {**reason, 'shared_ancestor_depth':5}}
            repo = FakeRepository([candidate('eco', 'Alpha bird', True, True),
                                   candidate('close', 'Zeta bird', True, True),
                                   candidate('unknown', 'Unknown bird', True, True)], [ecology('eco')])
            result = similar_species(repo, Mock(), lambda _:lineage, name)
            peers = result['groups'][0]['items']
            self.assertEqual(['close', 'eco', 'unknown'], [p['taxon_id'] for p in peers])
            self.assertEqual([80, 65, 60], [p['similarity_score'] for p in peers])
            self.assertEqual('taxonomy_ecology_fallback', peers[2]['score_basis'])
            self.assertFalse(peers[2]['phylogeny_available'])
            self.assertEqual(50, peers[2]['available_weight'])
            self.assertEqual('phylogenetic_clade', peers[0]['similarity_reasons'][-1]['key'])
            self.assertEqual('v2025b', phylogeny.call_args.args[0])
            self.assertEqual(target.taxon_id, phylogeny.call_args.args[1])
            self.assertEqual(name, phylogeny.call_args.args[2])

    @patch('robingraph.retrieval.similar_species.phylogenetic_relations', return_value={})
    @patch('robingraph.retrieval.similar_species.read_traits', return_value=[HABITAT])
    def test_missing_tree_uses_taxonomy_before_ecology_without_claiming_phylogeny(self, _traits, _phylogeny):
        repo = FakeRepository([candidate('genus', 'Zeta bird', True, True),
                               candidate('family', 'Alpha bird', True)], [ecology('family')])
        result = similar_species(repo, Mock(), lambda _:LINEAGE, 'test')
        peers = result['groups'][0]['items']
        self.assertEqual(['genus', 'family'], [p['taxon_id'] for p in peers])
        self.assertFalse(any(r['key']=='phylogenetic_clade' for p in peers for r in p['similarity_reasons']))

    @patch('robingraph.retrieval.similar_species.phylogenetic_relations')
    @patch('robingraph.retrieval.similar_species.read_traits', return_value=[HABITAT])
    def test_ordinal_closeness_ignores_branch_counts_and_ecology_breaks_clade_ties(self, _traits, phylogeny):
        repo = FakeRepository([candidate('a', 'Alpha bird', True, True),
                               candidate('b', 'Beta bird', True, True),
                               candidate('c', 'Charlie bird', True, True)], [ecology('b')])
        results = []
        for far, close in ((1, 2), (10, 900)):
            phylogeny.return_value = {key: {'key': 'phylogenetic_clade', 'points': 0,
                'shared_ancestor_depth': depth, **SOURCE} for key, depth in (('a', far), ('b', close), ('c', close))}
            peers = similar_species(repo, Mock(), lambda _:LINEAGE, 'test')['groups'][0]['items']
            results.append([(p['taxon_id'], p['similarity_score']) for p in peers])
            for peer in peers:
                self.assertEqual(peer['similarity_score'], sum(r['points'] for r in peer['similarity_reasons']))
        self.assertEqual([('b', 90), ('c', 80), ('a', 55)], results[0])
        self.assertEqual(results[0], results[1])
