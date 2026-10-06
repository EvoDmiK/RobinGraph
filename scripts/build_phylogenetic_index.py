#!/usr/bin/env python3
"""Build a release-scoped topology index from pinned AvesData source files.

The parser intentionally accepts only the branchless, named-node Newick subset
used by this pinned artifact. Other Newick formats fail rather than guessing.
No network calls and no active release mutations occur in this script.
"""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
from xml.etree import ElementTree as ET
from zipfile import ZipFile

COMMIT = 'c85b4b8e54c7031787c0506ea59fa02fc4f5ca6c'
BASE = f'https://raw.githubusercontent.com/McTavishLab/AvesData/{COMMIT}/'
TREE_FILE = 'Tree_versions/Aves_1.6/Clements2025/phylo_only_clements_labels.tre'
CROSSWALK_FILE = 'Taxonomy_versions/Clements2025/OTT_crosswalk_2025.csv'
TREE_HASH = 'dd95dd07350bbcca9c181e567b3eb0f1a9309e533453192cbb839f8372380100'
CROSSWALK_HASH = 'b9db44d58f24b059610109b132f652d97e1dfcb35866015bf501991445bf84b3'
ANNOTATIONS_FILE = 'Tree_versions/Aves_1.6/OpenTreeSynth/annotated_supertree/annotations.json'
ANNOTATIONS_HASH = 'c26513420317582a4d3cace58667a3f91c8357c72c9bcd0104ba5d6d8d054b2e'
RANK_FILE = 'Tree_versions/Aves_1.6/OpenTreeSynth/phylo_input/rank_collection.json'
RANK_HASH = '764ef1521be36c8492a6914aa4888cdb16486dd02489b2f9f67bb5ee66261a12'
AVILIST_WORKBOOK_HASH = '2e1fd3374e23af732b04115b033dd9d97fc53ba275c312d02ef5d12cfb85c988'
CONSTRAINT_STUDIES = frozenset({'ot_2019', 'ot_2770'})
METHOD = 'phylogeny-topology-v1'


def parse_topology(text):
    """Return (leaf label -> ancestor path, internal node IDs)."""
    tokens = re.findall(r'[(),;]|[^(),;\s]+', text)
    if ''.join(tokens) != re.sub(r'\s+', '', text):
        raise ValueError('Unsupported Newick whitespace')
    if any(any(c in t for c in ':[]\'"') for t in tokens):
        raise ValueError('Expected unquoted, branchless Newick')
    position = 0
    labels = set()
    leaves = {}
    nodes = set()

    def read():
        nonlocal position
        if position >= len(tokens):
            raise ValueError('Truncated Newick')
        children = []
        if tokens[position] == '(':
            position += 1
            children.append(read())
            while position < len(tokens) and tokens[position] == ',':
                position += 1
                children.append(read())
            if position >= len(tokens) or tokens[position] != ')':
                raise ValueError('Unbalanced Newick')
            position += 1
        if position >= len(tokens) or tokens[position] in ('(', ')', ',', ';'):
            raise ValueError('Every source node must have an identity')
        label = tokens[position]
        position += 1
        if label in labels:
            raise ValueError('Duplicate source node identity')
        labels.add(label)
        return label, children

    root = read()
    if position != len(tokens)-1 or tokens[position] != ';' or not root[1]:
        raise ValueError('Expected one rooted tree')
    stack = [(root, [])]
    while stack:
        (label, children), ancestors = stack.pop()
        if children:
            nodes.add(label)
            stack.extend((child, ancestors+[label]) for child in children)
        else:
            leaves[label] = ancestors
    return leaves, nodes


