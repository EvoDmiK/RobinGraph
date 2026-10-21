# RG-406 검토 국외 6종의 영어·학명 이름 검색 — 2026-10-19

## 요청 배경과 완료 범위

사용자가 RG-406의 남은 작업 설명을 확인한 뒤, 이미 국외 분포를 검토한 6종의 영어 이름·학명을
검색 자료에 포함하고 오타 후보 검색을 TEST에서 진행하도록 지시했다. RG-101은 기존 보류를 유지한다.
기존 6종의 분포를 다시 판정하거나 다른 종을 국외로 분류하는 작업은 아니다. 운영 반영 승인은 받지 않았다.

정확한 영어 이름/학명 조회는 변경 전에도 그래프 경로에서 모두 동작했다. 실제 부족했던 것은
6종 중 1종만 들어 있던 이름 벡터 후보 카탈로그와 Latin 오타의 확인 후보다. 따라서 정확 조회를
새로 구현했다고 주장하지 않으며, 기존 정확 조회를 유지하고 확인 후보 검색을 보완했다.

## 확인한 자료와 식별 범위

대상은 기존 species_distribution.json의 active v2025b/KR outside 6종이다.
영어 이름은 같은 활성 TaxonConceptSet·Taxon·VernacularName의 policy_status=allowed,
source-preferred 영어 이름·동일 dataset/source_release를 실제 TEST Neo4j에서 확인했다.
학명은 pinned 종 ID와 완전 일치해야 한다. 새 국명·영문명·옛 학명 alias를 생성하지 않는다.

| 활성 학명 | 확인한 영어 이름 |
|---|---|
| Apteryx maxima | Great Spotted Kiwi |
| Apteryx rowi | Okarito Kiwi |
| Apteryx mantelli | North Island Brown Kiwi |
| Nestor notabilis | Kea |
| Xenicus gilviventris | New Zealand Rockwren |
| Callaeas wilsoni | North Island Kokako |

## 변경 전후와 구현

- 기존: 검토 한국어 이름 850종의 텍스트만 임베딩했다. 정확 영어·학명은 그래프에서 찾지만,
  국외 종 오타 후보 집합에는 Kea 한 종만 있었다. 준비한 영어/학명 오타 12건은 모두 해당 종을 찾지 못했다.
- 변경: 기존 한국어 이름 집합과 위 6종을 ID 기준으로 합친다. 신규 5종은 검증 영어 이름+학명,
  기존 Kea는 기존 한국어 이름+영어 이름+학명을 텍스트에 보존한다. 850→855종이며 최대 1,000 상한은 유지한다.
- 자료 추가만 한 첫 검증에서는 오타 12건 중 6건만 통과했다. 나머지는 실제 cosine이 0.25 미만이었다.
  일반 하한을 낮추지 않고, 위 검토 국외 집합의 영어 원자료 이름/학명과 Latin 입력이 한 글자만 다른
  경우를 별도 확인 후보로 보완했다. 삽입·삭제·치환·인접 전치이며 입력 최소 4글자/원자료 최소 3글자,
  ASCII Latin 알파벳·공백·하이픈으로 제한한다. 이 분기는 일반/기존 한글 철자 보완 후보가 없을 때만 적용한다.
- 원자료 종을 활성 그래프에서 재검증해야 하며, 벡터/임베딩이 불능일 때 철자만으로 우회하지 않는다.
  실제 cosine은 그대로다. 예: Keaa→Kea는 약0.1449다. 확률/정답 신뢰도로 올려 적지 않는다.
  후보는 자동 매칭이 아니라 사용자 확인 대상이다. 질문/alias/조류 노드를 새로 쓰지 않는다.
- 국외 범위는 위 집합 안에서 확인한다. 전체 범위도 일반 후보가 없을 때 같은 제한 집합을 추가 확인한다.
  같은 query vector를 전달해 추가 embed_query를 만들지 않으며, 전체는 기존 검토 한국어 표시를 유지한다.
  Kea는 전체에서 높은산앵무, 국외에서 Kea다. 국내/미확인 범위에 이 국외 보완을 섞지 않는다.

## 변경 파일

- src/robingraph/retrieval/taxonomy_lineage_neo4j.py: reviewed_name_candidates에 실제 허용 영어 원자료
  이름과 pinned 국외 ID·학명 대조 조회를 추가하고, 기존 한국어 이름과 합친다. 전체 카탈로그 상한 유지.
