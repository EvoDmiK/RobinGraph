#!/usr/bin/env python3
"""Read-only audit: compare an explicitly selected AviList release with a pinned JSON snapshot.

No credentials or environment values are serialized. No graph updates are run.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from neo4j import GraphDatabase, READ_ACCESS
from robingraph.environment import load_local_environment
from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.species_profile import CONSERVATION_LABELS

QUERY = """
MATCH (t:Taxon:BirdTaxon {rank:'species', policy_status:'allowed'})
      -[:IN_CONCEPT_SET]->(s:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
WHERE t.source_release=s.version AND t.dataset_id=s.dataset_id
RETURN t.id AS taxon_id, t.source_taxon_id AS sequence,
       t.scientific_name AS scientific_name, t.source_id AS source_id,
       t.source_release AS source_release,
       t.iucn_red_list_category_raw AS category_raw,
       t.birdlife_url AS birdlife_url, s.snapshot_uri AS snapshot_uri,
       s.snapshot_sha256 AS snapshot_sha256
ORDER BY taxon_id
"""


def audit(rows, snapshot):
    expected = {str(row[0]): row for row in snapshot if row[1] == 'species'}
    counts = Counter(row['category_raw'] for row in rows)
    allowed = set(CONSERVATION_LABELS) | {'CR (PE)', 'CR (PEW)'}
    mismatches, missing, invalid, formatting = [], [], [], []
    observed = set()
    for row in rows:
        sequence = str(row['sequence'])
        observed.add(sequence)
        original = expected.get(sequence)
        if original is None:
            missing.append(row['taxon_id'])
        elif (original[5].strip(), original[15].strip() if isinstance(original[15],str) else original[15]) != (row['scientific_name'], row['category_raw']):
            mismatches.append({'taxon_id':row['taxon_id'], 'scientific_name':row['scientific_name'],
                               'stored_category':row['category_raw'], 'source_category':original[15]})
        elif original[15] != row['category_raw']:
            formatting.append({'taxon_id':row['taxon_id'], 'source_value':original[15], 'stored_value':row['category_raw']})
        if row['category_raw'] not in allowed or row['source_id'] != 'avilist-' + row['source_release']:
            invalid.append(row['taxon_id'])
    totals = len(rows)
    keys = Counter(row['taxon_id'] for row in rows)
    return {'rows':totals, 'expected_species':len(expected),
            'releases':dict(Counter(row['source_release'] for row in rows)),
            'category_counts':dict(sorted(counts.items(), key=lambda x:str(x[0]))),
            'category_shares':{str(k):round(v / totals, 6) for k,v in counts.items()} if totals else {},
            'duplicate_taxon_ids':sum(count-1 for count in keys.values()),
            'missing_source_rows':missing, 'missing_graph_sequences':sorted(set(expected)-observed),
            'source_mismatches':mismatches, 'source_format_differences':formatting, 'invalid_source_identity_or_category':invalid,
            'ne_rows':counts['NE'],
            'ne_with_birdlife_url':sum(row['category_raw']=='NE' and bool(row['birdlife_url']) for row in rows),
            'matched_category_without_birdlife_url':sum(row['category_raw'] not in ('NE',None,'') and not row['birdlife_url'] for row in rows),
            'samples':[row for row in rows if row['scientific_name'] in ('Pica serica','Pica pica','Anas platyrhynchos','Cyanopsitta spixii')]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot',type=Path,required=True)
    parser.add_argument('--env-file',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--concept-set-id',required=True)
    parser.add_argument('--taxonomy-release',required=True)
    args=parser.parse_args()
    data=args.snapshot.read_bytes()
    snapshot=json.loads(data)
    load_local_environment(args.env_file)
    settings=Neo4jSettings.from_environment()
    with GraphDatabase.driver(settings.uri,auth=(settings.username,settings.password),connection_timeout=8) as driver:
        with driver.session(database=settings.database,default_access_mode=READ_ACCESS) as session:
            rows=session.execute_read(lambda tx:tx.run(QUERY,concept_set_id=args.concept_set_id, taxonomy_release=args.taxonomy_release).data())
    result=audit(rows,snapshot)
    result.update(concept_set_id=args.concept_set_id, taxonomy_release=args.taxonomy_release, checked_at=datetime.now(timezone.utc).isoformat(), mode='neo4j_read_only',
                  comparison_snapshot_sha256=hashlib.sha256(data).hexdigest(),
                  independent_iucn_assessment_check=False,
                  ne_meaning='AviList source code; taxonomy/assessment linking needs review, not a confirmed IUCN NE assessment')
    result['stored_snapshot_checksum_matches']=all(row['snapshot_sha256']==result['comparison_snapshot_sha256'] for row in rows) and bool(rows)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:result[key] for key in ('rows','expected_species','category_counts','duplicate_taxon_ids','ne_rows','ne_with_birdlife_url','matched_category_without_birdlife_url','stored_snapshot_checksum_matches')},ensure_ascii=False))


if __name__=='__main__':
    main()
