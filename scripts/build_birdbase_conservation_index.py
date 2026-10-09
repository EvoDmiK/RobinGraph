#!/usr/bin/env python3
"""Extract reference-only 2024 categories from a pinned, CC BY BIRDBASE file.

The authors' explicit AviList column is a nominal crosswalk, not proof that the
IUCN assessment and current AviList biological concepts have identical scope.
No individual assessment date, ID, or live verification is inferred.
"""
import argparse
from collections import Counter
import hashlib
import io
import json
from pathlib import Path
from xml.etree import ElementTree as ET
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SHA256 = 'cccb01fe229c7b39156639e001098b29880fa1c91d294c17cb74a4a76381276b'
TAXONOMY_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
DOI = '10.6084/m9.figshare.27051040.v1'
SOURCE_URL = 'https://doi.org/' + DOI
DOWNLOAD_URL = 'https://ndownloader.figshare.com/files/55634729'
METHOD = 'exact_unique_birdbase_avilist_v1_2025'
COLUMN = '2024 IUCN Red List category'
CATEGORIES = frozenset(('LC', 'NT', 'VU', 'EN', 'CR', 'EW', 'EX', 'DD'))
NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}


def read_rows(content):
    """Read the exact Data worksheet while retaining original Excel row numbers."""
    with ZipFile(io.BytesIO(content)) as archive:
        workbook = ET.fromstring(archive.read('xl/workbook.xml'))
        data = workbook.find("x:sheets/x:sheet[@name='Data']", NS)
        rel = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'
        relationships = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        target = next((r.get('Target') for r in relationships if data is not None and r.get('Id') == data.get(rel)), None)
        if target != 'worksheets/sheet1.xml':
            raise ValueError('Unexpected BIRDBASE Data worksheet layout')
        strings = [''.join(e.itertext()) for e in ET.fromstring(archive.read('xl/sharedStrings.xml'))]
        sheet = ET.fromstring(archive.read('xl/' + target))
        header, rows = {}, []
        for row in sheet.findall('x:sheetData/x:row', NS):
            number = int(row.get('r'))
            cells = {}
            for cell in row.findall('x:c', NS):
                column = ''.join(c for c in cell.get('r') if c.isalpha())
                value = cell.findtext('x:v', namespaces=NS)
                if cell.get('t') == 's':
                    value = strings[int(value)] if value is not None else None
                elif cell.get('t') == 'inlineStr':
                    value = ''.join(cell.find('x:is', NS).itertext())
                cells[column] = value
            if number == 2:
                header = cells
            elif number > 2:
                rows.append({**{name: cells.get(column) for column, name in header.items() if name}, '_row': number})
        required = {'AviList v1 2025', 'HBW/BirdLife International (v9.1)', 'Family AviList v1 2025', COLUMN}
        if not required.issubset(header.values()):
            raise ValueError('Missing required BIRDBASE columns')
        return rows


def validate_metadata(metadata):
    files = metadata.get('files', [])
    if (metadata.get('id') != 27051040 or metadata.get('version') != 1
            or metadata.get('doi') != DOI or metadata.get('status') != 'public'
            or metadata.get('is_public') is not True
            or metadata.get('license') != {'value': 52, 'name': 'CC BY', 'url': 'https://creativecommons.org/licenses/by/4.0/'}
            or len(files) != 1 or files[0].get('id') != 55634729
            or files[0].get('download_url') != DOWNLOAD_URL):
        raise ValueError('BIRDBASE public release and CC BY 4.0 metadata must match')


def build(avilist, rows, *, require_complete=True):
    targets = {r[5]: r for r in avilist if r[1] == 'species'}
    selected = [r for r in rows if r.get('AviList v1 2025')]
    counts = Counter(r['AviList v1 2025'] for r in selected)
    if any(n != 1 for n in counts.values()):
        raise ValueError('Ambiguous BIRDBASE AviList mapping')
    if require_complete and (len(targets) != 11131 or set(counts) != set(targets)):
        raise ValueError('BIRDBASE must map the complete pinned AviList species set')
    entries = {}
    for source in selected:
        target = targets.get(source['AviList v1 2025'])
        if target is None or source.get('Family AviList v1 2025') != target[3]:
            raise ValueError('BIRDBASE explicit AviList family or species mismatch')
        category_raw = source.get(COLUMN)
        category = 'CR' if category_raw in ('CR (PE)', 'CR (PEW)') else category_raw
        if category is not None and category not in CATEGORIES:
            raise ValueError('Unexpected BIRDBASE conservation category')
        taxon_id = f'avilist-taxon:v2025b:{target[0]}'
        entries[taxon_id] = dict(taxon_id=taxon_id, scientific_name=target[5], authority=target[6],
            taxonomy_category_raw=target[15].strip(), category=category, category_raw=category_raw,
            assessment_scientific_name=source.get('HBW/BirdLife International (v9.1)'),
            source_scientific_name=source.get('Latin (BirdLife > IOC > Clements>AviList)'),
            source_row=source['_row'], source_locator=f"Data!row {source['_row']}")
    return dict(schema_version=1, taxonomy_release='v2025b', concept_set_id='rg:concept-set:avilist-v2025b',
        taxonomy_snapshot_sha256=TAXONOMY_SHA256, mapping_method=METHOD,
        source=dict(id='birdbase-v2025.1', name='BIRDBASE · IUCN 2024 reference', release='v2025.1',
            url=SOURCE_URL, download_url=DOWNLOAD_URL, snapshot_sha256=SHA256,
            publication_url='https://www.nature.com/articles/s41597-025-05615-3',
            data_year=2024, category_column=COLUMN, license_name='CC BY 4.0',
            license_url='https://creativecommons.org/licenses/by/4.0/',
            publisher='BIRDBASE authors · Scientific Data',
            citation='Şekercioğlu et al. (2025). BIRDBASE v2025.1. ' + SOURCE_URL),
        policy='Reference only; explicit publisher AviList crosswalk, biological scope unverified. Data year is not an assessment year. Null categories remain absent.',
        counts=dict(mapped_species=len(entries), category_present=sum(r['category'] is not None for r in entries.values()),
                    category_missing=sum(r['category'] is None for r in entries.values())), entries=entries)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--avilist', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / 'src/robingraph/retrieval/birdbase_conservation_index.json')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    content, taxonomy = args.source.read_bytes(), args.avilist.read_bytes()
    if hashlib.sha256(content).hexdigest() != SHA256 or hashlib.sha256(taxonomy).hexdigest() != TAXONOMY_SHA256:
        raise ValueError('Pinned BIRDBASE or AviList snapshot differs')
    validate_metadata(json.loads(args.metadata.read_text()))
    result = build(json.loads(taxonomy), read_rows(content))
    raw = (json.dumps(result, ensure_ascii=False, sort_keys=True, separators=(',', ':')) + '\n').encode()
    if args.check:
        if args.output.read_bytes() != raw:
            raise ValueError('BIRDBASE reference index differs from original')
    else:
        args.output.write_bytes(raw)
    print(json.dumps(result['counts']))


if __name__ == '__main__':
    main()
