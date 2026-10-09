#!/usr/bin/env python3
"""Build an offline, release-scoped index from the public CC BY GBIF archive.

Only an existing exact AviList/BirdLife SIS link may connect an assessment.
Scientific-name matches alone, synonyms and NE rows never inherit a grade.
"""
import argparse
from collections import Counter, defaultdict
import csv
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from xml.etree import ElementTree as ET
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from robingraph.retrieval.conservation import _reference_authority_match, _reference_assessment_identity

AVILIST_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
SOURCE_SHA256 = '2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d'
TAXONOMY_RELEASE = 'v2025b'
CONCEPT_SET_ID = 'rg:concept-set:avilist-v2025b'
DATASET_KEY = '19491596-35ae-4a91-9a98-85cf505f1bd3'
SOURCE_RELEASE = '2026-1'
PUBLISHER = 'International Union for Conservation of Nature'
TITLE = 'The IUCN Red List of Threatened Species'
METHOD = 'exact_avilist_birdlife_sis_and_scientific_name'
CATEGORIES = {'Least Concern':'LC', 'Near Threatened':'NT', 'Vulnerable':'VU',
              'Endangered':'EN', 'Critically Endangered':'CR',
              'Extinct in the Wild':'EW', 'Extinct':'EX', 'Data Deficient':'DD'}
DWC = 'http://rs.tdwg.org/dwc/terms/'
DC = 'http://purl.org/dc/terms/'
GBIF = 'http://rs.gbif.org/terms/1.0/'
NAMESPACE = {'a':'http://rs.tdwg.org/dwc/text/'}
CORE_FIELDS = [DWC + name for name in (
    'scientificName','kingdom','phylum','class','order','family','genus',
    'specificEpithet','scientificNameAuthorship','taxonRank','infraspecificEpithet',
    'taxonomicStatus','acceptedNameUsageID')] + [DC+'bibliographicCitation', DC+'references']
DISTRIBUTION_FIELDS = [DWC+'countryCode', DWC+'locality', DC+'source',
                       DWC+'establishmentMeans', 'http://iucn.org/terms/threatStatus',
                       DWC+'occurrenceStatus']


def _checksum(content, expected, label):
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f'{label} snapshot changed; review the release before building')


def _text(element):
    return ''.join(element.itertext()).strip() if element is not None else ''


def _archive_rows(archive, element, fields, filename):
    if (element is None or element.findtext('a:files/a:location', namespaces=NAMESPACE) != filename
            or element.get('fieldsTerminatedBy') != '\\t'
            or element.get('ignoreHeaderLines') != '0'
            or element.get('encoding') != 'utf-8'):
        raise ValueError('Unexpected Darwin Core archive layout')
    identity_tag = 'a:id' if filename == 'taxon.txt' else 'a:coreid'
    identities = element.findall(identity_tag, NAMESPACE)
    if len(identities) != 1 or identities[0].get('index') != '0':
        raise ValueError('Unexpected Darwin Core archive identity column')
    declared = {int(field.get('index')):field.get('term')
                for field in element.findall('a:field', NAMESPACE)}
    if (declared != dict(enumerate(fields, start=1))
            or len(element.findall('a:field', NAMESPACE)) != len(fields)):
        raise ValueError('Unexpected Darwin Core archive fields')
    rows = list(csv.reader(io.TextIOWrapper(archive.open(filename), encoding='utf-8'), delimiter='\t'))
    if any(len(row) != len(fields)+1 for row in rows):
        raise ValueError('Unexpected Darwin Core row width')
    return rows


