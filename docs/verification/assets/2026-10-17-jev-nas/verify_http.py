"""Read-only HTTP smoke check, run inside the deployed NAS TEST container."""
import json
from urllib.request import Request, urlopen

rows=[]
for question, expected in [
    ('청둥오리에 대해 일고 깊어', 'answer'),
    ('청둥오리에 대해 알고 싶어', 'answer'),
    ('청둥오리에 대해 알고 시퍼', 'answer'),
    ('청둥오리에 대해 일고 깊어 그리고 까치 먹이도 알려줘', 'clarify'),
    ('그 새에 대해 일고 깊어', 'clarify'),
]:
    request = Request('http://127.0.0.1:8000/v1/chat',
        data=json.dumps(dict(question=question,defer_enrichment=True,defer_discovery=True)).encode(),
        headers={'Content-Type':'application/json'})
    with urlopen(request, timeout=90) as response:
        body=json.load(response)
    taxon=(body.get('result',{}).get('profile') or {}).get('taxon',{})
    row=dict(question=question,disposition=body.get('disposition'),route_method=body.get('route_method'),
        scientific_name=taxon.get('scientific_name'))
    row['passed']=row['disposition']==expected and (expected!='answer' or row['scientific_name']=='Anas platyrhynchos')
    rows.append(row)
print(json.dumps(dict(passed=all(x['passed'] for x in rows),rows=rows),ensure_ascii=False))
raise SystemExit(0 if all(x['passed'] for x in rows) else 1)
