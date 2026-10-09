"""Offline audit classification contracts; these do not connect to TEST DB/API."""
from copy import deepcopy
import json
import unittest

from scripts.audit_trait_coverage import audit_traits, candidate_traits, compare_taxonomy, decode_value, gate_reasons, sample_comparison


def fixture():
    return {'taxonomy_release':'v1','taxa':[
        {'id':'t1','sequence':'1','scientific_name':'Pica pica','release':'v1','policy_status':'allowed'},
        {'id':'t2','sequence':'2','scientific_name':'Pica serica','release':'v1','policy_status':'allowed'}],
        'source_records':[{'id':'p1','record_type':'trait_profile','payload':{}},
            {'id':'a1','record_type':'taxon_concept','payload':{'rank':'species','scientific_name':'Pica pica'}},
            {'id':'a2','record_type':'taxon_concept','payload':{'rank':'species','scientific_name':'Pica serica'}}],
        'contexts':[{'pipeline':'reference-taxonomy-traits','dataset_id':'elton','release':'r1','cursor':{}},
                    {'pipeline':'reference-avonet','dataset_id':'avonet','release':'r1','cursor':{}}],
        'claims':[], 'reader_traits':{}, 'mapping_candidates':[], 'api_samples':[]}


def profiles():
    return {'elton':[{'record_id':'p1','scientific_name':'Pica pica',
                       'traits':{'diet_distribution':{'seed':0,'invertebrate':100},'nocturnal':False}}],
            'avonet':[]}


def claim(name='diet_distribution', value=None):
    value={'seed':0,'invertebrate':100} if value is None else value
    return {'taxon_id':'t1','claim':{'id':'c1','dataset_id':'elton','source_record_id':'p1','trait_name':name,
                                   'value_json':json.dumps(value),'value_boolean':None,'value_num':None,'value_text':None}}


