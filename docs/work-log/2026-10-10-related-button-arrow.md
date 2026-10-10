# 근연 관계 버튼 화살표 제거 — TEST 전용

## 요청과 목표

사용자가 더 알아보기의 네 버튼을 통일한 화면에서 근연 관계 버튼에만 남은 화살표를 제거하도록 요청했다. 근연 관계 버튼 앞의 접힘·펼침 표시만 없애고 버튼 크기 통일과 탐색 기능을 유지한다. 사용자 지시에 따라 TEST에만 반영한다.

## 원인·변경 파일·전후 동작

graphify query 후 `src/robingraph/api/static/styles.css`에서 두 ::before 규칙을 확인했다. `.species-related > button[aria-expanded]`에 ▸, expanded=true에 ▾ 문자를 CSS로 붙였다. HTML이나 버튼의 실제 이름에 들어 있는 문자가 아니었다.

이 두 규칙을 삭제했다. 접힘·펼침 상태 모두 문자 없는 근연 관계 버튼으로 표시한다. 앞선 네 버튼의 높이·너비·글자·여백 규칙은 유지된다. JS와 aria-expanded 상태 갱신, 탐색 조회, 키보드 버튼 동작을 변경하지 않는다. 더 알아보기와 답변 출처 같은 다른 토글의 화살표도 이번 변경 대상이 아니다.

## 검증과 결과

`node --test tests/frontend/*.test.js`: 303개 통과, 실패·취소·건너뛰기 0. fake DOM·단위 회귀이며 실제 DB 전수 검증은 아니다. 변경 규모가 CSS 두 줄 삭제이므로 새 단위 테스트는 추가하지 않았다. `git diff --check` 통과, `graphify update .` 완료. 기존 SQL 파서 미설치 경고는 이번 CSS 변경과 무관한 추출 범위 제한이다.

배포된 TEST 자산을 사용하는 Chrome 390·1280px에서 접힘 → 펼침 → 다시 접힘의 6상태를 확인했다. getComputedStyle(button, "::before").content가 항상 none이며 aria-expanded는 false → true → false로 정상 바뀌었다. 페이지 오류 0. 입력은 이전 실제 TEST profile 응답을 재생했고 탐색 HTTP는 빈 groups 모의 응답으로 처리했다. 공개 chat.js·styles.css는 로컬 파일과 바이트 단위로 일치했다. 별도 실제 health와 청둥오리 profile 질문 API도 정상 응답했다. 증거는 docs/verification/assets/2026-10-10-related-arrow-test.json, 2026-10-10-related-arrow-assets.json. 브라우저 도구는 /tmp/rg-answer-names-browser/related-arrow.cjs다.

## 배포·커밋·기록

앱 커밋 `06817474f5003bb359579b24868aa1ffa5cb8cdf`, origin/dev-codex push 완료. 표준 NAS 패키지 SHA-256은 `117bd0ce569a8a7cdaf7bf0d00a6d8883b4de07fa369b2d3b1a01a5c009f4754`이며 NAS에서 아카이브 해시를 검증했다. 이전 TEST 환경만 복사하고 PG가 robingraph_test인지 확인했다. 인증 정보는 문서에 넣지 않았다.

TEST 릴리스 `/home/kimdove/RobinGraph-related-arrow-0681747`에서 ROBINGRAPH_DEPLOY_TARGET=test로 표준 preflight → deploy → verify를 실행했다. 이미지 `robingraph-api:test-related-arrow-0681747`.

TEST 이미지 ID `sha256:db6b08852216ac26f4c99fd6a21b01dc85c43efe3ea9ca6faec9f7c880d892e4`, 시작 2026-10-10T06:04:04.423546085Z, health healthy. 표준 배포 검증을 통과했다. 배포 전후 운영 컨테이너 ID·이미지·시작 시각이 모두 동일함을 실제 docker inspect로 확인했다. buildx 경고 후 classic builder가 정상 완료했다.

운영 배포·운영 DB 변경·운영 환경 수정은 실행하지 않았다. main/dev 병합도 하지 않았다. 결과 문서는 저장소와 Obsidian 작업기록에 동일 본문을 기록하고 재조회한다. 검증 증거와 문서는 후속 기록 커밋에 저장한다.

## 한계·후속 사항

실제 휴대전화·iOS Safari, 전체 종 조회, 전체 backend 테스트·새 CI는 실행하지 않았다. UI 브라우저 검사는 응답 재생과 모의 탐색 데이터이며 실제 탐색 데이터 품질 검사로 계산하지 않는다. 근연 관계 조회의 기존 동작은 frontend 회귀에서 확인한다. 운영 반영은 이번 변경에 대한 명시적 승인 이후에 진행한다.
