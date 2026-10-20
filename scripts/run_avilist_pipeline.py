"""Manual TEST pilot: pinned source -> review -> verified PostgreSQL artifact.

No schedule, domain projection, name-index mutation or production path is provided.
Run as `python -m scripts.run_avilist_pipeline prepare|apply ...`.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
from urllib.request import Request, urlopen
from uuid import uuid4

from scripts import build_species_distribution as builder
from robingraph.ingest.postgres import PostgresSettings
from robingraph.ingest.store import (
    IngestionStore, IngestionRunInput, SourceDatasetInput, SourceReleaseInput, SourceRecordInput,
)

ROOT = Path(__file__).resolve().parents[1]
PIPELINE = 'avilist-distribution-pilot'
DATASET = 'rg:dataset:avilist-distribution-pilot'
MAX_SOURCE_BYTES = 25_000_000
API_URL = 'http://127.0.0.1:8000'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def prepare(source_path, output):
    from robingraph.ingest.avilist_pipeline import prepare_manifest

    if source_path is None:
        request = Request(builder.AVILIST_SOURCE['url'], headers={'User-Agent': 'RobinGraph TEST source pilot'})
        with urlopen(request, timeout=45) as response:
            # A redirect to another host or path must be reviewed too.
            if response.url != builder.AVILIST_SOURCE['url']:
                raise ValueError('Unexpected source redirect')
            source = response.read(MAX_SOURCE_BYTES + 1)
    else:
        if source_path.stat().st_size > MAX_SOURCE_BYTES:
            raise ValueError('Source exceeds size limit')
        source = source_path.read_bytes()
    if len(source) > MAX_SOURCE_BYTES:
        raise ValueError('Source exceeds size limit')
    names = (ROOT / 'src/robingraph/retrieval/species_ko_names.json').read_bytes()
    generator = Path(builder.__file__).read_bytes()
    bundle = builder.build(source, json.loads(names), builder.sha256(names), builder.sha256(generator))
    manifest = prepare_manifest(source, names, generator, bundle)
    # No overwriting an earlier operator review package.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'source.json').write_bytes(source)
    (output / 'manifest.json').write_bytes(encoded(manifest))
    (output / 'bundle.json').write_bytes(encoded(bundle))
    return {'status': 'review_required', 'manifest_sha256': digest(manifest), 'counts': bundle['counts']}


def load_review(package, approval_path):
    from robingraph.ingest.avilist_pipeline import prepare_manifest, validate_approval

    source = (package / 'source.json').read_bytes()
    names = (ROOT / 'src/robingraph/retrieval/species_ko_names.json').read_bytes()
    generator = Path(builder.__file__).read_bytes()
    bundle = json.loads((package / 'bundle.json').read_bytes())
    manifest = json.loads((package / 'manifest.json').read_bytes())
    rebuilt = builder.build(source, json.loads(names), builder.sha256(names), builder.sha256(generator))
    if encoded(bundle) != encoded(rebuilt):
        raise ValueError('Prepared bundle differs from recomputed source')
    if encoded(manifest) != encoded(prepare_manifest(source, names, generator, rebuilt)):
        raise ValueError('Prepared manifest or local inputs changed')
    approval = json.loads(approval_path.read_bytes())
    validate_approval(manifest, bundle, approval)
    return manifest, bundle, approval


def test_settings():
    if os.getenv('ROBINGRAPH_DEPLOY_TARGET') != 'test':
        raise ValueError('TEST target required before opening any DB connection')
    settings = PostgresSettings.from_environment()
    expected = ('192.168.219.99', 5433, 'robingraph_test', 'robingraph_test_app', 'ingest')
    if (settings.host, settings.port, settings.database, settings.username, settings.schema) != expected:
        raise ValueError('PostgreSQL target is outside the TEST allowlist')
    return settings


@contextmanager
def locked_store(settings):
    import psycopg

    with psycopg.connect(**settings.connection_kwargs(), autocommit=True) as connection:
        actual = connection.execute('SELECT current_database(), current_user').fetchone()
        if actual != ('robingraph_test', 'robingraph_test_app'):
            raise ValueError('Connected PostgreSQL identity differs from TEST')
        acquired = connection.execute(
            'SELECT pg_try_advisory_lock(hashtextextended(%s, 0))', (PIPELINE,),
        ).fetchone()[0]
        if not acquired:
            raise RuntimeError('Another pilot execution is running; retry later')
        try:
            from psycopg import sql
            existing = connection.execute(sql.SQL(
                'SELECT source_id, policy_status FROM {}.source_dataset WHERE id = %s'
            ).format(sql.Identifier(settings.schema)), (DATASET,)).fetchone()
            if existing is not None and existing != (builder.AVILIST_SOURCE['id'], 'allowed'):
                raise ValueError('Existing pilot source or license policy requires review')
            yield IngestionStore(settings)
        finally:
            connection.execute('SELECT pg_advisory_unlock(hashtextextended(%s, 0))', (PIPELINE,))


def request_json(path, body=None):
    request = Request(API_URL + path, data=None if body is None else encoded(body),
                      headers={'Content-Type': 'application/json'})
    with urlopen(request, timeout=45) as response:
        return json.load(response)


def verify_runtime(bundle):
    """Read-only regression gates, not projection of the pilot PG artifact."""
    from robingraph.embeddings import JinaEmbeddingClient
    from robingraph.graph.settings import Neo4jSettings
    from robingraph.retrieval.taxonomy_lineage_neo4j import Neo4jTaxonomyLineageRepository
    from robingraph.retrieval.taxon_name_vectors_neo4j import Neo4jTaxonNameVectorRepository

    settings = test_settings()
    graph = Neo4jSettings.from_environment()
    if (graph.uri, graph.database) != ('bolt://192.168.219.98:7687', 'neo4j'):
        raise ValueError('Neo4j target is outside the TEST allowlist')
    local_bundle = json.loads((ROOT / 'src/robingraph/retrieval/species_distribution.json').read_bytes())
    if encoded(bundle) != encoded(local_bundle):
        raise ValueError('Pilot bundle differs from installed distribution; domain deployment needs separate review')
    if request_json('/health').get('deployment_target') != 'test':
        raise ValueError('API did not identify as TEST')
    store = IngestionStore(settings)
    active = store.active_release_context('reference-taxonomy-traits')
    korean = store.active_release_context('korean-vernacular-names')
    if active is None:
        raise ValueError('No reviewed active taxonomy')
    context = (active.cursor.get('concept_set_id'), active.cursor.get('taxonomy_release'))
    if context != (builder.CONCEPT_SET_ID, builder.TAXONOMY_RELEASE):
        raise ValueError('Active taxonomy differs from pinned source')
    taxonomy = Neo4jTaxonomyLineageRepository(
        graph, lambda: None if korean is None else korean.dataset.id, lambda: context)
    vectors = Neo4jTaxonNameVectorRepository(graph)
    try:
        report = vectors.index_names(taxonomy.reviewed_name_candidates(), JinaEmbeddingClient.from_env(),
                                    context, dry_run=True)
    finally:
        vectors.close()
        taxonomy.close()
    if (report['to_embed'] or report['stale'] or not report['catalog_current']
            or report['schema'] != 'compatible' or report['constraint'] != 'compatible'):
        raise ValueError('Name index requires a separately reviewed update; no vector writes performed')
    checks = []
    for mention, science, scope, expected in (
        ('Kea', 'Nestor notabilis', 'outside', 'answer'),
        ('Kea', 'Nestor notabilis', 'all', 'answer'),
        ('Keaa', 'Nestor notabilis', 'outside', 'clarify'),
        ('청둥오리', 'Anas platyrhynchos', 'korea', 'answer'),
    ):
        response = request_json('/v1/chat', {'question': mention + '에 대해 알고 싶어', 'intent': 'profile',
                                             'species_scope': scope, 'defer_enrichment': True})
        if response.get('disposition') != expected or science not in json.dumps(response):
            raise ValueError(f'TEST search regression failed: {mention}/{scope}')
        if expected == 'clarify':
            resolution = response.get('entity_resolution') or {}
            candidates = resolution.get('candidates') or []
            if (resolution.get('status') != 'candidates' or resolution.get('method') != 'vector'
                    or science not in {candidate.get('scientific_name') for candidate in candidates}):
                raise ValueError('Typo did not return the expected vector candidate')
        if expected == 'answer':
            taxon = response.get('result', {}).get('profile', {}).get('taxon', {})
            planned = bundle['taxa'].get(taxon.get('taxon_id'))
            observed = taxon.get('distribution', {})
            if (planned is None or taxon.get('scientific_name') != science
                    or observed.get('status') != planned['status']
                    or encoded(observed.get('evidence')) != encoded(planned['evidence'])):
                raise ValueError('Live API distribution evidence differs from approved artifact')
        checks.append({'mention': mention, 'scope': scope, 'disposition': expected, 'passed': True})
    after = store.active_release_context('reference-taxonomy-traits')
    if after != active or store.active_release_context('korean-vernacular-names') != korean:
        raise ValueError('Active taxonomy or Korean names changed during verification')
    return {'name_index': report, 'search_regression': checks, 'projection_performed': False}


def store_bundle(store, manifest, bundle, approval, verification):
    key = digest(manifest)
    release_id = 'rg:release:avilist-pilot:' + key
    active = store.active_release_context(PIPELINE)
    if active is not None and (active.dataset.id != DATASET or active.release.dataset_id != DATASET
                               or active.dataset.source_id != builder.AVILIST_SOURCE['id']):
        raise ValueError('Pilot pipeline belongs to another dataset or source')
    if active is not None and active.release.id == release_id:
        if active.release.content_sha256 != digest(bundle) or active.release.metadata.get('manifest_sha256') != key:
            raise ValueError('Stored pilot provenance differs from reviewed package')
        return {'status': 'already_applied', 'release_id': release_id, 'run_id': active.last_successful_run_id}
    version = store.pipeline_state_version(PIPELINE)
    now = datetime.now(timezone.utc)
    run_id = 'avilist-pilot-' + str(uuid4())
    source = builder.AVILIST_SOURCE
    dataset = SourceDatasetInput(DATASET, source['id'], 'AviList reviewed distribution TEST pilot',
                                 'AviList Core Team', source['landing_url'], 'versioned', 'allowed',
                                 {'purpose': 'TEST composite artifact only; no domain projection',
                                  'sources': bundle['sources'], 'inputs': bundle['inputs']})
    artifact_uri = 'urn:robingraph:avilist-pilot:bundle:' + digest(bundle)
    release = SourceReleaseInput(release_id, DATASET, key, now, digest(bundle), artifact_uri,
                                 {'manifest_sha256': key, 'source_sha256': builder.AVILIST_SHA256,
                                  'sources': bundle['sources'], 'inputs': bundle['inputs']})
    run = IngestionRunInput(run_id, PIPELINE, release_id, now, config_sha256=key,
                           manifest={'prepared': manifest, 'approval': approval, 'verification': verification})
    store.begin_run(dataset, release, run)
    try:
        record = SourceRecordInput('rg:record:avilist-pilot:' + key, release_id, 'distribution-bundle',
                                   'reviewed_distribution_bundle', artifact_uri, digest(bundle), now,
                                   'avilist-pilot-v1', run_id, 'allowed', bundle)
        store.append_batch(run_id, records=(record,))
        state_version = store.activate_release(run_id, counts={'records': 1, **bundle['counts']},
                                               cursor_value={'manifest_sha256': key, 'projection_performed': False},
                                               expected_state_version=version)
    except Exception as error:
        # A lost commit response is uncertain until the committed pointer is read back.
        try:
            observed = store.active_release_context(PIPELINE)
            if observed is not None and observed.last_successful_run_id == run_id and observed.release.id == release_id:
                return {'status': 'applied_reconciled', 'release_id': release_id, 'run_id': run_id}
            store.fail_run(run_id, 'pilot_append_or_activation_failed')
        except Exception:
            error.add_note('Failure state could not be confirmed; retry will reconcile the pilot pointer.')
        raise
    return {'status': 'applied', 'release_id': release_id, 'run_id': run_id, 'state_version': state_version}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    prepare_command = commands.add_parser('prepare')
    prepare_command.add_argument('--source', type=Path, help='Optional cached pinned source; otherwise fetch official URL')
    prepare_command.add_argument('--output', type=Path, required=True)
    apply_command = commands.add_parser('apply')
    apply_command.add_argument('--package', type=Path, required=True)
    apply_command.add_argument('--approval', type=Path, required=True)
    apply_command.add_argument('--apply', action='store_true', help='Write TEST pilot artifact after all gates pass')
    args = parser.parse_args(argv)
    if args.command == 'prepare':
        result = prepare(args.source, args.output)
    else:
        settings = test_settings()
        manifest, bundle, approval = load_review(args.package, args.approval)
        verification = verify_runtime(bundle)
        if not args.apply:
            result = {'status': 'dry_run', 'verification': verification}
        else:
            with locked_store(settings) as store:
                result = {**store_bundle(store, manifest, bundle, approval, verification), 'verification': verification}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
