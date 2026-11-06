import contextlib
import io
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
from test_registry_prod_deployment import RegistryProductionDeploymentTests, module, IMAGE, REVISION

class ProductionTracingFlags(RegistryProductionDeploymentTests):
    def setUp(self):
        super().setUp()
        self.original += (b'ROBINGRAPH_MLFLOW_TRACING=false\nMLFLOW_EXPERIMENT_ID=7\n'
                          b'MLFLOW_EXPERIMENT_NAME=old\nMLFLOW_TRACKING_URI=http://tracking.internal\n'
                          b'MLFLOW_TRACKING_PASSWORD=fixture-private-value\n')
        self.env.write_bytes(self.original)
        self.tracing = dict(mlflow_tracing='true',mlflow_experiment_id='123',mlflow_experiment_name='robingraph-prod')

    def test_tracing_bundle_preserves_uri_auth_and_has_safe_receipt(self):
        seen=[]
        def run(args, **kwargs):
            if args[:2]==['docker','compose']: seen.append(self.env.read_text())
        output=io.StringIO()
        with patch.object(module.subprocess,'check_output',side_effect=self.inspect), patch.object(module.subprocess,'run',side_effect=run),contextlib.redirect_stdout(output):
            module.remote_deploy(dict(self.request,**self.tracing))
        self.assertEqual(len(seen),1)
        lines=seen[0].splitlines()
        for line in ['ROBINGRAPH_MLFLOW_TRACING=true','MLFLOW_EXPERIMENT_ID=123','MLFLOW_EXPERIMENT_NAME=robingraph-prod']:
            self.assertEqual(lines.count(line),1)
        self.assertNotIn('MLFLOW_EXPERIMENT_ID=7',lines)
        self.assertIn('MLFLOW_TRACKING_URI=http://tracking.internal',lines)
        self.assertIn('MLFLOW_TRACKING_PASSWORD=fixture-private-value',lines)
        receipt=json.loads(output.getvalue())
        self.assertEqual(receipt['runtime_overrides'],dict(ROBINGRAPH_MLFLOW_TRACING='true',MLFLOW_EXPERIMENT_ID='123',MLFLOW_EXPERIMENT_NAME='robingraph-prod'))
        self.assertNotIn('fixture-private-value',output.getvalue())
        self.assertNotIn('tracking.internal',output.getvalue())
        self.assertEqual(Path(receipt['previous_env_backup']).read_bytes(),self.original)

    def test_failed_verification_rolls_back_entire_tracing_bundle(self):
        snapshots=[]; calls=[]
        def run(args,**kwargs):
            if args[:2]==['docker','compose']:snapshots.append(self.env.read_bytes())
            if args[:2]==['docker','exec']:
                calls.append(args)
                if len(calls)==1:raise subprocess.CalledProcessError(1,args)
        with patch.object(module.subprocess,'check_output',side_effect=self.inspect),patch.object(module.subprocess,'run',side_effect=run),contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError): module.remote_deploy(dict(self.request,**self.tracing))
        self.assertEqual(snapshots[1],self.original)
        self.assertEqual(self.env.read_bytes(),self.original)
        self.assertEqual(len(calls),2)
        self.assertEqual(json.loads(next(self.root.glob('.registry-deployments/*.json')).read_text())['state'],'rolled_back')

    def test_bad_or_partial_bundle_rejected_before_external_calls(self):
        bad=[dict(mlflow_tracing='true'),dict(mlflow_experiment_id='123'),dict(mlflow_experiment_name='robingraph-prod')]
        for key,values in [('mlflow_tracing',['TRUE',True,'true\nNEO4J_URI=evil']),('mlflow_experiment_id',['',1,'-1','１２','123\nX=Y','1.5']),('mlflow_experiment_name',['robingraph-test','robingraph-prod\nX=Y',''])]:
            bad.extend(dict(self.tracing,**{key:value}) for value in values)
        for item in bad:
            with self.subTest(item=item),patch.object(module,'production_context') as context,patch.object(module.subprocess,'run') as run:
                with self.assertRaises(ValueError):module.remote_deploy(dict(self.request,**item))
                context.assert_not_called();run.assert_not_called()
        self.assertEqual(self.env.read_bytes(),self.original)

    def test_omitted_tracing_preserves_existing_bundle(self):
        with patch.object(module.subprocess,'check_output',side_effect=self.inspect),patch.object(module.subprocess,'run'),contextlib.redirect_stdout(io.StringIO()):
            module.remote_deploy(self.request)
        for line in self.original.decode().splitlines():
            if line.startswith(('MLFLOW_','ROBINGRAPH_MLFLOW_')):self.assertIn(line,self.env.read_text().splitlines())

    def test_cli_forwards_complete_bundle(self):
        with patch.object(module,'remote_deploy') as deploy,patch.object(module.sys,'argv',['deploy','--local','--image',IMAGE,'--revision',REVISION,'--mlflow-tracing','true','--mlflow-experiment-id','123','--mlflow-experiment-name','robingraph-prod']),patch.dict(module.os.environ,{'GHCR_USERNAME':'fixture','GHCR_TOKEN':'fixture-token'},clear=True):
            module.main()
        deploy.assert_called_once_with(dict(self.request,**self.tracing))

    def test_graph_and_tracing_update_together(self):
        with patch.object(module.subprocess,'check_output',side_effect=self.inspect),patch.object(module.subprocess,'run'),contextlib.redirect_stdout(io.StringIO()):
            module.remote_deploy(dict(self.request,**self.tracing,graph_intent_mode='active',graph_interpreter='semantic'))
        lines=self.env.read_text().splitlines()
        for line in ['ROBINGRAPH_GRAPH_INTENT_MODE=active','ROBINGRAPH_GRAPH_INTERPRETER=semantic','ROBINGRAPH_MLFLOW_TRACING=true','MLFLOW_EXPERIMENT_ID=123','MLFLOW_EXPERIMENT_NAME=robingraph-prod']:
            self.assertEqual(lines.count(line),1)


def load_tests(loader, tests, pattern):
    import unittest
    return unittest.TestSuite(ProductionTracingFlags(name) for name in ProductionTracingFlags.__dict__ if name.startswith('test_'))
