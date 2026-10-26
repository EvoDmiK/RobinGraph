"""Synthetic artifact mutations only. No live API/DB claims."""
import copy,importlib.util,json,os,unittest
from pathlib import Path
BASE=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex/docs/verification/assets/2026-10-23-semantic-graph-interpreter')
os.environ['RG212_SCORE_ASSET_DIR']=str(BASE)
spec=importlib.util.spec_from_file_location('score_api',Path(__file__).with_name('score-api.py'));sc=importlib.util.module_from_spec(spec);spec.loader.exec_module(sc)
rows={r['case']['id']:r for r in json.loads((BASE/'api-active.json').read_text())['rows']}
shadow={r['case']['id']:r for r in json.loads((BASE/'api-shadow.json').read_text())['rows']}
def synthetic(id='fresh-17'):
 r=copy.deepcopy(rows[id]);p=r['response']['result']['payload'];e=r['case']['expected'];t=p['taxon']
 p['execution_summary']=dict(kind='habitat_shared_diet' if e.get('habitat') else 'shared_diet',target_id=t['taxon_id'],reference_name=t['scientific_name'],species_scope='all',share_basis='trophic_niche',match='same',exclude_reference=True,habitat=e.get('habitat'),niche_value='Frugivore' if id=='fresh-17' else 'Herbivore aquatic',dataset_id='avonet:figshare-article-16586228-v7:file-34480856',release='figshare-article-16586228-v7:file-34480856',concept_set_id='rg:concept-set:avilist-v2025b',taxonomy_release='v2025b')
 return r
def verdict(r):return sc.audit(r['case'],r,None,None)['status']
class AuditTests(unittest.TestCase):
 def test_original_without_summary_remains_unverifiable(self):
  for id in ['fresh-14','fresh-17','fresh-18']:self.assertEqual(verdict(rows[id]),'unverifiable')
 def test_synthetic_matching_summary_passes(self):
  for id in ['fresh-14','fresh-17','fresh-18']:self.assertEqual(verdict(synthetic(id)),'pass')
 def test_every_missing_field_unverifiable(self):
  for field in list(synthetic()['response']['result']['payload']['execution_summary']):
   with self.subTest(field=field):
    r=synthetic();del r['response']['result']['payload']['execution_summary'][field];self.assertEqual(verdict(r),'unverifiable')
 def test_wrong_fields_fail(self):
  mutations={'kind':'shared_diet','target_id':'wrong','reference_name':'Anas platyrhynchos','species_scope':'korea','share_basis':'habitat','match':'different','exclude_reference':False,'habitat':None,'niche_value':'Omnivore','dataset_id':'wrong','release':'wrong','concept_set_id':'wrong','taxonomy_release':'wrong'}
  for k,v in mutations.items():
   with self.subTest(field=k):
    r=synthetic();r['response']['result']['payload']['execution_summary'][k]=v;self.assertEqual(verdict(r),'fail')
 def test_implicit_habitat_fails(self):
  r=synthetic('fresh-14');r['response']['result']['payload']['execution_summary']['habitat']='Wetland';self.assertEqual(verdict(r),'fail')
 def test_extra_condition_fails(self):
  r=synthetic();r['response']['result']['payload']['execution_summary']['conditions']=[{'trait_name':'body_mass','op':'num_gt','threshold':100}];self.assertEqual(verdict(r),'fail')
 def test_reference_result_fails(self):
  r=synthetic();p=r['response']['result']['payload'];p['items'][0]['taxon']=p['taxon'];self.assertEqual(verdict(r),'fail')
 def test_missing_habitat_evidence_fails(self):
  r=synthetic();p=r['response']['result']['payload'];p['items'][0]['paths']=[v for v in p['items'][0]['paths'] if 'field=Habitat' not in v['source_url']];self.assertEqual(verdict(r),'fail')
 def test_wrong_peer_niche_fails(self):
  r=synthetic();p=r['response']['result']['payload'];p['items'][0]['paths']=[{**v,'text':v['text'].replace('Frugivore','Omnivore')} for v in p['items'][0]['paths']];self.assertEqual(verdict(r),'fail')
 def test_empty_query_can_be_verified(self):
  r=synthetic();p=r['response']['result']['payload'];p['items']=[];p['status']='empty';r['response']['disposition']='abstain';self.assertEqual(verdict(r),'pass')
 def test_insufficient_without_execution_not_verified(self):
  r=synthetic();p=r['response']['result']['payload'];del p['execution_summary'];p['items']=[];p['status']='insufficient_data';r['response']['disposition']='abstain';self.assertEqual(verdict(r),'unverifiable')
 def test_preserve27_still_fails(self):
  r=rows['fresh-27'];self.assertEqual(sc.audit(r['case'],r,None,shadow['fresh-27'])['status'],'fail')
if __name__=='__main__':unittest.main()