def _source_archive(content):
    with ZipFile(io.BytesIO(content)) as archive:
        eml = ET.fromstring(archive.read('eml.xml'))
        if (eml.findtext('dataset/title') != TITLE
                or eml.findtext('dataset/creator/organizationName') != PUBLISHER):
            raise ValueError('Unexpected public archive publisher or title')
        rights_links = [element.get('url') for element in eml.findall('dataset/intellectualRights//ulink')]
        if (eml.findtext('dataset/licensed/identifier') != 'CC-BY-4.0'
                or rights_links not in (["http://creativecommons.org/licenses/by/4.0/legalcode"],
                                       ["https://creativecommons.org/licenses/by/4.0/legalcode"])):
            raise ValueError('Public archive CC BY 4.0 license must be explicit')
        published = _text(eml.find('dataset/pubDate'))
        date.fromisoformat(published)
        citation = _text(eml.find('additionalMetadata/metadata/gbif/citation'))
        if f'Version {SOURCE_RELEASE}.' not in citation or 'https://doi.org/10.15468/0qnb58' not in citation:
            raise ValueError('Unexpected public archive release or citation')
        descriptor = ET.fromstring(archive.read('meta.xml'))
        core = descriptor.find('a:core', NAMESPACE)
        extensions = [element for element in descriptor.findall('a:extension', NAMESPACE)
                      if element.get('rowType') == GBIF+'Distribution']
        if core is None or core.get('rowType') != DWC+'Taxon' or len(extensions) != 1:
            raise ValueError('Expected taxon core and one distribution extension')
        taxa = _archive_rows(archive, core, CORE_FIELDS, 'taxon.txt')
        distributions = _archive_rows(archive, extensions[0], DISTRIBUTION_FIELDS, 'distribution.txt')
    return taxa, distributions, published, citation


def _authority(value):
    """Ignore spacing and case, preserving nomenclatural parentheses."""
    return ' '.join(value.split()).casefold() if isinstance(value, str) else ''


def _authority_match(avilist, assessment):
    """Accept exact authorship or a single author's omitted initials only.

    Years and nomenclatural parentheses are never removed. Multi-author
    notation is eligible only for the exact comparison above this parser.
    """
    if _authority(avilist) and _authority(avilist) == _authority(assessment):
        return 'exact'
    if not isinstance(avilist, str) or not isinstance(assessment, str):
        return None
    left, right = avilist.strip(), assessment.strip()
    enclosed = left.startswith('(') and left.endswith(')')
    if enclosed != (right.startswith('(') and right.endswith(')')):
        return None
    if enclosed:
        left, right = left[1:-1].strip(), right[1:-1].strip()
    if any(character in left + right for character in '();&'):
        return None
    full = re.fullmatch(r'([^,]+),\s*([^,]+),\s*([0-9]{4})', left)
    abbreviated = re.fullmatch(r'([^,]+),\s*([0-9]{4})', right)
    if not full or not abbreviated:
        return None
    surname, initials, year = full.groups()
    initials = initials.strip()
    if (not any(character.isalpha() for character in initials)
            or any(not (character.isalpha() and character.isupper()
                        or character in '.-' or character.isspace()) for character in initials)
            or not surname.strip() or re.search(r'\bet\s+al\b', surname, re.IGNORECASE)
            or _authority(surname) != _authority(abbreviated[1]) or year != abbreviated[2]):
        return None
    return 'single_author_initials_omitted'


def _assessment_identity(row, sis_id):
    match = re.fullmatch(r'https://www\.iucnredlist\.org/species/([1-9][0-9]*)/([1-9][0-9]*)', row[15])
    cited = re.findall(r'RLTS\.T([1-9][0-9]*)A([1-9][0-9]*)\.en', row[14])
    if not match or match[1] != sis_id or cited != [(sis_id, match[2])]:
        return None
    return int(match[2])


def _assessment_year(citation):
    """A release/publication date is never substituted for an assessment year."""
    years = re.findall(r'The IUCN Red List of Threatened Species (\d{4}):', citation)
    doi_years = re.findall(r'IUCN\.UK\.(\d{4})-', citation)
    if len(years) == len(doi_years) == 1 and years == doi_years:
        return int(years[0])
    return None


