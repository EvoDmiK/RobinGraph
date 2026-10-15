import json,hashlib
import psycopg
from psycopg import sql
from robingraph.ingest.postgres import PostgresSettings
p=PostgresSettings.from_environment();out={}
h=lambda x:hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,default=str,separators=(',',':')).encode()).hexdigest()
with psycopg.connect(**p.connection_kwargs()) as c:
 c.execute('SET TRANSACTION READ ONLY')
 for t in ['ingest_state','ingestion_run','source_dataset','source_record','source_release']:
  keys=[r[0] for r in c.execute("SELECT a.attname FROM pg_index i JOIN pg_class r ON r.oid=i.indrelid JOIN pg_namespace n ON n.oid=r.relnamespace JOIN pg_attribute a ON a.attrelid=r.oid AND a.attnum=ANY(i.indkey) WHERE i.indisprimary AND n.nspname=%s AND r.relname=%s ORDER BY a.attnum",(p.schema,t)).fetchall()]
  assert keys,(t,'missing primary key')
  rows=c.execute(sql.SQL('SELECT row_to_json(r) FROM {}.{} r').format(sql.Identifier(p.schema),sql.Identifier(t))).fetchall()
  index={}
  for (row,) in rows:
   identity=h([row[k] for k in keys]);item={'sha256':h(row)}
   if t!='source_record':item['fields']={k:h(v) for k,v in row.items()}
   index[identity]=item
  out[t]={'pk_columns':keys,'rows':index}
print(json.dumps(out,separators=(',',':')))
