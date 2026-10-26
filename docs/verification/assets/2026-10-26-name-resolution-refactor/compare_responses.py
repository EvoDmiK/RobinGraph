"""Offline API characterization; no provider, DB, or live HTTP calls."""
import json
from pathlib import Path
import sys
from copy import deepcopy
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'tests'))
from asgi_client import TestClient
from test_entity_resolution_api import PROFILE, matched
from robingraph.api.drf import create_django_app
from robingraph.retrieval.graph_condition_extractor import extract_graph_intent

name = '흰뺨검둥오리'
valid = matched(name)
candidates = dict(mention=name, status='candidates', method='vector', candidates=[
    dict(taxon_id='duck', scientific_name='Anas zonorhyncha', display_name=name, score=.91)])
variants = {'matched': valid, 'normalized': dict(valid, method='graph_normalized'),
            'vector': candidates, 'changed_mention': dict(valid, mention='다른새'),
            'vector_identity': dict(valid, method='vector'),
            'empty_candidates': dict(candidates, candidates=[]),
            'exact_candidates': dict(candidates, method='graph_exact'),
            'not_found': dict(mention=name, status='not_found', method='none'),
            'unavailable': dict(mention=name, status='unavailable', method='none'),
            'malformed': None, 'exception': RuntimeError('private fixture failure')}
for field in ('canonical_name', 'taxon_id', 'concept_set_id', 'taxonomy_release'):
    variants['missing_' + field] = dict(valid, **{field: None})
rows=[]
for route, question in [('profile', name+'에 대해 알려줘'),
                        ('graph', name+'와 서식지가 겹치면서 먹이가 다른 새는?')]:
    for scope in ('all', 'korea'):
        for label, raw in variants.items():
            resolver = Mock(side_effect=raw) if isinstance(raw, Exception) else Mock(return_value=deepcopy(raw))
            profile=Mock(return_value=deepcopy(PROFILE))
            graph=Mock(return_value=dict(status='answer',title='fixture',text='fixture',limitations=[]))
            client=TestClient(create_django_app(species_profile_handler=profile,
                taxon_name_resolution_handler=resolver, graph_intent_mode='active',
                graph_intent_handler=extract_graph_intent, graph_question_handler=graph))
            response=client.post('/v1/chat',json=dict(question=question,species_scope=scope,
                                                   defer_enrichment=True,defer_discovery=True))
            rows.append(dict(route=route,scope=scope,case=label,status=response.status_code,
                response=response.json(),resolver_calls=[dict(args=c.args,kwargs=c.kwargs) for c in resolver.call_args_list],
                profile_calls=profile.call_count,graph_calls=graph.call_count))
output=Path(sys.argv[1]);output.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({'cases':len(rows),'output':str(output),'real_db_api_calls':0}))
