from pathlib import Path
import subprocess,shlex,json,sys
name=sys.argv[1]
base=Path('/Users/kimdove/robingraph-test/pipelines/n8n-avilist-test')
cmd='node -e '+shlex.quote('if(process.env.DB_POSTGRESDB_DATABASE!=="n8n-test")process.exit(2)')+' && N8N_RUNNERS_BROKER_PORT=15679 N8N_RUNNERS_MODE=internal n8n execute --id=rgAvilistTest01 --rawOutput'
args=['ssh','-o','BatchMode=yes','-i','/Users/kimdove/.ssh/id_ed25519_mini32','kimdove@192.168.219.98','/usr/local/bin/docker exec n8n-test sh -c '+shlex.quote(cmd)]
log=base/(name+'.raw.log')
with log.open('w') as output: result=subprocess.run(args,stdout=output,stderr=subprocess.STDOUT)
text=log.read_text();decoded=None
for pos,char in enumerate(text):
 if char!='{':continue
 try:
  value,_=json.JSONDecoder().raw_decode(text[pos:])
  if isinstance(value,dict) and ('data' in value or 'resultData' in value):decoded=value;break
 except ValueError:pass
assert decoded is not None, 'No workflow execution JSON found; inspect private log'
data=decoded.get('data',decoded);result_data=data.get('resultData',{})
if not result_data and 'resultData' in decoded:result_data=decoded['resultData']
run_data=result_data.get('runData',{})
phases={}
for node in ('Prepare pinned AviList','Verify approved artifact','Apply TEST pilot'):
 records=run_data.get(node,[])
 for record in records:
  main=record.get('data',{}).get('main',[])
  if main and main[0]:phases[node]=main[0][0].get('json',{})
summary={'cli_exit_code':result.returncode,'last_node':result_data.get('lastNodeExecuted'),
         'executed_nodes':list(run_data),'phases':phases,
         'error_present':bool(result_data.get('error'))}
folder=Path('docs/verification/assets/2026-10-20-rg701-complete');(folder/(name+'.json')).write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps(summary,ensure_ascii=False))
