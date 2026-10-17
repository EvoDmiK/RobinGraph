"""Scope routing contracts with fake handlers, separate from live DB checks."""
from copy import deepcopy
from dataclasses import replace
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from robingraph.api.app import create_app
from robingraph.retrieval.similar_species import similar_species
from tests.test_similar_species_korean_priority import NameRepository, checked_candidate
from tests.test_similar_species import LINEAGE, TARGET, candidate

CONCEPT = 'rg:concept-set:avilist-v2025b'
PROFILE = {
    'taxon': {'taxon_id':'avilist-taxon:v2025b:544','rank':'species',
              'scientific_name':'Anas platyrhynchos','english_name':'Mallard','korean_name':'청둥오리'},
    'lineage':{'concept_set_id':CONCEPT,'taxonomy_release':'v2025b'},
    'traits':[],'warnings':[], 'summary':'확인된 소개',
}


class SpeciesScopeApiTests(unittest.TestCase):
    def client(self, profile=PROFILE):
        self.reader=Mock(return_value=deepcopy(profile))
        return TestClient(create_app(species_profile_handler=self.reader))

    def test_korea_profile_and_chat_accept_verified_records(self):
        client=self.client()
        body=client.get('/v1/taxa/profile',params={'name':'청둥오리','species_scope':'korea'}).json()
        self.assertEqual('korea',body['taxon']['distribution']['status'])
        body=client.post('/v1/chat',json={'question':'청둥오리에 대해 알려줘','species_scope':'korea'}).json()
        self.assertEqual('answer',body['disposition'])
        self.assertEqual('청둥오리',body['result']['profile']['taxon']['display_name'])

    def test_excluded_profile_returns_404_and_chat_has_no_profile(self):
        for scope in ('outside','unknown'):
            with self.subTest(scope=scope):
                client=self.client()
                self.assertEqual(404,client.get('/v1/taxa/profile',params={'name':'청둥오리','species_scope':scope}).status_code)
                body=client.post('/v1/chat',json={'question':'청둥오리에 대해 알려줘','species_scope':scope}).json()
                self.assertEqual('abstain',body['disposition'])
                self.assertIsNone(body['result']['profile'])

    def test_missing_or_stale_context_is_unknown_not_outside(self):
        for context in ({}, {'concept_set_id':'different','taxonomy_release':'v2025b'}):
            profile=deepcopy(PROFILE);profile['lineage']=context
            client=self.client(profile)
            self.assertEqual(404,client.get('/v1/taxa/profile',params={'name':'청둥오리','species_scope':'outside'}).status_code)
            body=client.get('/v1/taxa/profile',params={'name':'청둥오리','species_scope':'unknown'}).json()
            self.assertEqual('unknown',body['taxon']['distribution']['status'])

    def test_default_and_explicit_all_keep_legacy_handler_contract(self):
        client=self.client()
        for params in ({'name':'청둥오리'},{'name':'청둥오리','species_scope':'all'}):
            self.assertEqual(PROFILE,client.get('/v1/taxa/profile',params=params).json())
        self.assertEqual([(('청둥오리',),{}), (('청둥오리',),{})], self.reader.call_args_list)

    def test_invalid_scope_fails_before_handler(self):
        client=self.client()
        self.assertEqual(422,client.get('/v1/taxa/profile',params={'name':'청둥오리','species_scope':'bogus'}).status_code)
        self.assertEqual(422,client.post('/v1/chat',json={'question':'청둥오리','species_scope':'bogus'}).status_code)
        self.reader.assert_not_called()

    def test_scoped_relation_endpoint_passes_scope_to_candidate_query(self):
        result={'taxon':PROFILE['taxon'],**PROFILE['lineage'],'groups':[]}
        for endpoint, arg in [('related','related_species_handler'),('similar','similar_species_handler'),('ecological-related','ecological_relations_handler')]:
            handler=Mock(return_value=result)
            client=TestClient(create_app(**{arg:handler}))
            self.assertEqual(200,client.get('/v1/taxa/'+endpoint,params={'name':'청둥오리','species_scope':'korea'}).status_code)
            handler.assert_called_once_with('청둥오리',species_scope='korea')

    def test_scoping_does_not_renormalize_similarity_scores_or_backfill(self):
        lineage=replace(LINEAGE,concept_set_id=CONCEPT)
        known=checked_candidate(0,genus=True)
        other=candidate('unknown-species','AAA Unknown',True,True)
        phylogeny={known['taxon_id']:{'key':'phylogenetic_clade','shared_ancestor_depth':1,'points':0},
                   other['taxon_id']:{'key':'phylogenetic_clade','shared_ancestor_depth':2,'points':0}}
        with patch('robingraph.retrieval.similar_species.read_traits',return_value=[]), \
             patch('robingraph.retrieval.similar_species.phylogenetic_relations',return_value=phylogeny):
            all_result=similar_species(NameRepository([known,other]),Mock(),lambda _:lineage,TARGET.scientific_name)
            scoped=similar_species(NameRepository([known,other]),Mock(),lambda _:lineage,TARGET.scientific_name,'korea')
        all_items={x['taxon_id']:x for x in all_result['groups'][0]['items']}
        items=scoped['groups'][0]['items']
        self.assertEqual([known['taxon_id']],[x['taxon_id'] for x in items])
        self.assertEqual(all_items[known['taxon_id']]['similarity_score'],items[0]['similarity_score'])
        self.assertEqual(1,len(items))

    def test_exact_name_resolver_does_not_bypass_selected_scope(self):
        from robingraph.retrieval.taxon_name_resolution import TaxonNameResolver
        from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage
        target=LineageTaxon('avilist-taxon:v2025b:544','species','Anas platyrhynchos',None,'청둥오리',english_name='Mallard')
        lineage=TaxonomyLineage('Anas platyrhynchos','AviList','v2025b',CONCEPT,(target,))
        load=Mock()
        resolver=TaxonNameResolver(lambda _:lineage,load,active_context=lambda:(CONCEPT,'v2025b'))
        self.assertEqual('matched',resolver.resolve('청둥오리','korea')['status'])
        self.assertEqual('not_found',resolver.resolve('청둥오리','outside')['status'])
        load.assert_not_called()

    def test_scoped_display_never_promotes_machine_translated_korean_name(self):
        from robingraph.retrieval.species_scope import with_species_scope
        taxon={'taxon_id':'unknown','rank':'species','scientific_name':'Example species',
               'korean_name':'검토되지 않은 이름','korean_name_status':'machine-translated','english_name':'Source English'}
        for scope in ('all','korea','outside','unknown'):
            result=with_species_scope(taxon,scope,CONCEPT,'v2025b')
            self.assertEqual('Source English',result['display_name'])

    def test_scoped_taxonomy_preserves_english_display_and_filters_target(self):
        from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage
        target=LineageTaxon('avilist-taxon:v2025b:11283','species','Nestor notabilis',None,'높은산앵무',english_name='Kea')
        lineage=TaxonomyLineage('Nestor notabilis','AviList','v2025b',CONCEPT,(target,))
        client=TestClient(create_app(lineage_handler=lambda _:lineage))
        response=client.get('/v1/taxa/lineage',params={'scientific_name':'Nestor notabilis','species_scope':'outside'})
        self.assertEqual('Kea',response.json()['lineage'][-1]['display_name'])
        self.assertEqual(404,client.get('/v1/taxa/lineage',params={'scientific_name':'Nestor notabilis','species_scope':'korea'}).status_code)
        body=client.post('/v1/chat',json={'question':'Nestor notabilis 분류 알려줘','species_scope':'outside'}).json()
        self.assertEqual('Kea',body['result']['lineage']['lineage'][-1]['display_name'])