def build_index(tree_text, crosswalk_rows, active, annotations, rank_collection=None):
    if active.get('taxonomy_release') != 'v2025b' or active.get('concept_set_id') != 'rg:concept-set:avilist-v2025b':
        raise ValueError('Expected active AviList v2025b context')
    leaves, internal = parse_topology(tree_text)
    rows = list(crosswalk_rows)
    species = active['species']
    ids = Counter(row['taxon_id'] for row in species)
    names = Counter(row['scientific_name'] for row in species)
    active_concepts = Counter(row.get('avibase_id') for row in species)
    source_names = Counter(row['SCI_NAME'] for row in rows)
    source_ott = Counter(row['ott_id'] for row in rows if row.get('ott_id'))
    source_concepts = Counter(row['TAXON_CONCEPT_ID'] for row in rows if row.get('TAXON_CONCEPT_ID'))
    unique = {row['TAXON_CONCEPT_ID']:row for row in rows
              if source_concepts[row['TAXON_CONCEPT_ID']] == 1}
    node_keys = {node:i for i,node in enumerate(sorted(internal))}
    source_metadata = {}
    for decision in (rank_collection or {}).get('decisions', []):
        key = decision['studyID']+'@'+decision['treeID']
        if decision['studyID'] not in CONSTRAINT_STUDIES:
            source_metadata[key] = {'citation':decision.get('compactRefText'),
                                    'source_url':decision.get('ot:studyPublication') or
                                                 'https://tree.opentreeoflife.org/curator/study/view/'+decision['studyID'],
                                    'study_id':decision['studyID']}
    nodes = {}
    for node_id in sorted(internal):
        annotation = annotations.get('nodes', {}).get(node_id, {})
        supporting = sorted(source for source in annotation.get('supported_by', {})
                            if source.split('@')[0] not in CONSTRAINT_STUDIES
                            and source in annotations.get('source_id_map', {})
                            and '@' in source)
        if supporting:
            nodes[str(node_keys[node_id])] = {'source_node_id':node_id, 'supporting_sources': supporting,
                             'conflicting_sources': sorted(source for source in annotation.get('conflicts_with', {})
                                                          if source.split('@')[0] not in CONSTRAINT_STUDIES)}
    taxa = {}
    excluded = Counter()
    for taxon in species:
        name = taxon['scientific_name']
        row = unique.get(taxon.get('avibase_id'))
        reason = None
        if ids[taxon['taxon_id']] != 1 or names[name] != 1:
            reason = 'ambiguous_active_identity'
        elif row is None:
            reason = 'no_unique_crosswalk_concept'
        elif (row.get('CATEGORY') != 'species' or row.get('sci_name_2025') != name
              or source_names[row['SCI_NAME']] != 1):
            reason = 'changed_or_ambiguous_source_identity'
        elif source_ott[row.get('ott_id')] != 1 or source_concepts[row.get('TAXON_CONCEPT_ID')] != 1:
            reason = 'ambiguous_source_identity'
        elif (not re.fullmatch(r'avibase-[0-9A-F]{8}', taxon.get('avibase_id', ''))
              or taxon['avibase_id'] != row.get('TAXON_CONCEPT_ID')
              or active_concepts[taxon['avibase_id']] != 1):
            reason = 'mismatched_or_ambiguous_avibase_concept'
        elif row.get('PRIMARY_COM_NAME') != taxon.get('clements_english_name'):
            reason = 'mismatched_clements_english_identity'
        elif row['SCI_NAME'].replace(' ', '_') not in leaves:
            reason = 'absent_from_phylogeny_only'
        if reason:
            excluded[reason] += 1
            continue
        label = row['SCI_NAME'].replace(' ', '_')
        tip_annotation = annotations.get('nodes', {}).get('ott'+row['ott_id'], {})
        tip_sources = set(tip_annotation.get('terminal', {})) | set(tip_annotation.get('supported_by', {}))
        if not any(source.split('@')[0] not in CONSTRAINT_STUDIES
                   and source in annotations.get('source_id_map', {}) for source in tip_sources):
            excluded['no_nonconstraint_tip_evidence'] += 1
            continue
        taxa[taxon['taxon_id']] = {
            'scientific_name':name, 'english_name':taxon.get('english_name'),
            'source_english_name':row.get('PRIMARY_COM_NAME'),
            'english_name_exact_match':taxon.get('english_name') == row.get('PRIMARY_COM_NAME'),
            'ott_id':row['ott_id'], 'avibase_id':row['TAXON_CONCEPT_ID'],
            'mapping_method':'unique_exact_avibase_current_scientific_and_clements_english',
            'source_scientific_name':row['SCI_NAME'],
            'ancestors':[node_keys[node] for node in leaves[label]],
        }
    return {
        'schema_version':1, 'method':METHOD,
        'taxonomy_release':active['taxonomy_release'], 'concept_set_id':active['concept_set_id'],
        'provenance':{
            'release':'Aves_1.6:Clements2025', 'commit':COMMIT,
            'source_name':'AvesData · McTavish et al. (2025)',
            'source_url':BASE+TREE_FILE,
            'citation':'McTavish et al. (2025), A complete and dynamic tree of birds, PNAS, doi:10.1073/pnas.2409658122',
            'license':'CC BY 4.0', 'license_url':'https://creativecommons.org/licenses/by/4.0/',
            'tree_sha256':hashlib.sha256(tree_text.encode()).hexdigest(),
            'crosswalk_url':BASE+CROSSWALK_FILE,
            'excluded_constraint_studies':sorted(CONSTRAINT_STUDIES),
            'support_note':'Non-constraint supported_by study/tree sources; synthesis support is not a bootstrap probability.',
        },
        'coverage':{'active_species':len(species), 'source_tips':len(leaves),
                    'mapped_species':len(taxa), 'supported_internal_nodes':len(nodes),
                    'excluded_species':len(species)-len(taxa), 'exclusion_reasons':dict(sorted(excluded.items()))},
        'sources':source_metadata, 'nodes':nodes, 'taxa':dict(sorted(taxa.items())),
    }


