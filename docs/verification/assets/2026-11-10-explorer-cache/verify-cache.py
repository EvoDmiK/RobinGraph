import json, os, time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from robingraph.retrieval.species_profile import licensed_images
from robingraph.retrieval.species_notes import create_species_notes
from robingraph.generation import GeminiAnswerer

root=Path(os.environ['ROBINGRAPH_SPECIES_CACHE_ROOT'])
assert str(root)=='/var/lib/robingraph/species-cache' and os.access(root,os.W_OK)
name='Asio otus'
lineage=SimpleNamespace(items=[SimpleNamespace(scientific_name=name)])
model=os.getenv('ROBINGRAPH_GEMINI_MODEL','gemini-3.8-flash')
mode=os.environ.get('CACHE_CHECK_MODE','populate')
answerer=GeminiAnswerer(os.environ['GEMINI_API_KEY'],model)
notes=create_species_notes(answerer.species_notes,model=model)
start=time.monotonic()
if mode=='offline':
    with patch('robingraph.retrieval.species_profile._json_get',side_effect=AssertionError('provider called')), patch('robingraph.retrieval.species_notes.encyclopedia_excerpt',side_effect=AssertionError('provider called')), patch.object(answerer,'species_notes',side_effect=AssertionError('generation called')):
        images=licensed_images(name)
        result=notes(lineage)
else:
    images=licensed_images(name)
    result=notes(lineage)
assert images and all(photo.get('license_name') and photo.get('source_url') for photo in images)
entries=[item for values in result.values() for item in values]
assert entries and all(item.get('license_name') and item.get('source_url') for item in entries)
print(json.dumps({'mode':mode,'seconds':round(time.monotonic()-start,3),'photo_count':len(images),'note_count':len(entries),'source_licenses_preserved':True,'cache_records':len(list(root.glob('*.json'))),'uid':os.getuid()}))
