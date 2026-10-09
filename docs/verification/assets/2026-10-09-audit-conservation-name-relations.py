#!/usr/bin/env python3
"""Read-only, pinned-archive audit of all 447 unresolved conservation identities.

Classifies evidence routes; it never assigns a candidate's grade to a target.
Only writes --output. Standard library only; no network, DB, or application edits.
"""
import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import html
import io
import json
from pathlib import Path
import re
from zipfile import ZipFile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
CATEGORIES = {'Least Concern': 'LC', 'Near Threatened': 'NT', 'Vulnerable': 'VU',
              'Endangered': 'EN', 'Critically Endangered': 'CR',
              'Extinct in the Wild': 'EW', 'Extinct': 'EX', 'Data Deficient': 'DD'}
AVI_SHA = '3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411'
GBIF_SHA = '2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d'
SCOPE_PATTERN = re.compile(r'conspecific|subspecies of|species separate|separate species|species distinct|split|species are recognized|species is recognized', re.I)
RENAME_PATTERN = re.compile(r'previously placed|transferred (?:from|to)|moved (?:from|to)|change of genus|placed in the genus', re.I)

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def plain(value):
    return ' '.join(html.unescape(re.sub(r'<[^>]*>', '', value or '')).split())

def mention_evidence(note, raw_note, source_name, target_name):
    """Return explicit textual occurrence, not synonymy or equivalence proof."""
    for kind, token in [('exact_binomial', source_name),
                        ('abbreviated_binomial', source_name[0] + '. ' + source_name.split()[1])]:
        pattern = re.compile(r'(?<![A-Za-z-])' + re.escape(token).replace(r'\ ', r'\s*') + r'(?![A-Za-z-])')
        match = pattern.search(note)
        if kind == 'abbreviated_binomial':
            explicit_genera = {m[0] for m in re.findall(r'\b([A-Z][a-z]+) ([a-z][a-z-]+)\b', note)} | {target_name.split()[0]}
            matching_genera = {g for g in explicit_genera if g[0] == source_name[0]}
            if matching_genera != {source_name.split()[0]}:
                continue
        if match:
            return {'kind': kind, 'matched_text': match[0], 'start': match.start(),
                    'end': match.end(), 'context': note[max(0, match.start()-100):match.end()+180]}
    # An explicitly named epithet in a decision is still not a genus crosswalk.
    italic_epithet_spans = [span for span in re.findall(r'<em>(.*?)</em>', raw_note or '', re.S) if not re.search(r'[A-Z]', span)]
    italic_words = set(re.findall(r'[a-z][a-z-]+', ' '.join(italic_epithet_spans)))
    if source_name.split()[0] == target_name.split()[0] and source_name.split()[1] in italic_words:
        token = source_name.split()[1]
        match = re.search(r'(?<![A-Za-z-])' + re.escape(token) + r'(?![A-Za-z-])', note)
        if match:
            return {'kind': 'same_genus_epithet_mentioned', 'matched_text': match[0],
                    'start': match.start(), 'end': match.end(),
                    'context': note[max(0, match.start()-100):match.end()+180]}
    return None

