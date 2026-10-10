# 비교 답변의 도감 카드 버튼 가로 배치 — TEST 전용

## 배경·목표·배포 범위

사용자가 비교 답변 아래 청둥오리·가창오리 도감 카드 버튼이 세로로 쌓인 화면을 제시하고 가로 배치를 요청했다. 비교 대상 두 종의 버튼을 같은 행과 같은 너비로 표시하며 모바일에서도 나란히 유지하는 것이 목표다.

직전 사용자가 변경별 승인 없는 운영 배포를 금지했다. 이번 작업은 로컬 수정·검증과 NAS TEST 반영까지 수행했으며 운영 배포·운영 DB 변경·롤백은 하지 않았다. 과거 승인을 이번 변경에 적용하지 않았다. 이전 작업 문서의 운영 승인 표현도 실제 사용자의 지적과 맞도록 정정했다.

## 원인과 구현

`buildSpeciesComparison`이 왼쪽과 오른쪽 도감 popup entry를 각각 비교 패널의 독립 block 자식으로 추가했고, 각 entry의 버튼도 display:block이어서 세로로 쌓였다.

- `src/robingraph/api/static/chat.js`: 두 popup entry를 `species-comparison-card-actions`라는 공용 행에 넣었다. 왼쪽 카드는 기존 bothCards 조건을 따르며, 카드가 하나만 가능한 경우에도 같은 행 안에서 정상 표시한다. 카드가 없으면 빈 행을 추가하지 않는다. 출처 통합과 카드 callback은 유지했다.
- `src/robingraph/api/static/styles.css`: 공용 행에 flex와 12px 간격을 적용했다. 각 entry는 flex:1, min-width:0을 사용해 같은 너비로 나란히 놓인다. 버튼은 행의 너비·높이를 채우고 긴 이름은 내부에서 줄바꿈한다. 한 카드만 있으면 행의 전체 너비를 사용한다.

버튼의 텍스트·자료·카드 여닫기·키보드 진입은 변경하지 않았다. 단순 배치 변경이라 구현을 그대로 복제하는 새 unit test는 추가하지 않고 기존 회귀와 실제 브라우저의 위치·크기 검증을 실행했다.

## 검증 결과와 범위

`node --test tests/frontend/*.test.js`: 301개 통과, 실패·취소·건너뛰기 0. 기존 fake DOM 회귀 검증이며 실제 DB 테스트가 아니다.

Chrome headless에서 320·390·768·1280px × 카드 2개/1개 = 8사례를 로컬 자산으로 실행했고 모두 통과했다. 실제 TEST API에서 앞선 작업 중 받은 청둥오리·원앙 프로필을 재사용하여 공개 `buildSpeciesComparison` helper로 비교 패널을 만들었다. 두 버튼의 y 좌표와 너비 일치, 버튼 간 간격, 가로 넘침 없음, 각각 Enter로 카드 열기·닫기 후 포커스 복원, 페이지 오류 0을 확인했다. 단일 카드도 정상 표시됐다.

TEST 배포 자산으로 동일한 8사례를 다시 실행해 모두 통과했다. 이 검사는 실제 프로필 기반의 UI 렌더링 검증이며, 새로운 실제 비교 질문을 전송한 전체 채팅 검증으로 표현하지 않는다. 별도로 공개 TEST chat.js·styles.css 바이트가 로컬 앱 파일과 같음을 확인했고, 실제 /health와 청둥오리 profile 질문도 통과했다.

증거는 `docs/verification/assets/2026-10-10-comparison-buttons-{local,test}.json`과 `2026-10-10-comparison-buttons-test-assets.json`에 있다. 화면은 `/tmp/rg-answer-names-browser/comparison-buttons-{width}-{bothCards}.png`에 저장했다. 실제 물리 모바일 기기·Safari와 전체 백엔드 테스트는 실행하지 않았다. 이번 변경은 새 데이터 수집이나 종별 데이터 품질 검증을 포함하지 않는다.

`graphify update .` 실행 완료: 5,097 nodes, 10,583 edges, 307 communities. SQL 파서 부재 경고는 기존 SQL 추출에 해당하며 이번 JS/CSS 변경 검증과 구분한다.

## TEST 배포·Git·운영 보존

앱 커밋은 `c8c36630ce01594a12c5e1c20552de1ccfc82104`, origin/dev-codex에 push했다. 표준 패키징으로 런타임 허용 목록만 묶었으며 아카이브 SHA-256은 `fa58b03121cac83706c956dce0ceabb015db43796ce9d711c45040b1284de5bd`다. SSH 전송 후 아카이브·MANIFEST 파일별 해시를 검사했다. TEST 환경만 NAS에서 복사하고 ROBINGRAPH_PG_DATABASE=robingraph_test를 검사했다. 운영 환경 파일은 복사·수정하지 않았다. 인증 정보는 기록하지 않았다.

NAS 릴리스 `/home/kimdove/RobinGraph-comparison-buttons-c8c3663`에서 ROBINGRAPH_DEPLOY_TARGET=test로 표준 preflight → deploy → verify를 통과했다. buildx 경고 후 기존 classic builder로 정상 빌드됐다.

- TEST 이미지: `robingraph-api:test-comparison-buttons-c8c3663`.
- 이미지 ID: `sha256:9c32a39eac8de166573005759f8c245b67d294d0f088b5f99149c489651ac69d`.
- TEST 시작: 2026-10-10T05:30:10.974270037Z, healthy.

배포 도구에서 운영 컨테이너의 ID·이미지·시작 시각을 배포 전후 비교했고 동일했다. 마지막 읽기 확인에서도 운영은 기존 `prod-food-ui-2ee9318`, 이미지 `sha256:c32be224b61c44b2cd2425f69fcf765e3d065182a9b892f2b0540bccf70b8226`, 시작 2026-10-10T05:12:57.867612805Z를 유지했다. 운영을 재시작하거나 신규 코드를 반영하지 않았다.

문서와 검증 JSON은 후속 기록 커밋으로 dev-codex에 반영한다. 같은 본문을 Obsidian 작업기록에 저장하고 인덱스에 링크를 추가한다. main/dev 병합과 운영 반영은 이번에 수행하지 않았으며 이후 명시적 지시에 따른다.
