#!/usr/bin/env python3
"""Read-only full-release audit of the shared subspecies display function."""
import argparse
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
from urllib.request import Request, urlopen

from robingraph.retrieval.subspecies import _display_subspecies
from robingraph.retrieval.taxonomy_lineage import LineageTaxon, TaxonomyLineage, with_korean_display_name

SOURCE = 'https://explore.avilist.org/data/avilist-2025b.json'
PINNED_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'


def audit(content):
    digest = sha256(content).hexdigest()
    if digest != PINNED_SHA256:
        raise ValueError('AviList snapshot changed; review the new source before auditing')
    rows = json.loads(content)
    counts = dict(subspecies=0, source_ranges=0, named=0, korean_descriptions=0, english_originals=0, distribution_captions=0)
    review_counts = {}
    ids = set()
    parent = None
    examples = []
    for raw in rows:
        if raw[1] == 'species':
            value = with_korean_display_name(dict(taxon_id='avilist-taxon:v2025b:'+raw[0], rank='species', scientific_name=raw[5], authority=raw[6], english_name=raw[8]))
            parent = LineageTaxon(**value)
        elif raw[1] == 'subspecies':
            if parent is None:
                raise ValueError('Subspecies lacks an explicit preceding species')
            child = LineageTaxon('avilist-taxon:v2025b:'+raw[0], 'subspecies', raw[5], raw[6], english_name=raw[8])
            if child.taxon_id in ids:
                raise ValueError('Duplicate subspecies identity')
            ids.add(child.taxon_id)
            lineage = TaxonomyLineage(raw[5], 'AviList', 'v2025b', 'rg:concept-set:avilist-v2025b', (parent, child))
            row = dict(taxon=asdict(child), range_text=raw[13], source_url=SOURCE, source_name='AviList global avian checklist')
            display = _display_subspecies(row, parent, lineage)
            assert display['range_text'] == raw[13].strip()
            assert display.get('korean_name') or display.get('english_name') or display.get('display_label')
            assert display.get('description') and display.get('description_source_url')
            status = display['range_review_status']
            review_counts[status] = review_counts.get(status, 0) + 1
            counts['subspecies'] += 1
            counts['source_ranges'] += bool(raw[13])
            counts['named'] += bool(display.get('korean_name') or display.get('english_name'))
            counts['distribution_captions'] += bool(display.get('display_label'))
            counts['korean_descriptions'] += display['description_language'] == 'ko'
            counts['english_originals'] += display['description_language'] == 'en'
            if len(examples) < 8:
                examples.append(display)
        elif raw[1] in ('order', 'family', 'genus'):
            parent = None
    assert counts['subspecies'] == 19879
    return dict(source_url=SOURCE, source_sha256=digest, taxonomy_release='v2025b', scope='full primary snapshot, shared display function; not live DB/API', counts=counts, range_review_counts=review_counts, examples=examples)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, help='Use a previously downloaded official snapshot')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.snapshot:
        content = args.snapshot.read_bytes()
    else:
        with urlopen(Request(SOURCE, headers={'User-Agent':'RobinGraph-source-audit/1.0'}), timeout=60) as response:
            content = response.read()
    report = audit(content)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report['counts']))


if __name__ == '__main__':
    main()