- src/robingraph/retrieval/taxon_name_resolution.py: 한정 Latin one-edit 확인, 그래프 검증 재사용,
  전체 범위의 질의 벡터 재사용과 기존 이름 표시 유지. 기존 일반 cosine/한국어 철자 조건은 유지한다.
- tests/test_taxonomy_lineage_neo4j.py, tests/test_taxon_name_catalog.py, tests/test_taxon_name_resolution.py:
  source/release/정책 guard, 중복 종 병합, 미확인 자료 미생성, 문맥 불일치 거부,
  one-edit 경계·실제 점수 유지·그래프 의존·질의 임베딩 1회 확인.
- docs/decisions/0008-graph-first-name-resolution.md: 현재 855종과 한정 철자 보완 계약을 기록했다.
- 본 작업 기록과 docs/verification/assets/2026-10-19-rg406-outside/: 실제 결과와 실행 코드.

## TEST 데이터 갱신·보존

ROBINGRAPH_DEPLOY_TARGET=test, Neo4j URI bolt://192.168.219.98:7687를 확인한 뒤 수행했다.
현재 이름 벡터 엔트리·catalog·인덱스 정의를 M4 관리 폴더에 private 백업했다.
/Users/kimdove/robingraph-test/backups/2026-10-19-outside-before.json (0600, 부모0700)이며
벡터가 포함되어 저장소/Obsidian에는 복사하지 않았다. 새 6개 벡터의 준비 파일도 같은 private 폴더에 보관했다.
환경 파일이나 인증정보는 산출물에 포함하지 않았다.

실제 dry-run: inventory855, reused849, to_embed6, 기존 schema/constraint compatible.
준비 단계에서 6개 텍스트를 실제 설정 embedding service로 임베딩했다. 기존 index_names의
명시적 쓰기 경로에 준비된 벡터를 전달했다. 한 트랜잭션에서 855개 catalog metadata를 갱신한다.
849개를 새로 임베딩하지 않았지만 metadata fingerprint는 새 카탈로그로 갱신된다는 점을 구별한다.

실제 apply: inventory855/reused849/embedded6/stale0/catalog_current true.
후속 dry-run은 reused855/to_embed0/embedded0/catalog_current true였다.
이름 벡터 인덱스 정의·차원·제약 조건은 바뀌지 않았고 삭제/재생성하지 않았다. 문헌 청크 인덱스는 대상이 아니다.

보존 대조: 기존849개 text_hash 유지, 그중845개 벡터는 바이트 값까지 같고 나머지4개는 기존
단위 벡터 정규화 경로 재사용에 따른 최대2.7755575615628914e-17 차이였다. 이를 849개 완전 바이트
동일이라고 표현하지 않는다. 의미 있는 텍스트 변경은 Kea 1종, 새 ID는5개다(preservation.json).
첫 보존 검사에서 정확 값 변경이 Kea 1개뿐이라고 예상해 assertion이 실패했고, 실측 roundoff와
텍스트/의미 변경을 구별하도록 검사와 기록을 정정했다. 의미/점수 영향 전체를 수학적으로 증명한 것은 아니다.

## 실제 검증과 실패 보정

- 수정 전 실제 TEST resolver: 정확 영어6+학명6=12건 모두 matched, 오타12건은 해당 종 후보0건.
- 자료 갱신만 한 1차: 정확12 유지, 오타6/12 후보 성공. 이 결과를 완료로 처리하지 않았다.
- 한정 철자 보완 후 국외24건 모두 성공. 이후 전체 범위 보완까지 포함한 최종 검사:
  6종 × (정확 영어/정확 학명/영어 오타/학명 오타) × 전체/국외 = **48건 모두 해당 ID 확인**.
  정확 조회는 matched, 오타는 candidates이며 자동 matched로 바꾸지 않았다.
- 공개 TEST 실제 Chromium1280/390/320 각 12POST = **36요청** 모두 통과.
  각6종의 영어 오타를 전체/국외에서 요청해 예상 후보 이름·clarify·범위·화면 표시·넘침 없음·pageerror0 확인.
  전체 Kea 후보는 높은산앵무, 국외는 Kea 표시를 확인했다.
- 기존 높은산앵무아/청둥오리아/타조아/천둥오리 후보 및 국외에서 국내 종 후보를 내지 않는 5건도 통과했다.
- Python 전체 최종944개 실행: **906통과·38skip·실패0**. 38개 외부/DB 통합 skip을 실제 검증 성공으로 바꾸지 않는다.
  fake/model/정책 guard 단위 검사와 위 실제 TEST DB/embedding/HTTP/브라우저 검증을 구별한다.