def enrich_active_species(active, workbook_bytes):
    """Verify each active identity against the official pinned workbook rows."""
    namespace = {'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with ZipFile(io.BytesIO(workbook_bytes)) as archive:
        strings = [''.join(si.itertext()) for si in
                   ET.fromstring(archive.read('xl/sharedStrings.xml')).findall('s:si',namespace)]
        sheet = ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
    workbook_species = {}
    header = None
    for row in sheet.findall('.//s:row',namespace):
        values = {}
        for cell in row.findall('s:c',namespace):
            column = re.sub(r'\d+$','',cell.attrib['r'])
            value = cell.find('s:v',namespace)
            text = value.text if value is not None else ''
            values[column] = strings[int(text)] if cell.attrib.get('t') == 's' else text
        if header is None:
            header = values
            expected = {'A':'Sequence','B':'Taxon_rank','F':'Scientific_name',
                        'I':'English_name_AviList','J':'English_name_Clements_v2025','T':'AvibaseID'}
            if any(header.get(k) != v for k,v in expected.items()):
                raise ValueError('Unexpected AviList workbook columns')
        if values.get('B') != 'species':
            continue
        taxon_id = 'avilist-taxon:v2025b:'+values['A']
        if taxon_id in workbook_species:
            raise ValueError('Duplicate workbook sequence')
        workbook_species[taxon_id] = values
    enriched = []
    seen = set()
    for taxon in active['species']:
        taxon_id = taxon['taxon_id']
        source = workbook_species.get(taxon_id)
        if (source is None or taxon_id in seen
                or source['F'] != taxon['scientific_name']
                or source['I'] != taxon.get('english_name')):
            raise ValueError('Active identity does not match official workbook')
        for supplied, column in [('avibase_id','T'),('clements_english_name','J')]:
            if supplied in taxon and taxon[supplied] != source.get(column):
                raise ValueError('Supplied enrichment disagrees with official workbook')
        seen.add(taxon_id)
        enriched.append({**taxon,'avibase_id':source.get('T'),
                         'clements_english_name':source.get('J')})
    return {**active,'species':enriched}


def checked_bytes(path, expected):
    content = path.read_bytes()
    if hashlib.sha256(content).hexdigest() != expected:
        raise ValueError(f'Pinned hash mismatch: {path.name}')
    return content


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--crosswalk', type=Path, required=True)
    parser.add_argument('--active-species', type=Path, required=True)
    parser.add_argument('--annotations', type=Path, required=True)
    parser.add_argument('--rank-collection', type=Path, required=True)
    parser.add_argument('--avilist-workbook', type=Path, required=True)
    parser.add_argument('--avilist-url', required=True)
    parser.add_argument('--output', type=Path, default=Path('src/robingraph/retrieval/species_phylogeny.json'))
    args = parser.parse_args()
    workbook = checked_bytes(args.avilist_workbook,AVILIST_WORKBOOK_HASH)
    tree = checked_bytes(args.tree,TREE_HASH)
    crosswalk = checked_bytes(args.crosswalk,CROSSWALK_HASH)
    annotation_bytes = checked_bytes(args.annotations,ANNOTATIONS_HASH)
    rank_bytes = checked_bytes(args.rank_collection,RANK_HASH)
    index = build_index(tree.decode(),csv.DictReader(io.StringIO(crosswalk.decode())),
                        enrich_active_species(json.loads(args.active_species.read_text()),workbook),
                        json.loads(annotation_bytes),json.loads(rank_bytes))
    index['provenance'].update(crosswalk_sha256=CROSSWALK_HASH,
                               annotations_url=BASE+ANNOTATIONS_FILE,
                               annotations_sha256=ANNOTATIONS_HASH,
                               rank_collection_url=BASE+RANK_FILE,
                               rank_collection_sha256=RANK_HASH,
                               avilist_url=args.avilist_url,
                               avilist_workbook_sha256=hashlib.sha256(workbook).hexdigest(),
                               active_species_sha256=hashlib.sha256(args.active_species.read_bytes()).hexdigest())
    if not index['taxa'] or not index['nodes']:
        raise ValueError('No mapped taxa or supported ancestors')
    args.output.write_text(json.dumps(index,ensure_ascii=False,separators=(',',':'))+'\n',encoding='utf-8')
    print(json.dumps(index['coverage'],ensure_ascii=False))


if __name__ == '__main__':
    main()
