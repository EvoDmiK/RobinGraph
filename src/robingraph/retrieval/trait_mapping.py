"""Recover uniquely approved trait rows from stored candidates, without writes.

The crosswalk aligns concepts; it contains no trait values. Candidate evidence
comes from the allowed PostgreSQL source record in the active pinned release,
not from an invented EvidenceUnit relationship. Exact legacy claims are retained.
"""
from collections import Counter, defaultdict
from functools import lru_cache
import json
import math
from pathlib import Path
import re
from urllib.parse import quote

PINS = {
    'taxonomy': ('v2025b', '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411',
                 'https://explore.avilist.org/data/avilist-2025b.json', 'CC BY 4.0'),
    'eltontraits': ('figshare-article-3559887-v1:file-5631081',
                   '97216eb1797da077169ebb1ebea275db293b09fc62f8bb8911f9beb98c50d321',
                   'https://ndownloader.figshare.com/files/5631081', 'CC0 1.0'),
    'avonet': ('figshare-article-16586228-v7:file-34480856',
               'eb645e83dddb40f1654a3e8d721998dbca76eff540231b7b809267c1e96f8d3e',
               'https://ndownloader.figshare.com/files/34480856', 'CC BY 4.0'),
}
SOURCE_IDS = {'taxonomy':'taxonomy-avilist-v2025b', 'eltontraits':'traits-eltontraits-v1', 'avonet':'traits-avonet'}
DATASETS = {'eltontraits':'reference-bundle:avilist-v2025b:eltontraits-v1', 'avonet':'avonet:'+PINS['avonet'][0]}
PIPELINES = {'reference-taxonomy-traits':'eltontraits', 'reference-avonet':'avonet'}
REFERENCE_BUNDLE_SHA256 = 'fd3749be71afd154155b46c3e065e32485bd4106c1883b928a2064aa5c39822f'
FIELDS = {
    'beak_length_culmen': ('Beak.Length_Culmen','mm','Beak Culmen'),
    'beak_length_nares': ('Beak.Length_Nares','mm','Beak Nares'),
    'beak_width': ('Beak.Width','mm','Beak Width'), 'beak_depth': ('Beak.Depth','mm','Beak Depth'),
    'tarsus_length': ('Tarsus.Length','mm','Tarsus Length'), 'wing_length': ('Wing.Length','mm','Wing Length'),
    'tail_length': ('Tail.Length','mm','Tail Length'), 'body_mass': ('Mass','g','Body Mass'),
    'habitat': ('Habitat',None,None), 'habitat_density_category': ('Habitat.Density',None,None),
    'trophic_level': ('Trophic.Level',None,None), 'trophic_niche': ('Trophic.Niche',None,None),
    'primary_lifestyle': ('Primary.Lifestyle',None,None),
}
DIET_KEYS = {'invertebrate','endotherm_vertebrate','ectotherm_vertebrate','fish','unknown_vertebrate',
             'carrion','fruit','nectar','seed','other_plant'}
STRATA_KEYS = {'below_water_surface','around_water_surface','ground','understory','mid_high','canopy','aerial'}

CANDIDATE_QUERY = """
UNWIND $requests AS request
MATCH (t:Taxon:BirdTaxon {id:$taxon_id, rank:'species', policy_status:'allowed'})
      -[:IN_CONCEPT_SET]->(s:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
WHERE t.source_release=$taxonomy_release AND t.dataset_id=s.dataset_id
  AND t.scientific_name=request.target_name AND s.snapshot_sha256=$taxonomy_sha256
MATCH (t)-[:HAS_EXTERNAL_IDENTIFIER]->(i:ExternalIdentifier {scheme:'avibase'})
WHERE toLower(i.value)=request.target_avibase_id
MATCH (m:TaxonMappingCandidate {id:request.candidate_id, dataset_id:request.dataset_id, policy_status:'allowed'})
WHERE m.source_record_id=request.record_id AND m.source_scientific_name=request.source_name
  AND m.last_seen_run_id=request.run_id AND m.resolution_status='open'
  AND (m.taxonomy_release IS NULL OR m.taxonomy_release=$taxonomy_release)
RETURN m{.*} AS candidate
LIMIT 8
"""


