import json
import psycopg
from psycopg import sql
from robingraph.ingest.postgres import PostgresSettings
p=PostgresSettings.from_environment()
with psycopg.connect(**p.connection_kwargs()) as c:
    c.execute('SET TRANSACTION READ ONLY')
    database,role=c.execute('SELECT current_database(),current_user').fetchone()
    schema_owner=c.execute('SELECT pg_get_userbyid(nspowner) FROM pg_namespace WHERE nspname=%s',(p.schema,)).fetchone()[0]
    objects=[dict(zip(['name','kind','owner'],r)) for r in c.execute("SELECT relname,relkind,pg_get_userbyid(relowner) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=%s AND c.relkind IN ('r','p','S') ORDER BY relname",(p.schema,))]
    sequences=[]
    for o in objects:
        if o['kind']=='S':
            value,called=c.execute(sql.SQL('SELECT last_value,is_called FROM {}.{}').format(sql.Identifier(p.schema),sql.Identifier(o['name']))).fetchone()
            sequences.append({'name':o['name'],'last_value':value,'is_called':called})
    constraints=[dict(zip(['table','name','type','validated'],r)) for r in c.execute("SELECT r.relname,c.conname,c.contype,c.convalidated FROM pg_constraint c JOIN pg_class r ON r.oid=c.conrelid JOIN pg_namespace n ON n.oid=r.relnamespace WHERE n.nspname=%s ORDER BY r.relname,c.conname",(p.schema,))]
    statuses=[dict(zip(['status','count'],r)) for r in c.execute(sql.SQL('SELECT status,count(*) FROM {}.ingestion_run GROUP BY status ORDER BY status').format(sql.Identifier(p.schema)))]
    assert schema_owner==role
    assert all(o['owner']==role for o in objects)
    assert all(o['validated'] for o in constraints)
    print(json.dumps({'database':database,'role':role,'schema_owner':schema_owner,'objects':objects,'sequences':sequences,'constraints':constraints,'run_statuses':statuses,'passed':True},indent=2))