def _reference_index(active, source, source_ids, global_rows, linked_taxa):
    """Separate same-name published assessments, without concept/grade inheritance."""
    ids = Counter(row[0] for row in active)
    names = Counter(row[5] for row in active)
    by_name = defaultdict(list)
    for row in source:
        by_name[' '.join((row[7], row[8]))].append(row)
    references, excluded = {}, Counter()
    for taxonomy in active:
        sequence, name, authority, raw = (taxonomy[i] for i in (0, 5, 6, 15))
        key = f'avilist-taxon:{TAXONOMY_RELEASE}:{sequence}'
        if key in linked_taxa:
            continue
        candidates = by_name[name]
        if ids[sequence] != 1 or names[name] != 1:
            reason = 'ambiguous_avilist_identity'
        elif len(candidates) != 1:
            reason = 'missing_or_ambiguous_exact_source_name'
        else:
            row = candidates[0]
            sis = row[0]
            ne_reference = isinstance(raw, str) and raw.strip().upper() == 'NE'
            method = (_reference_authority_match(authority, row[9]) if ne_reference
                      else _authority_match(authority, row[9]))
            if source_ids[sis] != 1 or row[13] != sis:
                reason = 'ambiguous_source_identity'
            elif not method:
                reason = 'authority_mismatch'
            elif len(global_rows[sis]) != 1:
                reason = 'missing_or_ambiguous_global_assessment'
            else:
                distribution = global_rows[sis][0]
                category = CATEGORIES.get(distribution[5])
                strict_assessment = _assessment_identity(row, sis)
                identity = (_reference_assessment_identity(name, row[9], row[14], row[15], sis) if ne_reference
                            else (str(strict_assessment), 'citation_doi') if strict_assessment else None)
                assessment = int(identity[0]) if identity else None
                if not category:
                    reason = 'unsupported_source_category'
                elif not assessment or distribution[3] != row[14]:
                    reason = 'assessment_identity_or_citation_mismatch'
                else:
                    record = dict(scientific_name=name, authority=authority,
                                  assessment_authority=row[9], authority_match_method=method,
                                  taxonomy_category_raw=raw, category=category, sis_id=int(sis),
                                  assessment_id=assessment, assessment_reference_url=row[15],
                                  assessment_citation=row[14], taxonomy_alignment='unverified',
                                  assessment_identity_method=identity[1])
                    year = _assessment_year(row[14])
                    if year is not None:
                        record['assessment_year'] = year
                    references[key] = record
                    continue
        excluded[reason] += 1
    return dict(sorted(references.items())), dict(sorted(excluded.items()))


