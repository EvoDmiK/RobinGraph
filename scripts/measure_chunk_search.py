#!/usr/bin/env python3
"""Read-only TEST Chunk latency probe; never bootstraps or indexes data.

Run inside the existing TEST app (environment credentials stay inside it).
Query embeddings are generated once, timed separately, and reused for warm
sequential DB probes. This is a fixture baseline, not a scale/load test.
"""
import json
import math
import os
from pathlib import Path
import statistics
import time
from types import SimpleNamespace

from neo4j import GraphDatabase, Query, READ_ACCESS
from robingraph.embeddings import JinaEmbeddingClient
from robingraph.graph.settings import Neo4jSettings
from robingraph.ingest.postgres import PostgresSettings
from robingraph.retrieval import neo4j_hybrid as hybrid


def summary(samples):
    values = sorted(samples)
    return {'samples': len(values), 'p50_ms': round(statistics.median(values), 3),
            'p95_ms': round(values[math.ceil(len(values) * .95) - 1], 3),
            'max_ms': round(max(values), 3)}


def require_test(settings):
    if os.environ.get('ROBINGRAPH_DEPLOY_TARGET') != 'test' or settings.uri != 'bolt://192.168.219.98:7687':
        raise ValueError('This probe only supports the current confirmed TEST Neo4j')


