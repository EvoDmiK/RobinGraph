# RG-101 보류와 RG-406 범위별 후보 재현율·표시 보완 — 2026-10-18

## 사용자 요청과 범위

사용자가 RG-101을 일단 보류하고 RG-406 진행을 지시했다. RG-101은 소규모 문헌 기준선 결과를
보존한 보류 상태다. 새 문헌 축적 후 재개 판단하며 DB 이전이나 추가 수집을 진행하지 않는다.
Writer에게 1xx·전체 Obsidian 백로그 보류 변경을 전달했고, 해당 담당의 완료 보고와 Codex의 실제 MCP 재조회로 RG-101 보류 상태를 확인했다.
Codex는 Obsidian에 중복 쓰지 않았다.

RG-406 후속 중 기존에 미검증으로 남은 범위별 이름 벡터 후보 재현율부터 진행했다.
국내/국외/미확인의 판정 자료를 새로 만들거나 종 범위를 확대하는 작업은 아니다.
사용자 결과 확인과 별도 승인 전까지 운영 반영은 하지 않는다.

## 재현 근거와 원인

기존 TaxonNameResolver는 Neo4j 전역 ANN 상위 10개를 받은 뒤 scope_matches로 범위를 걸렀다.
따라서 범위 안 후보가 전역 11위 이하이면 점수 하한을 넘겨도 확인 후보가 될 수 없었다.
실제 TEST 850개 저장 벡터에 대해 8개 입력 × 국내/국외/미확인 24사례를 감사했으며,
현재 자료에서는 점수 하한 0.25 이상 후보가 전역 상위 10개 밖에 빠진 지리 사례를 찾지 못했다.
이 결과를 실제 종 검색 장애를 재현했다고 확대하지 않는다.

대신 11개 가짜 후보 중 앞 10개는 범위 밖·11번째는 범위 안인 회귀 사례를 만들었다.
변경 전 HEAD resolver에서 not_found가 나와 실패했고 새 코드에서는 candidates로 통과했다.
실제 TEST DB에서도 허용 ID 집합을 통제한 limit=1 사례를 만들어 전역 2위가 기존에는 제외되고
새 검색에서 반환됨을 확인했다. 이는 실제 저장 벡터를 이용한 cutoff 경계 검증이지
그 종의 지리적 분포 근거를 새로 판정한 검증이 아니다.

추가로 실제 API에서 국외 높은산앵무아 입력의 후보가 높은산앵무로 표시돼 영어 우선 정책을
지키지 않는 것을 확인했다. 후보 inventory는 한국어 표시 이름만 보존하는 구조라 기존
with_species_scope 호출에 영어 이름이 전달되지 않았다. 재검증한 그래프 종 노드의
english_name을 사용해 Kea로 표시하도록 수정했다. 새 번역이나 국명을 생성하지 않는다.

## 구현과 변경 파일

- src/robingraph/retrieval/taxon_name_resolution.py: 범위에 맞는 reviewed inventory ID를 저장소에 전달한다.
  전체 inventory는 그대로 전달해 catalog fingerprint 검증이 유지된다. 후보를 받은 뒤에도 범위를
  다시 확인하고 최대 10개 그래프 재검증·최대 3개 제안·기존 cosine 하한과 철자 보완 조건을 유지한다.
  검증된 LineageTaxon을 반환하는 _verified_target으로 영문명을 얻어 국외 후보에 적용한다.
- src/robingraph/retrieval/taxon_name_vectors_neo4j.py: optional eligible_taxon_ids 인자를 추가한다.
  all은 기존 ANN 경로, 선택 범위는 해당 ID 집합의 저장 벡터에 vector.similarity.cosine을 적용하고
  점수 정렬 후 limit을 적용한다. 현재 reviewed inventory 상한 1,000개 안에서만 수행한다.
  index/profile/catalog fingerprint/활성 concept set/graph link/본문 hash 검증은 유지한다.
  미지의 ID를 거부하고 빈 집합은 빈 후보를 반환하며 잘못 반환된 범위 밖 hit도 제거한다.
- tests/test_taxon_name_resolution.py, tests/test_taxon_name_vectors_neo4j.py:
  전역 cutoff 이후 후보 복구, 빈 범위, ID guard, stale catalog, 범위 밖 hit 차단, 검증 영문명 표시를 추가했다.
- docs/work-log/2026-10-18-rg101-chunk-search-baseline.md, ADR-0007: 사용자 보류 지시를 기록했다.
- docs/verification/assets/2026-10-18-rg406-recall/: 실제 결과와 재현 코드를 보관한다.

새 Neo4j 인덱스나 scope 속성을 만들지 않았다. 전체 검색은 기존 ANN 방식이고,
선택 범위는 현재 850개 중 해당 범위를 정확 비교하므로 커진 inventory에서 동일 지연을 보장하지 않는다.
향후 상한을 늘리기 전에 범위 검색의 규모별 성능을 다시 평가해야 한다.

## 점수·재현율 해석

