#!/usr/bin/env python3
"""Build identity-bound reviews and a full-release processing ledger, offline."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

SOURCE_SHA256 = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
SOURCE_URL = 'https://explore.avilist.org/data/avilist-2025b.json'


def build(content, reviewed):
    if sha256(content).hexdigest() != SOURCE_SHA256:
        raise ValueError('Snapshot changed; review the new release before building')
    if reviewed.get('schema_version') != 1 or not reviewed.get('reviewer') or not reviewed.get('review_method'):
        raise ValueError('Review provenance is required')
    phrases = reviewed['phrases']
    output, ledger, used = {}, [], set()
    for row in json.loads(content):
        if row[1] != 'subspecies':
            continue
        tid, raw = 'avilist-taxon:v2025b:' + row[0], row[13].strip()
        record = dict(taxon_id=tid, scientific_name=row[5], taxonomy_release='v2025b',
                      concept_set_id='rg:concept-set:avilist-v2025b',
                      source_sha256=sha256(raw.encode()).hexdigest())
        phrase = phrases.get(raw)
        status = 'pending-review' if raw else 'missing-source'
        if phrase:
            used.add(raw)
            status = phrase.get('status', 'pending-review')
            if status not in ('reviewed', 'pending-review', 'conflict', 'translation-failed'):
                raise ValueError('Unknown review status')
        if phrase and status == 'reviewed':
            if not all(isinstance(phrase.get(key), str) and phrase[key].strip() for key in ('description','caption')):
                raise ValueError('Reviewed descriptions and captions must be nonempty')
        if phrase:
            output[tid] = {**record, 'description':phrase.get('description'),
                           'caption':phrase.get('caption'), 'status':status,
                           'reviewer':reviewed['reviewer'], 'review_method':reviewed['review_method']}
        ledger.append({**record, 'status':status})
    if len({r['taxon_id'] for r in ledger}) != len(ledger):
        raise ValueError('Duplicate identity')
    unused = sorted(set(phrases) - used)
    if unused:
        raise ValueError(f'{len(unused)} review phrases do not match the pinned snapshot')
    bundle = dict(schema_version=1, source_url=SOURCE_URL, snapshot_sha256=SOURCE_SHA256, reviews=output)
    ledger_text = ''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger)
    report = dict(ledger_sha256=sha256(ledger_text.encode()).hexdigest(), schema_version=1, taxonomy_release='v2025b', source_url=SOURCE_URL,
                  snapshot_sha256=SOURCE_SHA256, scope='All pinned snapshot subspecies; offline source comparison, not live DB/API',
                  counts=dict(total=len(ledger), **{status:sum(r['status']==status for r in ledger) for status in ('reviewed','pending-review','conflict','translation-failed','missing-source')}),
                  reviewed_phrases=sum(phrases[raw].get('status') == 'reviewed' for raw in used), automatic_translations=0,
                  independent_human_review=False)
    return bundle, report, ledger


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--snapshot',type=Path,required=True)
    p.add_argument('--reviews',type=Path,default=Path('data/review/subspecies-range-ko.json'))
    p.add_argument('--output',type=Path,default=Path('src/robingraph/retrieval/subspecies_range_reviews.json'))
    p.add_argument('--report',type=Path,required=True)
    p.add_argument('--ledger',type=Path,required=True)
    p.add_argument('--check',action='store_true')
    a=p.parse_args()
    bundle,report,ledger=build(a.snapshot.read_bytes(),json.loads(a.reviews.read_text()))
    encoded=json.dumps(bundle,ensure_ascii=False,indent=2)+'\n'
    if a.check:
        if a.output.read_text(encoding='utf-8') != encoded:
            raise ValueError('Review bundle is not reproducible')
    else:
        a.output.write_text(encoded,encoding='utf-8')
    a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    a.ledger.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in ledger),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
