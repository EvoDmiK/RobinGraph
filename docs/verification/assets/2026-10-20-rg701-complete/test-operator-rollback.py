"""Isolated mocks of the exact operator rollback AST; no Docker or DB calls."""
import ast,json,tempfile
from pathlib import Path
source=Path('/tmp/rg701-complete/upgrade-runner.py').read_text()
module=ast.parse(source)
handler=[n for n in module.body if isinstance(n,ast.Try)][0].handlers[0]
func=ast.FunctionDef(name='rollback',args=ast.arguments(posonlyargs=[],args=[],kwonlyargs=[],kw_defaults=[],defaults=[]),body=handler.body[:-1],decorator_list=[])
program=ast.fix_missing_locations(ast.Module(body=[func],type_ignores=[]))
rows=[]
for case in ('success','stop_failed_running','stop_failed_stopped','inspect_failed','approval_restore_failed','audit_failed','wrong_image'):
 with tempfile.TemporaryDirectory() as directory:
  base=Path(directory);(base/'review').mkdir();(base/'state/review-package').mkdir(parents=True)
  env=base/'compose.env';env.write_bytes(b'newenv')
  (base/'review/approval.json').write_bytes(b'newapproval');(base/'state/review-package/code.json').write_bytes(b'newcode')
  calls=[];receipt={};running=True;inspects=0
  mounts={d:{'Source':d,'RW':d=='/state'} for d in ('/code','/state','/review')}
  def docker(*args):
   global inspects
   inspects+=1
   if case=='inspect_failed':raise RuntimeError('mock inspect failure')
   return json.dumps([{'State':{'Running':False if inspects>1 else case=='stop_failed_running'},'Image':'wrong' if case=='wrong_image' else 'oldimage','Mounts':[dict(Destination=k,**v) for k,v in mounts.items()],'Config':{'Env':['ROBINGRAPH_DEPLOY_TARGET=test']}}])
  def compose(*args):
   calls.append(('compose',args))
   if args[0]=='stop' and case.startswith('stop_failed'):raise RuntimeError('mock stop failure')
  def atomic(path,data):
   calls.append(('write',str(path.relative_to(base))))
   if case=='approval_restore_failed' and path.name=='approval.json':raise OSError('mock restore failure')
   path.write_bytes(data)
  def save():
   calls.append(('audit',))
   if case=='audit_failed':raise OSError('mock audit failure')
  g={'BASE':base,'ENV':env,'receipt':receipt,'docker':docker,'compose':compose,'atomic':atomic,'save':save,'json':json,'old_approval':b'oldapproval','old_code':b'oldcode','rollback_env':b'oldenv','old':{'Image':'oldimage'},'mounts':mounts,'healthy':lambda:None,'probe':lambda:{'http':200,'body':{'status':'verified'}}}
  exec(compile(program,'operator-exact-rollback','exec'),g);g['rollback']()
  writes=[x for x in calls if x[0]=='write'];starts=[x for x in calls if x[0]=='compose' and x[1][0]=='up']
  if case in ('stop_failed_running','inspect_failed'):assert not writes and not starts and receipt['state']=='rollback_unverified'
  elif case=='approval_restore_failed':assert not starts and receipt['state']=='rollback_unverified'
  elif case=='wrong_image':assert receipt['state']=='rollback_unverified'
  else:assert receipt['state']=='rolled_back' and len(writes)==3 and len(starts)==1
  rows.append({'case':case,'passed':True,'state':receipt['state']})
result={'kind':'isolated AST rollback mocks; no actual Docker/DB/rollback performed','passed':True,'cases':rows}
Path('docs/verification/assets/2026-10-20-rg701-complete/operator-rollback-mocks.json').write_text(json.dumps(result,indent=2)+'\n')
print('Rollback mock cases passed:',len(rows))