def record_id(entry):
    if entry['dataset']=='eltontraits':
        return 'eltontraits-record:v1:'+entry['source_id']
    return 'avonet:'+PINS['avonet'][0]+':'+quote(entry['source_name'],safe="-_.!~*'()")


def accepted_evidence(entry):
    """Recheck the crosswalk's permitted 1:1 method, including split/lump vetoes."""
    ev=entry.get('evidence')
    target=entry.get('target_avibase_id')
    if not isinstance(ev,dict) or not isinstance(target,str) or not re.fullmatch(r'avibase-[0-9a-fA-F]{8}',target):
        return False
    if entry['dataset']=='avonet':
        return (entry['method']=='avibase_id_unique' and entry['source_taxonomy']=='HBW-BirdLife v5.0'
                and entry['source_id'].lower()==target.lower() and ev.get('inference') in ('YES','NO'))
    return (entry['method']=='birdtree_birdlife_avibase_chain' and entry['source_taxonomy']=='BL3'
            and ev.get('match_types')==['1BL to 1BT'] and ev.get('birdtree_name')==entry['source_name']
            and isinstance(ev.get('birdlife_names'),list) and len(ev['birdlife_names'])==1
            and isinstance(ev['birdlife_names'][0],str) and bool(ev['birdlife_names'][0].strip())
            and isinstance(ev.get('avibase_id'),str) and ev['avibase_id'].lower()==target.lower())


def build_index(data):
    """Fail closed on source pins; quarantine malformed/conflicting entries only."""
    if data.get('schema_version')!=1 or data.get('taxonomy_release')!=PINS['taxonomy'][0]:
        return None
    for source,pin in PINS.items():
        matches=[s for s in data.get('sources',[]) if isinstance(s,dict) and s.get('id')==SOURCE_IDS[source]]
        if len(matches)!=1 or tuple(matches[0].get(k) for k in ('release','sha256','url','license_name'))!=pin:
            return None
    columns=data.get('schema',{}).get('entry_columns')
    expected=['dataset','source_row','source_id','source_name','source_taxonomy','target_sequence','target_name',
              'target_avibase_id','status','method','name_relation','reason','evidence']
    if columns!=expected: return None
    entries=[]
    for raw in data.get('entries',[]):
        if not isinstance(raw,list) or len(raw)!=len(columns): continue
        e=dict(zip(columns,raw))
        if (e['dataset'] not in DATASETS or not isinstance(e['source_row'],int) or isinstance(e['source_row'],bool)
                or e['source_row']<2 or not isinstance(e['source_id'],str) or not e['source_id']
                or not isinstance(e['source_name'],str) or not e['source_name'].strip()
                or e['status'] not in ('accepted','needs_review','unresolved')): continue
        if e['target_sequence'] is not None and not re.fullmatch(r'[1-9][0-9]*',str(e['target_sequence'])): continue
        e['record_id']=record_id(e)
        e['accepted_valid']=e['status']=='accepted' and accepted_evidence(e)
        entries.append(e)
    records=Counter((e['dataset'],e['record_id']) for e in entries)
    targets=Counter((e['dataset'],str(e['target_sequence'])) for e in entries if e['accepted_valid'])
    by_target=defaultdict(list); by_record={}
    for e in entries:
        if records[(e['dataset'],e['record_id'])]!=1: continue
        if e['accepted_valid'] and targets[(e['dataset'],str(e['target_sequence']))]!=1: e['accepted_valid']=False
        by_record[(e['dataset'],e['record_id'])]=e
        if e['target_sequence'] is not None:
            by_target[(e['dataset'],str(e['target_sequence']))].append(e)
    return {'by_target':dict(by_target),'by_record':by_record,'taxonomy_release':data['taxonomy_release']}


@lru_cache(maxsize=1)
def crosswalk_index():
    try:
        return build_index(json.loads(Path(__file__).with_name('trait_crosswalk.json').read_text(encoding='utf-8')))
    except (OSError,ValueError,TypeError,KeyError):
        return None


