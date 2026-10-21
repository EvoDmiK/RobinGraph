"""Korea (KR) species scope bound to a reviewed, release-scoped distribution bundle.

`korea` means a pinned source records the species in the wild in Korea or
names Korea in its range, in any season; it is not a residency claim.
`outside` means a manually reviewed source range outside KR, not proof that
no vagrant or captive record exists. Everything else is `unknown`, which is
the complement of the exact known identities and never negative evidence.
Korean names, missing observations and missing Korea text are never used.
"""
from functools import lru_cache
import json
from pathlib import Path
from typing import Literal, get_args

SpeciesScope = Literal['all', 'korea', 'outside', 'unknown']
SPECIES_SCOPES = get_args(SpeciesScope)
DISTRIBUTION_STATUSES = ('korea', 'outside')
NOTES = {
    'korea': '국내 기록·분포 확인: 출처에 한국의 야생 기록 또는 분포가 있습니다. 텃새·철새·미조 구분과 현재 서식 여부는 확인되지 않았습니다.',
    'outside': '국외 분포 검토: 검토한 출처의 정상 분포가 한국 밖입니다. 우연한 도래나 사육 기록이 없다는 뜻은 아닙니다.',
    'unknown': '미확인: 한국 분포 근거를 확인하지 못했습니다. 국외 분포라는 뜻은 아닙니다.',
}


@lru_cache(maxsize=1)
def _bundle():
    data = json.loads(Path(__file__).with_name('species_distribution.json').read_text(encoding='utf-8'))
    if (data.get('schema_version') != 1 or data.get('geographic_scope') != 'KR'
            or not isinstance(data.get('taxa'), dict)):
        raise ValueError('Unsupported species distribution bundle')
    for taxon_id, entry in data['taxa'].items():
        if (not isinstance(entry, dict) or entry.get('status') not in DISTRIBUTION_STATUSES
                or not isinstance(entry.get('scientific_name'), str) or not entry.get('evidence')):
            raise ValueError(f'Invalid species distribution entry {taxon_id}')
    return data


def _scope(species_scope):
    if species_scope not in SPECIES_SCOPES:
        raise ValueError(f'Unsupported species_scope: {species_scope!r}')
    return species_scope


def _entries(concept_set_id, taxonomy_release):
    """Entries for the active context only; any mismatch or bad bundle is empty."""
    try:
        data = _bundle()
    except (OSError, ValueError):
        return None
    if data.get('concept_set_id') != concept_set_id or data.get('taxonomy_release') != taxonomy_release:
        return None
    return data['taxa']


def _unknown(basis):
    return {'status': 'unknown', 'geographic_scope': 'KR', 'basis': basis, 'evidence': [],
            'seasonal_status': None, 'note': NOTES['unknown']}


def distribution_for(taxon: dict, concept_set_id: str, taxonomy_release: str) -> dict:
    entries = _entries(concept_set_id, taxonomy_release)
    if entries is None:
        return _unknown('no_current_distribution_context')
    if taxon.get('rank', 'species') != 'species':
        return _unknown('species_rank_only')
    entry = entries.get(taxon.get('taxon_id'))
    if entry is None:
        return _unknown('no_reviewed_source_distribution')
    if entry['scientific_name'] != taxon.get('scientific_name'):
        return _unknown('identity_mismatch')
    return {'status': entry['status'], 'geographic_scope': 'KR', 'basis': entry['basis'],
            'evidence': [dict(item) for item in entry['evidence']], 'seasonal_status': None,
            'note': NOTES[entry['status']]}


def _display_name(taxon, species_scope):
    order = (('english_name', 'korean_name') if species_scope == 'outside'
             else ('korean_name', 'english_name'))
    for key in order + ('scientific_name',):
        value = taxon.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def with_species_scope(taxon: dict, species_scope: str, concept_set_id: str, taxonomy_release: str) -> dict:
    species_scope = _scope(species_scope)
    return {**taxon, 'distribution': distribution_for(taxon, concept_set_id, taxonomy_release),
            'display_name': _display_name(taxon, species_scope)}


def scope_matches(taxon: dict, species_scope: str, concept_set_id: str, taxonomy_release: str) -> bool:
    species_scope = _scope(species_scope)
    if species_scope == 'all':
        return True
    return distribution_for(taxon, concept_set_id, taxonomy_release)['status'] == species_scope


def scope_query_parameters(species_scope: str, concept_set_id: str, taxonomy_release: str) -> dict:
    """Cypher maps; unknown = not an exact known (taxon_id, scientific_name) pair."""
    species_scope = _scope(species_scope)
    entries = _entries(concept_set_id, taxonomy_release) or {}
    known = {} if species_scope == 'all' else {
        taxon_id: entry['scientific_name'] for taxon_id, entry in entries.items()}
    selected = {taxon_id: entry['scientific_name'] for taxon_id, entry in entries.items()
                if entry['status'] == species_scope}
    return {'species_scope': species_scope, 'scope_known': known, 'scope_selected': selected}
