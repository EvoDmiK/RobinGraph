#!/usr/bin/env python3
"""Audit every species conservation result with batched TEST rows; no DB writes.

--rows replays a saved read-only export (not live verification).
Without --rows, fetch actual active TEST taxonomy rows before replaying readers.
"""
import argparse
from collections import Counter
from hashlib import sha256
import json
from types import SimpleNamespace
from pathlib import Path
from robingraph.retrieval import species_profile as sp
from robingraph.retrieval.taxonomy_lineage import TaxonomyLineage, LineageTaxon


def audit(rows, mode):
    results, errors = [], []
    if len({r['taxon_id'] for r in rows}) != len(rows):
        raise ValueError('duplicate taxon identity')
    for row in rows:
        taxon = LineageTaxon(row['taxon_id'], 'species', row['scientific_name'], row['authority'])
        lineage = TaxonomyLineage(row['scientific_name'], 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b', (taxon,))
        try:
            result = sp.read_conservation(SimpleNamespace(_run=lambda *a, **kw: [row]), lineage)
            ref = result.get('reference_assessment') or {}
            if ref and (ref.get('scientific_name') != row['scientific_name'] or
                        ref.get('taxon_id', row['taxon_id']) != row['taxon_id']):
                raise ValueError('reference-target identity mismatch')
            if ref.get('evidence_kind') == 'reviewed_expert_reference' and (
                    result.get('category') is not None or ref.get('assessment_year') is not None or
                    ref.get('independently_verified') is not False):
                raise ValueError('expert account promoted to independent assessment')
            results.append({'taxon': {'taxon_id':row['taxon_id'], 'scientific_name':row['scientific_name'], 'rank':'species'},
                            'conservation':result})
        except Exception as exc:
            errors.append({'taxon_id':row['taxon_id'], 'error':type(exc).__name__, 'message':str(exc)})
    return {'mode':mode, 'input_rows_sha256':sha256(json.dumps(rows,sort_keys=True,ensure_ascii=False).encode()).hexdigest(),
            'species_count':len(rows), 'processed':len(results), 'errors':errors,
            'status_counts':dict(Counter(r['conservation'].get('assessment_status') for r in results)),
            'reference_sources':dict(Counter((r['conservation'].get('reference_assessment') or {}).get('source_id','none') for r in results)),
            'unlinked_without_reference':sum(r['conservation'].get('assessment_status')=='needs_review' and not r['conservation'].get('reference_assessment') for r in results),
            'species':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows',type=Path)
    args=parser.parse_args()
    if args.rows:
        rows=json.loads(args.rows.read_text());mode='saved read-only DB rows replay; not a live DB/API test'
    else:
        from robingraph.graph.settings import Neo4jSettings
        from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
        repo=Neo4jTaxonomyLineageRepository(Neo4jSettings.from_environment())
        query=sp.CONSERVATION_QUERY.replace('id:$taxon_id, ', '').replace('RETURN t.iucn', 'RETURN t.id AS taxon_id, t.scientific_name AS scientific_name, t.authority AS authority, t.iucn')
        try: rows=repo._run(query,concept_set_id='rg:concept-set:avilist-v2025b',taxonomy_release='v2025b')
        finally: repo.close()
        mode='live DB batch rows replayed through deployed reader; not all-species HTTP'
    report=audit(rows,mode)
    print(json.dumps(report,ensure_ascii=False))
    if report['errors']: raise SystemExit(1)

if __name__=='__main__':main()