def main():
    settings = Neo4jSettings.from_environment()
    require_test(settings)
    questions = [json.loads(line) for line in Path('data/eval/v1/search-questions.jsonl').read_text().splitlines()]
    repeats = 10
    report = {'target': 'test', 'neo4j_host': '192.168.219.98', 'repeats': repeats,
              'question_count': len(questions), 'concurrency': 1,
              'scope': 'warm sequential fixture baseline; embedding generation measured separately',
              'modes': {}, 'embedding': [], 'stage_samples': {}}
    driver = GraphDatabase.driver(settings.uri, auth=(settings.username, settings.password))
    def run(query, **params):
        with driver.session(database=settings.database, default_access_mode=READ_ACCESS) as session:
            return session.run(Query(query, timeout=20), **params).data()
    def snapshot():
        return run('MATCH (c:Chunk) RETURN count(c) AS count, sum(size(coalesce(c.text,""))) AS text_characters, '
                   'sum(CASE WHEN c.hybrid_vector IS NULL THEN 0 ELSE size(c.hybrid_vector) END) AS vector_components')
    try:
        report['corpus_before'] = snapshot()
        report['text_utf8_bytes'] = run('MATCH (c:Chunk) RETURN c.text AS text')
        report['text_utf8_bytes'] = sum(len((row['text'] or '').encode()) for row in report['text_utf8_bytes'])
        try:
            report['server_memory_config'] = run("SHOW SETTINGS YIELD name,value WHERE name IN ['server.memory.heap.max_size','server.memory.heap.initial_size','server.memory.pagecache.size'] RETURN name,value")
        except Exception as error:
            report['server_memory_config'] = {'unavailable': type(error).__name__}
        embedder = JinaEmbeddingClient.from_env()
        vectors = {}
        for question in questions:
            start = time.perf_counter()
            try:
                vectors[question['question_ko']] = embedder.embed_query(question['question_ko'])
                report['embedding'].append({'question_id': question['question_id'], 'elapsed_ms': round((time.perf_counter()-start)*1000, 3), 'ok': True})
            except Exception as error:
                report['embedding'].append({'question_id': question['question_id'], 'ok': False, 'error_type': type(error).__name__})
        cached = SimpleNamespace(profile=embedder.profile, embed_query=lambda text: vectors[text])
        with hybrid.Neo4jHybridSearch(settings) as search:
            for mode, channels in [('fulltext', ('fulltext',)), ('vector', ('vector',)), ('hybrid', ('fulltext', 'vector'))]:
                if mode != 'fulltext' and len(vectors) != len(questions):
                    report['modes'][mode] = {'skipped': 'query embedding unavailable'}
                    continue
                durations, counts, violations, warning_counts = [], [], 0, []
                for repetition in range(repeats + 1):
                    for question in questions:
                        start = time.perf_counter()
                        result = search.search(hybrid.HybridSearchRequest(question['question_ko'], limit=5, channels=channels),
                                               query_embedder=None if mode == 'fulltext' else cached)
                        if repetition == 0:
                            continue
                        durations.append((time.perf_counter()-start)*1000)
                        counts.append(len(result.results))
                        warning_counts.append(len(result.warnings))
                        violations += len({r.chunk_id for r in result.results} & set(question.get('forbidden_chunk_ids', [])))
                report['modes'][mode] = {**summary(durations), 'returned_results_total': sum(counts),
                    'forbidden_result_count': violations, 'warning_count': sum(warning_counts),
                    'embedding_latency_excluded': True}
        stages = {'fulltext': [], 'vector': [], 'policy_recheck': []}
        policy = {'candidate_occurrences': 0, 'excluded_occurrences': 0, 'eligible_embedding_disallowed_occurrences': 0}
        if len(vectors) == len(questions):
            for _ in range(repeats):
                for question in questions:
                    start = time.perf_counter()
                    ft = run(hybrid._FULLTEXT_SEARCH_QUERY, index_name=hybrid.DEFAULT_FULLTEXT_INDEX_NAME,
                             query_text=hybrid.escape_lucene_query_text(question['question_ko']), top_k=25)
                    stages['fulltext'].append((time.perf_counter()-start)*1000)
                    start = time.perf_counter()
                    vr = run(hybrid._VECTOR_SEARCH_QUERY, index_name=hybrid.DEFAULT_VECTOR_INDEX_NAME, top_k=25,
                             query_vector=list(vectors[question['question_ko']]), expected_model=embedder.profile.model,
                             expected_dimensions=embedder.profile.dimensions, expected_normalized=embedder.profile.normalized)
                    stages['vector'].append((time.perf_counter()-start)*1000)
                    ids = sorted({r['chunk_id'] for r in ft+vr})
                    if ids:
                        start = time.perf_counter()
                        eligible = run(hybrid._RECHECK_AND_CITE_QUERY, chunk_ids=ids)
                        stages['policy_recheck'].append((time.perf_counter()-start)*1000)
                        policy['candidate_occurrences'] += len(ids)
                        policy['excluded_occurrences'] += len(ids)-len(eligible)
                        policy['eligible_embedding_disallowed_occurrences'] += sum(not row['embedding_allowed'] for row in eligible)
            report['stage_samples'] = {name: summary(values) for name, values in stages.items() if values}
            report['policy'] = policy
        report['corpus_after'] = snapshot()
        report['corpus_aggregate_unchanged'] = report['corpus_before'] == report['corpus_after']
    finally:
        driver.close()
    try:
        import psycopg
        pg = PostgresSettings.from_environment()
        if pg.host != '192.168.219.99' or pg.database != 'robingraph_test':
            raise ValueError('Only confirmed TEST PostgreSQL is allowed')
        kwargs = pg.connection_kwargs()
        kwargs.update(application_name='robingraph-rg101-readonly', connect_timeout=10,
                      options='-c default_transaction_read_only=on -c statement_timeout=10000')
        with psycopg.connect(**kwargs) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SHOW transaction_read_only')
                assert cursor.fetchone()[0] == 'on'
                cursor.execute("SELECT name,default_version,installed_version FROM pg_available_extensions WHERE name IN ('vector','pg_trgm','pg_bigm','pgroonga') ORDER BY name")
                report['postgres'] = {'database': pg.database, 'transaction_read_only': True,
                    'extensions': [dict(zip(['name','default_version','installed_version'], row)) for row in cursor.fetchall()]}
    except Exception as error:
        report['postgres'] = {'unavailable': type(error).__name__}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