def build_index(avilist_content, source_content):
    _checksum(avilist_content, AVILIST_SHA256, 'AviList')
    _checksum(source_content, SOURCE_SHA256, 'IUCN GBIF')
    avilist = json.loads(avilist_content)
    if not isinstance(avilist, list) or any(not isinstance(row, list) or len(row) < 17 for row in avilist):
        raise ValueError('Expected AviList source rows')
    active = [row for row in avilist if row[1] == 'species']
    ids = Counter(row[0] for row in active)
    names = Counter(row[5] for row in active)
    source_rows, distributions, published, citation = _source_archive(source_content)
    source = [row for row in source_rows if row[4] == 'AVES' and row[10] == 'species' and row[12] == 'accepted']
    source_ids = Counter(row[0] for row in source_rows)
    source_names = Counter((row[7], row[8]) for row in source)
    by_sis = {row[0]:row for row in source if source_ids[row[0]] == 1}
    global_rows = defaultdict(list)
    for row in distributions:
        if row[1] == '' and row[2] == 'Global':
            global_rows[row[0]].append(row)
    links = Counter(row[16] for row in active if row[16])
    taxa, excluded = {}, Counter()
    for active_row in active:
        sequence, name, authority, original_grade, reference = (active_row[index] for index in (0,5,6,15,16))
        reason = None
        grade = original_grade.strip().upper() if isinstance(original_grade, str) else ''
        link = re.fullmatch(r'https://datazone\.birdlife\.org/species/factsheet/([1-9][0-9]*)', reference or '')
        if ids[sequence] != 1 or names[name] != 1:
            reason = 'ambiguous_avilist_identity'
        elif grade == 'NE':
            reason = 'avilist_ne_requires_concept_review'
        elif grade not in set(CATEGORIES.values()) | {'CR (PE)', 'CR (PEW)'}:
            reason = 'unconfirmed_taxonomy_category'
        elif not reference:
            reason = 'missing_birdlife_exact_link'
        elif not link or links[reference] != 1:
            reason = 'invalid_or_ambiguous_birdlife_exact_link'
        else:
            sis_id = link[1]
            row = by_sis.get(sis_id)
            if source_ids[sis_id] > 1:
                reason = 'duplicate_source_sis_id'
            elif row is None:
                reason = 'no_accepted_source_bird_species'
            elif row[13] != sis_id or source_names[(row[7], row[8])] != 1:
                reason = 'ambiguous_source_identity'
            elif ' '.join((row[7], row[8])) != name:
                reason = 'scientific_name_mismatch'
            elif not _authority_match(authority, row[9]):
                reason = 'authority_mismatch'
            elif len(global_rows[sis_id]) != 1:
                reason = 'missing_or_ambiguous_global_assessment'
            else:
                distribution = global_rows[sis_id][0]
                category = CATEGORIES.get(distribution[5])
                assessment_id = _assessment_identity(row, sis_id)
                if not category:
                    reason = 'unsupported_source_category'
                elif not assessment_id or distribution[3] != row[14]:
                    reason = 'assessment_identity_or_citation_mismatch'
                else:
                    record = dict(scientific_name=name, authority=authority,
                                  assessment_authority=row[9],
                                  authority_match_method=_authority_match(authority, row[9]),
                                  sis_id=int(sis_id), category=category,
                                  assessment_id=assessment_id, assessment_reference_url=row[15],
                                  assessment_citation=row[14], mapping_reference_url=reference,
                                  taxonomy_category_raw=original_grade)
                    year = _assessment_year(row[14])
                    if year is not None:
                        record['assessment_year'] = year
                    taxa[f'avilist-taxon:{TAXONOMY_RELEASE}:{sequence}'] = record
        if reason:
            excluded[reason] += 1
    references, reference_excluded = _reference_index(active, source, source_ids, global_rows, taxa)
    return dict(schema_version=1, taxonomy_release=TAXONOMY_RELEASE,
                concept_set_id=CONCEPT_SET_ID, mapping_method=METHOD,
                taxonomy_snapshot_sha256=AVILIST_SHA256,
                source=dict(dataset_key=DATASET_KEY, name=TITLE,
                            url=f'https://www.gbif.org/dataset/{DATASET_KEY}', release=SOURCE_RELEASE,
                            license_name='CC BY 4.0', license_url='https://creativecommons.org/licenses/by/4.0/',
                            publisher=PUBLISHER, citation=citation, snapshot_sha256=SOURCE_SHA256,
                            published_at=published),
                coverage=dict(active_species=len(active), source_bird_species=len(source),
                              mapped_species=len(taxa), excluded_reasons=dict(sorted(excluded.items()))),
                taxa=dict(sorted(taxa.items())), references=references,
                reference_coverage=dict(unlinked_species=len(active)-len(taxa),
                                        reference_species=len(references),
                                        excluded_reasons=reference_excluded))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--avilist', type=Path, required=True)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=Path('src/robingraph/retrieval/conservation_index.json'))
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    index = build_index(args.avilist.read_bytes(), args.snapshot.read_bytes())
    encoded = json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True)+'\n'
    if args.check:
        if args.output.read_text(encoding='utf-8') != encoded:
            raise ValueError('Conservation index is not reproducible')
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding='utf-8')
    print(json.dumps(index['coverage'], ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
