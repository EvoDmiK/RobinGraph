import importlib.util,json
from pathlib import Path
from robingraph.retrieval.graph_intent_schema import execution_gate,to_graph_question
f=Path('src/robingraph/retrieval/semantic_graph_intent.py');spec=importlib.util.spec_from_file_location('robingraph.retrieval.semantic_safety_review',f);s=importlib.util.module_from_spec(spec);spec.loader.exec_module(s)
cases=json.loads(Path('/tmp/rg212-followup-safety-cases.json').read_text())['cases']
def sd(name,relation):return dict(kind='shared_diet',species=name,relation_text=relation)
def tt(name,trait,op,surface,value=None,num=None,unit=None):return dict(kind='taxon_traits',taxon=name,conditions=[dict(trait_name=trait,op=op,surface=surface,value=value,threshold=num,unit=unit)])
plans=[sd('직박구리','같은 먹이 범주의'),sd('청둥오리','먹이 범주가 같지만'),sd('직박구리','먹이 범주가 같은'),sd('청둥오리','같은 먹이 범주의'),sd('청둥오리','먹이 범주가 같지 않은'),tt('오리과','body_mass','num_gt','몸무게 200g 초과',num=200,unit='g'),tt('오리과','body_mass','num_gte','몸무게 200g 이상',num=200,unit='g'),tt('오리과','body_mass','num_gt','몸무게 200g 초과',num=200,unit='g'),tt('오리과','body_mass','num_lt','몸무게 200g 미만',num=200,unit='g'),tt(None,'habitat','eq','숲에 사는','Forest'),sd('모아','먹이 범주가 같은'),sd('청둥오리','같은 먹이 범주인')]
rows=[]
for c,p in zip(cases,plans):
 calls=[]
 def provider(q,e,contract):calls.append(True);return dict(conditions=[],unresolved=[],unknown_relation=False,**p)
 # Avoid duplicate key in mock if condition plan already includes conditions.
 def provider(q,e,contract):
  calls.append(True);return {'conditions':[],'unresolved':[],'unknown_relation':False,**p}
 intent=s.graph_intent_handler(c['question'],provider=provider);gate=execution_gate(c['question'],intent)
 direct=s.interpret(c['question'],provider);dg=execution_gate(c['question'],direct)
 safety_expected=c['expected'].startswith('must_hold')
 # SF-03 preserving distinct reference could theoretically be valid, but this mock plan drops the exclusion.
 if c['id']=='SF-03':safety_expected=True
 passed=(gate!='answer')if safety_expected else True
 rows.append(dict(**c,gate=gate,direct_build_gate=dg,source=intent.source,provider_calls=len(calls),safety_passed=passed,raw_mock_plan=p))
out={'provider':'mocked deliberately incomplete/malicious raw plans; independent Gemini audit NOT invoked','scope':'current root semantic module; mock provider; no API/DB/network','rows':rows,'raw_mock_omission_cases':[r['id']for r in rows if not r['safety_passed']], 'audit_trust_boundary':'Raw mock bypasses compulsory generation transport semantic audit. An accepted raw plan is not proof of an end-to-end production omission. Negative/unsupported cues veto graph_intent_handler before interpretation even when direct interpret accepts a mock.'}
Path('/tmp/rg212-followup-root-safety-results.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
for r in rows:print(r['id'],r['gate'],r['direct_build_gate'],'PASS'if r['safety_passed']else'UNSAFE')