기존 cosine 점수 공식·0.25 일반 하한·0.20 철자 보완 하한은 변경하지 않았다.
다만 선택 범위는 quantized ANN 점수 대신 저장 벡터의 정확 cosine을 사용하므로 숫자가
완전히 같다고 주장하지 않는다. 같은 설정의 실제 API 관측에서 청둥오리아 0.2690→0.2575,
타조아 0.3091→0.2913, 천둥오리 0.2188→0.2138이었다. 지연/서비스 변동을 통제한
동일 query vector 쌍의 수학적 비교는 아니므로 차이를 전부 단일 원인에 귀속하지 않는다.
점수는 이름 확인 후보 순위이며 종 식별 확률이 아니다. 제안을 자동 확정하지 않는다.

선택 범위 24사례의 새 DB 결과를 실제 query vector와 모든 reviewed 저장 벡터의 Python cosine
oracle에 대조했다. 점수 0.25 이상 후보 ID 순서가 모두 일치했다. UI spelling floor 동작은
천둥오리 실제 API로 별도 확인했다. 24개 사례는 전체 종/모든 오타의 완전 재현율 증명이 아니다.

## 실제 검증 결과

- 최종 Python 전체: 939개 실행, 901개 통과·38개 skip, 실패 0.
  skip을 실제 공유 DB/외부 연동 통과로 간주하지 않는다. 기존 guard3개와 RG-406 신규8개가 포함된다.
- Node UI: 317개 통과·실패/skip 0. 이번 UI JS/HTML/CSS 변경은 없다.
- 기존 코드 부정 회귀: 전역 11위 범위 후보의 not_found 실패를 확인했다(before-regression.txt).
  초기 회귀 runner는 PYTHONPATH 누락으로 import 오류가 있었고 경로를 바로잡아 실제 assertion 실패를 확인했다.
  신규 repository 테스트 setup 재사용에서 3개 오류가 있었으나 자체 setUp으로 수정해 최종 전체 검사 통과했다.
- 실제 TEST Neo4j/Jina: 8입력 × 3범위 24 oracle 대조 통과, 제어된 limit=1/global-rank=2 cutoff 전후 검증 통과.
- 배포된 코드에서 반복한 24회 scoped repository 검색의 median 21.182ms / max 58.25ms.
  warmup/동시성 통제 없는 단발 지연이며 성능 보장이나 이전 ANN 대비 향상 주장이 아니다.
- TEST 내부 API 전후 각 5요청: 국외 높은산앵무아→Kea, 국내 청둥오리아/천둥오리→청둥오리,
  미확인 타조아→타조 후보. 청둥오리아를 국외로 요청하면 후보 없음·abstain 유지.
- 공개 TEST Chromium 1280/390/320 각 3요청, 총 9POST: 위 후보 이름·scope 전달·화면 표시·가로 넘침 없음·pageerror 0 통과.
- TEST health와 API 계약/청둥오리 lineage 검증 통과. 배포된 두 Python 파일의 sha256가 로컬 소스와 일치한다.
- graphify update . AST 갱신 실행. SQL parser/커뮤니티 label 안내는 앱 기능 실패가 아니다.

## TEST 배포·형상

이전 TEST CSS 레이아웃 이미지 위에 Python 두 파일만 교체한 ARM64 TEST 전용 이미지다.
이미지: robingraph-api:test-rg406-recall-f8c64d62bbc8
기반 revision: bc643ee9edef0fc58c605adde70b4808b7622ac5
미커밋 runtime patch SHA-256: f8c64d62bbc8a2a5317ac7d23d346dfa881b7157272cdde4e41b41a0dd661681

같은 compose/env를 private 새 릴리스로 복사하고 image만 바꿨다. current atomic 교체·healthy/API 검증 후
receipt verified. 실패 시 이전 release로 되돌리는 경로를 준비했으나 실제 rollback은 발생하지 않았다.
이전 CSS 정렬도 기반 이미지에서 유지한다. Jenkins 운영 job을 실행하지 않았으며 신규 commit/push/merge 없음.
운영 앱·DB·벡터 인덱스·분포 데이터는 이 작업에서 변경하지 않았다.

## 현재 상태와 남은 한계

RG-101은 **보류**. RG-406은 **후속 보완 TEST 완료·분포 자료 확대 및 운영 승인 대기**다.
전체 11,131종 중 국내 592·국외 검토 6·미확인 10,533의 분포 자료는 그대로다.
현재 이름 벡터 850개 안의 범위는 국내 591·국외 1·미확인 258이며, 전체 분포 집합과 같지 않다.
특히 국외 6종 중 1종만 현재 이름 벡터 inventory에 있어 모든 국외 종 오타 검색을 지원한다고 할 수 없다.
이름 없는 종을 추정 국명으로 채우거나 검토되지 않은 종을 국외로 분류하지 않았다.

실제 분포 자료 확대, 계절성/현재 서식 판정, 영문 이름 벡터 inventory 확대, 전 종/모든 오타 평가,
큰 카탈로그 성능, 물리 모바일·Safari·Firefox는 후속이다. 운영 반영은 사용자의 이 결과 확인·별도 승인 이후다.
