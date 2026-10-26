import json
from pathlib import Path
p=Path(__file__).resolve().parent
cases=[]
def add(q,outcome,**expectations):
 cases.append(dict(id=f'FG-{len(cases)+1:02}',question=q,outcome=outcome,**expectations))
for prefix in ['까마귀과 중에서','딱따구리과 중','참새목 가운데','Corvus 중에서','Anas platyrhynchos 중','Corvus corone corone 중','']:
 add((prefix+' 곤충을 먹는 새는?').strip(),'food_guidance',requested_food='곤충',broader_category='무척추동물')
for q,word,broader in [('오리과 중에서 곡물을 먹는 새는?','곡물','씨앗'),('Anser 중 잎을 먹는 새는?','잎','기타 식물'),('벌새 중 꿀을 먹는 새는?','꿀','꽃꿀')]:
 add(q,'food_guidance',requested_food=word,broader_category=broader)
for name,taxon,rank in [('까마귀과','Corvidae','family'),('딱따구리과','Picidae','family'),('참새목','Passeriformes','order'),('Turdus','Turdus','genus'),('Anas platyrhynchos','Anas platyrhynchos','species'),('Corvus corone corone','Corvus corone corone','subspecies')]:
 for connector in ['중','중에서']:
  add(f'{name} {connector} 무척추동물을 먹는 새는?','query',taxon=taxon,rank=rank,conditions=[{'trait_name':'diet_distribution','op':'share_gt','value':{'invertebrate':0},'unit':None}])
for q,trait,value in [('오리과 중에서 물고기를 먹는 새는?','diet_distribution',{'fish':0}),('참새과 중에서 씨앗을 먹는 새는?','diet_distribution',{'seed':0}),('Nectarinidae 중에서 꽃꿀을 먹는 새는?','diet_distribution',{'nectar':0}),('직박구리과 중에서 열매를 먹는 새는?','diet_distribution',{'fruit':0})]:
 add(q,'supported_food',trait=trait,value=value)
for q in ['까마귀과 중에서 곤충을 안 먹는 새는?','까마귀과 중에서 곤충을 먹지 않는 새는?','겨울에만 까마귀과 중 곤충을 먹는 새는?','까마귀과 중 빨간 곤충을 먹는 새는?','까마귀과 중 곤충을 먹고 먹이 경쟁을 하는 새는?','까마귀과 중 곤충을 먹고 공존하는 새는?','까마귀과 중 곤충을 먹고 체중이 30cm 이상인 새는?','까마귀과 중 곤충 말고 열매를 먹는 새는?']:
 add(q,'clarify')
(p/'cases.json').write_text(json.dumps({'scope':'Requested-food granularity, canonical supported categories, connectors and safety; authored before fix integration. Not human-reviewed gold.', 'cases':cases},ensure_ascii=False,indent=2)+'\n');print(len(cases))
