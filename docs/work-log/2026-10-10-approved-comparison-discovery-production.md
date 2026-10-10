# 사용자 승인 후 비교·탐색 UI 운영 배포

## 승인·요청 배경·목표

사용자가 TEST에서 비교 화면과 출처 디자인, 네 탐색 버튼 크기, 근연 관계 화살표 제거를 확인한 후 “굿 고생햇어. 이제 운영서버에 배포하자”라고 명시적으로 운영 배포를 승인했다. 이전 변경에는 운영 금지 지시를 지켜 TEST만 반영했고, 이번 승인을 근거로 그동안 검증된 UI 변경을 운영으로 옮겼다. 목표는 TEST에서 확인한 동일 UI를 운영 DB 연결과 서비스 설정을 유지하며 제공하는 것이다. DB 마이그레이션이나 main/dev 병합은 이번 요청 대상이 아니며 수행하지 않았다.

## 포함된 구현·변경 전후

운영의 이전 이미지는 prod-food-ui-2ee9318이었다. 이후 dev-codex에서 검증한 다음 UI 변경을 포함한다.

- 비교 도감 버튼 가로 배치(c8c3663): 두 종 버튼이 한 줄에 같은 너비로 표시된다.
- 비교값 중복·출처 통합(2fe5a01): 동일한 표시값을 한 번만 출력하고 원자료 근거는 하나의 출처 패널에 보관한다. 서로 다른 값이나 평균 기준은 구별한다.
- 비교 하단 정리·kg·출처 카드(d5ff022): 1156g → 1.16kg, 반복 추천·탐색 영역을 비교 본문에서 제거하며 카드 버튼과 출처로 마무리한다. 항목별 출처 카드의 제목·자료 링크를 먼저 보이고 긴 코드·검증 설명은 자료 상세 정보에 보관한다. 추천 점수와 분류 근거도 이 패널에서 유지한다.
- 탐색 버튼 크기 통일(3a24dc9): 근연 관계·생태·아종·통칭 네 버튼의 글꼴·폭·높이·여백을 통일한다.
- 근연 관계 화살표 제거(0681747): 버튼의 접힘·펼침 CSS 문자만 제거하고 aria-expanded와 조회 기능을 유지한다.

실제 구현 파일은 `src/robingraph/api/static/chat.js`, `styles.css`, 관련 frontend 회귀다. 이번 운영 배포에서는 코드 변경을 추가하지 않았다. 각 세부 원인과 구현·검증은 같은 날짜의 comparison-card-buttons-horizontal, comparison-values-sources-summary, comparison-compact-sources-kg, discovery-button-sizes, related-button-arrow 작업 문서에 자세히 기록되어 있다.

## 배포 방식·실행 근거

배포 전 실제 docker inspect로 운영·TEST의 태그·이미지·작업 디렉터리·health를 확인했다. 최신 저장소 커밋은 e7ad221c6acdbb88b31564119f7dd470d5e1e73f이며 런타임 UI 커밋은 06817474f5003bb359579b24868aa1ffa5cb8cdf다. 표준 NAS 패키지를 만들고 아카이브 SHA-256 `04a1ed32d8138df1ff521a074ca18e9da2d4146d3d8d0d5d9aa274ed9beec9fc`을 NAS에서 검증했다.

TEST 컨테이너 이미지 ID를 기대한 db6b088…과 비교하고, 컨테이너 안의 chat.js·styles.css가 릴리스 파일과 바이트 단위로 같은지 검사했다. 새 빌드 대신 검증된 TEST 이미지 자체를 운영 태그로 붙여 동일 이미지 ID를 승격했다. 기존 운영 작업 디렉터리의 .env.nas.prod를 새 운영 릴리스에 복사했고 파일 권한 600을 적용했다. ROBINGRAPH_IMAGE만 변경했으며 나머지 설정이 원본과 같음을 사전 비교했다. PG가 robingraph_test가 아닌 운영 DB임을 확인했다. 인증 정보는 로그·문서에 출력하지 않았다.

