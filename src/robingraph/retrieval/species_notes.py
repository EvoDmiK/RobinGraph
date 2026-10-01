"""Bounded, attributed encyclopedia excerpts for species descriptions."""
from functools import lru_cache
import json
import time
from urllib.parse import unquote, urlsplit

from .species_profile import _json_get


@lru_cache(maxsize=128)
def encyclopedia_excerpt(scientific_name, hour):
    query = ('SELECT ?item ?article WHERE { ?item wdt:P225 ' + json.dumps(scientific_name)
             + '; wdt:P105 wd:Q7432. ?article schema:about ?item; '
             'schema:isPartOf <https://en.wikipedia.org/>. } LIMIT 2')
    rows = _json_get('https://query.wikidata.org/sparql', {'query':query, 'format':'json'})['results']['bindings']
    if len(rows) != 1:
        return None  # Ambiguous taxon/article mapping is not a source.
    article = urlsplit(rows[0]['article']['value'])
    if article.scheme != 'https' or article.hostname != 'en.wikipedia.org' or not article.path.startswith('/wiki/'):
        return None
    title = unquote(article.path.removeprefix('/wiki/'))
    data = _json_get('https://en.wikipedia.org/w/api.php', {
        'action':'query', 'format':'json', 'prop':'extracts|info|revisions|pageprops',
        'titles':title, 'redirects':1, 'explaintext':1, 'inprop':'url', 'rvprop':'ids',
        'ppprop':'wikibase_item',
    })
    pages = list(data.get('query', {}).get('pages', {}).values())
    if len(pages) != 1:
        return None
    page = pages[0]
    if page.get('pageprops', {}).get('wikibase_item') != rows[0]['item']['value'].rsplit('/', 1)[-1]:
        return None
    text = page.get('extract')
    revisions = page.get('revisions', [])
    if 'missing' in page or not isinstance(text, str) or not text.strip() or not revisions:
        return None
    revision = revisions[0].get('revid')
    if not isinstance(revision, int) or revision <= 0:
        return None
    return {'text':text[:18000], 'source_name':'Wikipedia · ' + page.get('title', title),
            'source_url':f'https://en.wikipedia.org/w/index.php?oldid={revision}',
            'license_name':'CC BY-SA 4.0', 'license_url':'https://creativecommons.org/licenses/by-sa/4.0/',
            'source_release':str(revision)}


def create_species_notes(summarize):
    @lru_cache(maxsize=128)
    def cached(scientific_name, hour):
        source = encyclopedia_excerpt(scientific_name, hour)
        if source is None:
            return {'appearance':[], 'fun_facts':[]}
        # The adapter validates every item against the supplied excerpt.
        notes = summarize(scientific_name, source['text'])
        return {key:[{'text':item['text'], **{k:v for k,v in source.items() if k != 'text'}}
                     for item in notes.get(key, [])]
                for key in ('appearance', 'fun_facts')}
    return lambda lineage: cached(lineage.items[-1].scientific_name, int(time.time() // 3600))
