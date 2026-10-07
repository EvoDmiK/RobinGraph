from dataclasses import asdict
from unittest import TestCase
from unittest.mock import Mock,patch
from fastapi.testclient import TestClient
from robingraph.api.app import create_app
from robingraph.retrieval.taxonomy_lineage import LineageTaxon,TaxonomyLineage
from robingraph.retrieval.species_profile import create_species_flow,PhotoLookup,SpeciesNotFoundError,_licensed_images
from robingraph.retrieval.subspecies import subspecies_for,subspecies_metadata

PARENT=LineageTaxon('parent','species','Anas platyrhynchos',None,'청둥오리')
CHILD=LineageTaxon('avilist-taxon:v2025b:546','subspecies','Anas platyrhynchos conboschas','Brehm, CL, 1831')
LINEAGE=TaxonomyLineage(CHILD.scientific_name,'AviList','v2025b','rg:concept-set:avilist-v2025b',(PARENT,CHILD))
ROW={'taxon':asdict(CHILD),'range_text':'coastal southwestern Greenland',
     'source_name':'AviList v2025b','source_url':'https://www.avilist.org/checklist/v2025b/'}

class SubspeciesTest(TestCase):
 def test_global_names_reject_wrong_identity_and_machine_translated_korean(self):
  from robingraph.retrieval.taxonomy_lineage import sourced_subspecies_names,with_korean_display_name
  tid,reference=next((tid,r) for tid,r in sourced_subspecies_names().items() if tid not in ('avilist-taxon:v2025b:546','avilist-taxon:v2025b:545','avilist-taxon:v2025b:5421','avilist-taxon:v2025b:5422'))
  taxon={'taxon_id':tid,'rank':'subspecies','scientific_name':reference['scientific_name'],
         'korean_name':'추정 번역','korean_name_status':'machine-translated'}
  shown=with_korean_display_name(taxon)
  self.assertIsNone(shown['korean_name'])
  self.assertEqual(reference['english_name'],shown['english_name'])
  self.assertIn('#page=',shown['english_name_source_url'])
  self.assertNotIn('english_name',with_korean_display_name({**taxon,'scientific_name':'Wrong species identity'}))
  conflicting=with_korean_display_name({**taxon,'english_name':'Different verified name'})
  self.assertEqual('Different verified name',conflicting['english_name'])

 def test_sourced_english_subspecies_names_are_identity_bound_and_shared_by_profiles(self):
  repo=Mock();repo._run.return_value=[ROW]
  data=subspecies_for(repo,lambda _:LINEAGE,'청둥오리')
  child=data['subspecies'][0]
  self.assertEqual('Greenland Mallard',child['english_name'])
  self.assertIn('dof.dk',child['english_name_source_url'])
  self.assertIn('그린란드',child['description'])
  from robingraph.retrieval.taxonomy_lineage import with_korean_display_name
  nominate=with_korean_display_name({'rank':'subspecies','taxon_id':'avilist-taxon:v2025b:545',
                                   'scientific_name':'Anas platyrhynchos platyrhynchos'})
  self.assertEqual('Northern Mallard',nominate['english_name'])
  for changed in ({**asdict(CHILD),'taxon_id':'unknown'},{**asdict(CHILD),'scientific_name':'Other species test'}):
   self.assertIsNone(with_korean_display_name(changed)['english_name'])
  existing=with_korean_display_name({**asdict(CHILD),'english_name':'Existing source name'})
  self.assertEqual('Existing source name',existing['english_name'])
  flow=create_species_flow(lambda _:LINEAGE,lambda _:[],photos=lambda _:[],
                           subspecies_info=lambda lin:subspecies_metadata(repo,lin))
  profile=flow.invoke(CHILD.scientific_name)
  self.assertEqual(child['english_name'],profile['taxon']['english_name'])
  self.assertEqual(child['english_name_source_url'],profile['taxon']['english_name_source_url'])

 def test_heron_subspecies_use_verified_names_or_distribution_captions(self):
  HERON_DISTRIBUTIONS = {
   'avilist-taxon:v2025b:5420': ('Ardea cinerea cinerea', 'Eurasia to Manchuria, India, Africa, and Comoros'),
   'avilist-taxon:v2025b:5421': ('Ardea cinerea jouyi', 'Japan, China, Indochina, Malaya, Sumatra, and Java'),
   'avilist-taxon:v2025b:5422': ('Ardea cinerea monicae', "islands off Banc d'Arguin (Mauritania)"),
   'avilist-taxon:v2025b:5423': ('Ardea cinerea firasa', 'Madagascar'),
  }
  parent=LineageTaxon('avilist-taxon:v2025b:5419','species','Ardea cinerea',None,'왜가리',english_name='Grey Heron')
  lineage=TaxonomyLineage('Ardea cinerea','AviList','v2025b','rg:concept-set:avilist-v2025b',(parent,))
  repo=Mock();repo._run.return_value=[{**ROW,'taxon':asdict(LineageTaxon(key,'subspecies',value[0],None)), 'range_text':value[1]} for key,value in HERON_DISTRIBUTIONS.items()]
  taxa=subspecies_for(repo,lambda _:lineage,'왜가리')['subspecies']
  self.assertEqual('Oriental Grey Heron',taxa[1]['english_name'])
  self.assertEqual('Mauritanian Heron',taxa[2]['english_name'])
  self.assertIsNone(taxa[3]['english_name'])
  self.assertEqual('왜가리 아종 · 마다가스카르 분포',taxa[3]['display_label'])
  self.assertTrue(all(t['description_source_url'] == ROW['source_url'] for t in taxa))
  child=LineageTaxon(taxa[1]['taxon_id'],'subspecies',taxa[1]['scientific_name'],None)
  repo._run.return_value=[{**ROW,'taxon':asdict(child),'range_text':HERON_DISTRIBUTIONS[child.taxon_id][1]}]
  meta=subspecies_metadata(repo,TaxonomyLineage(child.scientific_name,'AviList','v2025b',lineage.concept_set_id,(parent,child)))
  self.assertIn('일본·중국',meta['section']['items'][1]['text'])
  changed=TaxonomyLineage('Ardea cinerea','AviList','other',lineage.concept_set_id,(parent,))
  self.assertEqual('source-original',subspecies_for(repo,lambda _:changed,'왜가리')['subspecies'][0]['description_status'])

 def test_graph_navigation_pins_parent_child_release_and_provenance(self):
  repo=Mock();repo._run.return_value=[ROW]
  data=subspecies_for(repo,lambda _:LINEAGE,'청둥오리')
  self.assertEqual(CHILD.taxon_id,data['subspecies'][0]['taxon_id']);self.assertEqual('parent',data['parent_species']['taxon']['taxon_id'])
  query=repo._run.call_args.args[0];self.assertIn('PARENT_OF',query);self.assertIn('child.source_release=$taxonomy_release',query)
  self.assertEqual(LINEAGE.concept_set_id,repo._run.call_args.kwargs['concept_set_id'])
  meta=subspecies_metadata(repo,LINEAGE)
  self.assertIn('그린란드 남서부',meta['section']['items'][1]['text'])
  self.assertEqual(CHILD.taxon_id,repo._run.call_args.kwargs['child_id'])
  repo._run.return_value=[{**ROW,'range_text':'changed'}]
  self.assertEqual('분포(영어 원문): changed',subspecies_metadata(repo,LINEAGE)['section']['items'][1]['text'])
  repo._run.return_value=[{**ROW,'source_url':'javascript:evil'}]
  with self.assertRaises(ValueError):subspecies_for(repo,lambda _:LINEAGE,'청둥오리')
  repo._run.return_value=[]
  with self.assertRaises(ValueError):subspecies_metadata(repo,LINEAGE)
  repo._run.return_value=[{**ROW,'taxon':{**ROW['taxon'],'scientific_name':'Changed identity'}}]
  with self.assertRaises(ValueError):subspecies_metadata(repo,LINEAGE)
  repo._run.return_value=[ROW,ROW]
  with self.assertRaises(ValueError):subspecies_for(repo,lambda _:LINEAGE,'청둥오리')

 def test_subspecies_profile_keeps_parent_traits_separate_and_never_inherits_risk_photo_notes(self):
  repo=Mock();repo._run.return_value=[ROW]
  parent_trait={'name':'body_mass','value':843,'display':'843','unit':'g','source_name':'EltonTraits','source_url':'https://example.org/elton'}
  traits=Mock(side_effect=lambda lin:[parent_trait] if lin.items[-1].rank=='species' else [])
  photo=Mock(return_value=PhotoLookup([],'unconfirmed_taxon'));risk=Mock(return_value={'category':'LC'});notes=Mock()
  flow=create_species_flow(lambda _:LINEAGE,traits,photos=photo,conservation=risk,notes=notes,subspecies_info=lambda lin:subspecies_metadata(repo,lin))
  data=flow.invoke(CHILD.scientific_name)
  self.assertEqual([],data['traits']);self.assertEqual([],data['images']);self.assertIsNone(data['conservation']['category'])
  self.assertEqual('species',data['reference_traits'][0]['reference_scope']);self.assertEqual('parent',data['reference_traits'][0]['reference_taxon']['taxon_id'])
  self.assertNotIn('843',data['summary']);self.assertEqual('parent',data['parent_species']['taxon']['taxon_id'])
  self.assertEqual('subspecies_taxonomy',data['sections'][0]['key'])
  photo.assert_called_once_with(CHILD.scientific_name);risk.assert_not_called();notes.assert_not_called()
  self.assertNotIn('reference_scope',parent_trait)
  for missing in (None,Mock(side_effect=ValueError('changed parent'))):
   broken=create_species_flow(lambda _:LINEAGE,traits,photos=photo,subspecies_info=missing)
   with self.assertRaises((SpeciesNotFoundError,ValueError)):broken.invoke(CHILD.scientific_name)

 def test_every_genus_gets_source_distribution_and_same_profile_caption(self):
  for science,common,sub,raw in (
      ('Parus major','Great Tit','Parus major major','Europe to western Siberia'),
      ('Phasianus colchicus','꿩','Phasianus colchicus torquatus','eastern China'),
      ('Corvus macrorhynchos','큰부리까마귀','Corvus macrorhynchos japonensis','Japan'),
      ('Struthio camelus','타조','Struthio camelus syriacus','formerly Syrian and Arabian desert; extinct ca. 1966')):
   parent=LineageTaxon('parent','species',science,None,common)
   child=LineageTaxon('unreviewed:'+sub,'subspecies',sub,None)
   lineage=TaxonomyLineage(science,'AviList','v2025b','rg:concept-set:avilist-v2025b',(parent,child))
   repo=Mock();repo._run.return_value=[{**ROW,'taxon':asdict(child),'range_text':raw}]
   listed=subspecies_for(repo,lambda _:lineage,common)['subspecies'][0]
   meta=subspecies_metadata(repo,lineage)
   self.assertEqual(raw,listed['description'])
   self.assertEqual('en',listed['description_language'])
   self.assertTrue(listed['display_label'].startswith(common+' 아종 · '))
   self.assertIsNone(listed['korean_name']);self.assertIsNone(listed['english_name'])
   self.assertEqual(listed,meta['display_taxon'])
   self.assertEqual('분포(영어 원문): '+raw,meta['section']['items'][1]['text'])
   flow=create_species_flow(lambda _:lineage,lambda _:[],photos=lambda _:[],subspecies_info=lambda lin:subspecies_metadata(repo,lin))
   self.assertEqual(listed['display_label'],flow.invoke(sub)['taxon']['display_label'])
  repo._run.return_value=[{**ROW,'taxon':asdict(child),'range_text':None}]
  missing=subspecies_for(repo,lambda _:lineage,common)['subspecies'][0]
  self.assertEqual(common+' 아종',missing['display_label'])
  self.assertNotIn('description',missing)
  repo._run.return_value=[{**ROW,'taxon':asdict(child),'range_text':'  '+('long region '*30)+'; other range'}]
  clipped=subspecies_for(repo,lambda _:lineage,common)['subspecies'][0]
  self.assertTrue(clipped['display_label'].endswith('…'))
  self.assertIn('other range',clipped['description'])

 def test_photo_lookup_requires_subspecies_rank_and_exact_name(self):
  _licensed_images.cache_clear()
  with patch('robingraph.retrieval.species_profile._json_get',return_value={'results':{'bindings':[]}}) as get:
   data=_licensed_images(CHILD.scientific_name,1,'subspecies')
   query=get.call_args.args[1]['query'];self.assertIn('wd:Q68947',query);self.assertNotIn('wd:Q7432',query);self.assertIn(CHILD.scientific_name,query)
   self.assertEqual('unconfirmed_taxon',data.status)

 def test_subspecies_api_and_trinomial_chat_use_graph_profile_not_name_relation_fallback(self):
  profile={'taxon':asdict(CHILD),'summary':'청둥오리에 속하는 아종입니다.','traits':[],'warnings':[]}
  handler=Mock(return_value=profile);relations=Mock(side_effect=AssertionError('should bypass'))
  client=TestClient(create_app(species_profile_handler=handler,name_relations_handler=relations,subspecies_handler=lambda name:{'subspecies':[asdict(CHILD)]}))
  self.assertEqual(200,client.get('/v1/taxa/subspecies?name=청둥오리').status_code)
  self.assertEqual(422,client.get('/v1/taxa/subspecies?name=%20').status_code)
  for q in (CHILD.scientific_name+'에 대해 알려줘',CHILD.scientific_name):
   data=client.post('/v1/chat',json={'question':q,'intent':'profile' if q==CHILD.scientific_name else 'auto'}).json()
   self.assertEqual('answer',data['disposition']);self.assertEqual('subspecies',data['result']['profile']['taxon']['rank'])
  relations.assert_not_called()
  self.assertEqual(503,TestClient(create_app()).get('/v1/taxa/subspecies?name=청둥오리').status_code)

 def test_single_common_graph_target_is_answer_but_multiple_and_domestic_require_choice(self):
  relation={'entity_kind':'common_name','relation_type':'common_usage','taxon':asdict(PARENT)}
  reader=Mock(return_value={'is_search_term':True,'relations':[relation],'summary':'연결된 종'})
  client=TestClient(create_app(name_relations_handler=reader))
  data=client.post('/v1/chat',json={'question':'비둘기'}).json()
  self.assertEqual('answer',data['disposition']);self.assertEqual('name_relations',data['result']['kind'])
  for other in ({**relation,'taxon':{**asdict(PARENT),'taxon_id':'other'}},{**relation,'entity_kind':'domestic_form'}):
   reader.return_value={'is_search_term':True,'relations':[relation,other],'summary':'선택'}
   self.assertEqual('clarify',client.post('/v1/chat',json={'question':'비둘기'}).json()['disposition'])