def active_provenance(context, source, lineage):
    """Require real allowed active context and exact snapshot metadata, no fallback."""
    try:
        if context.dataset.id!=DATASETS[source] or context.dataset.policy_status!='allowed': return False
        cur=context.cursor; meta=context.release.metadata
        if not isinstance(meta,dict): return False
        concept=cur.get('concept_set_id',cur.get('taxonomy_concept_set_id'))
        if (concept!=lineage.concept_set_id or cur.get('taxonomy_release')!=lineage.taxonomy_release
                or lineage.taxonomy_release!=PINS['taxonomy'][0]
                or lineage.concept_set_id!='rg:concept-set:avilist-'+PINS['taxonomy'][0]): return False
        if source=='avonet':
            return (context.release.release_key==PINS[source][0] and context.release.content_sha256==PINS[source][1]
                    and cur.get('trait_release',context.release.release_key)==PINS[source][0]
                    and meta.get('taxonomy_release')==lineage.taxonomy_release
                    and meta.get('taxonomy_concept_set_id')==lineage.concept_set_id
                    and meta.get('sheet')=='AVONET1_BirdLife')
        return (cur.get('trait_release')==PINS[source][0] and meta.get('trait_release')==PINS[source][0]
                and meta.get('trait_sha256')==PINS[source][1] and meta.get('taxonomy_sha256')==PINS['taxonomy'][1]
                and meta.get('taxonomy_release')==lineage.taxonomy_release and meta.get('concept_set_id')==lineage.concept_set_id
                and context.release.content_sha256==REFERENCE_BUNDLE_SHA256
                and context.release.release_key=='reference-bundle:sha256-'+context.release.content_sha256)
    except (AttributeError,TypeError):
        return False


def source_records(store, context, ids):
    """Read canonical evidence only from the current PostgreSQL source release."""
    try:
        with store._connect() as connection:
            connection.execute('SET TRANSACTION READ ONLY')
            rows=connection.execute("""
                SELECT s.id,s.external_id,s.raw_object_uri,s.raw_sha256,s.payload
                FROM source_record s JOIN ingestion_run r ON r.id=%s
                WHERE s.id=ANY(%s) AND s.source_release_id=%s
                  AND s.record_type='trait_profile' AND s.license_policy_status='allowed'
                  AND r.source_release_id=s.source_release_id AND r.status='succeeded'
            """,(context.last_successful_run_id,ids,context.release.id)).fetchall()
        return {r[0]:dict(zip(('id','external_id','url','sha256','payload'),r)) for r in rows}
    except Exception:
        # Candidate recovery is optional: preserve good exact traits on failure.
        return {}


def source_url(entry):
    base=PINS[entry['dataset']][2]
    if entry['dataset']=='eltontraits': return base+'#SpecID='+quote(entry['source_id'],safe='')
    return base+'#sheet=AVONET1_BirdLife&row='+str(entry['source_row'])


def valid_record(record, entry):
    if not isinstance(record,dict): return False
    p=record.get('payload'); source=entry['dataset']
    if (record.get('id')!=entry['record_id'] or record.get('sha256')!=PINS[source][1]
            or record.get('url')!=source_url(entry) or not isinstance(p,dict)
            or p.get('scientific_name')!=entry['source_name']): return False
    if source=='eltontraits':
        return (record.get('external_id')=='eltontraits:'+entry['source_id'] and p.get('source_id')=='eltontraits'
                and p.get('trait_release')==PINS[source][0])
    return (p.get('row_number')==entry['source_row'] and p.get('sheet')=='AVONET1_BirdLife'
            and p.get('avibase_id')==entry['source_id'] and p.get('inference_raw')==entry['evidence']['inference'])


def number(value, *, positive=False):
    if isinstance(value,bool) or not isinstance(value,(float,int)) or not math.isfinite(value): raise ValueError('invalid_number')
    if positive and value<=0: raise ValueError('nonpositive_measurement')
    return value