- Node UI317개 통과·실패/skip0. 이번 UI JS/CSS 변경은 없고 이전 정렬이 그대로 유지된다.
- 초기 전체 검사에서 기존 catalog 테스트가 단일 DB 조회를 전제하여1개 실패했다. 기존 한국어 조회 guard는
  첫 call로 계속 검증하고, 새 영어 query guard는 별도 테스트로 확인하도록 바꾼 뒤 최종 통과했다.
- 첫 브라우저 runner는 임시 Playwright 설치가 없어 시작하지 못했다. /tmp QA 환경에 다시 설치한 후 실제 검사 통과했다.
  앱 dependency는 변경하지 않았다. 중간 raw-score 진단1회는 TEST 앱 재시작으로137 종료돼 최종 검증과 구별했다.
- TEST healthy 및 manage.sh verify의 실제 health/OpenAPI/청둥오리 lineage 계약 검사 통과.
  최종 실행 resolver·vector repository·inventory provider·기존 CSS sha256가 로컬 소스와 일치한다.
- graphify update . AST 갱신 실행. SQL parser/커뮤니티 label 안내는 앱 실패가 아니다.

## TEST 배포·커밋·운영 경계

최종 TEST 이미지: robingraph-api:test-rg406-outside-spelling-1c7cbbdaf1c7
기반 Git revision: bc643ee9edef0fc58c605adde70b4808b7622ac5
최종 runtime patch SHA-256: 1c7cbbdaf1c7c1eda5139aa5adc55df69fbf095c9bc22277153b65479cfdd8d0

이전 TEST 이미지 위에 필요한 Python 파일을 교체한 미커밋 패치 이미지다. 기반 revision만으로 새
소스가 커밋됐다고 표현하지 않는다. inventory 확장 이미지와 후속 resolver 이미지 receipt를 각각 보존했다.
동일 private compose/env를 유지하고 current를 atomic 갱신한 뒤 health/API를 확인했다. TEST 이름
catalog와 앱 fingerprint가 맞아야 하므로 갱신 중 잠시 vector 검색이 unavailable일 수 있다.
실제 rollback은 실행하지 않았고, 실패 시 이전 앱/백업 catalog로 복구하는 준비 경로만 마련했다.

Production 컨테이너·DB·이름 catalog는 변경하지 않았다. Jenkins 운영 job 실행·commit/push/merge도 없다.
운영 승인을 받더라도 앱 이미지 교체만 하면 catalog fingerprint가 불일치할 수 있으므로,
운영 catalog의 별도 백업·검토된6종 갱신·같은 소스 앱 반영·실제 이름 검색 검증을 함께 수행해야 한다.
현재 Jenkins 앱 배포 job만으로 이 데이터 전환까지 완료된다고 가정하지 않는다.

## 재현 자료와 남은 한계

산출물: plan.json, before.json, after.json(자료만 보완한1차), after-outside.json,
after-final.json(최종48건), browser.json(최종36건), korean-regression.json,
index-apply.json, reuse-check.json, preservation.json, deployed-source-hashes.json,
python-tests-final.txt, frontend-tests.txt, test-release.json 및 중간 receipt·스크린샷.
실행 코드는 같은 폴더의 six-probe.py/six-final-probe.py/index-plan.py/prepare-vectors.py/
index-cached.py/apply-test.py/deploy-inventory-test.py/deploy-resolver-test.py를 참조한다.
백업/준비 벡터는 private 관리 폴더에만 있고 code runner는 해당 payload를 stdin으로 주입한다.
재실행 시 현재 TEST 대상과 새 백업·current/catalog 상태를 다시 확인해야 한다.

전체 분포 자료 11,131종 중 국내592·국외검토6·미확인10,533은 변하지 않았다. 현재855종 이름 벡터에서
국내591·국외6·미확인258이다. **검토 국외6종의 이름 검색 TEST 보완은 완료**했지만 RG-406 전체 자료
확대/운영 완료가 아니다. 고정 오타 사례 결과를 모든 오타·종·분류판으로 일반화하지 않는다.
3글자 Latin 오타는 전용 one-edit 보완 대상이 아니고, 두 글자 이상 오타·다국어 이름·별칭·미검토 해외 종은
별도 자료/평가가 필요하다. 큰 카탈로그 부하·물리 모바일·Safari/Firefox·운영 실검증은 미실행이다.
