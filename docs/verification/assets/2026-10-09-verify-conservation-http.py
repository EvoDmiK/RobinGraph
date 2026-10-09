"""Check representative real public TEST profiles after deployment (no response mocking)."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
from urllib.parse import urlencode


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', default='https://robingraph-test.dove-nest.com')
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    expected = {
        '큰부리까마귀': 'LC', 'Corvus macrorhynchos': 'LC', 'Pica pica': 'LC',
        'Pyrrhura subandina': 'CR', 'Premnoplex tatei': 'EN',
        'Pionites leucogaster': 'VU', 'Pteroglossus bitorquatus': 'NT',
        'Pica serica': None, 'Anser serrirostris': None,
        'Anas platyrhynchos': None, 'Hypsipetes amaurotis': None,
    }
    def get(path):
        return subprocess.check_output(['curl', '--fail', '--silent', '--show-error',
            '--max-time', '60', args.base + path])
    def check(name):
        p = json.loads(get('/v1/taxa/profile?' + urlencode({'name': name})))
        c = p['conservation']
        ref = c.get('reference_assessment')
        if expected[name]:
            assert c['category'] is None and c['category_raw'] == 'NE'
            assert c['assessment_status'] == 'needs_review' and c['label'] != '미평가'
            assert ref['category'] == expected[name]
            assert ref['assessment_status'] == 'reference_only'
            assert ref['taxonomy_alignment'] == 'unverified'
            assert ref['independently_verified'] is False
            assert ref['scientific_name'] == p['taxon']['scientific_name']
        else:
            assert ref is None
        if name in ('큰부리까마귀', 'Corvus macrorhynchos'):
            assert p['taxon']['scientific_name'] == 'Corvus macrorhynchos'
            assert ref['assessment_year'] == 2024
            assert ref['assessment_reference_url'] == 'https://www.iucnredlist.org/species/103727590/264280673'
        if name == 'Pica serica':
            assert c['category'] == 'LC' and c['assessment_status'] == 'manual_override'
        if name == 'Anser serrirostris':
            assert c['category'] is None and c['assessment_status'] == 'needs_review'
        if name == 'Anas platyrhynchos':
            assert c['category'] == 'LC' and c['assessment_status'] == 'linked_checklist'
        if name == 'Hypsipetes amaurotis':
            assert {'diet_distribution', 'foraging_strata_distribution'} <= {t['name'] for t in p['traits']}
        return {'query': name, 'http_status': 200, 'taxon': p['taxon'], 'conservation': c}
    with ThreadPoolExecutor(max_workers=3) as pool:
        checks = list(pool.map(check, expected))
    static = {}
    for file in ('chat.js', 'styles.css'):
        local = Path('src/robingraph/api/static') / file
        data = get('/static/' + file)
        assert data == local.read_bytes(), file
        static[file] = hashlib.sha256(data).hexdigest()
    report = {'base': args.base, 'actual_http': True, 'response_mocking': False,
        'checks': checks, 'static_matches': static}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'passed': len(checks), 'static_matches': static}, ensure_ascii=False))


if __name__ == '__main__':
    main()