def distribution(value, keys):
    if not isinstance(value,dict) or set(value)!=keys: raise ValueError('invalid_distribution_shape')
    known=[number(v) for v in value.values() if v is not None]
    if any(v<0 or v>100 for v in known) or (known and not 99<=sum(known)<=101): raise ValueError('invalid_distribution_value')
    return value if known else None


def elton_inferred(name, certainty):
    """Only explicit interpolation codes; C alone is not proof of inference.

    EltonTraits metadata.htm (Figshare file 5631093): body mass / foraging
    SpecLevel 0 lacks species data; diet D1/D2 is interpolated. Preserve the
    original certainty separately rather than collapsing all uncertainty.
    """
    code=certainty.strip().upper() if isinstance(certainty,str) else None
    if name in ('body_mass','foraging_strata_distribution'): return code=='0'
    if name in ('diet_category','diet_distribution'): return code in ('D1','D2')
    return False


def normalized_traits(profile, entry, record):
    """Validate stored normalization output; preserve source zeros and booleans."""
    if not isinstance(profile,dict) or profile.get('scientific_name')!=entry['source_name']: raise ValueError('profile_identity')
    if entry['dataset']=='eltontraits':
        if profile.get('source_taxon_id')!=entry['source_id'] or profile.get('source_taxonomy')!='BL3': raise ValueError('profile_taxonomy')
        traits=[]
        for key in ('body_mass_source','body_mass_spec_level','diet_source','diet_certainty','foraging_source','foraging_spec_level'):
            if profile.get(key) is not None and not isinstance(profile[key],str): raise ValueError('invalid_source_metadata')
        for key in ('body_mass_g','nocturnal','pelagic_specialist','diet_category','diet_distribution','foraging_distribution'):
            if key not in profile: raise ValueError('missing_profile_field')
        mass=profile['body_mass_g']
        if mass is not None:
            traits.append({'name':'body_mass','value':number(mass,positive=True),'unit':'g',
                           'source_note':profile.get('body_mass_source'),'certainty':profile.get('body_mass_spec_level')})
        for key in ('nocturnal','pelagic_specialist'):
            value=profile[key]
            if value is not None:
                if number(value) not in (0,1): raise ValueError('invalid_boolean_code')
                if key=='nocturnal': traits.append({'name':key,'value':value==1,'unit':None})
        category=profile['diet_category']
        if category is not None:
            if not isinstance(category,str) or not category.strip(): raise ValueError('invalid_category')
            traits.append({'name':'diet_category','value':category,'unit':None,'source_note':profile.get('diet_source'),'certainty':profile.get('diet_certainty')})
        for key,name,keys,prefix in [('diet_distribution','diet_distribution',DIET_KEYS,'diet'),
                                     ('foraging_distribution','foraging_strata_distribution',STRATA_KEYS,'foraging')]:
            value=distribution(profile[key],keys)
            if value is not None:
                traits.append({'name':name,'value':value,'unit':'percent','source_note':profile.get(prefix+'_source'),
                               'certainty':profile.get('diet_certainty' if prefix=='diet' else 'foraging_spec_level')})
        return [{**t,'inferred':elton_inferred(t['name'],t.get('certainty')),'summary_statistic':None} for t in traits]
    if (profile.get('id')!=entry['record_id'] or profile.get('row_number')!=entry['source_row']
            or profile.get('avibase_id')!=entry['source_id'] or profile.get('source_uri')!=source_url(entry)
            or profile.get('inference_raw')!=entry['evidence']['inference']): raise ValueError('profile_identity')
    payload=record['payload']
    for key in ('inference_raw','inferred_fields_raw','reference_species','sample_size','avibase_id','row_number'):
        if profile.get(key)!=payload.get(key): raise ValueError('profile_record_metadata')
    size=profile.get('sample_size')
    if isinstance(size,bool) or not isinstance(size,int) or size<0: raise ValueError('sample_size')
    inferred_raw=profile.get('inferred_fields_raw')
    if inferred_raw is not None and not isinstance(inferred_raw,str): raise ValueError('inferred_fields')
    inferred={s.strip().lower() for s in (inferred_raw or '').split(';')}
    claims=profile.get('claims')
    if not isinstance(claims,list) or not claims or len(claims)>len(FIELDS): raise ValueError('invalid_claims')
    traits=[]; seen=set()
    for c in claims:
        if not isinstance(c,dict) or c.get('trait_name') not in FIELDS: raise ValueError('unknown_trait')
        name=c['trait_name']; field,unit,inferred_name=FIELDS[name]
        if name in seen: raise ValueError('duplicate_trait')
        seen.add(name)
        if (c.get('source_field')!=field or c.get('id')!=entry['record_id']+':'+name or c.get('unit')!=unit
                or c.get('evidence_kind')!='literature_dataset' or type(c.get('inferred')) is not bool
                or c['inferred']!=bool(inferred_name and inferred_name.lower() in inferred)): raise ValueError('claim_provenance')
        statistic='species_mean' if unit else 'species_category'
        if c.get('summary_statistic')!=statistic: raise ValueError('claim_statistic')
        if unit:
            value=number(c.get('value_num'),positive=True)
            if c.get('value_text') is not None or float(c.get('raw_value'))!=value: raise ValueError('claim_raw_value')
        else:
            value=c.get('value_text'); raw=c.get('raw_value')
            if not isinstance(value,str) or not value.strip() or value=='NA' or c.get('value_num') is not None: raise ValueError('claim_category')
            expected={'1':'dense','2':'semi_open','3':'open'}.get(raw) if name=='habitat_density_category' else raw
            if value!=expected: raise ValueError('claim_raw_category')
        traits.append({'name':name,'value':value,'unit':unit,'inferred':c['inferred'],'summary_statistic':statistic,
                       'source_field':field,'source_url':source_url(entry)+'&field='+field})
    return traits