ROBINGRAPH_DEPLOY_TARGET=prod로 표준 preflight를 통과한 뒤 운영 Compose 프로젝트와 운영 컨테이너를 명시해 config --quiet, up -d --no-build api를 실행했다. TEST를 재시작하거나 DB 볼륨을 변경하지 않았다. 운영 healthy 대기 후 표준 verify에서 deployment_target=prod를 확인했다.

운영 릴리스 `/home/kimdove/RobinGraph-approved-ui-e7ad221`. 태그 `robingraph-api:prod-approved-ui-0681747`. 이미지 ID `sha256:db6b08852216ac26f4c99fd6a21b01dc85c43efe3ea9ca6faec9f7c880d892e4`로 TEST와 동일하다. 운영 시작 2026-10-10T06:07:33.413088244Z, health healthy. 이전 태그 `robingraph-api:prod-food-ui-2ee9318`, 이전 이미지 ID `sha256:c32be224b61c44b2cd2425f69fcf765e3d065182a9b892f2b0540bccf70b8226`. 공개 URL https://robingraph.dove-nest.com/chat.

이전 운영 이미지와 릴리스는 보존해 복구에 사용할 수 있다. 배포 후 TEST 컨테이너 ID·이미지·시작 시각이 배포 전과 같은지 검사했고 모두 같았다. 데이터 수집·DB 마이그레이션·운영 데이터 수정은 실행하지 않았다.

## 실제 검증 결과

운영 공개 JS/CSS는 로컬 최종 파일과 바이트 단위로 일치했다. 실제 /health 정상, 실제 청둥오리 profile 질문 API가 answer·Anas platyrhynchos·Mallard를 반환했다. 운영 actual chat에서 청둥오리 먹이 질문 → 더 알아보기 → 근연종 조회 → 흰뺨검둥오리 비교를 390·1280px 2흐름 실행해 모두 통과했다. 이 흐름의 채팅·후보·profile API는 가로채지 않았다. 1.16kg, 비교값 중복 없음, 도감 버튼 → 출처 순서, 반복 추천·탐색 없음, 출처 상세 기본 접힘·열림, 가로 넘침 없음, 페이지 오류 0을 확인했다.

별도 UI 회귀는 기존 실제 TEST 응답을 운영 자산에서 재생해 320·390·768·1280px × 네 답변 형식 16사례 모두 통과했다. 네 버튼 높이·폭·글꼴·여백이 실제 치수상 동일했다. 근연 관계 화살표는 390·1280px의 접힘 → 펼침 → 다시 접힘 6상태에서 ::before content가 none이고 aria-expanded가 false → true → false임을 확인했다. 이 화살표 검사는 profile 재생과 빈 groups 모의 조회 응답이며 실제 탐색 데이터 품질 검사와 구별한다. 실제 운영 채팅 검증과 응답 재생 사례를 합쳐 실제 API 조회 건수처럼 세지 않는다.

최근 최종 `node --test tests/frontend/*.test.js`는 303개 통과, 실패·취소·건너뛰기 0이다. 이번 턴에는 런타임 코드를 바꾸지 않아 동일 테스트를 다시 실행하지 않고 기존 통과 결과와 배포된 자산 일치·운영 브라우저 검증을 사용했다. fake DOM 회귀를 실제 DB 검증으로 기록하지 않는다.

증거는 `docs/verification/assets/2026-10-10-approved-ui-prod-deploy.json`, `approved-ui-prod-assets.json`, `discovery-size-prod.json`, `related-arrow-prod.json`, `comparison-compact-prod.json`(모두 2026-10-10 접두사)이다. 실행 도구와 스크린샷은 `/tmp/rg-answer-names-browser`의 *-prod.cjs 및 *-prod-*.png에 있다.

## Git·작업 문서·한계

검증 결과와 작업 문서는 dev-codex 후속 기록 커밋으로 push하고 동일 본문을 Obsidian 작업기록에 저장해 재조회한다. main/dev 병합은 요청되지 않아 하지 않았다. 물리 모바일·iOS Safari·모든 종 HTTP·전체 backend 테스트·새 CI는 이 배포에서 실행하지 않았다. 운영 데이터 전체의 품질을 새로 검증한 작업은 아니며 검증 범위는 승인된 UI 수정과 서비스 상태다. 운영에 필요한 새 수정은 별도로 TEST 검증과 변경별 승인을 거쳐 반영한다.
