import unittest
from dataclasses import replace
from types import SimpleNamespace as NS
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from robingraph.api.app import create_app
from robingraph.retrieval.ecological_relations import ecological_relations, PEERS_QUERY
from robingraph.retrieval.species_profile import SpeciesNotFoundError
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon

LINEAGE = TaxonomyLineage('Anas platyrhynchos','AviList','v2025b','active',(
    LineageTaxon('mallard','species','Anas platyrhynchos',None,'청둥오리'),))
SOURCE = dict(source_name='AVONET',source_url='https://example.org/avonet',citation='AVONET',
              dataset_id='avonet',release='2022',license_name='CC BY 4.0')


def trait(name='habitat',value='Wetland',**extra):
    return {**SOURCE,'name':name,'value':value,'inferred':False,**extra}


def peer(i):
    return {'taxon':{'taxon_id':f'p{i}','rank':'species','scientific_name':f'Peer species{i}',
                     'korean_name':None,'english_name':f'Bird {i}'},
            'source_url':'https://example.org/peer','citation':f'Row {i}'}


class EcologicalRelationsTest(unittest.TestCase):
    @patch('robingraph.retrieval.ecological_relations.read_traits')
    def test_bounded_categories_keep_both_provenances_and_exact_source_release(self, traits):
        traits.return_value = [trait(),trait(),trait('trophic_niche','Aquatic predator')]
        repo = Mock(); repo._korean_dataset_id.return_value='ko-active'
        repo._run.side_effect = [[peer(i) for i in range(4)],[]]
        result=ecological_relations(repo,Mock(),lambda _:LINEAGE,'청둥오리')
        self.assertEqual(2,len(result['groups']))
        habitat,niche=result['groups']
        self.assertEqual('습지',habitat['display'])
        self.assertEqual(3,len(habitat['items']))
        self.assertTrue(habitat['has_more'])
        self.assertEqual('https://example.org/avonet',habitat['source']['source_url'])
        self.assertEqual('https://example.org/peer',habitat['items'][0]['evidence']['source_url'])
        self.assertEqual('Row 0',habitat['items'][0]['evidence']['citation'])
        self.assertEqual('수생동물 포식',niche['display'])
        self.assertFalse(niche['has_more'])
        self.assertIn('실제 공존',result['note'])
        for call in repo._run.call_args_list:
            self.assertEqual('2022',call.kwargs['release'])
            self.assertEqual('avonet',call.kwargs['dataset_id'])
            self.assertEqual('active',call.kwargs['concept_set_id'])
            self.assertEqual('v2025b',call.kwargs['taxonomy_release'])
        # The two record evidences and inferred/taxonomy gates must remain distinct.
        for clause in ('origin.inferred=false','claim.inferred=false',
                       'originEvidence.source_record_id=origin.source_record_id',
                       'evidence.source_record_id=claim.source_record_id',
                       'peer.id <> $target_id',"source_release:$taxonomy_release"):
            self.assertIn(clause,PEERS_QUERY)

    @patch('robingraph.retrieval.ecological_relations.read_traits')
    def test_unsupported_inferred_and_unsafe_target_claims_are_not_relations(self, traits):
        traits.return_value=[trait(value='UNKNOWN'),trait(value='Unreviewed'),
                             trait(inferred=True),trait(source_url='javascript:bad'),
                             trait(source_url='https://['),trait('body_mass',10)]
        repo=Mock()
        self.assertEqual([],ecological_relations(repo,Mock(),lambda _:LINEAGE,'x')['groups'])
        repo._run.assert_not_called()

    def test_revoked_or_stale_active_contexts_never_query_traits_or_peers(self):
        repo=Mock(); store=Mock()
        for cursor in (None,{'concept_set_id':'old','taxonomy_release':'v2025b'},
                       {'concept_set_id':'active','taxonomy_release':'old'}):
            store.active_release_context.return_value=(None if cursor is None else NS(cursor=cursor))
            self.assertEqual([],ecological_relations(repo,store,lambda _:LINEAGE,'x')['groups'])
        repo._run.assert_not_called()

    @patch('robingraph.retrieval.ecological_relations.read_traits',return_value=[trait()])
    def test_invalid_peer_provenance_fails_closed(self, traits):
        repo=Mock()
        for row in ({**peer(1),'source_url':'javascript:bad'},
                    {**peer(1),'taxon':{'taxon_id':'mallard','rank':'species'}},
                    {**peer(1),'taxon':{'taxon_id':'p1','rank':'subspecies'}}):
            repo._run.return_value=[row]
            with self.assertRaises(ValueError):
                ecological_relations(repo,Mock(),lambda _:LINEAGE,'x')

    def test_species_only_and_safe_api_errors(self):
        for lineage in (None,replace(LINEAGE,items=()),replace(LINEAGE,items=(
                replace(LINEAGE.items[0],rank='subspecies'),))):
            repo=Mock()
            with self.assertRaises(SpeciesNotFoundError):
                ecological_relations(repo,Mock(),lambda _:lineage,'x')
            repo._run.assert_not_called()
        handler=Mock(return_value={'groups':[]})
        client=TestClient(create_app(ecological_relations_handler=handler))
        url='/v1/taxa/ecological-related'
        self.assertEqual(200,client.get(url,params={'name':' 청둥오리 '}).status_code)
        handler.assert_called_once_with('청둥오리')
        for name in (' ','x'*201):
            self.assertEqual(422,client.get(url,params={'name':name}).status_code)
        handler.side_effect=SpeciesNotFoundError()
        self.assertEqual(404,client.get(url,params={'name':'missing'}).status_code)
        handler.side_effect=RuntimeError('secret database password')
        response=client.get(url,params={'name':'x'})
        self.assertEqual(503,response.status_code)
        self.assertNotIn('secret',response.text)
        self.assertEqual(503,TestClient(create_app()).get(url,params={'name':'x'}).status_code)
