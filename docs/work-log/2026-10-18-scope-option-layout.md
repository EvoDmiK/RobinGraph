# 고급 조회 옵션 분포 범위 정렬 — 2026-10-18

## 요청과 완료 범위

사용자가 분포 범위 4개 옵션이 불규칙하게 3+1줄로 나열된 화면을 제시했다. 목표는 옵션 정렬을 다듬고 TEST 서버에서 먼저 확인하는 것이다. 운영 반영은 사용자가 이 수정 결과를 확인하고 별도 승인한 이후에만 가능하다. 앞선 Jenkins 운영 배포 승인은 이 새 UI 변경에 재사용하지 않았다.

## 원인과 변경 전후

기존 .species-scope-options는 flex-wrap으로 내용 길이에 따라 줄이 바뀌었다. 옵션 너비가 서로 달라 마지막 하나만 다음 행에 남았다. 전역 일반 입력 필드의 최소 높이가 라디오에도 적용되어 키보드 focus 표시가 세로로 늘어날 수 있었다.

styles.css의 해당 범위만 CSS grid 두 열·동일 행 높이·10px 간격으로 변경했다. 600px 이하에서는 한 열이다. 옵션은 padding 10px/14px와 12px 모서리를 사용하고 기존 최소 터치 높이 44px를 유지한다. 라디오는 1rem 정사각형·min-height 0·shrink 방지로 중앙에 배치했다. 문구와 API scope 값·JS 동작은 변경하지 않았다. 선택 색과 focus-within 표시를 유지한다.

## 협업과 변경 파일

UI 담당 main 터미널에 담당 범위 작업을 요청했다. 응답 완료를 기다려 구현했다고 주장하지 않으며, Codex가 dev-codex의 CSS만 직접 구현했다. 이후 담당자에게 현재 diff의 읽기 전용 UI 검토를 요청했다. main의 기존 미커밋 파일은 가져오거나 덮어쓰지 않았다. 후속 터미널 조회에서 UI agent가 panic으로 종료된 것을 확인했다. 따라서 UI 담당 검토 완료로 보고하지 않으며 Codex의 실제 TEST 검사 결과만 근거로 삼는다.

- src/robingraph/api/static/styles.css: 정렬과 라디오 크기 수정.
- docs/verification/assets/2026-10-18-scope-layout/: 실제 브라우저 검사 코드·결과·전후 스크린샷·TEST receipt·검사 로그.
- 이 작업 기록. 기존 Jenkins 작업의 미커밋 파일은 보존했다.

## TEST 배포

기존 TEST immutable image를 기반으로 CSS 한 파일만 교체한 ARM64 로컬 이미지를 빌드했다. 전체 앱 checkout의 Git revision과 미커밋 CSS를 구별하기 위해 별도 css-sha256 label과 receipt를 기록했다. 이전 릴리스 compose/env를 private 새 릴리스로 복사하고 image만 교체했다. env 권한 0600, 디렉터리 0700을 유지하고 current 심볼릭 링크를 atomic 교체했다. 실패하면 이전 current 복구 및 앱 재시작하도록 실행했다. 운영 job이나 GHCR 배포는 실행하지 않았다.

- TEST 주소: https://robingraph-test.dove-nest.com/chat
- 이미지: robingraph-api:test-scope-layout-733d461cbc61
- 기반 revision: bc643ee9edef0fc58c605adde70b4808b7622ac5
- CSS SHA-256: 733d461cbc61ec6361223c056c262a54bc036d70819c11096c5bf5e2138849c6
- TEST receipt state: verified. 이전 릴리스 경로는 test-release.json에 기록했다.

## 실제 검증 결과

- node --test tests/frontend/chat_ui.test.js: 최종 313개 통과, 실패/skip 0. 첫 검사에서는 임의로 바꾼 최소 높이 48px가 기존 44px 검증과 불일치해 1개 실패했다. 기존 44px 계약을 유지하도록 수정한 뒤 통과했다. 테스트를 완화하지 않았다.
- TEST 컨테이너 healthy 및 manage.sh verify 실제 health/OpenAPI/청둥오리 lineage API 계약 검사 통과.
- 실제 공개 TEST Chromium 1440/1024/768/480/390/320 너비 모두 통과. PC/태블릿 2×2, 600px 이하 1열, 동일 너비/높이, Space 키로 radio 선택, 작성 중 질문 유지, 가로 넘침 없음, pageerror 없음 확인.
- 브라우저에서 POST를 차단하고 /v1/chat POST 0을 확인했다. 실제 정적 자산을 읽었으며 답변 생성/DB 쓰기 테스트는 하지 않았다. 실제 운영·TEST DB 전체 데이터 품질 검증이 아니다.
- 공개 운영 CSS를 curl로 읽고 변경 전 HEAD CSS와 바이트 일치를 확인했다. urllib 기본 요청은 HTTP403으로 거부돼 curl로 재확인했다. 운영 stylesheet는 기존 상태이며 이번 수정 미배포다.
- graphify update . 성공. SQL parser 미설치 및 community label 갱신 안내는 앱 장애가 아니다.

## 형상·한계·후속

신규 commit/push/merge는 하지 않았다. 변경은 로컬 CSS와 TEST 이미지에 반영됐다. 실제 rollback 유발, Safari/Firefox, 물리 모바일, 브라우저 확대율 전체 검증은 하지 않았다. Python/API 코드가 바뀌지 않아 전체 Python 검사를 반복하지 않았다. 사용자 TEST 확인·명시 승인 전까지 운영 앱과 운영 이미지는 교체하지 않는다. 승인 후 배포 시 이 CSS hash가 포함된 이미지를 검증해야 한다.