def audit(ledger_path, avilist_path, archive_path, index_path):
    assert sha(avilist_path) == AVI_SHA, 'AviList snapshot changed'
    assert sha(archive_path) == GBIF_SHA, 'GBIF archive snapshot changed'
    ledger = json.loads(ledger_path.read_text())
    index = json.loads(index_path.read_text())
    assert ledger['taxonomy_snapshot_sha256'] == AVI_SHA == index['taxonomy_snapshot_sha256']
    assert ledger['source']['snapshot_sha256'] == GBIF_SHA == index['source']['snapshot_sha256']
    targets = ledger['species']
    assert len(targets) == len({r['taxon_id'] for r in targets}) == 447
    assert sum(r['reference_category'] is None for r in targets) == 305
    avilist = {f'avilist-taxon:v2025b:{r[0]}': r for r in json.loads(avilist_path.read_text()) if r[1] == 'species'}
    needed = {str(c['sis_id']) for t in targets for c in t['candidates']}
    rows, globals_, source_ids, source_names = {}, defaultdict(list), Counter(), Counter()
    with ZipFile(archive_path) as z:
        meta = ET.fromstring(z.read('meta.xml'))
        ns = {'a': 'http://rs.tdwg.org/dwc/text/'}
        assert meta.find('a:core/a:files/a:location', ns).text == 'taxon.txt'
        for line_no, r in enumerate(csv.reader(io.TextIOWrapper(z.open('taxon.txt'), encoding='utf-8'), delimiter='\t'), 1):
            assert len(r) == 16
            source_ids[r[0]] += 1
            if r[4] == 'AVES' and r[10] == 'species' and r[12] == 'accepted':
                source_names[' '.join(r[7:9])] += 1
                if r[0] in needed:
                    rows[r[0]] = (r, line_no)
        for line_no, r in enumerate(csv.reader(io.TextIOWrapper(z.open('distribution.txt'), encoding='utf-8'), delimiter='\t'), 1):
            assert len(r) == 7
            if r[0] in needed and r[1] == '' and r[2] == 'Global':
                globals_[r[0]].append((r, line_no))
    output = []
    for target in targets:
        a = avilist[target['taxon_id']]
        assert (a[5], a[6], a[11], a[12] or None) == (target['scientific_name'], target['authority'], target['taxonomy_decision_id'], target['taxonomy_decision_text'])
        note = plain(a[12])
        candidates = []
        for old in target['candidates']:
            sid = str(old['sis_id']); raw, line_no = rows[sid]
            name = ' '.join(raw[7:9]); dist = globals_[sid]
            assert name == old['scientific_name'] and raw[9] == old['authorship']
            assert raw[14] == old['citation'] and raw[15] == old['assessment_url']
            assert [r[5] for r, _ in dist] == old['global_categories_raw']
            url = re.fullmatch(r'https://www\.iucnredlist\.org/species/(\d+)/(\d+)', raw[15])
            dois = re.findall(r'RLTS\.T(\d+)A(\d+)\.en', raw[14])
            years = re.findall(r'The IUCN Red List of Threatened Species (\d{4}):', raw[14])
            doi_years = re.findall(r'IUCN\.UK\.(\d{4})-', raw[14])
            checks = {
                'source_binomial_in_citation': bool(re.search(r'(?<![A-Za-z-])'+re.escape(name)+r'(?![A-Za-z-])', raw[14])),
                'raw_scientific_name_matches_fields': ' '.join(raw[1].split()) == ' '.join((name+' '+raw[9]).split()),
                'unique_source_sis': source_ids[sid] == 1,
                'unique_accepted_bird_name': source_names[name] == 1,
                'accepted_species_self_reference': raw[13] == sid,
                'one_global_distribution': len(dist) == 1,
                'recognized_category': len(dist) == 1 and dist[0][0][5] in CATEGORIES,
                'global_citation_equals_taxon_citation': len(dist) == 1 and dist[0][0][3] == raw[14],
                'url_sis_and_doi_assessment_identity': bool(url and url[1] == sid and dois == [(sid, url[2])]),
                'citation_and_doi_year_agree': len(years) == len(doi_years) == 1 and years == doi_years,
            }
            mention = mention_evidence(note, a[12], name, a[5])
            scope_statement = bool(SCOPE_PATTERN.search(note))
            higher_match = bool(a[2] and a[3] and a[2].casefold() == raw[5].casefold() and a[3].casefold() == raw[6].casefold())
            genus_diff = name.split()[0] != a[5].split()[0]
            epithet_same = name.split()[1] == a[5].split()[1]
            nominal_genus = 'same_epithet_author_year_different_genus_candidate' in old['match_routes']
            # Deliberately restrictive: 'genus' by itself is not a rename.
            rename_only = bool(genus_diff and epithet_same and nominal_genus and higher_match
                               and RENAME_PATTERN.search(note) and not scope_statement
                               and re.search(r'\b'+re.escape(name.split()[0])+r'\b', note)
                               and re.search(r'\b'+re.escape(a[5].split()[0])+r'\b', note))
            if rename_only:
                relationship = 'genus_rename_only_explicit_decision_candidate'
            elif mention and scope_statement:
                relationship = 'explicit_name_in_split_or_merge_decision'
            elif name == a[5]:
                relationship = 'same_name_only_concept_not_established'
            elif nominal_genus:
                relationship = 'nominal_genus_change_not_explicitly_proven'
            elif 'official_decision_nominal_name_chain_candidate' in old['match_routes']:
                relationship = 'nominal_chain_from_decision_name_not_equivalence'
            elif mention:
                relationship = 'decision_name_mentioned_without_split_merge_or_rename_proof'
            else:
                relationship = 'no_explicit_name_relationship'
            verified = all(checks.values())
            candidates.append({
                'source_scientific_name': name, 'source_authorship': raw[9], 'sis_id': sid,
                'source_assessment_id': url[2] if url else None,
                'source_assessment_url': raw[15], 'source_citation': raw[14],
                'source_assessment_year': int(years[0]) if len(years) == len(doi_years) == 1 and years == doi_years else None,
                'source_global_categories': [CATEGORIES.get(r[5]) for r, _ in dist],
                'source_global_categories_raw': [r[5] for r, _ in dist],
                'source_locations': {'taxon': f'taxon.txt:{line_no}', 'global_distributions': [f'distribution.txt:{ln}' for _, ln in dist]},
                'archive_integrity_checks': checks, 'source_grade_verified_in_pinned_archive': verified,
                'failed_checks': [k for k, v in checks.items() if not v],
                'source_order': raw[5], 'source_family': raw[6], 'target_order': a[2], 'target_family': a[3],
                'higher_taxonomy_matches': higher_match,
                'relationship': relationship, 'official_decision_name_occurrence': mention,
                'legacy_candidate_routes': old['match_routes'],
                'source_authorship_equals_target': raw[9] == a[6],
                'same_epithet_author_route_only': nominal_genus,
                'target_grade_assignment_allowed': False,
                'current_species_concept_equivalence_verified': False,
                'assessment_original_page_opened': False,
            })
        usable = [c for c in candidates if c['source_grade_verified_in_pinned_archive']]
        if any(c['relationship'] == 'genus_rename_only_explicit_decision_candidate' for c in usable):
            classification = 'genus_rename_only'
        elif any(c['relationship'] == 'explicit_name_in_split_or_merge_decision' for c in usable):
            classification = 'explicit_merged_or_split_source_name'
        else:
            classification = 'no_reliable_explicit_taxonomic_relationship'
        category_set = sorted({v for c in usable for v in c['source_global_categories'] if v})
        output.append({
            'taxon_id': target['taxon_id'], 'scientific_name': a[5], 'authority': a[6],
            'current_reference_category': target['reference_category'],
            'current_reference_source': target['selected_reference_source'],
            'is_original_305_missing_reference': target['reference_category'] is None,
            'taxonomy_decision_id': a[11], 'taxonomy_decision_text': a[12],
            'taxonomy_decision_plain': note, 'taxonomy_source_url': target['taxonomy_source_url'],
            'classification': classification,
            'legacy_genus_keyword_flag': 'genus_change' in target['taxonomy_relations'],
            'genus_keyword_does_not_prove_rename': 'genus_change' in target['taxonomy_relations'] and not any(c['relationship'] == 'genus_rename_only_explicit_decision_candidate' for c in candidates),
            'source_grade_candidate_count': len(usable), 'source_candidate_categories': category_set,
            'has_conflicting_source_candidate_categories': len(category_set) > 1,
            'has_source_grade_candidate': bool(usable),
            'safe_to_assign_current_species_grade': False,
            'current_species_concept_equivalence_verified': False,
            'index_reference_entry': index['references'].get(target['taxon_id']),
            'index_primary_entry': index['taxa'].get(target['taxon_id']),
            'unreleased_recommendation_excluded': target.get('unreleased_recommendation'),
            'candidates': candidates,
        })
    missing = [r for r in output if r['is_original_305_missing_reference']]
    def counts(rows):
        return {'species': len(rows), 'classification': {key: sum(r['classification'] == key for r in rows) for key in ('genus_rename_only', 'explicit_merged_or_split_source_name', 'no_reliable_explicit_taxonomic_relationship')},
                'with_any_raw_global_category_candidate': sum(any(c['source_global_categories'] for c in r['candidates']) for r in rows),
                'with_verified_source_grade_candidate': sum(r['has_source_grade_candidate'] for r in rows),
                'without_verified_source_grade_candidate': sum(not r['has_source_grade_candidate'] for r in rows),
                'multiple_candidate_categories': sum(r['has_conflicting_source_candidate_categories'] for r in rows),
                'same_concept_grade_assignments': 0,
                'candidate_relationships': dict(sorted(Counter(c['relationship'] for r in rows for c in r['candidates']).items())),
                'candidates_failing_source_integrity': sum(not c['source_grade_verified_in_pinned_archive'] for r in rows for c in r['candidates'])}
    return {
        'schema_version': 1,
        'scope': '447 original unresolved species; focus on 305 without any reference category',
        'operation': 'read_only_offline_audit_no_database_or_application_data_changes',
        'method': {'three_way_classification_is_relationship_evidence_not_grade_approval': True,
                   'same_scientific_name_is_not_concept_equivalence': True,
                   'same_epithet_and_author_is_not_genus_rename_proof': True,
                   'genus_keyword_is_not_genus_rename_proof': True,
                   'split_merge_name_occurrence_is_not_directional_parent_child_or_synonymy_proof': True,
                   'candidate_discovery_scope': 'existing complete 447-species ledger; each candidate independently re-read from pinned taxon.txt and distribution.txt',
                   'no_reliable_explicit_taxonomic_relationship_means': 'no archive-valid candidate with an explicit accepted rename or a source-name occurrence in a split/merge decision; a source grade can still exist',
                   'assessment_original_pages_reviewed': 0, 'hkbws_audit_performed': False},
        'input_sha256': {'ledger': sha(ledger_path), 'avilist': sha(avilist_path), 'gbif_archive': sha(archive_path), 'conservation_index': sha(index_path)},
        'sources': {'gbif': ledger['source'], 'avilist_url': 'https://explore.avilist.org/data/avilist-2025b.json',
                    'archive_download_url': 'https://hosted-datasets.gbif.org/datasets/iucn/iucn-latest.zip'},
        'counts_all_447': counts(output), 'counts_missing_305': counts(missing),
        'legacy_genus_flags_without_explicit_rename_proof': sum(r['genus_keyword_does_not_prove_rename'] for r in output),
        'missing_305_with_verified_source_grade_candidates': [r['taxon_id'] for r in missing if r['has_source_grade_candidate']],
        'species': output,
    }

