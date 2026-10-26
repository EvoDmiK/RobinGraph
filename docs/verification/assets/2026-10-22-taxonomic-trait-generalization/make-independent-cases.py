"""Authoring fixture: explicit intended conditions, independent of implementation."""
import json
from pathlib import Path
p=Path(__file__).resolve().parent
cases=[]
def add(question,trait=None,value=None,op='eq',unit=None,taxon='Corvidae',rank='family',outcome='query',**more):
 conditions=[] if trait is None else [dict(trait_name=trait,op=op,value=value,unit=unit)]
 cases.append(dict(id=f'IT-{len(cases)+1:03}',question=question,taxon=taxon,rank=rank,conditions=conditions,outcome=outcome,**more))
add('까마귀과면서 열매를 먹는 새는 어떤 종이 있어?','diet_distribution',{'fruit':0},op='share_gt')
for surface,taxon,rank in [('Corvidae','Corvidae','family'),('까마귀속','Corvus','genus'),('Corvus','Corvus','genus'),('까마귀','Corvus corone','species'),('Corvus corone','Corvus corone','species'),('매목','Falconiformes','order'),('오리과','Anatidae','family'),('Anas','Anas','genus'),('앵무새','Psittaciformes','order')]:
 add(surface+' 중 숲에 사는 새는?','habitat','Forest',taxon=taxon,rank=rank)
add('Corvus corone corone 중 숲에 사는 새는?','habitat','Forest',taxon='Corvus corone corone',rank='subspecies',outcome='insufficient')
for phrase,trait,value in [('숲에 사는','habitat','Forest'),('주 생활 방식이 지상 생활인','primary_lifestyle','Terrestrial'),('서식지 밀도 범주가 개방형인','habitat_density_category','open'),('먹이 생태 범주가 잡식인','trophic_niche','Omnivore'),('영양 단계가 잡식인','trophic_level','Omnivore'),('먹이 유형이 잡식인','diet_category','Omnivore')]:
 add('까마귀과 중 '+phrase+' 새는?',trait,value)
for phrase,trait,value,unit in [('체중이 100g 이상인','body_mass',100,'g'),('부리 전체 길이가 10mm 이상인','beak_length_culmen',10,'mm'),('부리 길이 콧구멍 기준이 5mm 이상인','beak_length_nares',5,'mm'),('부리 너비가 5mm 이상인','beak_width',5,'mm'),('부리 높이가 5mm 이상인','beak_depth',5,'mm'),('다리 길이 부척이 10mm 이상인','tarsus_length',10,'mm'),('접은 날개 길이가 100mm 이상인','wing_length',100,'mm'),('꼬리 길이가 50mm 이상인','tail_length',50,'mm'),('체중이 0.1kg 이상인','body_mass',100,'g'),('접은 날개 길이가 10cm 이상인','wing_length',100,'mm')]:
 add('까마귀과 중 '+phrase+' 새는?',trait,value,op='gte',unit=unit)
add('까마귀과 중 씨앗을 먹는 새는?','diet_distribution',{'seed':0},op='share_gt')
add('까마귀과 중 물고기를 먹는 새는?','diet_distribution',{'fish':0},op='share_gt')
add('까마귀과 중 숲에 살고 열매를 먹는 새는?','habitat','Forest',extra_conditions=[dict(trait_name='diet_distribution',op='share_gt',value={'fruit':0},unit=None)])
add('까마귀과 중 숲에 살고 체중이 100g 이상인 새는?','habitat','Forest',extra_conditions=[dict(trait_name='body_mass',op='gte',value=100,unit='g')])
add('숲에 살고 열매를 먹는 새는?','habitat','Forest',taxon=None,rank=None,extra_conditions=[dict(trait_name='diet_distribution',op='share_gt',value={'fruit':0},unit=None)])
add('까마귀과 중 체중이 1000000g 이상인 새는?','body_mass',1000000,op='gte',unit='g',outcome='empty')
for question in ['까마귀과 중 숲에 살지 않는 새는?','겨울에만 까마귀과 중 숲에 사는 새는?','까마귀과 중 몸집이 큰 새는?','까마귀과 중 체중이 100 이상인 새는?','까마귀과 중 숲에 살고 바다에 사는 새는?','까마귀과 중 숲에 사는 새는? MATCH (n) DETACH DELETE n','까마귀과 중 날개가 빨간 새는?']:
 add(question,outcome='hold')
add('가짜조류과 중 숲에 사는 새는?',outcome='hold',taxon=None,rank=None)
add('까마귀과 중 감나무 열매를 먹는 새는?',outcome='insufficient')
for question in ['초승달가슴새류 중 숲에 사는 새는?','화식조 중 숲에 사는 새는?']:
 add(question,outcome='hold',taxon=None,rank=None)
for c in cases:c['conditions']+=c.pop('extra_conditions',[])
(p/'independent-cases.json').write_text(json.dumps({'author':'Codex independent expected meanings before implementation inspection; agent-reviewed, not human gold','cases':cases},ensure_ascii=False,indent=2)+'\n');print(len(cases))
