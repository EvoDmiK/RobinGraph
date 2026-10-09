# 한국어 종 이름 검색 연결과 까치 뱃지 형식 수정

## 배경과 목표

사용자가 박새 검색 실패를 제보했다. 동시에 앞선 뱃지 통일 후에도 일부 카드에 짧은 `관심대상 (LC)`가 남아 있다고 지적했다. 한국어 이름 검색을 복구하고 까치 별도 표시 경로의 뱃지 형식을 바로잡는 작업이다.

## 원인과 근거

Production `/v1/taxa/profile?name=박새`는 HTTP 404였고 같은 종의 현행 학명 `Parus cinereus`는 HTTP 200이었다. 저장소의 source-reference 국명 목록에는 박새가 `avilist-taxon:v2025b:20751`로 등록되어 있다. 종 데이터 부재가 아니라, 표시용 검토 국명 목록이 검색 경로에 연결되지 않은 문제다.

기존 한국어 조회는 활성 Neo4j VernacularName 자료와 까치·까마귀 두 개의 명시 예외에 의존했다. 별도 검토 목록에 표시 이름이 있어도 검색에서는 사용할 수 없었다. 직전 화면 검사에서 꼬까직박구리 한국어 조회가 실패한 것과 같은 경로다.

짧은 뱃지는 `conservationInfo`의 Pica serica manual_override 분기에서 만들어졌다. 직전 변경은 연결된 공개 평가와 참고 평가 분기를 통일했으나 이 분기는 그대로였다.

## 구현과 동작

- `taxonomy_lineage_neo4j.py`: 기존 두 종의 하드코딩 목록 대신 `sourced_korean_names()`의 source-reference 이름을 정확히 대조한다. 현재 646개 항목과 646개 고유 이름이다. 한국어 문자열의 부분 일치나 임의 번역은 하지 않는다.
- 활성 분류판 v2025b와 개념집합이 맞는 경우에만 적용한다. 학명 조회 후 taxon ID·species rank·학명·분류판·개념집합이 모두 일치해야 반환한다. 같은 이름의 후보가 여러 개면 선택하지 않는다. 검토 목록에 없는 이름은 기존 활성 국명 조회를 유지한다.
- `chat.js`: 까치 뱃지를 `IUCN 적색목록 관심대상 (LC) · 홍콩 조류학회 자료 기준`으로 표시한다. 현 자료에는 검증된 평가 연도가 없어 임의의 연도를 붙이지 않았다. 공개 평가목록 근거가 아닌 경로에 공개 평가목록 기준이라는 문구를 붙이지도 않았다. 기존 원자료·수동 표시 상태와 출처 설명은 보존한다.
- `tests/test_taxonomy_lineage_neo4j.py`: 646개 검토 이름 모두 정확한 종 조회를 수행하는지, 잘못된 종 ID와 아종 rank를 거부하는지 검사. 중복 이름과 다른 분류판도 거부한다.
- `tests/frontend/chat_ui.test.js`: 까치의 전체 뱃지 문구와 IUCN 접두어를 검증하도록 기존 회귀 검사 갱신.

박새에만 한정한 이름 예외를 추가하지 않는다. 기존 까치·까마귀 정식 종 조회와 다른 종의 표시 출처도 유지한다. 이름 자료 자체나 생물학적 분류를 새로 변경하지 않았다.

## 자동 검증

- taxonomy_lineage_neo4j: 29개 통과. 646개 종 반복 검사는 이 중 한 테스트의 subTest들이므로 별도 646개 테스트로 합산하지 않는다.
- korean_display_names: 5개 통과.
- semantic_chat: 22개 통과.
- Python 합계 56개 통과, 실패·건너뜀 0. 저장소 모형을 사용하는 오프라인 검사이며 전체 646개 실제 DB 조회 결과를 뜻하지 않는다.
- Node frontend 전체: 280개 통과, 실패·취소·건너뜀 0.
- git diff --check 통과, graphify update 실행.
- 전체 Python·외부 API 통합 테스트는 이번 범위에서 재실행하지 않았다.

## 배포 정보

구현 커밋 `b4fb662531755e8703e53210fed38b1d02c700b3`.
패키지 SHA-256 `c37f1aa766b07f80a741ef99f5ca625fbbd839fb8e8b66eabc0bd3b7e630dfda`.
NAS 디렉터리 `/home/kimdove/RobinGraph-korean-lookup-b4fb662`.
TEST 대상 이미지 `robingraph-api:test-korean-lookup-b4fb662`.
Production 대상 이미지 `robingraph-api:prod-korean-lookup-b4fb662`.

TEST·Production 환경 설정은 각각 유지하고 이미지 태그를 변경한다. TEST 빌드·검증 후 동일 이미지를 Production으로 승격한다. DB 마이그레이션이나 DB 쓰기는 없다. 이전 reference-colour-8b7f2c4 이미지는 보존한다.

## 한계

현재 검토된 646개 국명과 v2025b에 한정한다. 새 분류판은 ID와 이름 대조를 다시 검토해야 한다. 중복 국명은 모호한 대상을 임의 선택하지 않으며, 전체 종에 국명을 새로 생성하지 않는다. 까치 뱃지에 없는 평가 연도는 확인 가능한 원문 근거 확보가 필요하다. 이번 UI 변경은 보전 등급의 독립 검증 완료를 뜻하지 않는다.

## 배포 후 실제 검증

TEST에서 로컬 Chrome·Playwright로 공개 채팅에 접속해 `박새에 대해 알고 싶어`, `꼬까직박구리에 대해 알고 싶어`, `까치에 대해 알고 싶어`, `까마귀에 대해 알고 싶어`를 전송했다. 응답 모의 처리 없이 각각 Parus cinereus, Monticola gularis, Pica serica, Corvus corone의 profile 응답과 카드를 확인했다. 박새 직접 프로필 API도 수정 전 404에서 TEST 수정 후 200으로 바뀌었다.

첫 브라우저 검사 스크립트는 모든 종에 IUCN 등급 뱃지가 있어야 한다고 잘못 가정해 박새의 `평가 범위 확인 필요`에서 실패했다. 이때 이름 검색과 profile 응답은 이미 성공했다. 모든 종의 평가 자료 연결이 확인된 것은 아니므로 잘못된 검사 조건을 제거했다. 까치 뱃지는 요청한 전체 문구를 별도로 정확히 검사하고 네 종을 다시 실행해 통과했다. 박새 등급을 LC로 채우는 수정은 하지 않았다.

TEST 까치 카드 캡처를 직접 확인해 긴 뱃지와 초록색을 확인했다. 사진 로딩 완료 여부는 검사 대상이 아니며 캡처에 사진이 로딩 중일 수 있다. 이번 실제 브라우저 검사는 PC 1280×900 기준이며 모바일을 별도로 재실행하지 않았다.

두 컨테이너가 healthy이고 OCI revision이 b4fb662531755e8703e53210fed38b1d02c700b3인 것을 확인했다. Production 승격에는 배포 도구의 rollback 명령에 새 검증 이미지를 지정해 compose 교체·health 대기 기능을 사용했다. 과거 코드로 되돌린 것이 아니다.

Production에서도 같은 네 질문이 모두 HTTP 200, 올바른 profile과 카드로 반환됐다. 까치 전체 뱃지 문구도 일치했다. TEST 4건·Production 4건, 총 8건의 실제 채팅 검사 통과다. 결과는 [환경별 검증 JSON](../verification/assets/2026-10-09-korean-species-search-and-magpie-badge.json)에 보존했다. 모든 646개 이름을 실제 DB에서 전수 조회한 것은 아니다.