def self_checks():
    """Four edge cases that prevent false taxonomic-name relationships."""
    assert mention_evidence('Alectoris chukar is separate from Alectoris graeca.', '<em>Alectoris chukar</em> is separate from <em>Alectoris graeca</em>.', 'Alectoris graeca', 'Alectoris chukar')['kind'] == 'exact_binomial'
    assert mention_evidence('Columba livia and Coturnix coturnix, C. major', '<em>Columba livia</em> and <em>Coturnix coturnix</em>, <em>C. major</em>', 'Columba major', 'Columba livia') is None
    assert mention_evidence('There are major differences.', 'There are major differences.', 'Parus major', 'Parus cinereus') is None
    assert mention_evidence('Taxon major is treated as conspecific.', 'Taxon <em>major</em> is treated as conspecific.', 'Parus major', 'Parus cinereus')['kind'] == 'same_genus_epithet_mentioned'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger', type=Path, default=ROOT/'docs/verification/assets/2026-10-09-unresolved-conservation-review.json')
    parser.add_argument('--avilist', type=Path, default=Path('/tmp/robingraph-global-avilist-2025b.json'))
    parser.add_argument('--archive', type=Path, default=Path('/tmp/robingraph-alternative-sources/iucn-2026-1.zip'))
    parser.add_argument('--index', type=Path, default=ROOT/'src/robingraph/retrieval/conservation_index.json')
    parser.add_argument('--output', type=Path, default=ROOT/'docs/verification/assets/2026-10-09-conservation-name-relationship-audit.json')
    args = parser.parse_args()
    self_checks()
    result = audit(args.ledger, args.avilist, args.archive, args.index)
    assert all(not r['safe_to_assign_current_species_grade'] for r in result['species'])
    assert all(not c['target_grade_assignment_allowed'] for r in result['species'] for c in r['candidates'])
    result['validation'] = {'focused_name_occurrence_cases_passed': 4, 'all_447_unique_targets_checked_against_official_snapshot': True, 'missing_reference_305_count_checked': True, 'ledger_candidates_rechecked_in_raw_archive': sum(len(r['candidates']) for r in result['species']), 'grade_assignments': 0}
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('counts_all_447','counts_missing_305','legacy_genus_flags_without_explicit_rename_proof')},ensure_ascii=False,indent=2))

if __name__ == '__main__':
    main()
