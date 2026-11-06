import json
from pathlib import Path
import unittest

from scripts.generate_n8n_avilist_pipeline import build_workflow, PHASES, SERVICE_URL


class AviListWorkflowTest(unittest.TestCase):
    def test_daily_schedule_and_manual_trigger_without_notifications(self):
        workflow = build_workflow()
        self.assertFalse(workflow['active'])
        self.assertEqual([n['type'] for n in workflow['nodes']],
                         ['n8n-nodes-base.manualTrigger', 'n8n-nodes-base.scheduleTrigger']
                         + ['n8n-nodes-base.httpRequest', 'n8n-nodes-base.if'] * 3
                         + ['n8n-nodes-base.stopAndError'])
        self.assertEqual(workflow['settings']['timezone'], 'Asia/Seoul')
        self.assertEqual(workflow['nodes'][1]['parameters']['rule']['interval'][0]['expression'], '0 6 * * *')
        self.assertEqual(workflow['connections']['Daily 06:00 KST'], workflow['connections']['Manual TEST run'])

    def test_phase_failure_stops_without_blind_apply_retries(self):
        nodes = [n for n in build_workflow()['nodes'] if n['type'] == 'n8n-nodes-base.httpRequest']
        self.assertEqual([n['parameters']['url'] for n in nodes], [SERVICE_URL + route for _, route in PHASES])
        for node in nodes:
            self.assertFalse(node['retryOnFail'])
            self.assertEqual(node['onError'], 'stopWorkflow')
            self.assertEqual(node['parameters']['jsonBody'], '{}')
            self.assertNotIn('neverError', json.dumps(node))
            self.assertNotIn('Authorization', json.dumps(node))
            self.assertIn('httpHeaderAuth', node['credentials'])

    def test_prepare_verify_apply_order_and_reproducible_artifact(self):
        workflow = build_workflow()
        names = [n['name'] for n in workflow['nodes'][:-1] if n['type'] != 'n8n-nodes-base.scheduleTrigger']
        for previous, following in zip(names, names[1:]):
            self.assertEqual(workflow['connections'][previous]['main'][0][0]['node'], following)
        for _, route in PHASES:
            guard = 'Check ' + route[1:] + ' result'
            self.assertEqual(workflow['connections'][guard]['main'][1][0]['node'], 'Reject unexpected result')
        stored = json.loads((Path(__file__).resolve().parents[1] / 'n8n/robingraph-avilist-pipeline-test.json').read_text())
        self.assertEqual(stored, workflow)
