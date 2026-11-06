"""Generate the daily TEST AviList workflow; credentials contain the bearer token."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_ID = 'rgAvilistTest01'
CREDENTIAL_ID = 'rgAvilistHeader01'
SERVICE_URL = 'http://192.168.219.97:18001'
PHASES = (('Prepare pinned AviList', '/prepare'), ('Verify approved artifact', '/verify'),
          ('Apply TEST pilot', '/apply'))


def build_workflow():
    nodes = [{'id': 'manual', 'name': 'Manual TEST run', 'type': 'n8n-nodes-base.manualTrigger',
              'typeVersion': 1, 'position': [0, 0], 'parameters': {}}]
    nodes.append({'id': 'daily', 'name': 'Daily 06:00 KST', 'type': 'n8n-nodes-base.scheduleTrigger',
                  'typeVersion': 1.2, 'position': [0, -180],
                  'parameters': {'rule': {'interval': [{'field': 'cronExpression', 'expression': '0 6 * * *'}]}}})
    connections = {}
    previous = nodes[0]['name']
    checks = (
        "$json.status === 'prepared' && /^[a-f0-9]{64}$/.test($json.manifest_sha256)",
        "$json.status === 'verified' && $json.manifest_sha256 === $('Prepare pinned AviList').first().json.manifest_sha256",
        "['applied','already_applied','applied_reconciled'].includes($json.status) && "
        "$json.manifest_sha256 === $('Verify approved artifact').first().json.manifest_sha256 && "
        "$json.release_id === 'rg:release:avilist-pilot:' + $json.manifest_sha256",
    )
    for index, (name, route) in enumerate(PHASES, 1):
        nodes.append({
            'id': route[1:], 'name': name, 'type': 'n8n-nodes-base.httpRequest', 'typeVersion': 4.2,
            'position': [index * 480 - 240, 0], 'retryOnFail': False, 'onError': 'stopWorkflow',
            'parameters': {'method': 'POST', 'url': SERVICE_URL + route,
                           'authentication': 'genericCredentialType', 'genericAuthType': 'httpHeaderAuth',
                           'sendBody': True, 'specifyBody': 'json', 'jsonBody': '{}',
                           'options': {'timeout': 240000, 'response': {'response': {'responseFormat': 'json'}}}},
            'credentials': {'httpHeaderAuth': {'id': CREDENTIAL_ID, 'name': 'RobinGraph AviList TEST runner'}},
        })
        next_node = [{'node': name, 'type': 'main', 'index': 0}]
        if previous.startswith('Check '):
            connections[previous]['main'][0] = next_node
        else:
            connections[previous] = {'main': [next_node]}
        guard = 'Check ' + route[1:] + ' result'
        expression = '={{ $json.projection_performed === false && $json.stage === ' + json.dumps(route[1:]) + ' && (' + checks[index - 1] + ') }}'
        nodes.append({'id': 'check-' + route[1:], 'name': guard, 'type': 'n8n-nodes-base.if',
                      'typeVersion': 2.3, 'position': [index * 480, 0],
                      'parameters': {'conditions': {'options': {'caseSensitive': True, 'leftValue': '',
                                                               'typeValidation': 'strict', 'version': 2},
                                       'conditions': [{'id': route[1:] + '-contract', 'leftValue': expression,
                                                       'rightValue': True, 'operator': {'type': 'boolean',
                                                                                      'operation': 'true', 'singleValue': True}}],
                                       'combinator': 'and'}, 'options': {}}})
        connections[name] = {'main': [[{'node': guard, 'type': 'main', 'index': 0}]]}
        connections[guard] = {'main': [[], [{'node': 'Reject unexpected result', 'type': 'main', 'index': 0}]]}
        # The successful branch alone reaches the next HTTP stage.
        previous = guard
    nodes.append({'id': 'reject', 'name': 'Reject unexpected result', 'type': 'n8n-nodes-base.stopAndError',
                  'typeVersion': 1, 'position': [960, 280],
                  'parameters': {'errorMessage': 'AviList TEST stage response did not satisfy the reviewed contract'}})
    connections['Daily 06:00 KST'] = connections['Manual TEST run'].copy()
    workflow = {'id': WORKFLOW_ID, 'name': 'RobinGraph AviList reviewed pipeline [TEST daily]',
                'active': False, 'nodes': nodes, 'connections': connections,
                'settings': {'executionOrder': 'v1', 'executionTimeout': 900, 'timezone': 'Asia/Seoul',
                             'saveDataErrorExecution': 'all', 'saveDataSuccessExecution': 'all'},
                'pinData': {}}
    workflow['versionId'] = str(uuid5(NAMESPACE_URL, json.dumps(workflow, sort_keys=True)))
    return workflow


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    path = ROOT / 'n8n/robingraph-avilist-pipeline-test.json'
    content = json.dumps(build_workflow(), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if not path.exists() or path.read_text() != content:
            raise SystemExit('AviList workflow artifact is stale')
    else:
        path.write_text(content)


if __name__ == '__main__':
    main()