class CoverageAuditTests(unittest.TestCase):
    def test_taxonomy_bidirectional_keys_and_duplicate_detection(self):
        snapshot=[['1','species',None,None,None,'Pica pica'],['3','species',None,None,None,'Other bird']]
        live=fixture(); live['taxa'].append(deepcopy(live['taxa'][0]))
        report=compare_taxonomy(snapshot,live)
        self.assertEqual(['3'],report['source_not_in_graph_sequences'])
        self.assertEqual(['2'],report['graph_not_in_source_sequences'])
        self.assertEqual({'t1':2},report['graph_duplicate_ids'])
        self.assertEqual(['Other bird'],report['source_not_in_postgres_names'])

    def test_no_presplit_inheritance_to_serica(self):
        report=audit_traits(fixture(),profiles(),{'diet_distribution','nocturnal'})['elton']
        diet=report['coverage_by_trait']['diet_distribution']
        self.assertEqual(1,diet['source_absent_exact_current_name'])
        self.assertEqual(1,diet['source_present_claim_missing_graph'])
        self.assertTrue(all(g['scientific_name']=='Pica pica' for g in report['gaps']))

    def test_source_record_loss_is_separate_from_graph_loss(self):
        live=fixture(); live['source_records']=[]
        report=audit_traits(live,profiles(),{'diet_distribution','nocturnal'})['elton']
        self.assertEqual(['p1'],report['postgres_missing_source_record_ids'])
        self.assertEqual(1,report['coverage_by_trait']['diet_distribution']['source_record_missing_postgres'])

    def test_claim_exists_but_reader_drops_and_unsupported_trait(self):
        live=fixture(); live['claims']=[claim()]
        report=audit_traits(live,profiles(),{'diet_distribution','nocturnal'})['elton']
        self.assertEqual(1,report['coverage_by_trait']['diet_distribution']['graph_claim_not_returned_by_reader'])
        report=audit_traits(live,profiles(),{'nocturnal'})['elton']
        self.assertEqual(1,report['coverage_by_trait']['diet_distribution']['reader_trait_not_supported'])

    def test_readable_values_and_zero_components_are_preserved(self):
        live=fixture(); live['claims']=[claim()]
        live['reader_traits']={'t1':[{'name':'diet_distribution','dataset_id':'elton','value':{'seed':0,'invertebrate':100}}]}
        report=audit_traits(live,profiles(),{'diet_distribution','nocturnal'})['elton']
        self.assertEqual(1,report['coverage_by_trait']['diet_distribution']['readable'])
        self.assertEqual([],report['value_mismatches'])
        self.assertIs(decode_value({'value_boolean':False}),False)
        self.assertEqual(0,decode_value({'value_num':0}))

    def test_value_mismatch_and_duplicate_claim(self):
        live=fixture(); live['claims']=[claim(value={'seed':100}),claim(value={'seed':100})]
        live['claims'][1]['claim']['id']='c2'
        report=audit_traits(live,profiles(),{'diet_distribution','nocturnal'})['elton']
        self.assertEqual(1,len(report['value_mismatches']))
        self.assertEqual(2,report['graph_duplicate_claim_keys'][0]['rows'])

    def test_mapping_gap_and_missing_candidate_are_explicit(self):
        ps=profiles(); ps['elton'].append({'record_id':'p3','scientific_name':'Old bird','traits':{'nocturnal':False}})
        report=audit_traits(fixture(),ps,{'nocturnal'})['elton']
        self.assertEqual('exact_name_not_found',report['unresolved_profiles'][0]['reason'])
        self.assertEqual(['p3'],report['unresolved_without_candidate'])

    def test_http_overlay_is_visible_not_called_query_loss(self):
        live=fixture(); live['reader_traits']={'t2':[]}
        live['api_samples']=[{'query':'까치','status':200,'taxon':{'scientific_name':'Pica serica'},
                             'traits':[{'name':'body_mass','value':190,'source_name':'reviewed'}]}]
        report=sample_comparison(live)[0]
        self.assertFalse(report['api_equals_read_traits'])
        self.assertEqual(0,report['raw_claim_count'])
        self.assertEqual(190,report['traits'][0]['value'])

    def test_activity_review_keeps_raw_source_claim(self):
        live=fixture(); live['claims']=[claim('nocturnal',False)]
        live['reader_traits']={'t1':[{'name':'activity_pattern','value':True,
            'source_claims':[{'name':'nocturnal','dataset_id':'elton','value':False}]}]}
        report=audit_traits(live,profiles(),{'diet_distribution','nocturnal'})['elton']
        self.assertEqual(1,report['coverage_by_trait']['nocturnal']['preserved_in_reviewed_trait'])
        self.assertFalse(any(g['trait']=='nocturnal' for g in report['gaps']))

    def test_candidate_values_remain_unassigned_and_exact(self):
        candidate={'profile_json':json.dumps({'claims':[{'trait_name':'body_mass','value_num':100,'value_text':None}]})}
        self.assertEqual({'body_mass':100},candidate_traits(candidate,'avonet'))
        ps=profiles(); ps['elton'].append({'record_id':'p3','scientific_name':'Old bird','traits':{'nocturnal':False}})
        live=fixture(); live['mapping_candidates']=[{'dataset_id':'elton','source_record_id':'p3',
            'reason':'exact_name_not_found','policy_status':'allowed','profile_json':json.dumps({'nocturnal':0})}]
        report=audit_traits(live,ps,{'nocturnal'})['elton']
        self.assertEqual([],report['candidate_profile_value_issues'])
        live['mapping_candidates'][0]['profile_json']='invalid'
        report=audit_traits(live,ps,{'nocturnal'})['elton']
        self.assertEqual('candidate_profile_missing_or_invalid',report['candidate_profile_value_issues'][0]['reason'])

    def test_gate_reasons_preserve_release_and_evidence_boundaries(self):
        row=claim(); row['claim'].update(policy_status='allowed',source_release='old',taxonomy_release='v1')
        row.update(evidence_policy='allowed',evidence_dataset='elton',evidence_record='other')
        ctx={'policy_status':'allowed','release':'r1','cursor':{'concept_set_id':'cs','taxonomy_release':'v1'}}
        self.assertEqual(['inactive_source_release','evidence_record_mismatch'],
                         gate_reasons(row,ctx,{'concept_set_id':'cs','taxonomy_release':'v1'}))

    def test_multiple_evidence_rows_do_not_invent_duplicate_claims(self):
        live=fixture(); live['claims']=[claim(),claim()]
        report=audit_traits(live,profiles(),{'diet_distribution'})['elton']
        self.assertEqual([],report['graph_duplicate_claim_keys'])


if __name__=='__main__':
    unittest.main()
