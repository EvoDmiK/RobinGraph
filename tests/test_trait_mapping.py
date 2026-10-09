"""Offline mapping contracts; live TEST measurements are reported separately."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace as NS
import unittest
from unittest.mock import MagicMock, Mock, patch

from robingraph.retrieval import trait_mapping as tm
from robingraph.retrieval.species_profile import LABELS, trait_display, read_traits
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon

INDEX=tm.crosswalk_index()


def entry(source='eltontraits',name='Hypsipetes amaurotis'):
    return next(e for entries in INDEX['by_target'].values() for e in entries
                if e['dataset']==source and e['target_name']==name)


def lineage(e):
    name=e['target_name']
    return TaxonomyLineage(name,'AviList','v2025b','rg:concept-set:avilist-v2025b',
        (LineageTaxon('avilist-taxon:v2025b:'+str(e['target_sequence']),'species',name,None),))


def context(source):
    meta={'taxonomy_release':'v2025b'}
    cursor={'taxonomy_release':'v2025b','concept_set_id':'rg:concept-set:avilist-v2025b'}
    if source=='eltontraits':
        meta.update(trait_release=tm.PINS[source][0],trait_sha256=tm.PINS[source][1],
                    taxonomy_sha256=tm.PINS['taxonomy'][1],concept_set_id=cursor['concept_set_id'])
        cursor['trait_release']=tm.PINS[source][0]
        sha=tm.REFERENCE_BUNDLE_SHA256; key='reference-bundle:sha256-'+sha
    else:
        meta.update(sheet='AVONET1_BirdLife',taxonomy_concept_set_id=cursor['concept_set_id'])
        key,sha=tm.PINS[source][:2]
    return NS(dataset=NS(id=tm.DATASETS[source],name=source,policy_status='allowed'),
              release=NS(id='release',release_key=key,content_sha256=sha,metadata=meta),
              cursor=cursor,last_successful_run_id='run')


def elton_profile(e):
    return {'scientific_name':e['source_name'],'source_taxon_id':e['source_id'],'source_taxonomy':'BL3',
        'body_mass_g':70.89,'nocturnal':0,'pelagic_specialist':0,'diet_category':'FruiNect',
        'diet_distribution':{key:100 if key=='fruit' else 0 for key in tm.DIET_KEYS},
        'foraging_distribution':{key:100 if key=='ground' else 0 for key in tm.STRATA_KEYS}}


def avonet_profile(e):
    rid=e['record_id']; yes=e['evidence']['inference']
    inferred='Body Mass' if yes=='YES' else None
    return {'id':rid,'scientific_name':e['source_name'],'row_number':e['source_row'],
        'source_uri':tm.source_url(e),'avibase_id':e['source_id'],'sample_size':0,
        'inference_raw':yes,'inferred_fields_raw':inferred,'reference_species':None,
        'claims':[{'id':rid+':body_mass','trait_name':'body_mass','source_field':'Mass','value_num':131.15,
                   'value_text':None,'raw_value':'131.15','unit':'g','inferred':yes=='YES',
                   'evidence_kind':'literature_dataset','summary_statistic':'species_mean'}]}


def record(e,p):
    payload={'scientific_name':e['source_name']}
    if e['dataset']=='eltontraits': payload.update(source_id='eltontraits',trait_release=tm.PINS['eltontraits'][0])
    else: payload.update({k:p[k] for k in ['row_number','sample_size','inference_raw','inferred_fields_raw','reference_species','avibase_id']},sheet='AVONET1_BirdLife')
    return {'id':e['record_id'],'external_id':'eltontraits:'+e['source_id'],'url':tm.source_url(e),
            'sha256':tm.PINS[e['dataset']][1],'payload':payload}


def candidate(e,p):
    rid=e['record_id']
    return {'id':'taxon-mapping-candidate:eltontraits-v1:'+e['source_id'] if e['dataset']=='eltontraits' else rid+':candidate:v2025b',
        'source_record_id':rid,'dataset_id':tm.DATASETS[e['dataset']],'policy_status':'allowed','resolution_status':'open',
        'last_seen_run_id':'run','source_scientific_name':e['source_name'],'source_taxon_id':e['source_id'],
        'source_taxonomy':'BL3' if e['dataset']=='eltontraits' else 'HBW-BirdLife v5',
        'profile_json':json.dumps(p)}


def recover(e,p=None, *, mutation=None, exact=()):
    p=p or (elton_profile(e) if e['dataset']=='eltontraits' else avonet_profile(e))
    c=candidate(e,p)
    if mutation: mutation(c)
    repository=Mock(); repository._run.return_value=[{'candidate':c}]
    rec=record(e,p); ctx=context(e['dataset']); pipeline=next(k for k,v in tm.PIPELINES.items() if v==e['dataset'])
    with patch.object(tm,'source_records',return_value={e['record_id']:rec}):
        traits=tm.apply_trait_mapping(repository,Mock(),lineage(e),{pipeline:ctx},list(exact),LABELS,trait_display)
    return traits,repository


class TraitMappingTests(unittest.TestCase):
    def test_index_is_cached_and_real_pica_serica_has_no_entries(self):
        self.assertIs(INDEX,tm.crosswalk_index())
        self.assertFalse(any(e['target_name']=='Pica serica' for e in INDEX['by_record'].values()))

    def test_three_representative_renames(self):
        for name in ['Hypsipetes amaurotis','Ardea alba','Tachyspiza badia']:
            traits,repo=recover(entry(name=name))
            self.assertEqual(5,len(traits))
            self.assertTrue(all(t['taxonomy_alignment']['status']=='accepted' for t in traits))
            self.assertTrue(all(t['mapping_provenance']['read_time_recovery'] for t in traits))
            self.assertEqual(1,repo._run.call_count)
            self.assertEqual(1,len(repo._run.call_args.kwargs['requests']))

    def test_zero_and_false_preserved_and_pelagic_not_exposed(self):
        traits,_=recover(entry()); ts={t['name']:t for t in traits}
        self.assertIs(ts['nocturnal']['value'],False)
        self.assertEqual(0,ts['diet_distribution']['value']['seed'])
        self.assertNotIn('pelagic_specialist',ts)
        self.assertEqual('CC0 1.0',ts['diet_distribution']['license_name'])

    def test_avonet_recovery_preserves_units_and_source_fields(self):
        e=entry('avonet','Tachyspiza badia'); ts,_=recover(e)
        self.assertEqual(1,len(ts)); t=ts[0]
        self.assertEqual(131.15,t['value']); self.assertEqual('g',t['unit'])
        self.assertFalse(t['inferred']); self.assertEqual('species_mean',t['summary_statistic'])
        self.assertEqual(tm.source_url(e)+'&field=Mass',t['source_url'])
        self.assertEqual('CC BY 4.0',t['license_name'])

    def test_inferred_source_fields_remain_inferred(self):
        e=next(e for e in INDEX['by_record'].values() if e['dataset']=='avonet' and e['accepted_valid']
               and e['name_relation']=='name_changed' and e['evidence']['inference']=='YES')
        ts,_=recover(e)
        self.assertTrue(ts[0]['inferred'])

    def test_existing_same_source_type_is_not_replaced(self):
        e=entry(); exact=[({'name':'body_mass','value':999,'dataset_id':tm.DATASETS['eltontraits']},
                          {'source_record_id':e['record_id']})]
        ts,_=recover(e,exact=exact)
        self.assertEqual([999],[t['value'] for t in ts if t['name']=='body_mass'])
        self.assertEqual(5,len(ts))

    def test_legacy_pica_values_are_retained_and_qualified(self):
        e=entry(name='Pica pica'); ctx=context('eltontraits'); repo=Mock()
        exact=[({'name':'diet_distribution','value':{'seed':10},'dataset_id':tm.DATASETS['eltontraits']},
                {'source_record_id':e['record_id']})]
        ts=tm.apply_trait_mapping(repo,Mock(),lineage(e),{'reference-taxonomy-traits':ctx},exact,LABELS,trait_display)
        self.assertEqual({'seed':10},ts[0]['value']); a=ts[0]['taxonomy_alignment']
        self.assertEqual('needs_review',a['status']); self.assertEqual('birdtree_merges_birdlife_species',a['reason'])
        self.assertNotIn('pre_split',a['reason']); repo._run.assert_not_called()

    def test_same_name_approved_exact_is_annotated(self):
        e=entry('avonet','Hypsipetes amaurotis'); ctx=context('avonet'); repo=Mock()
        exact=[({'name':'body_mass','value':10,'dataset_id':tm.DATASETS['avonet']},{'source_record_id':e['record_id']})]
        ts=tm.apply_trait_mapping(repo,Mock(),lineage(e),{'reference-avonet':ctx},exact,LABELS,trait_display)
        self.assertEqual('accepted',ts[0]['taxonomy_alignment']['status']); repo._run.assert_not_called()

    def test_wrong_active_provenance_refuses_recovery(self):
        e=entry(); lin=lineage(e)
        for mutate in [lambda c:setattr(c.dataset,'id','wrong'),lambda c:setattr(c.dataset,'policy_status','blocked'),
                       lambda c:c.cursor.update(trait_release='old'),lambda c:c.cursor.update(taxonomy_release='v0'),
                       lambda c:c.cursor.update(concept_set_id='wrong'),lambda c:c.release.metadata.update(trait_sha256='0'*64),
                       lambda c:c.release.metadata.update(taxonomy_sha256='0'*64),lambda c:setattr(c.release,'release_key','old')]:
            ctx=context('eltontraits'); mutate(ctx); repo=Mock()
            self.assertEqual([],tm.apply_trait_mapping(repo,Mock(),lin,{'reference-taxonomy-traits':ctx},[],LABELS,trait_display))
            repo._run.assert_not_called()

    def test_wrong_candidate_identity_policy_run_release_refused(self):
        for k,v in [('id','wrong'),('source_record_id','wrong'),('dataset_id','wrong'),('source_scientific_name','Pica pica'),
                    ('source_taxon_id','wrong'),('source_taxonomy','IOC27'),('policy_status','blocked'),
                    ('resolution_status','closed'),('last_seen_run_id','old'),('taxonomy_release','v0'),('source_release','old')]:
            ts,_=recover(entry(),mutation=lambda c,k=k,v=v:c.update({k:v}))
            self.assertEqual([],ts,(k,v))

    def test_wrong_record_hash_uri_payload_release_identity_refused(self):
        e=entry(); p=elton_profile(e)
        for key,value in [('id','wrong'),('sha256','0'*64),('url','https://example.org'),('external_id','wrong')]:
            rec=record(e,p); rec[key]=value
            self.assertFalse(tm.valid_record(rec,e))
        rec=record(e,p); rec['payload']['trait_release']='old'
        self.assertFalse(tm.valid_record(rec,e))

    def test_invalid_profiles_do_not_create_traits(self):
        e=entry()
        mutations=[lambda p:p.update(nocturnal=True),lambda p:p.update(nocturnal=2),lambda p:p.update(body_mass_g=-1),
                   lambda p:p.update(body_mass_g=float('nan')),lambda p:p.update(source_taxon_id='wrong'),
                   lambda p:p['diet_distribution'].update(seed=200),lambda p:p['diet_distribution'].pop('seed'),
                   lambda p:p.update(scientific_name='wrong')]
        for mutate in mutations:
            p=elton_profile(e); mutate(p); ts,_=recover(e,p)
            self.assertEqual([],ts)

    def test_rounded_distribution_99_is_preserved(self):
        e=entry(); p=elton_profile(e); p['diet_distribution']['fruit']=99
        ts,_=recover(e,p)
        self.assertEqual(99,next(t['value']['fruit'] for t in ts if t['name']=='diet_distribution'))

    def test_malformed_candidate_does_not_hide_good_other_source(self):
        e1=entry(name='Tachyspiza badia'); e2=entry('avonet','Tachyspiza badia')
        c1=candidate(e1,elton_profile(e1)); c1['profile_json']='invalid'
        p2=avonet_profile(e2); c2=candidate(e2,p2)
        repo=Mock(); repo._run.return_value=[{'candidate':c1},{'candidate':c2},{'candidate':None},
                                           {'candidate':{'source_record_id':[]}}]
        records={e2['record_id']:record(e2,p2),e1['record_id']:record(e1,elton_profile(e1))}
        with patch.object(tm,'source_records',return_value=records):
            ts=tm.apply_trait_mapping(repo,Mock(),lineage(e1),{'reference-taxonomy-traits':context('eltontraits'),
                'reference-avonet':context('avonet')},[],LABELS,trait_display)
        self.assertEqual(1,len(ts)); self.assertEqual(tm.DATASETS['avonet'],ts[0]['dataset_id'])
        self.assertEqual(2,len(repo._run.call_args.kwargs['requests']))

    def test_duplicate_candidate_results_are_not_arbitrarily_selected(self):
        e=entry(); p=elton_profile(e); repo=Mock(); c=candidate(e,p)
        repo._run.return_value=[{'candidate':c},{'candidate':c}]
        self.assertEqual([],tm.apply_trait_mapping(repo,Mock(),lineage(e),{'reference-taxonomy-traits':context('eltontraits')},[],LABELS,trait_display))

    def test_split_lump_unsupported_taxonomy_and_mismatched_id_cannot_be_accepted(self):
        e=deepcopy(entry())
        for mutate in [lambda x:x['evidence'].update(match_types=['Many BL to 1BT']),
                       lambda x:x['evidence'].update(match_types=['1BL to many BT']),
                       lambda x:x.update(source_taxonomy='IOC27'),
                       lambda x:x['evidence'].update(avibase_id='AVIBASE-00000000')]:
            altered=deepcopy(e); mutate(altered); self.assertFalse(tm.accepted_evidence(altered))
        pica=deepcopy(entry('avonet','Pica pica')); pica['status']='accepted'; pica['method']='avibase_id_unique'
        self.assertFalse(tm.accepted_evidence(pica))

    def test_no_recovery_for_subspecies_wrong_taxon_or_concept(self):
        e=entry()
        for change in [('rank','subspecies'),('taxon_id','other'),('scientific_name','Pica serica')]:
            target=NS(**vars(lineage(e).items[-1])); setattr(target,*change)
            lin=NS(items=(target,),taxonomy_release='v2025b',concept_set_id='rg:concept-set:avilist-v2025b')
            repo=Mock()
            self.assertEqual([],tm.apply_trait_mapping(repo,Mock(),lin,{'reference-taxonomy-traits':context('eltontraits')},[],LABELS,trait_display))
            repo._run.assert_not_called()

    def test_profile_shape_and_claim_inference_tampering_refused(self):
        e=entry('avonet','Tachyspiza badia')
        for mutate in [lambda p:p['claims'].append(deepcopy(p['claims'][0])),
                       lambda p:p['claims'][0].update(inferred=True),lambda p:p['claims'][0].update(source_field='other'),
                       lambda p:p['claims'][0].update(raw_value='999'),lambda p:p.update(sample_size=-1),
                       lambda p:p.update(source_uri='https://example.com')]:
            p=avonet_profile(e); mutate(p); ts,_=recover(e,p); self.assertEqual([],ts)

    def test_missing_evidence_keeps_existing_traits(self):
        e=entry(); p=elton_profile(e); repo=Mock(); repo._run.return_value=[{'candidate':candidate(e,p)}]
        exact=[({'name':'habitat','value':'Forest','dataset_id':'ordinary-fixture'}, {})]
        with patch.object(tm,'source_records',return_value={}):
            ts=tm.apply_trait_mapping(repo,Mock(),lineage(e),{'reference-taxonomy-traits':context('eltontraits')},exact,LABELS,trait_display)
        self.assertEqual([exact[0][0]],ts)

    def test_postgres_evidence_query_is_read_only_and_release_scoped(self):
        store=MagicMock(); connection=Mock(); store._connect.return_value.__enter__.return_value=connection
        connection.execute.return_value.fetchall.return_value=[]
        self.assertEqual({},tm.source_records(store,context('eltontraits'),['p1']))
        self.assertEqual('SET TRANSACTION READ ONLY',connection.execute.call_args_list[0].args[0])
        query,params=connection.execute.call_args_list[1].args
        self.assertIn("s.license_policy_status='allowed'",query)
        self.assertIn('s.source_release_id=%s',query)
        self.assertEqual(('run',['p1'],'release'),params)

    def test_query_has_target_snapshot_and_policy_identity_gates(self):
        self.assertIn('s.snapshot_sha256=$taxonomy_sha256',tm.CANDIDATE_QUERY)
        self.assertIn('m.last_seen_run_id=request.run_id',tm.CANDIDATE_QUERY)
        self.assertIn('toLower(i.value)=request.target_avibase_id',tm.CANDIDATE_QUERY)
        self.assertIn('m.source_record_id=request.record_id',tm.CANDIDATE_QUERY)

    def test_changed_snapshot_pin_and_duplicate_mapping_fail_closed(self):
        data=json.loads(Path(tm.__file__).with_name('trait_crosswalk.json').read_text())
        wrong=deepcopy(data); wrong['sources'][1]['sha256']='0'*64
        self.assertIsNone(tm.build_index(wrong))
        wanted=entry()
        raw=next(r for r in data['entries'] if r[0]=='eltontraits' and r[2]==wanted['source_id'])
        data['entries'].append(deepcopy(raw))
        duplicate=tm.build_index(data)
        self.assertNotIn(('eltontraits',wanted['record_id']),duplicate['by_record'])

    def test_missing_crosswalk_or_source_identity_does_not_claim_verification(self):
        e=entry('avonet','Hypsipetes amaurotis')
        exact=[({'name':'body_mass','value':10,'dataset_id':tm.DATASETS['avonet']},{'source_record_id':'unknown'})]
        ts=tm.apply_trait_mapping(Mock(),Mock(),lineage(e),{'reference-avonet':context('avonet')},exact,LABELS,trait_display)
        self.assertEqual('needs_review',ts[0]['taxonomy_alignment']['status'])
        with patch.object(tm,'crosswalk_index',return_value=None):
            ts=tm.apply_trait_mapping(Mock(),Mock(),lineage(e),{},exact,LABELS,trait_display)
        self.assertEqual(10,ts[0]['value'])
        self.assertEqual('needs_review',ts[0]['taxonomy_alignment']['status'])

    def test_explicit_elton_interpolation_codes_and_c_uncertainty(self):
        e=entry()
        for code in ('D1','D2','C','A',None):
            p=elton_profile(e); p.update(body_mass_spec_level='0',foraging_spec_level='0',diet_certainty=code)
            ts,_=recover(e,p); byname={t['name']:t for t in ts}
            self.assertTrue(byname['body_mass']['inferred'])
            self.assertTrue(byname['foraging_strata_distribution']['inferred'])
            self.assertEqual(code in ('D1','D2'),byname['diet_distribution']['inferred'])
            self.assertEqual(code in ('D1','D2'),byname['diet_category']['inferred'])
            self.assertEqual(code,byname['diet_distribution']['certainty'])
            self.assertEqual(70.89,byname['body_mass']['value'])
            self.assertIs(byname['nocturnal']['value'],False)

    def test_exact_elton_claim_keeps_codes_notes_and_inference(self):
        e=entry(name='Pica pica'); repo=Mock(); store=Mock()
        store.active_release_context.side_effect=[context('eltontraits'),None]
        repo._run.return_value=[{'claim':{'trait_name':'body_mass','value_num':217.48,'unit':'g',
            'dataset_id':tm.DATASETS['eltontraits'],'source_release':tm.PINS['eltontraits'][0],
            'source_record_id':e['record_id'],'certainty':'0','source_note':'GenAvg'},
            'source_url':tm.source_url(e),'citation':'Wilman et al.'}]
        trait=read_traits(repo,store,lineage(e))[0]
        self.assertEqual(217.48,trait['value']); self.assertTrue(trait['inferred'])
        self.assertEqual('0',trait['certainty']); self.assertEqual('GenAvg',trait['source_note'])
        self.assertEqual('needs_review',trait['taxonomy_alignment']['status'])


if __name__=='__main__': unittest.main()
