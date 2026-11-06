"""Pinned Commons audio evidence, connected to the exact AviList species through MediaAsset nodes."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit

from robingraph.ingest.collection_points import default_config_root
from robingraph.ingest.validation import validate_source_registry_record
from .species_profile import PlainText

SOURCE_ID = 'wikimedia-commons-bird-recordings'
SOURCE_RELEASE = 'commons-reviewed-2026-11-02-verified'
ARTIFACT_SHA256 = '11005050c3247a7440d6c2a57320b05f1fa879a30f05ca1a13c164ca00120958'

READ_RECORDINGS = """
MATCH (taxon:Taxon:BirdTaxon {id:$taxon_id, rank:'species', scientific_name:$scientific_name,
  source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->
  (:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
MATCH (taxon)-[link:HAS_RECORDING]->(media:MediaAsset:Recording {dataset_id:$dataset_id,
  source_release:$source_release, policy_status:'allowed', redistribution_allowed:true})
MATCH (media)-[:SUPPORTED_BY]->(evidence:EvidenceUnit {policy_status:'allowed'})
WHERE link.concept_set_id=$concept_set_id AND link.taxonomy_release=$taxonomy_release
  AND media.scientific_name=taxon.scientific_name AND media.source_scope_kind='exact_species'
  AND evidence.dataset_id=media.dataset_id AND evidence.source_release=media.source_release
  AND evidence.source_record_id=media.id AND evidence.content_hash=media.metadata_sha256
  AND evidence.locator=media.landing_uri AND evidence.license_uri=media.license_uri
RETURN DISTINCT media.id AS id, media.payload_json AS payload_json, media.metadata_sha256 AS metadata_sha256
ORDER BY id LIMIT 3
"""

UPSERT_RECORDINGS = """
MATCH (concept:TaxonConceptSet {id:$concept_set_id, version:$taxonomy_release, policy_status:'allowed'})
UNWIND $rows AS row
MATCH (taxon:Taxon:BirdTaxon {rank:'species', scientific_name:row.scientific_name,
  source_release:$taxonomy_release, policy_status:'allowed'})-[:IN_CONCEPT_SET]->(concept)
MERGE (media:MediaAsset:Recording {id:row.id})
SET media += row, media.media_type='sound', media.dataset_id=$dataset_id,
    media.source_release=$source_release, media.policy_status='allowed',
    media.redistribution_allowed=true, media.source_record_id=row.id, media.source_scope_kind='exact_species'
MERGE (evidence:EvidenceUnit {id:row.evidence_id})
SET evidence.dataset_id=$dataset_id, evidence.source_release=$source_release,
    evidence.source_record_id=row.id, evidence.content_hash=row.metadata_sha256,
    evidence.locator=row.landing_uri, evidence.policy_status='allowed',
    evidence.license_uri=row.license_uri, evidence.retrieved_at=row.retrieved_at
MERGE (media)-[:SUPPORTED_BY]->(evidence)
MERGE (taxon)-[link:HAS_RECORDING {concept_set_id:$concept_set_id, taxonomy_release:$taxonomy_release}]->(media)
RETURN count(*) AS recordings
"""


def source_allowed():
    try:
        registry = json.loads((default_config_root() / 'source-registry.json').read_text())
        if not isinstance(registry, list):
            return False
        entries = [item for item in registry if isinstance(item, dict) and item.get('source_id') == SOURCE_ID]
        return (len(entries) == 1 and not validate_source_registry_record(entries[0])
                and entries[0].get('enabled') is True and entries[0].get('license_policy_status') == 'allowed'
                and entries[0].get('landing_uri') == 'https://commons.wikimedia.org/'
                and entries[0].get('license_uri') == 'https://commons.wikimedia.org/wiki/Commons:Licensing')
    except (OSError, ValueError, TypeError):
        return False


def _url(value, host, prefix):
    if not isinstance(value, str):
        raise ValueError('Missing recording URL')
    path = urlsplit(value)
    if (path.scheme != 'https' or path.hostname != host or path.username or path.password
            or path.port not in (None, 443) or not path.path.startswith(prefix) or path.fragment):
        raise ValueError('Untrusted recording URL')
    return path


def reviewed_record(row, retrieved_at):
    """Validate file-specific rights and exact species evidence; never use upload dates as recording dates."""
    info = row['imageinfo']
    metadata = info.get('extmetadata', {})
    def field(name):
        return str(PlainText(str(metadata.get(name, {}).get('value', ''))))
    science, title = row['scientific_name'], row['title']
    if (not re.fullmatch(r'[A-Z][a-z]+ [a-z]+(?:-[a-z]+)?', science)
            or not re.match(r'^File:.*\.(?:ogg|mp3|wav)$', title)
            or not re.search(r'(?<![A-Za-z])' + re.escape(science) + r'(?![A-Za-z])', title.replace('-', ' ').replace('_', ' '))
            or info.get('mime') not in ('audio/ogg', 'application/ogg', 'audio/mpeg', 'audio/wav')
            or info.get('width', 0) or info.get('height', 0)):
        raise ValueError('Recording taxon or audio format is unconfirmed')
    code = field('License').lower()
    if not re.fullmatch(r'cc-by(?:-sa)?-(?:2\.0|2\.5|3\.0|4\.0)', code) or field('Restrictions'):
        raise ValueError('Recording license is not allowed')
    kind, version = code.removeprefix('cc-').rsplit('-', 1)
    license_path = urlsplit(field('LicenseUrl'))
    if (license_path.scheme not in ('http', 'https') or license_path.netloc != 'creativecommons.org'
            or license_path.query or license_path.fragment):
        raise ValueError('Recording license URL mismatch')
    license_url = license_path._replace(scheme='https').geturl()
    if license_url.rstrip('/') != f'https://creativecommons.org/licenses/{kind}/{version}':
        raise ValueError('Recording license URL mismatch')
    artist = field('Artist')
    if not artist or not field('LicenseShortName'):
        raise ValueError('Recording attribution is missing')
    audio = _url(info.get('url'), 'upload.wikimedia.org', '/wikipedia/commons/')
    source = _url(info.get('descriptionurl'), 'commons.wikimedia.org', '/wiki/File:')
    if (unquote(source.path.removeprefix('/wiki/')).replace('_', ' ') != title.replace('_', ' ')
            or unquote(audio.path.rsplit('/', 1)[-1]).replace('_', ' ') != title.removeprefix('File:').replace('_', ' ')):
        raise ValueError('Recording source page mismatch')
    description = field('ImageDescription')
    for key in ('location', 'recording_type'):
        if row.get(key) and row[key] not in description:
            raise ValueError('Unsupported recording metadata')
    if type(row['page_id']) is not int or row['page_id'] <= 0 or type(row['revision_id']) is not int or row['revision_id'] <= 0:
        raise ValueError('Invalid Commons provenance')
    digest = sha256(json.dumps(info, sort_keys=True).encode()).hexdigest()
    return {'id': f"commons-recording:{row['page_id']}", 'scientific_name': science,
            'audio_url': audio._replace(query='').geturl(), 'source_url': source.geturl(),
            'creator': artist, 'license_name': field('LicenseShortName'), 'license_url': license_url,
            'title': title.removeprefix('File:'), 'recording_type': row.get('recording_type'),
            'recorded_at': field('DateTimeOriginal') or None, 'location': row.get('location'),
            'evidence': {'metadata_sha256': digest, 'page_id': row['page_id'], 'revision_id': row['revision_id'],
                         'retrieved_at': retrieved_at, 'taxon_match': 'exact_scientific_name'}}


def _reviewed_data():
    raw = Path(__file__).with_name('commons_bird_recordings.json').read_bytes()
    if sha256(raw).hexdigest() != ARTIFACT_SHA256:
        raise ValueError('Reviewed recording source snapshot differs from its pinned hash')
    return json.loads(raw)


@lru_cache(maxsize=1)
def reviewed_catalog():
    data = _reviewed_data()
    records = [reviewed_record(row, row.get('retrieved_at', data['retrieved_at'])) for row in data['records']]
    count = data.get('expected_recordings')
    expected = data.get('expected_species', [])
    if (type(count) is not int or count < 1 or len(records) != count
            or len({r['id'] for r in records}) != count or len({r['scientific_name'] for r in records}) != count
            or sorted(r['scientific_name'] for r in records) != sorted(expected)):
        raise ValueError('Recording catalog differs from the reviewed species/count manifest')
    return {record['id']: record for record in records}


def graph_rows():
    """Validated bounded import rows, no database access or writes."""
    if not source_allowed():
        raise ValueError('Recording source is not allowed')
    data = _reviewed_data()
    formats = {f"commons-recording:{row['page_id']}": row['imageinfo']['mime'] for row in data['records']}
    return [{'id': r['id'], 'scientific_name': r['scientific_name'], 'asset_uri': r['audio_url'],
             'landing_uri': r['source_url'], 'creator': r['creator'], 'publisher': 'Wikimedia Commons',
             'attribution': r['creator'] + ' · ' + r['license_name'], 'license_uri': r['license_url'],
             'format': formats[r['id']], 'metadata_sha256': r['evidence']['metadata_sha256'],
             'retrieved_at': r['evidence']['retrieved_at'],
             'evidence_id': r['id'] + ':' + r['evidence']['metadata_sha256'],
             'payload_json': json.dumps(r, ensure_ascii=False, sort_keys=True)} for r in reviewed_catalog().values()]


def read_recordings(repository, lineage):
    target = lineage.items[-1]
    if target.rank != 'species' or not source_allowed():
        return []
    rows = repository._run(READ_RECORDINGS, taxon_id=target.taxon_id, scientific_name=target.scientific_name,
                           concept_set_id=lineage.concept_set_id, taxonomy_release=lineage.taxonomy_release,
                           dataset_id=SOURCE_ID, source_release=SOURCE_RELEASE)
    catalog = reviewed_catalog()
    records = []
    for row in rows:
        record = json.loads(row['payload_json'])
        if (record != catalog.get(row['id']) or record['scientific_name'] != target.scientific_name
                or row.get('metadata_sha256') != record['evidence']['metadata_sha256']):
            raise ValueError('Recording graph evidence differs from the reviewed source')
        records.append(record)
    return records
