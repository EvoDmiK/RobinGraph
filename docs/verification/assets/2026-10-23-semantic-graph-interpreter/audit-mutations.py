"""Candidate proposals mocked deliberately; the independent audit uses the real configured model."""
import json,os
from pathlib import Path
from robingraph.generation import GeminiAnswerer,GeminiAnswerError
from robingraph.retrieval.semantic_graph_intent import CONTRACT
p=Path(__file__).parent
cases=[('unknown-condition-omitted','까마귀과 중 붉은 눈이고 곤충을 먹는 새는?',{'kind':'taxon_traits','taxon':'까마귀과','conditions':[{'trait_name':'diet_distribution','op':'share_gt','value':'invertebrates','threshold':0,'surface':'곤충을 먹는'}],'unresolved':[],'unknown_relation':False}),('scope-omitted','오리과 중 숲에 사는 새는?',{'kind':'taxon_traits','taxon':None,'conditions':[{'trait_name':'habitat','op':'eq','value':'Forest','surface':'숲에 사는'}],'unresolved':[],'unknown_relation':False}),('condition-invented','참새목 중 씨앗을 먹는 새는?',{'kind':'taxon_traits','taxon':'참새목','conditions':[{'trait_name':'diet_distribution','op':'share_gt','value':'seed','threshold':0,'surface':'씨앗을 먹는'},{'trait_name':'habitat','op':'eq','value':'Forest','surface':'새는'}],'unresolved':[],'unknown_relation':False})]
rows=[]
for id,q,plan in cases:
 provider=GeminiAnswerer(os.environ['GEMINI_API_KEY'],os.getenv('ROBINGRAPH_GEMINI_MODEL','gemini-3.8-flash'),timeout_seconds=30)
 original=provider._request
 def request(prompt,*,schema=None,operation=None):
  if operation=='graph_intent':return {'candidates':[{'content':{'parts':[{'text':json.dumps(plan)}]}}]}
  return original(prompt,schema=schema,operation=operation)
 provider._request=request
 try:provider.propose_structured_graph_intent(q,[],CONTRACT);result='accepted'
 except GeminiAnswerError as e:result='audit_rejected' if 'semantic audit' in str(e) else 'provider_error'
 rows.append({'id':id,'result':result})
(p/'audit-mutations.json').write_text(json.dumps({'candidate_mocking':True,'audit_mocking':False,'bird_db_writes':0,'rows':rows},indent=2)+'\n')
print(json.dumps(rows))
