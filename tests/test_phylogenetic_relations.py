import importlib.util
import io
from zipfile import ZipFile
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

from robingraph.retrieval.phylogenetic_relations import (
    _load_index, phylogenetic_relations, phylogeny_metadata,
)

SPEC = importlib.util.spec_from_file_location('phylogeny_builder',
    Path(__file__).resolve().parents[1]/'scripts/build_phylogenetic_index.py')
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def fixture(tree='((Target_bird,(Near_bird,Tied_bird)n1)n2,Far_bird)root;'):
    names = ['Target bird','Near bird','Tied bird','Far bird']
    rows = [{'SCI_NAME':name,'sci_name_2025':name,'ott_name':name,
             'CATEGORY':'species','ott_id':str(i),'TAXON_CONCEPT_ID':f'avibase-{i:08X}',
             'match_type':'canonical_match','PRIMARY_COM_NAME':name}
            for i,name in enumerate(names,1)]
    active = {'taxonomy_release':'v2025b','concept_set_id':'rg:concept-set:avilist-v2025b',
              'species':[{'taxon_id':str(i),'scientific_name':name,'english_name':name,
                          'clements_english_name':name,'avibase_id':f'avibase-{i:08X}'}
                         for i,name in enumerate(names,1)]}
    annotations = {'source_id_map':{'ot_1@tree1':{},'ot_2019@tree1':{},'ot_2770@tree1':{}},
                   'nodes':{n:{'supported_by':{'ot_1@tree1':'source-node'}} for n in ['root','n1','n2']}}
    annotations['nodes'].update({f'ott{i}':{'terminal':{'ot_1@tree1':'source-tip'}} for i in range(1,5)})
    return tree,rows,active,annotations


class PhylogenyBuilderTest(TestCase):
    def test_workbook_enrichment_verifies_active_science_english_and_sequence(self):
        namespace='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
        shared=['Sequence','Taxon_rank','Scientific_name','English_name_AviList',
                'English_name_Clements_v2025','AvibaseID','species','Target bird',
                'Target English','Source English','avibase-00000001']
        strings='<sst xmlns="'+namespace+'">'+''.join('<si><t>'+s+'</t></si>' for s in shared)+'</sst>'
        def cell(column,row,index):
            return f'<c r="{column}{row}" t="s"><v>{index}</v></c>'
        header=''.join(cell(c,1,i) for i,c in enumerate(['A','B','F','I','J','T']))
        body='<c r="A2"><v>1</v></c>'+''.join(cell(c,2,i) for c,i in [('B',6),('F',7),('I',8),('J',9),('T',10)])
        sheet='<worksheet xmlns="'+namespace+'"><sheetData><row>'+header+'</row><row>'+body+'</row></sheetData></worksheet>'
        buffer=io.BytesIO()
        with ZipFile(buffer,'w') as archive:
            archive.writestr('xl/sharedStrings.xml',strings)
            archive.writestr('xl/worksheets/sheet1.xml',sheet)
        active={'species':[{'taxon_id':'avilist-taxon:v2025b:1',
                            'scientific_name':'Target bird','english_name':'Target English'}]}
        enriched=builder.enrich_active_species(active,buffer.getvalue())
        self.assertEqual('avibase-00000001',enriched['species'][0]['avibase_id'])
        self.assertEqual('Source English',enriched['species'][0]['clements_english_name'])
        self.assertNotIn('avibase_id',active['species'][0])
        for change in [{'taxon_id':'avilist-taxon:v2025b:2'}, {'scientific_name':'Changed'},
                       {'english_name':'Changed'}, {'avibase_id':'avibase-99999999'}]:
            with self.subTest(change=change),self.assertRaises(ValueError):
                builder.enrich_active_species({'species':[{**active['species'][0],**change}]},buffer.getvalue())

    def test_source_hash_gate_rejects_changed_bytes(self):
        with TemporaryDirectory() as folder:
            path=Path(folder)/'source'
            path.write_bytes(b'changed')
            with self.assertRaises(ValueError):
                builder.checked_bytes(path,builder.TREE_HASH)

    def test_strict_tree_parse_and_polytomy(self):
        paths,nodes=builder.parse_topology('(A,B,C)root;')
        self.assertEqual({'A':['root'],'B':['root'],'C':['root']},paths)
        self.assertEqual({'root'},nodes)
        for tree in ['(A,A)root;','(A,B)root;(C,D)other;', '(A,B;', '(A:1,B:2)root;', '(A,B);']:
            with self.subTest(tree=tree),self.assertRaises(ValueError):
                builder.parse_topology(tree)

    def test_exact_mapping_and_tip_evidence_guards(self):
        tree,rows,active,annotations=fixture()
        good=builder.build_index(tree,rows,active,annotations)
        self.assertEqual(4,good['coverage']['mapped_species'])
        alterations = [lambda:rows[0].update(sci_name_2025='Changed bird'),
                       lambda:rows[0].update(TAXON_CONCEPT_ID='avibase-12345678'),
                       lambda:rows[0].update(PRIMARY_COM_NAME='Changed English'),
                       lambda:active['species'].append(dict(active['species'][0])),
                       lambda:annotations['nodes']['ott1'].update(terminal={'ot_2019@tree1':'tax'})]
        for alter in alterations:
            tree,rows,active,annotations=fixture()
            alter()
            with self.subTest(alter=alter):
                self.assertNotIn('1',builder.build_index(tree,rows,active,annotations)['taxa'])
        tree,rows,active,annotations=fixture('(Near_bird,Tied_bird,Far_bird)root;')
        self.assertNotIn('1',builder.build_index(tree,rows,active,annotations)['taxa'])

    def test_duplicate_source_names_and_concepts_rejected(self):
        tree,rows,active,annotations=fixture()
        rows.append(dict(rows[0]))
        self.assertNotIn('1',builder.build_index(tree,rows,active,annotations)['taxa'])
        tree,rows,active,annotations=fixture()
        rows[1]['TAXON_CONCEPT_ID']=rows[0]['TAXON_CONCEPT_ID']
        result=builder.build_index(tree,rows,active,annotations)
        self.assertNotIn('1',result['taxa'])
        self.assertNotIn('2',result['taxa'])

    def test_exact_concept_allows_authoritative_genus_move(self):
        tree,rows,active,annotations=fixture('(Oldgenus_bird,Near_bird,Tied_bird,Far_bird)root;')
        rows[0].update(SCI_NAME='Oldgenus bird',ott_name='Oldgenus bird',match_type='synonym_match')
        result=builder.build_index(tree,rows,active,annotations)
        self.assertIn('1',result['taxa'])
        self.assertEqual('Target bird',result['taxa']['1']['scientific_name'])
        self.assertEqual('Oldgenus bird',result['taxa']['1']['source_scientific_name'])
        active['species'][0].pop('avibase_id')
        self.assertNotIn('1',builder.build_index(tree,rows,active,annotations)['taxa'])

    def test_taxonomy_constraints_do_not_support_clades(self):
        tree,rows,active,annotations=fixture()
        annotations['nodes']['n2']={'supported_by':{'ot_2770@tree1':'tax'},
                                    'resolves':{'ot_1@tree1':'not-used'}}
        self.assertNotIn('n2',{n['source_node_id'] for n in builder.build_index(tree,rows,active,annotations)['nodes'].values()})
        active['taxonomy_release']='future'
        with self.assertRaises(ValueError):
            builder.build_index(tree,rows,active,annotations)


