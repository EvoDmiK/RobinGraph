"""Execute AVONET normalizer and batch gates with real JavaScript semantics."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import generate_n8n_avonet_ingest as avonet


def execute_js(source, items, config=None, sha=None, normalized=None):
    config = config or avonet.configuration()
    bindings = {'Build AVONET configuration': config,
                'Hash AVONET snapshot': {'raw_sha256': avonet.SHA256 if sha is None else sha},
                'Normalize AVONET species': normalized}
    script = "const fs=require('fs'); const d=JSON.parse(fs.readFileSync(0,'utf8')); const $=name=>({first:()=>({json:d.bindings[name]})}); const $input={all:()=>d.items.map(json=>({json})),first:()=>({json:d.items[0]})}; const result=new Function('$','$input',d.source)($,$input); process.stdout.write(JSON.stringify(result));"
    result = subprocess.run(['node','-e',script],input=json.dumps({'items':items,'bindings':bindings,'source':source}),text=True,capture_output=True,encoding='utf8')
    if result.returncode:
        raise ValueError(result.stderr)
    return json.loads(result.stdout)


def sample():
    row = {field: 12 if unit else 'Forest' for field,_,unit,_ in avonet.FIELDS}
    row.update({'Species1':'Example bird','Sequence':1,'Inference':'YES',
                'Traits.inferred':'Wing Length','Reference.species':'Example reference',
                'Total.individuals':2,'Habitat.Density':1})
    return row


@unittest.skipUnless(shutil.which('node'), 'Node.js required')
class AvonetWorkflowTest(unittest.TestCase):
    def config(self):
        return {
            **avonet.configuration(),
            'expected_rows': 1,
            'expected_source_claims': 13,
            'expected_matched_profiles': 1,
            'expected_loaded_claims': 13,
            'expected_mapping_candidates': 0,
        }

    def test_traits_units_inference_and_habitat_semantics(self):
        result = execute_js(avonet.NORMALIZE_JS,[sample()],self.config())[0]['json']
        claims = {c['trait_name']:c for c in result['profiles'][0]['claims']}
        self.assertEqual(claims['wing_length']['unit'],'mm')
        self.assertTrue(claims['wing_length']['inferred'])
        self.assertFalse(claims['body_mass']['inferred'])
        self.assertEqual(claims['habitat_density_category']['value_text'],'dense')
        self.assertNotIn('wingspan',claims)
        self.assertEqual(result['profiles'][0]['row_number'],2)

    def test_hash_invalid_measurement_duplicate_and_missing_column_fail(self):
        bad = sample(); bad['Mass']=-1
        missing = sample(); del missing['Wing.Length']
        for rows,cfg,sha in [([sample()],self.config(),'bad'),([bad],self.config(),None),
                             ([missing],self.config(),None),([sample(),sample()],{**self.config(),'expected_rows':2},None),
                             ([],self.config(),None)]:
            with self.subTest(rows=len(rows),sha=sha):
                with self.assertRaises(ValueError): execute_js(avonet.NORMALIZE_JS,rows,cfg,sha)

    def test_missing_value_is_not_zero(self):
        row=sample(); row['Mass']='NA'
        result=execute_js(
            avonet.NORMALIZE_JS, [row],
            {**self.config(), 'expected_source_claims': 12},
        )[0]['json']
        self.assertNotIn('body_mass',[c['trait_name'] for c in result['profiles'][0]['claims']])

    def test_missing_birdlife_sequence_keeps_distinct_species(self):
        first=sample(); first['Sequence']='NA'
        second={**first,'Species1':'Another bird'}
        result=execute_js(
            avonet.NORMALIZE_JS, [first,second],
            {**self.config(), 'expected_rows':2, 'expected_source_claims':26},
        )[0]['json']
        self.assertEqual(len({p['id'] for p in result['profiles']}),2)
        self.assertIsNone(result['profiles'][0]['sequence'])

    def test_batch_gate_rejects_missing_duplicate_and_wrong_counts(self):
        config={
            **self.config(),
            'expected_rows':101,
            'expected_source_claims':1313,
            'expected_matched_profiles':101,
            'expected_loaded_claims':1313,
            'profiles':[],
        }
        rows=[{'batch_index':i,'batch_count':2,'loaded_profiles':n,'loaded_claims':n*13,'expected_claims':n*13,'loaded_candidates':0,'matched_profiles':n} for i,n in enumerate([100,1])]
        self.assertEqual(execute_js(avonet.VERIFY_JS,rows,normalized=config)[0]['json']['loaded_profiles'],101)
        for invalid in [rows[:1],[rows[0],rows[0]],[rows[0],{**rows[1],'loaded_claims':0}]]:
            with self.assertRaises(ValueError): execute_js(avonet.VERIFY_JS,invalid,normalized=config)

    def test_artifact_reproducible_connections_and_javascript(self):
        artifact=json.loads(avonet.OUTPUT.read_text(encoding='utf8'))
        self.assertEqual(artifact,avonet.build_workflow())
        self.assertFalse(artifact['active'])
        names={n['name'] for n in artifact['nodes']}
        self.assertEqual(len(names),len(artifact['nodes']))
        for source,outputs in artifact['connections'].items():
            self.assertIn(source,names)
            for branch in outputs['main']:
                for target in branch:self.assertIn(target['node'],names)
        for node in artifact['nodes']:
            params=node['parameters']
            js=params.get('jsCode')
            if js:
                process=subprocess.run(['node','-e','new Function(JSON.parse(process.argv[1]))',json.dumps(js)],capture_output=True,text=True)
                self.assertEqual(process.returncode,0,process.stderr)
            expression=params.get('cypherQuery')
            if expression:
                process=subprocess.run(['node','-e','new Function("return ("+JSON.parse(process.argv[1])+" )")',json.dumps(expression[3:-2].strip())],capture_output=True,text=True)
                self.assertEqual(process.returncode,0,process.stderr)
        self.assertIn("state.active_release = $taxonomy_release",avonet.BATCH_CYPHER)
        self.assertIn('size(taxa)=1',avonet.BATCH_CYPHER)
        self.assertIn('profiles=$loaded_profiles',avonet.FINALIZE_CYPHER)
        self.assertFalse(any('discord' in n['type'] for n in artifact['nodes']))


if __name__ == '__main__': unittest.main()
