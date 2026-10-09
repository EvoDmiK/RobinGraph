# 까마귀를 통칭 대신 정식 종 설명으로 조회

## 요청·배경

2026-10-09 사용자가 `까마귀는 이제 통칭이 나오게 하면 안되지`라고 지적했다. 직전 작업에서 까마귀 → 큰부리까마귀 연결만 제거하고 까마귀 → Corvus corone 관계를 남겨둔 탓에 채팅은 여전히 통칭 관계 결과를 반환했다. 이번 목표는 까마귀를 검색하면 일반 종 설명·도감 카드가 바로 나오는 것이다.

## 원인

- name_relations.json의 `crow-corone` 항목이 `까마귀`를 reviewed_search_terms에 포함시켰다.
- 활성 DB에도 같은 common_usage 관계가 있어 채팅의 통칭 우선 경로가 일반 프로필 경로보다 먼저 실행됐다.
- 표시명 자료 species_ko_names.json에는 한국조류학회 2025 목록에 근거한 `까마귀 = Corvus corone`, AviList ID `avilist-taxon:v2025b:20280`이 이미 있었다. 그러나 표시명 자료는 일반 이름 검색 키로 자동 사용되지 않는다. 이전 직접 프로필 요청 `name=까마귀`는 404였다.
- 따라서 관계만 삭제하면 정상 종 설명을 보장할 수 없어서 종 이름 조회도 함께 수정했다.

## 변경 파일·동작

| 파일 | 변경 |
|---|---|
| src/robingraph/retrieval/name_relations.json | crow-corone 삭제. 까마귀 통칭 엔티티·검색어 모두 제거 |
| src/robingraph/retrieval/taxonomy_lineage_neo4j.py | 명시적으로 검토된 종 이름 조회에 까마귀 → Corvus corone 추가 |
| tests/test_taxonomy_lineage_neo4j.py | 까마귀의 직접 조회, 통칭 검색어 제외, 큰부리까마귀·잘못된 ID·다른 분류판 거부 검증 |
| docs/name-relations-coverage.md | 현재 목록·제거 이유 현행화 |

직접 조회는 v2025b와 `rg:concept-set:avilist-v2025b`에서만 적용한다. 조회된 학명·종 rank·taxon ID·분류판·개념집합이 모두 일치해야 한다. 다른 종이나 다른 버전을 임의로 선택하지 않는다. 기존 까치의 명시 조회 경로도 유지한다.

현재 통칭 목록: 엔티티 32개, 검색어 69개, 관계 45개, 대상 종 35개. 두 차례 수정 전의 47개 관계에서 crow-large-billed와 crow-corone을 각각 제거한 결과다. 다른 통칭·가축형 관계는 유지한다.

변경 전 채팅은 result.kind=name_relations와 통칭 안내를 반환했다. 변경 후 `까마귀에 대해 알려줘`는 result.kind=profile, disposition=answer, Corvus corone 종 설명을 반환한다. 큰부리까마귀 검색은 Corvus macrorhynchos를 유지한다.

## 테스트

- taxonomy_lineage_neo4j 단위 테스트: 27개 통과, 실패·건너뜀 0.
- name_relations 단위 테스트: 17개 통과, 실패·건너뜀 0.
- semantic_chat 단위 테스트: 22개 통과, 실패·건너뜀 0.
- 합계 66개 통과. 모의 저장소를 포함한 단위 검사이며 아래 실제 API 검증과 구분한다.
- git diff --check 통과, graphify update 실행.
- 프런트엔드 소스 변경이 없어 Node 전체 테스트를 반복하지 않았다. 전체 Python·전체 종 감사를 다시 실행했다고 주장하지 않는다.

## 코드·자료 배포

구현 커밋: `a87eb9b9998d093e6b8d21ecc8a529fc5cced3b2`.
패키지 SHA-256: `773c7aec5411b0989efe072cb62a73649d2417caabf59ed652ab6c448e9fc073`.
NAS 작업 디렉터리: `/home/kimdove/RobinGraph-crow-direct-a87eb9b`.

각 환경의 기존 .env.nas.test·.env.nas.prod를 별도로 내부 복사하고 권한 600을 유지했다. 이미지 태그만 분리 변경했으며 TEST 설정을 Production에 덮어쓰지 않았다.

TEST 이미지 `robingraph-api:test-crow-direct-a87eb9b`를 먼저 빌드·배포하고 healthy를 확인했다. 컨테이너 안에서 `scripts/load_name_relations.py` dry-run과 --apply로 새 manifest를 PostgreSQL·Neo4j 활성 관계 릴리스에 적용했다. 원장을 물리 삭제하는 대신 새 버전을 활성화했다.

새 manifest SHA-256: `667ac24dfbd63af64765e085bef648836c4dbb354b7f957de1e798d150e212fd`. dry-run·apply 모두 45개 관계·35개 대상을 확인했다.

TEST 실제 API 검증 후 같은 이미지에 Production 태그를 붙여 승격했다. 배포 도구의 rollback 하위 명령은 기존 로컬 이미지로 compose 교체·health 대기를 수행하므로, 이번에는 `prod-crow-direct-a87eb9b`를 지정해 검증된 새 이미지를 배포하는 데 사용했다. 과거 버전으로 되돌리는 작업이 아니다. Production에서도 같은 manifest를 자체 DB에 dry-run·apply했다. 두 환경 DB 전체를 다시 복사하지 않는다.

## 한계·복구

명시 조회는 현재 검토된 v2025b에 한정된다. 분류판이 바뀌면 종 ID·이름을 다시 검토해야 한다. 모든 한국어 표시명을 검색 키로 자동 승격하는 변경은 아니다.

앱 이미지와 통칭 활성 자료를 함께 관리해야 한다. 이전 앱 이미지만 되돌리거나 이전 manifest만 활성화하면 통칭 우선 경로가 다시 나타날 수 있다. 이전 릴리스 원장·이미지는 보존했고 실제 롤백은 실행하지 않았다. 인증 정보는 기록하지 않았다.

## 배포 후 실제 결과

TEST와 Production에서 각각 아래 4개 요청을 수행했다. 모의 응답이 아닌 공개 API 결과다.

1. `/v1/taxa/profile?name=까마귀`: Corvus corone 프로필 정상 반환.
2. `/v1/taxa/name-relations?name=까마귀`: is_search_term=false, relations 빈 배열.
3. `/v1/taxa/profile?name=큰부리까마귀`: Corvus macrorhynchos 유지.
4. `/v1/chat`에 `까마귀에 대해 알려줘`: result.kind=profile, disposition=answer, Corvus corone 반환. name_relations 결과가 아님.

두 컨테이너의 이미지 태그는 각각 test-crow-direct-a87eb9b, prod-crow-direct-a87eb9b이며, healthy와 OCI revision a87eb9b9998d093e6b8d21ecc8a529fc5cced3b2를 직접 확인했다. 이번에는 브라우저 렌더링을 별도로 검증하지 않았으며 실제 채팅 응답 계약으로 일반 프로필 경로 전환을 확인했다.

[환경별 실제 API 증거](../verification/assets/2026-10-09-crow-direct-species-profile.json)
