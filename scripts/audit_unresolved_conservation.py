#!/usr/bin/env python3
"""Reproducible full unresolved-subset audit; candidates never inherit grades."""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('unresolved_builder', ROOT / 'scripts/build_conservation_index.py')
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
spec = importlib.util.spec_from_file_location('unresolved_reconciliation', ROOT / 'scripts/audit_conservation_reconciliation.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)

BIRDLIFE_RECOMMENDATIONS = {'Scytalopus intermedius': 'LC', 'Scytalopus whitneyi': 'NT',
                          'Scytalopus frankeae': 'LC', 'Scytalopus androstictus': 'LC'}
BIRDLIFE_PDF = 'https://forums.birdlife.org/wp-content/uploads/2026/02/Red_List_status_changes_2026.1.pdf'
BIRDLIFE_SHA256 = '051d899372dfb9eccdcca68bdd5b64699019fec9fb540d99650d78679c81195a'


def compatible_higher_taxonomy(avilist_row, source_row):
    """Nominal author/epithet collisions require matching order AND family.

    This is an audit discovery filter, not concept-equivalence evidence. Exact
    names and explicitly mentioned source names remain direct source evidence.
    """
    def normalized(value):
        return value.strip().casefold() if isinstance(value, str) else ''
    return all(normalized(left) and normalized(left) == normalized(right)
               for left, right in ((avilist_row[2], source_row[5]), (avilist_row[3], source_row[6])))


def classify_subset(runtime, avilist_bytes, source_bytes, index, birdbase=None):
    """Inspect every original needs_review/no-reference species, not a sample.

    Same-name evidence, official decision mentions and nominal genus-change
    candidates are distinct. None proves biological concept equivalence.
    """
    builder._checksum(avilist_bytes, builder.AVILIST_SHA256, 'AviList')
    builder._checksum(source_bytes, builder.SOURCE_SHA256, 'IUCN GBIF')
    active = [row for row in json.loads(avilist_bytes) if row[1] == 'species']
    taxonomy = {f'avilist-taxon:v2025b:{row[0]}': row for row in active}
    taxonomy_by_name = {row[5]: row for row in active}
    taxonomy_abbreviations = defaultdict(list)
    for row in active:
        parts = row[5].split()
        taxonomy_abbreviations[(parts[0][0], parts[1])].append(row)
    source_rows, distributions, _, _ = builder._source_archive(source_bytes)
    source = [r for r in source_rows if r[4] == 'AVES' and r[10] == 'species' and r[12] == 'accepted']
    ids = Counter(r[0] for r in source_rows)
    by_name, by_epithet, by_dist = (defaultdict(list) for _ in range(3))
    for row in source:
        by_name[' '.join((row[7], row[8]))].append(row)
        by_epithet[row[8]].append(row)
    for row in distributions:
        by_dist[row[0]].append(row)
    names = Counter(' '.join((r[7], r[8])) for r in source)
    source_names = re.compile(r'(?<![\w-])(?:' + '|'.join(re.escape(n) for n in sorted(by_name, key=len, reverse=True)) + r')(?![\w-])')
    selected = [r for r in runtime['species'] if r.get('assessment_status') == 'needs_review' and r.get('reference_category') is None]
    if len({r['taxon_id'] for r in selected}) != len(selected):
        raise ValueError('Duplicate unresolved runtime identity')
    ledger = []
    for runtime_row in selected:
        taxon_id = runtime_row['taxon_id']
        row = taxonomy.get(taxon_id)
        if row is None or row[5] != runtime_row['scientific_name'] or row[15].strip() != 'NE':
            raise ValueError('Runtime subset does not identify the pinned NE taxonomy')
        name, authority = row[5], row[6]
        note = row[12] or ''
        plain = re.sub(r'<[^>]+>', '', note)
        candidates = {}
        rejected_nominal = {}

        def add_nominal(candidate, route):
            if compatible_higher_taxonomy(row, candidate):
                candidates.setdefault(candidate[0], [candidate, set()])[1].add(route)
            else:
                rejected_nominal.setdefault(candidate[0], [candidate, set()])[1].add(route)

        for candidate in by_name[name]:
            candidates.setdefault(candidate[0], [candidate, set()])[1].add('exact_scientific_name')
        # Official decision mentions are scope evidence, never a crosswalk.
        for mentioned in set(source_names.findall(plain)):
            for candidate in by_name[mentioned]:
                candidates.setdefault(candidate[0], [candidate, set()])[1].add('mentioned_in_official_taxonomy_decision')
        # A decision may use current genera while the assessment archive retains
        # older genera, or abbreviate a genus. Keep both links as candidates,
        # rather than treating this nominal chain as concept equivalence.
        decision_taxa = {mentioned: taxonomy_by_name[mentioned]
                         for mentioned in set(re.findall(r'\b[A-Z][a-z]+ [a-z][a-z-]+\b', plain))
                         if mentioned in taxonomy_by_name}
        for initial, epithet in re.findall(r'\b([A-Z])\.\s*([a-z][a-z-]+)\b', plain):
            for parent in taxonomy_abbreviations[(initial, epithet)]:
                decision_taxa[parent[5]] = parent
        for parent in decision_taxa.values():
            for candidate in by_epithet[parent[5].split()[1]]:
                if builder._reference_authority_match(parent[6].strip('() '), candidate[9].strip('() ')):
                    add_nominal(candidate, 'official_decision_nominal_name_chain_candidate')
        parts = name.split()
        for candidate in by_epithet[parts[1]]:
            if ' '.join((candidate[7], candidate[8])) == name:
                continue
            # Parentheses may differ after a genus change. That is permitted only
            # in candidate discovery; neither reference nor primary assignment.
            if builder._reference_authority_match(authority.strip('() '), candidate[9].strip('() ')):
                add_nominal(candidate, 'same_epithet_author_year_different_genus_candidate')
        records = []
        for candidate, routes in candidates.values():
            reference = audit.reference_record(candidate, by_dist[candidate[0]], row, routes,
                                               ids[candidate[0]], names[' '.join((candidate[7], candidate[8]))])
            reference['reference_authority_match_method'] = builder._reference_authority_match(authority, candidate[9])
            reference['source_order'], reference['source_family'] = candidate[5], candidate[6]
            reference['target_order'], reference['target_family'] = row[2], row[3]
            reference['higher_taxonomy_matches'] = compatible_higher_taxonomy(row, candidate)
            identity = builder._reference_assessment_identity(' '.join((candidate[7], candidate[8])), candidate[9],
                                                             candidate[14], candidate[15], candidate[0])
            reference['reference_assessment_identity_method'] = identity[1] if identity else None
            reference['reference_assessment_id'] = identity[0] if identity else None
            reference['eligible_for_same_name_reference'] = bool(reference['name_exact'] and
                reference['reference_authority_match_method'] and identity and ids[candidate[0]] == 1 and
                names[' '.join((candidate[7], candidate[8]))] == 1 and candidate[13] == candidate[0] and
                len(reference['global_categories']) == 1 and reference['global_categories'][0] and
                reference['global_distribution_citations'] == [candidate[14]])
            reference['evidence_integrity_policy'] = 'strict_primary_citation_doi_identity'
            reference['reference_evidence_integrity_valid'] = reference['eligible_for_same_name_reference']
            if reference['name_exact']:
                if reference['eligible_for_same_name_reference']:
                    issue = 'same_name_reference_available_concept_unverified'
                elif reference['reference_authority_match_method']:
                    issue = 'same_name_assessment_integrity_gap'
                else:
                    left_year = re.findall(r'\d{4}', authority)
                    right_year = re.findall(r'\d{4}', candidate[9])
                    issue = 'same_name_authorship_year_conflict' if left_year != right_year else 'same_name_authorship_notation_or_identity_conflict'
            else:
                issue = 'different_name_taxonomy_scope_candidate'
            reference['review_issue'] = issue
            reference['assign_grade_to_target'] = False
            records.append(reference)
        new_reference = index.get('references', {}).get(taxon_id)
        if new_reference:
            status = 'reference_added_concept_unverified'
        elif any(r['name_exact'] for r in records):
            status = 'same_name_identity_or_integrity_conflict'
        elif records:
            status = 'different_name_or_taxonomy_scope_candidates'
        else:
            status = 'no_candidate_in_pinned_public_source'
        relations = []
        for label, pattern in (('split', r'split|species separate|separate species|species distinct'),
                               ('lump', r'conspecific|subspecies of'), ('genus_change', r'genus|generic')):
            if re.search(pattern, plain, re.I):
                relations.append(label)
        ledger.append(dict(taxon_id=taxon_id, scientific_name=name, authority=authority,
                           taxonomy_category_raw=row[15], taxonomy_decision_id=row[11],
                           taxonomy_decision_text=note or None, taxonomy_relations=relations,
                           taxonomy_source_url='https://explore.avilist.org/data/avilist-2025b.json',
                           birdlife_sis_url=row[16], review_status=status,
                           reference_added=bool(new_reference), primary_grade_assigned=False,
                           independently_verified=False, concept_alignment='unverified',
                           candidate_count=len(records), candidates=sorted(records, key=lambda r:r['sis_id'])))
        item = ledger[-1]
        item['excluded_nominal_collisions'] = [dict(sis_id=c[0], scientific_name=' '.join((c[7], c[8])),
            source_order=c[5], source_family=c[6], target_order=row[2], target_family=row[3],
            rejected_routes=sorted(routes), reason='nominal_chain_order_or_family_mismatch',
            assign_grade_to_target=False) for c, routes in sorted(rejected_nominal.values(), key=lambda item:item[0][0])]
        if birdbase is not None:
            source_record = birdbase['entries'].get(taxon_id)
            if (not source_record or source_record['scientific_name'] != name
                    or source_record['authority'] != authority or source_record['taxonomy_category_raw'] != 'NE'):
                raise ValueError('Every unresolved row must retain the pinned BIRDBASE source lookup')
            item['birdbase_lookup'] = dict(source_record, mapping_method=birdbase['mapping_method'],
                source_id=birdbase['source']['id'], snapshot_sha256=birdbase['source']['snapshot_sha256'],
                data_year=2024, concept_alignment='unverified', category_missing=source_record['category'] is None)
            item['selected_reference_source'] = ('gbif-iucn-2026-1' if new_reference else
                'birdbase-v2025.1' if source_record['category'] is not None else None)
            item['reference_category'] = new_reference['category'] if new_reference else source_record['category']
            item['reference_resolution'] = 'reference_only_concept_unverified' if item['reference_category'] else 'no_published_category_in_reviewed_sources'
        if name in BIRDLIFE_RECOMMENDATIONS:
            item['unreleased_recommendation'] = dict(source_url=BIRDLIFE_PDF, snapshot_sha256=BIRDLIFE_SHA256,
                source_page=1, decision_year=2026, recommended_category=BIRDLIFE_RECOMMENDATIONS[name],
                publication_status='recommended_to_iucn_not_published', assign_grade_to_target=False,
                exclusion_reason='Official BirdLife timeline schedules publication for November 2026; current audit is 2026-10-09. Recommendations are not released assessments.',
                release_timeline_url='https://forums.birdlife.org/red-list-changes-forum/',
                decision_example_url='https://forums.birdlife.org/2026-1-loja-tapaculo-scytalopus-androstictus/')
    result = dict(schema_version=1, subset_definition='needs_review and reference_category is null in input runtime audit',
                input_runtime_sha256=hashlib.sha256(json.dumps(runtime, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
                source=index['source'], taxonomy_snapshot_sha256=builder.AVILIST_SHA256,
                method=dict(all_rows_processed=True, primary_grade_inheritance=False,
                            authenticated_api_access=False, live_assessment_originals_reviewed=0,
                            evidence='pinned official AviList decisions and public IUCN GBIF archive',
                            nominal_candidate_filter='Nonempty exact order AND family match (case-insensitive); exact names and explicitly mentioned source names remain direct evidence. Never concept-equivalence proof.',
                            candidate_routes=['exact_scientific_name', 'mentioned_in_official_taxonomy_decision',
                                              'official_decision_nominal_name_chain_candidate',
                                              'same_epithet_author_year_different_genus_candidate']),
                counts=dict(input_unresolved=len(selected), processed=len(ledger),
                            review_status=dict(sorted(Counter(r['review_status'] for r in ledger).items())),
                            candidate_issues=dict(sorted(Counter(c['review_issue'] for r in ledger for c in r['candidates']).items())),
                            taxonomy_relations=dict(sorted(Counter(v for r in ledger for v in r['taxonomy_relations']).items())),
                            without_taxonomy_decision=sum(not r['taxonomy_decision_text'] for r in ledger),
                            excluded_nominal_collisions=sum(len(r['excluded_nominal_collisions']) for r in ledger),
                            primary_grades_assigned=0), species=ledger)
    if birdbase is not None:
        result['birdbase_source'] = birdbase['source']
        result['counts']['combined_reference_sources'] = dict(sorted(Counter(r['selected_reference_source'] or 'missing' for r in ledger).items()))
        result['counts']['birdbase_category_present'] = sum(not r['birdbase_lookup']['category_missing'] for r in ledger)
        result['counts']['birdbase_category_missing'] = sum(r['birdbase_lookup']['category_missing'] for r in ledger)
        result['counts']['excluded_unreleased_recommendations'] = sum('unreleased_recommendation' in r for r in ledger)
        result['method']['evidence'] += ' and pinned CC BY BIRDBASE v2025.1 explicit AviList crosswalk'
        result['method']['birdbase_data_year_not_assessment_year'] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-audit', type=Path, required=True)
    parser.add_argument('--avilist', type=Path, required=True)
    parser.add_argument('--iucn', type=Path, required=True)
    parser.add_argument('--index', type=Path, default=ROOT / 'src/robingraph/retrieval/conservation_index.json')
    parser.add_argument('--birdbase-index', type=Path, default=ROOT / 'src/robingraph/retrieval/birdbase_conservation_index.json')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = classify_subset(json.loads(args.runtime_audit.read_text()), args.avilist.read_bytes(),
                             args.iucn.read_bytes(), json.loads(args.index.read_text()), json.loads(args.birdbase_index.read_text()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(result['counts'], ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