def alignment(entry, target, *, verified=True):
    accepted=entry is not None and entry['accepted_valid'] and verified
    return {'status':'accepted' if accepted else 'needs_review',
            'method':entry['method'] if entry is not None else 'exact_name_legacy',
            'source_scientific_name':entry['source_name'] if entry is not None else target,
            'target_scientific_name':target,
            'reason':None if accepted else (entry.get('reason') if entry is not None else None) or 'source_concept_alignment_unverified'}


def apply_trait_mapping(repository, store, lineage, contexts, exact_traits, labels, display):
    """Annotate exact traits; add only accepted changed-name candidate values."""
    index=crosswalk_index(); target=lineage.items[-1]
    if target.rank!='species':
        return [t for t,_ in exact_traits]
    if index is None:
        return [{**t,'taxonomy_alignment':alignment(None,target.scientific_name,verified=False)}
                if t.get('dataset_id') in DATASETS.values() else t for t,_ in exact_traits]
    if lineage.taxonomy_release!=index['taxonomy_release']:
        return [t for t,_ in exact_traits]
    prefix='avilist-taxon:'+index['taxonomy_release']+':'
    if not target.taxon_id.startswith(prefix): return [t for t,_ in exact_traits]
    sequence=target.taxon_id[len(prefix):]
    active={PIPELINES[p]:c for p,c in contexts.items() if p in PIPELINES}
    result=[]
    for trait,claim in exact_traits:
        source=next((s for s,ds in DATASETS.items() if ds==trait['dataset_id']),None)
        if source is None: result.append(trait); continue
        if source=='eltontraits':
            trait={**trait,'inferred':bool(trait.get('inferred')) or elton_inferred(trait['name'],claim.get('certainty'))}
        rid=claim.get('source_record_id')
        entry=index['by_record'].get((source,rid)) if isinstance(rid,str) else None
        if entry is not None and (str(entry['target_sequence'])!=sequence or entry['target_name']!=target.scientific_name): entry=None
        verified=source in active and active_provenance(active[source],source,lineage)
        result.append({**trait,'taxonomy_alignment':alignment(entry,target.scientific_name,verified=verified)})
    existing={(t['dataset_id'],t['name']) for t in result}; requests=[]; selected={}
    for source,context in active.items():
        if not active_provenance(context,source,lineage): continue
        entries=[e for e in index['by_target'].get((source,sequence),[]) if e['accepted_valid']
                 and e['name_relation']=='name_changed' and e['target_name']==target.scientific_name
                 and e['source_name']!=target.scientific_name]
        if len(entries)!=1: continue
        e=entries[0]; rid=e['record_id']
        candidate_id=('taxon-mapping-candidate:eltontraits-v1:'+e['source_id'] if source=='eltontraits'
                      else rid+':candidate:'+lineage.taxonomy_release)
        selected[rid]=(e,context)
        requests.append({'candidate_id':candidate_id,'dataset_id':context.dataset.id,'record_id':rid,
                         'source_name':e['source_name'],'target_name':e['target_name'],
                         'target_avibase_id':e['target_avibase_id'].lower(),'run_id':context.last_successful_run_id})
    if not requests: return result
    try:
        rows=repository._run(CANDIDATE_QUERY,requests=requests,taxon_id=target.taxon_id,
                             concept_set_id=lineage.concept_set_id,taxonomy_release=lineage.taxonomy_release,
                             taxonomy_sha256=PINS['taxonomy'][1])
    except Exception: return result
    by_id=defaultdict(list)
    for row in rows:
        candidate=row.get('candidate') if isinstance(row,dict) else None
        if isinstance(candidate,dict) and isinstance(candidate.get('source_record_id'),str):
            by_id[candidate['source_record_id']].append(candidate)
    for rid,(e,context) in selected.items():
        candidates=by_id[rid]
        if len(candidates)!=1: continue
        c=candidates[0]; request=next(r for r in requests if r['record_id']==rid)
        # Python gates also protect adapters/tests and malformed query results.
        if (c.get('id')!=request['candidate_id'] or c.get('dataset_id')!=context.dataset.id
                or c.get('policy_status')!='allowed' or c.get('resolution_status')!='open'
                or c.get('last_seen_run_id')!=context.last_successful_run_id
                or c.get('source_scientific_name')!=e['source_name']
                or c.get('taxonomy_release') not in (None,lineage.taxonomy_release)
                or c.get('source_release') not in (None,PINS[e['dataset']][0])): continue
        if e['dataset']=='eltontraits' and (c.get('source_taxon_id')!=e['source_id'] or c.get('source_taxonomy')!='BL3'): continue
        if e['dataset']=='avonet' and c.get('source_taxonomy')!='HBW-BirdLife v5': continue
        records=source_records(store,context,[rid]); record=records.get(rid)
        if not valid_record(record,e): continue
        try:
            raw=c.get('profile_json')
            if not isinstance(raw,str) or len(raw)>100_000: continue
            profile=json.loads(raw)
            recovered=normalized_traits(profile,e,record)
        except (ValueError,TypeError,KeyError,OverflowError): continue
        for trait in recovered:
            key=(context.dataset.id,trait['name'])
            if trait['name'] not in labels or key in existing: continue
            source=e['dataset']
            result.append({**trait,'label':labels[trait['name']],'display':display(trait['name'],trait['value']),
                           'dataset_id':context.dataset.id,'release':PINS[source][0],
                           'license_name':PINS[source][3],'source_name':context.dataset.name,
                           'source_url':trait.get('source_url',source_url(e)),
                           'citation':'Wilman et al. (2014), EltonTraits 1.0' if source=='eltontraits' else 'Tobias et al. (2022), AVONET; Figshare 16586228 v7',
                           'source_record_id':rid,'evidence_kind':'stored_source_record',
                           'taxonomy_alignment':alignment(e,target.scientific_name),
                           'mapping_provenance':{'read_time_recovery':True,'source_snapshot_sha256':PINS[source][1],
                                                 'crosswalk_snapshot_sha256':PINS['avonet'][1],
                                                 'taxonomy_snapshot_sha256':PINS['taxonomy'][1]}})
            existing.add(key)
    return result