def index_candidates(index):
    return [{'taxon_id':k,'scientific_name':v['scientific_name']} for k,v in index['taxa'].items()]


class PhylogeneticRelationsTest(TestCase):
    def test_polytomy_preserves_equal_biological_strata(self):
        index=builder.build_index(*fixture('(Target_bird,Near_bird,Tied_bird,Far_bird)root;'))
        with patch('robingraph.retrieval.phylogenetic_relations._load_index',return_value=index):
            reasons=phylogenetic_relations('v2025b','1','Target bird',index_candidates(index))
        self.assertEqual({0},{r['shared_ancestor_depth'] for r in reasons.values()})


    def test_target_lca_strata_and_ties_not_peer_branch_depth(self):
        index=builder.build_index(*fixture())
        candidates=[{'taxon_id':str(i),'scientific_name':name} for i,name in
                    [(2,'Near bird'),(3,'Tied bird'),(4,'Far bird')]]
        with patch('robingraph.retrieval.phylogenetic_relations._load_index',return_value=index):
            reasons=phylogenetic_relations('v2025b','1','Target bird',candidates)
        self.assertEqual(reasons['2']['shared_ancestor_depth'],reasons['3']['shared_ancestor_depth'])
        self.assertGreater(reasons['2']['shared_ancestor_depth'],reasons['4']['shared_ancestor_depth'])
        self.assertEqual('n2',reasons['2']['shared_ancestor_id'])
        self.assertEqual(0,reasons['2']['points'])

    def test_context_and_exact_runtime_identity_guards(self):
        index=builder.build_index(*fixture())
        candidate={'taxon_id':'2','scientific_name':'Near bird'}
        with patch('robingraph.retrieval.phylogenetic_relations._load_index',return_value=index):
            for release,target,name,peers,concept in [
                ('future','1','Target bird',[candidate],None),
                ('v2025b','wrong','Target bird',[candidate],None),
                ('v2025b','1','Changed bird',[candidate],None),
                ('v2025b','1','Target bird',[{**candidate,'scientific_name':'Changed bird'}],None),
                ('v2025b','1','Target bird',[candidate],'other')]:
                self.assertEqual({},phylogenetic_relations(release,target,name,peers,concept_set_id=concept))
            self.assertFalse(phylogeny_metadata(concept_set_id='other')['available'])
            self.assertFalse(phylogeny_metadata(taxonomy_release='future')['available'])

    def test_unsupported_refinement_does_not_improve_rank(self):
        tree,rows,active,annotations=fixture()
        annotations['nodes']['n2']={'supported_by':{'ot_2770@tree1':'tax'}}
        index=builder.build_index(tree,rows,active,annotations)
        with patch('robingraph.retrieval.phylogenetic_relations._load_index',return_value=index):
            reasons=phylogenetic_relations('v2025b','1','Target bird',active['species'])
        self.assertEqual({'root'},{r['shared_ancestor_id'] for r in reasons.values()})

    def test_pinned_real_index_duck_and_non_duck_pairs(self):
        _load_index.cache_clear()
        index=_load_index()
        self.assertIsNotNone(index)
        taxa=index['taxa']
        by_name={v['scientific_name']:k for k,v in taxa.items()}
        candidates=[{'taxon_id':k,'scientific_name':v['scientific_name']} for k,v in taxa.items()]
        for target,close,far in [('Anas zonorhyncha','Anas platyrhynchos','Anas acuta'),
                                  ('Nycticorax nycticorax','Nycticorax caledonicus','Ardea cinerea')]:
            with self.subTest(target=target):
                reasons=phylogenetic_relations('v2025b',by_name[target],target,candidates)
                self.assertGreater(reasons[by_name[close]]['shared_ancestor_depth'],
                                   reasons[by_name[far]]['shared_ancestor_depth'])
                self.assertTrue(reasons[by_name[close]]['supporting_studies'])
                self.assertFalse(any(s.split('@')[0] in builder.CONSTRAINT_STUDIES
                                     for s in reasons[by_name[close]]['supporting_sources']))
