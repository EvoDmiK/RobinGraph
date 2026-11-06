"""Read-only by default; --apply-confirmed applies only the reviewed additive TEST migration."""
import argparse
import hashlib
import json
import os
from pathlib import Path

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--apply-confirmed',action='store_true')
args=parser.parse_args()
work=Path('/tmp/robingraph-n8n-audio-20261105')
source=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-claude')
coordinator=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex')
values=dict(line.split('=',1) for line in Path('/Users/kimdove/robingraph-test/current/.env.nas.test').read_text().splitlines() if '=' in line and not line.startswith('#'))
os.environ.update(values)
os.environ['ROBINGRAPH_POSTGRES_INTEGRATION_TESTS']='1'
from robingraph.ingest.postgres import PostgresSettings, discover_migrations, apply_migrations
from robingraph.ingest.audio_store import AudioStore
settings=PostgresSettings.from_environment()
assert (settings.host,settings.port,settings.database,settings.schema)==('192.168.219.99',5433,'robingraph_test','ingest')
expected_identity=json.loads((work/'pg-server-identity.json').read_text())
assert expected_identity['database']=='robingraph_test' and expected_identity['schema']=='ingest' and expected_identity['server_port']==5432
migrations=discover_migrations()
assert [item.version for item in migrations]==['0001','0002','0003','0004','0005']
assert migrations[-1].name=='0005_audio_candidates.sql'
for name in ['src/robingraph/ingest/postgres.py','src/robingraph/ingest/migrations/0005_audio_candidates.sql']:
    assert (source/name).read_bytes()==(coordinator/name).read_bytes(), 'Root reviewed source differs: '+name
with AudioStore(settings).session() as cursor:
    cursor.execute('SET TRANSACTION READ ONLY')
    cursor.execute('SELECT current_database() AS database,current_schema() AS schema,inet_server_addr()::text AS server_address,inet_server_port() AS server_port')
    assert cursor.fetchone()==expected_identity, 'Actual PostgreSQL server identity changed'
    cursor.execute('SELECT version,name,checksum FROM _schema_migration ORDER BY version')
    ledger=cursor.fetchall()
    expected=[{'version':item.version,'name':item.name,'checksum':item.checksum} for item in migrations[:-1]]
    assert ledger==expected,'Ledger must contain exactly the unchanged reviewed migrations 0001-0004'
    cursor.execute("SELECT count(*) AS count FROM pg_catalog.pg_tables WHERE schemaname=%s AND tablename='audio_recording_candidate'",(settings.schema,))
    assert cursor.fetchone()['count']==0
receipt={'target':'test','host':settings.host,'port':settings.port,'database':settings.database,'schema':settings.schema,
         'actual_server':expected_identity,'before_ledger':ledger,'migration':migrations[-1].name,
         'migration_sha256':migrations[-1].checksum,'writes':0,'production_changed':False,'credentials_recorded':False}
if args.apply_confirmed:
    report=apply_migrations(settings)
    assert report.applied==('0005_audio_candidates.sql',)
    receipt.update(applied=list(report.applied),writes='additive schema only')
    with AudioStore(settings).session() as cursor:
        cursor.execute('SET TRANSACTION READ ONLY')
        cursor.execute('SELECT count(*) AS count FROM audio_recording_candidate')
        assert cursor.fetchone()['count']==0
        cursor.execute('SELECT version,name,checksum FROM _schema_migration ORDER BY version')
        receipt['after_ledger']=cursor.fetchall()
    (work/'test-audio-migration-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt))
