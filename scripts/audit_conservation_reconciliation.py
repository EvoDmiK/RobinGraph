#!/usr/bin/env python3
"""Offline ALL-species ledger; source matches never prove biological equivalence.

Uses pinned bytes and the production builder's schema/license checks. No network,
DB, runtime bundle writes, name-only upgrades or NE replacement.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from robingraph.retrieval import conservation

_spec = importlib.util.spec_from_file_location('reconciliation_builder', ROOT / 'scripts/build_conservation_index.py')
builder = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(builder)
LINK = re.compile(r'https://datazone\.birdlife\.org/species/factsheet/([1-9][0-9]*)')


def reference_record(row, distributions, taxonomy, routes, source_id_count, source_name_count):
    """Expose raw evidence and failures separately from mapping eligibility."""
    globals_ = [d for d in distributions if d[1] == '' and d[2] == 'Global']
    name = ' '.join((row[7], row[8]))
    assessment = builder._assessment_identity(row, row[0])
    authority_method = conservation._authority_match(taxonomy[6], row[9])
    flags = []
    if source_id_count != 1:
        flags.append('duplicate_source_sis_id')
    if source_name_count != 1:
        flags.append('multiple_accepted_source_rows_for_name')
    if row[13] != row[0]:
        flags.append('accepted_name_usage_id_mismatch')
    if len(globals_) != 1:
        flags.append('missing_or_ambiguous_global_assessment')
    if not assessment:
        flags.append('assessment_identity_or_citation_mismatch')
    if len(globals_) == 1:
        if globals_[0][3] != row[14]:
            flags.append('distribution_citation_mismatch')
        if globals_[0][5] not in builder.CATEGORIES:
            flags.append('unsupported_source_category')
    return dict(sis_id=row[0], accepted_name_usage_id=row[13], scientific_name=name,
                scientific_name_raw=row[1], authorship=row[9], taxonomic_status=row[12],
                name_exact=name == taxonomy[5], authorship_exact=row[9] == taxonomy[6],
                authorship_match_method=authority_method, match_routes=sorted(routes),
                assessment_id=assessment, assessment_url=row[15], citation=row[14],
                assessment_year=builder._assessment_year(row[14]),
                global_distribution_count=len(globals_),
                global_categories_raw=[d[5] for d in globals_],
                global_categories=[builder.CATEGORIES.get(d[5]) for d in globals_],
                global_distribution_citations=[d[3] for d in globals_],
                evidence_integrity_failures=flags, evidence_integrity_valid=not flags,
                concept_alignment='unverified', independently_verified=False)


def exclusion(row, ids, names, links, by_sis, source_ids, source_names, globals_):
    """Mirror current fail-closed precedence; checked against builder coverage."""
    seq, name, auth, grade, ref = (row[i] for i in (0, 5, 6, 15, 16))
    grade = grade.strip().upper() if isinstance(grade, str) else ''
    match = LINK.fullmatch(ref or '')
    if ids[seq] != 1 or names[name] != 1: return 'ambiguous_avilist_identity'
    if grade == 'NE': return 'avilist_ne_requires_concept_review'
    if grade not in set(builder.CATEGORIES.values()) | {'CR (PE)', 'CR (PEW)'}: return 'unconfirmed_taxonomy_category'
    if not ref: return 'missing_birdlife_exact_link'
    if not match or links[ref] != 1: return 'invalid_or_ambiguous_birdlife_exact_link'
    sis = match[1]
    candidates = by_sis.get(sis, [])
    if source_ids[sis] > 1: return 'duplicate_source_sis_id'
    if not candidates: return 'no_accepted_source_bird_species'
    src = candidates[0]
    if src[13] != sis or source_names[' '.join((src[7], src[8]))] != 1: return 'ambiguous_source_identity'
    if ' '.join((src[7], src[8])) != name: return 'scientific_name_mismatch'
    if not conservation._authority_match(auth, src[9]): return 'authority_mismatch'
    if len(globals_[sis]) != 1: return 'missing_or_ambiguous_global_assessment'
    dist = globals_[sis][0]
    if dist[5] not in builder.CATEGORIES: return 'unsupported_source_category'
    if not builder._assessment_identity(src, sis) or dist[3] != src[14]: return 'assessment_identity_or_citation_mismatch'
    return 'mapped_species'


def reconcile(avilist_content, source_content, packaged_index=None):
    if builder.AVILIST_SHA256 != conservation.TAXONOMY_SHA256 or builder.SOURCE_SHA256 != conservation.SOURCE_SHA256:
        raise ValueError('Builder/runtime source pins disagree')
    baseline = builder.build_index(avilist_content, source_content)
    active = [r for r in json.loads(avilist_content) if r[1] == 'species']
    core, distributions, _, _ = builder._source_archive(source_content)
    source = [r for r in core if r[4] == 'AVES' and r[10] == 'species' and r[12] == 'accepted']
    by_sis, by_name, by_dist, globals_ = (defaultdict(list) for _ in range(4))
    for src in source:
        by_sis[src[0]].append(src)
        by_name[' '.join((src[7], src[8]))].append(src)
    for d in distributions:
        by_dist[d[0]].append(d)
        if d[1] == '' and d[2] == 'Global': globals_[d[0]].append(d)
    ids, names, links = (Counter(r[i] for r in active) for i in (0, 5, 16))
    source_ids = Counter(r[0] for r in core)
    source_names = Counter(' '.join((r[7], r[8])) for r in source)
    ledger = []
    for row in active:
        taxon_id = f'avilist-taxon:v2025b:{row[0]}'
        raw = row[15]
        grade = raw.strip().upper() if isinstance(raw, str) else None
        link = LINK.fullmatch(row[16] or '')
        sis = link[1] if link else None
        selected = {}
        for route, candidates in (('exact_scientific_name', by_name[row[5]]), ('avilist_birdlife_sis', by_sis.get(sis, []))):
            for src in candidates:
                # Preserve duplicate rows, even when identical, using source-list position.
                key = id(src)
                selected.setdefault(key, [src, set()])[1].add(route)
        refs = [reference_record(src, by_dist[src[0]], row, routes, source_ids[src[0]],
                                 source_names[' '.join((src[7], src[8]))]) for src, routes in selected.values()]
        reason = exclusion(row, ids, names, links, by_sis, source_ids, source_names, globals_)
        linked = baseline['taxa'].get(taxon_id)
        current = dict(category=linked['category'] if linked else (grade.split(' (')[0] if grade else grade),
                       evidence_kind='red_list_checklist' if linked else 'taxonomy_snapshot',
                       assessment_status='linked_checklist' if linked else ('needs_review' if grade == 'NE' else 'snapshot_only'),
                       independently_verified=False, basis='offline_baseline_HEAD_0689001_not_current_runtime_or_live_API')
        if row[0] == '20193' and row[5] == 'Pica serica' and grade == 'NE':
            current.update(category='LC', evidence_kind='manual_override', assessment_status='manual_override')
        eligible = [r for r in refs if r['name_exact'] and r['authorship_match_method'] and r['evidence_integrity_valid']]
        if grade == 'NE':
            ne_class = ('unique_integrity_valid_name_authorship_reference_concept_unverified' if len(refs) == len(eligible) == 1 else
                        'ambiguous_reference_candidates' if len(refs) > 1 else
                        'same_name_or_sis_reference_with_identity_or_integrity_gap' if refs else 'no_exact_name_or_sis_reference')
        else: ne_class = None
        if not refs: comparison = 'no_reference_candidate'
        elif len(refs) != 1: comparison = 'multiple_reference_candidates'
        elif not refs[0]['evidence_integrity_valid']: comparison = 'reference_integrity_gap'
        elif not refs[0]['name_exact']: comparison = 'reference_name_differs'
        else:
            source_grade = refs[0]['global_categories'][0]
            comparison = ('taxonomy_NE_reference_assessed' if grade == 'NE' else
                          'taxonomy_reference_grade_agree' if (grade or '').split(' (')[0] == source_grade else 'taxonomy_reference_grade_differ')
        ledger.append(dict(taxon_id=taxon_id, sequence=row[0], scientific_name=row[5], authorship=row[6],
                           taxonomy_category_raw=raw, taxonomy_category=grade, birdlife_reference=row[16], birdlife_sis_id=sis,
                           taxonomy_decision_id=row[11] if len(row) > 11 else None,
                           taxonomy_decision_text=row[12] if len(row) > 12 else None,
                           current_status=current, current_mapping_category=reason,
                           reference_comparison_category=comparison, ne_evidence_category=ne_class,
                           reference_candidate_count=len(refs), reference_candidates=refs,
                           ambiguity=dict(avilist_identity=ids[row[0]] != 1 or names[row[5]] != 1,
                                          shared_birdlife_reference=bool(row[16]) and links[row[16]] > 1,
                                          multiple_reference_rows=len(refs) > 1,
                                          biological_concept_alignment_unverified=True),
                           reference_only_eligible=taxon_id in baseline.get('references', {}),
                           safe_independent_same_concept_evidence=False,
                           auto_upgrade_authorized=False))
    mapping = Counter(r['current_mapping_category'] for r in ledger)
    expected = dict(baseline['coverage']['excluded_reasons'], mapped_species=baseline['coverage']['mapped_species'])
    if dict(mapping) != {k: v for k, v in expected.items() if v}: raise ValueError('Ledger categories disagree with production builder')
    ne = [r for r in ledger if r['taxonomy_category'] == 'NE']
    counts = dict(all_species=len(ledger), taxonomy_ne=len(ne), source_accepted_bird_species=len(source),
                  current_mapping_categories=dict(sorted(mapping.items())),
                  reference_comparison_categories=dict(sorted(Counter(r['reference_comparison_category'] for r in ledger).items())),
                  taxonomy_category_counts=dict(sorted(Counter(r['taxonomy_category'] for r in ledger).items())),
                  current_category_counts=dict(sorted(Counter(r['current_status']['category'] for r in ledger).items())),
                  ne_evidence_categories=dict(sorted(Counter(r['ne_evidence_category'] for r in ne).items())),
                  reference_only_category_counts=dict(sorted(Counter(r['category'] for r in baseline.get('references', {}).values()).items())),
                  ne_safe_independent_same_concept_evidence=0)
    representatives = {}
    for field in ('current_mapping_category', 'reference_comparison_category', 'ne_evidence_category'):
        representatives[field] = {category: [r['scientific_name'] for r in ledger if r[field] == category][:5]
                                  for category in sorted({r[field] for r in ledger if r[field] is not None})}
    return dict(schema_version=1, source=dict(baseline['source']),
                taxonomy_snapshot_sha256=hashlib.sha256(avilist_content).hexdigest(),
                denominators=dict(all_species=len(ledger), ne_subset=len(ne), accepted_source_bird_species=len(source)),
                methodology=dict(baseline_revision='0689001',
                                 current_status_semantics='fixed_HEAD_0689001_baseline_not_final_runtime',
                                 candidate_routes=['exact_scientific_name', 'avilist_birdlife_sis'],
                                 fuzzy_or_synonym_matching=False, same_name_is_concept_proof=False,
                                 same_authorship_is_concept_proof=False, individual_assessment_originals_reviewed=0,
                                 source_pins_verified=True, audit_operation_read_only=True,
                                 packaged_index_reproduced=packaged_index == baseline if packaged_index is not None else None),
                reference_coverage=baseline.get('reference_coverage'),
                counts=counts, representatives=representatives, species=ledger)


def markdown_report(result, command):
    c = result['counts']
    lines = ['# 전체 종 보전 자료 reconciliation 감사', '',
             '작성일: 2026-10-09. 대상: RobinGraph dev-3 HEAD 0689001의 고정 원본과 매핑 규칙.', '',
             '## 배경·목표', '',
             '큰부리까마귀 공개 응답의 NE / needs_review / 미평가(taxon20296)를 계기로 전체 AviList 종을 조사했다. 공개 응답 사실은 coordinator가 전달한 확인 결과이며 이 작업에서 DB/API를 재조회하지 않았다. 한 종의 표시 수정이 아니라 전체 종의 현행 연결, 원자료 NE, 실제 공개 참고 평가 및 개념 불확실성을 분리하는 것이 목적이다.', '',
             '## 원본·방법·분모', '',
             f"AviList SHA-256: `{result['taxonomy_snapshot_sha256']}`. IUCN ZIP SHA-256: `{result['source']['snapshot_sha256']}`.",
             f"IUCN 릴리스 {result['source']['release']}, 배포일 {result['source']['published_at']}, CC BY 4.0. conservation.py와 builder의 핀을 비교하고 원본 해시·EML·Darwin Core 스키마 검증을 실행했다.",
             f"전체 분모 {c['all_species']:,}종, NE 하위 분모 {c['taxonomy_ne']:,}종, IUCN accepted AVES species {c['source_accepted_bird_species']:,}행. 모든 AviList species 행을 JSON ledger에 포함했다.",
             '정확한 학명 또는 기존 BirdLife SIS 참조로 후보를 검색한다. 후보의 실제 global distribution 등급, 명명자, SIS/accepted ID, 평가 URL·ID·인용문을 보존한다. 이름/명명자 일치는 개념 동등성 증명이 아니며, 이명·퍼지·속 이동 동등성을 추론하지 않았다. 같은 이름의 복수 행과 공유 참조를 숨기지 않는다. 독립적인 동일 개념 평가 원문 검증은 0건이다.', '',
             '## 현행 매핑 및 참조 비교', '']
    for key, denominator in (('current_mapping_categories', c['all_species']), ('reference_comparison_categories', c['all_species']), ('ne_evidence_categories', c['taxonomy_ne'])):
        lines += [f'### {key} (분모 {denominator:,})', '', '| 범주 | 종 수 | 대표 종 |', '|---|---:|---|']
        field = {'current_mapping_categories':'current_mapping_category', 'reference_comparison_categories':'reference_comparison_category', 'ne_evidence_categories':'ne_evidence_category'}[key]
        for category, count in c[key].items():
            lines.append(f"| {category} | {count:,} | {', '.join(result['representatives'][field][category])} |")
        lines.append('')
    lines += ['## NE의 독립 근거와 큰부리까마귀', '',
              'NE 행도 후보 검색을 수행하므로 기존 NE 차단이 참고 평가 정보를 숨기는 정도를 측정할 수 있다. integrity-valid 참고 평가는 해당 IUCN 출처에 그 평가가 존재한다는 증거로 제시할 수 있으나 AviList 개념에 등급을 부여하는 독립 증거로 승격할 수 없다. 안전한 동일 개념 자동 승격을 입증한 NE는 0종이며, 이는 808종이 실제 미평가라는 의미가 아니다.', '']
    for name in ('Corvus macrorhynchos', 'Pica serica', 'Pica pica'):
        r = next((r for r in result['species'] if r['scientific_name'] == name), None)
        if not r: continue
        lines += [f"### {name} ({r['taxon_id']})", '',
                  f"원자료 {r['taxonomy_category_raw']}, HEAD 0689001 기준 등급 {r['current_status']['category']}, 상태 {r['current_status']['assessment_status']}, BirdLife 참조 {r['birdlife_reference']!r}.",
                  f"AviList 명명자 `{r['authorship']}`. 결정 `{r['taxonomy_decision_id']}`: {r['taxonomy_decision_text']}"]
        for ref in r['reference_candidates']:
            lines += [f"공개 IUCN 후보: {ref['scientific_name']} `{ref['authorship']}`, SIS {ref['sis_id']}, 평가 {ref['assessment_id']}, 연도 {ref['assessment_year']}, 실제 세계 등급 {ref['global_categories_raw']}; 비교 {ref['authorship_match_method']}, 무결성 검증 {ref['evidence_integrity_valid']}. URL: {ref['assessment_url']}."]
        lines.append('')
    lines += ['## 변경 전후·구현', '',
              '신규 scripts/audit_conservation_reconciliation.py는 읽기 전용 전체 ledger와 요약을 생성한다. 신규 tests/test_conservation_reconciliation.py는 NE·다중 후보·인용 불일치·핀 거부·전체 고정 원본 회귀를 검증한다. 조정자의 후속 승인으로 scripts/build_conservation_index.py와 conservation.py 및 conservation_index.json에 별도 references 섹션과 reference_checklist 헬퍼를 추가했다. 기존 taxa 연결 7,507종 및 원래 등급·제외 규칙을 유지하며 참고 평가로 등급을 승격하지 않는다. JSON current_status는 HEAD 0689001의 고정 원본+연결 정책 기준 상태이며 최종 수정된 런타임 또는 전 종 live API 결과라고 해석하면 안 된다. 최종 API 계약에서는 needs_review NE 종의 primary category가 null이고 category_raw 및 taxonomy 원자료 NE는 보존된다. 별도 reference_assessment의 LC 등급은 해당 참고 평가의 값이다. Pica serica의 기존 수동 LC 표시는 독립 검증된 평가와 구분한다.', '',
              f"패키지 index와 원본 재빌드의 완전 일치: {result['methodology']['packaged_index_reproduced']}.", '',
              '## 검증·실제 결과', '',
              '고정 실제 ZIP 및 JSON 전수 감사 실행 완료. 종별 배타적 매핑 범주 합계가 builder coverage와 일치하도록 실행 중 검증했다. 단위 테스트의 mock 입력과 실제 원본 통합 테스트 결과는 아래 실행 로그에 기록한다. 실제 DB/API 평가 검증, 11,131종 평가 원문 검토는 미실행이다.', '',
              '재현 명령:', '', '```sh', command, '```', '',
              '## 별도 참고 평가 구현·검증 범위', '',
              '배포·커밋·DB 쓰기 없음: 이 worker에는 승인되지 않았다. 참고 평가 구현의 단위 검증은 tests/test_conservation_reference.py에 추가했다. 실제 DB 연결과 UI 통합 검증은 coordinator와 다른 worker의 범위다. 전 종 참고 정보의 분리 표시와 개념 확인 워크플로는 coordinator가 결정한다. 이름 변경 후보, split/lump 관계, 평가 범위의 포함·제외는 추가 분류 근거와 평가 원문 검토가 필요하다. source matching은 biological equivalence proof가 아니다. 후보가 없다는 결과도 실제 평가 부재 증거가 아니며 정확한 이름/SIS 검색 범위의 부재다.', '']
    coverage = result.get('reference_coverage')
    if coverage:
        lines += ['## 참고 전용 index 범위', '', f"기존 미연결 {coverage['unlinked_species']:,}종 중 {coverage['reference_species']:,}종에만 별도 참고 평가를 추가했다. 제외 범주: {json.dumps(coverage['excluded_reasons'], ensure_ascii=False)}.", f"참고 등급 분포(분모 {coverage['reference_species']}): {json.dumps(c['reference_only_category_counts'], ensure_ascii=False)}. NE 참고 평가가 모두 LC인 것은 아니다.", '', 'reference_only_eligible은 참고 표시 가능 여부이며 동일 개념 평가 승인 여부가 아니다. reference_checklist는 고정 원본·릴리스·concept set·활성 종 ID/학명/명명자·원자료 등급·평가 ID/URL/인용 연도를 재검증하고 taxonomy_alignment=unverified 및 independently_verified=false를 반환한다. 다른 속·학명, 복수 accepted 행, 공유 SIS, 다중 Global, 인용 불일치 후보를 자동 표시하지 않는다. AVES/species/accepted 조건과 canonical genus+specific epithet의 완전 일치를 확인한다; family 일치는 분류 체계별 변동이 있어 개념 동등성 증거로 쓰지 않았다.', '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--avilist', type=Path, default=Path('/tmp/robingraph-global-avilist-2025b.json'))
    parser.add_argument('--iucn', type=Path, default=Path('/tmp/robingraph-alternative-sources/iucn-2026-1.zip'))
    parser.add_argument('--output', type=Path, default=Path('/tmp/rg-conservation-reconciliation-sol.json'))
    parser.add_argument('--report', type=Path, default=Path('/tmp/rg-conservation-reconciliation-sol.md'))
    args = parser.parse_args()
    index = json.loads((ROOT / 'src/robingraph/retrieval/conservation_index.json').read_text())
    result = reconcile(args.avilist.read_bytes(), args.iucn.read_bytes(), index)
    result['input_paths'] = dict(avilist=str(args.avilist.resolve()), iucn=str(args.iucn.resolve()))
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    command = f'python3 scripts/audit_conservation_reconciliation.py --avilist {args.avilist} --iucn {args.iucn} --output {args.output} --report {args.report}'
    args.report.write_text(markdown_report(result, command))
    print(json.dumps(result['counts'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
