"""Read-only RG-202 prerequisite audit; run inside the configured TEST container.

python - < scripts/audit_retrieval_readiness.py
No indexing, extraction, database writes, or document text serialization.
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone

from neo4j import GraphDatabase, READ_ACCESS, unit_of_work

from robingraph.graph.settings import Neo4jSettings
from robingraph.retrieval.neo4j_hybrid import _RECHECK_AND_CITE_QUERY


QUERIES = {
    "counts": """MATCH (n) UNWIND labels(n) AS label
WITH label, count(*) AS count
WHERE label IN ['Document', 'Chunk', 'Claim', 'EvidenceUnit', 'Taxon',
                'HybridSearchChunk', 'HybridVectorChunk']
RETURN label, count ORDER BY label""",
    "corpus": """MATCH (d:Document) OPTIONAL MATCH (d)-[:HAS_CHUNK]->(c:Chunk)
RETURN labels(d) AS document_labels, count(DISTINCT d) AS documents,
       count(DISTINCT c) AS chunks, sum(size(coalesce(c.text, ''))) AS text_characters""",
    "indexes": """SHOW INDEXES YIELD name, type, state, labelsOrTypes, properties, options
WHERE type IN ['FULLTEXT', 'VECTOR']
RETURN name, type, state, labelsOrTypes, properties, options ORDER BY name""",
    "profiles": """MATCH (c:HybridVectorChunk)
RETURN c.hybrid_model AS model, c.hybrid_dimensions AS dimensions,
       c.hybrid_normalized AS normalized, count(*) AS chunks""",
    "chunk_relations": """MATCH (c:Chunk)-[r]-(n)
RETURN type(r) AS relationship, labels(n) AS target_labels, count(*) AS count
ORDER BY count DESC LIMIT 30""",
    "candidates": """MATCH (c:HybridSearchChunk:Fixture)
RETURN c.id AS chunk_id ORDER BY chunk_id LIMIT 1001""",
}

# Use the production reader's policy check instead of trusting search labels.
MANIFEST_QUERY = _RECHECK_AND_CITE_QUERY.replace(
    "RETURN c.id AS chunk_id,",
    "RETURN d.id AS document_id, labels(d) AS document_labels, "
    "c.content_hash AS content_hash, sr.raw_hash AS source_record_hash, "
    "c.id AS chunk_id,",
)


def summarize_manifest(rows):
    """Freeze only policy-rechecked, hash-matched records, without their text."""
    manifest = []
    invalid_hashes = 0
    for row in rows:
        text_hash = hashlib.sha256(row['text'].encode('utf-8')).hexdigest()
        if text_hash != row.get('content_hash'):
            invalid_hashes += 1
            continue
        synthetic = (row['document_id'].startswith('fixture-')
                     and row['source_url'].startswith('https://example.invalid/'))
        kind = ('synthetic' if synthetic else 'pmc_pilot'
                if 'PmcPilot' in row['document_labels'] else 'unclassified')
        manifest.append({
            'chunk_id': row['chunk_id'], 'document_id': row['document_id'],
            'content_hash': text_hash, 'source_record_hash': row['source_record_hash'],
            'source_id': row['source_id'], 'kind': kind,
            'embedding_allowed': row['embedding_allowed'],
        })
    manifest.sort(key=lambda item: (item['document_id'], item['chunk_id']))
    digest = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    return {'records': manifest, 'sha256': digest, 'invalid_content_hashes': invalid_hashes,
            'synthetic_documents': len({r['document_id'] for r in manifest if r['kind'] == 'synthetic'}),
            'pmc_pilot_documents': len({r['document_id'] for r in manifest if r['kind'] == 'pmc_pilot'}),
            'unclassified_documents': len({r['document_id'] for r in manifest if r['kind'] == 'unclassified'})}


def audit(session):
    # Bound one read transaction; no index bootstrap or corpus mutation.
    @unit_of_work(timeout=30)
    def read(tx):
        inventory = {name: tx.run(query).data() for name, query in QUERIES.items()}
        candidates = inventory.pop('candidates')
        truncated = len(candidates) > 1000
        ids = [row['chunk_id'] for row in candidates[:1000]]
        rows = tx.run(MANIFEST_QUERY, chunk_ids=ids).data() if ids else []
        manifest = summarize_manifest(rows)
        inventory['policy_rechecked_manifest'] = manifest
        inventory['manifest_truncated'] = truncated
        inventory['candidate_count_sampled'] = len(ids)
        inventory['policy_excluded_candidates'] = len(set(ids) - {r['chunk_id'] for r in rows})
        # These are prerequisites, not an automatic authorization to activate PPR.
        inventory['experiment_status'] = 'not_ready_for_quality_comparison'
        inventory['remaining_gates'] = [
            'Freeze a reviewed multi-document literature corpus with release provenance.',
            'Review passage-linked entity/fact extraction separately from taxonomy/trait claims.',
            'Freeze 50 questions (20 multi-hop minimum), tuning/heldout split and gold evidence.',
            'Measure baseline, then freeze improvement and resource thresholds before PPR implementation.',
        ]
        return inventory
    return session.execute_read(read)


def main():
    if os.getenv('ROBINGRAPH_DEPLOY_TARGET') != 'test':
        raise SystemExit('This audit requires ROBINGRAPH_DEPLOY_TARGET=test; no DB connection was opened.')
    settings = Neo4jSettings.from_environment()
    with GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password)) as driver:
        with driver.session(database=settings.database, default_access_mode=READ_ACCESS) as session:
            report = audit(session)
    report.update({'timestamp': datetime.now(timezone.utc).isoformat(),
                   'deployment_target': 'test', 'mode': 'live_db_read_only',
                   'scope': 'Current reader uses Fixture labels, including optional PmcPilot; manifest capped at 1000.'})
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
