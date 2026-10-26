import importlib.util,sys,unittest
from pathlib import Path
root=Path('/Users/kimdove/orca/workspaces/RobinGraph/dev-codex');sys.path.insert(0,str(root/'src'))
from robingraph.retrieval import semantic_graph_intent
extractor=Path(sys.argv[1]).with_name('graph_condition_extractor.py')
if extractor.exists():
 spec=importlib.util.spec_from_file_location('robingraph.retrieval.graph_condition_extractor',extractor);mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
 import robingraph.retrieval
 robingraph.retrieval.graph_condition_extractor=mod
modulepath=Path(sys.argv[1]);spec=importlib.util.spec_from_file_location('robingraph.retrieval.semantic_graph_intent',modulepath);m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
import robingraph.retrieval
robingraph.retrieval.semantic_graph_intent=m
suite=unittest.defaultTestLoader.discover(sys.argv[3] if len(sys.argv)>3 else '/tmp/rg-enum-review-20261026',pattern=sys.argv[2] if len(sys.argv)>2 else 'test_enum_guards.py')
r=unittest.TextTestRunner(verbosity=2).run(suite);sys.exit(not r.wasSuccessful())
