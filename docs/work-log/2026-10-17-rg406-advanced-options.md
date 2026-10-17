# RG-406 범위 선택을 고급 조회 옵션으로 이동 — 2026-10-17

## 배경과 목표

사용자가 국내·국외 분포 범위 선택도 기존 `고급 조회 옵션` 안에 넣도록 요청했다. 채팅 상단에 항상 표시되던 범위 선택을 필요할 때 펼치는 기존 옵션에 통합한다.

## 원인과 변경 전후

`src/robingraph/api/static/index.html`에서 `species-scope-controls` fieldset이 예시 질문과 main 사이에 독립 배치돼 있었다. 같은 fieldset 전체를 `advanced-settings` details의 summary 바로 다음으로 이동했다. details는 기존처럼 기본적으로 닫힌 상태다. 선택지·기본값·ID·이름·안내 문구를 유지하여 기존 JavaScript 이벤트 및 API 요청의 scope 전달은 유지한다. CSS·JS·백엔드·DB는 이번 요청으로 변경하지 않았다.

## 변경 파일과 구현

- `src/robingraph/api/static/index.html`: 범위 선택 블록 위치 이동.
- 이 작업 기록: 요청·변경·실제 검증과 배포 경계 기록.

## 실제 검증

- `node --test tests/frontend/chat_ui.test.js tests/frontend/birds_ui.test.js`: 317 통과, 실패 0, 건너뜀 0. fake DOM 단위 검사이며 실제 브라우저/DB 검증은 아니다.
- Python 표준 HTMLParser로 실제 HTML 구조를 확인: scope fieldset이 고급 옵션 내부에 정확히 한 번 존재하고 details에 open 속성이 없는 것 확인.
- `git diff --check`: 통과.
- `graphify update .`: 코드 그래프 갱신 실행. 기존 SQL parser 부재 등 제한은 기존 환경과 같다.

## 최초 수정 시점의 배포·커밋과 한계

이 변경으로 NAS TEST/Production 배포·재시작·DB 쓰기·commit/push/병합은 수행하지 않았다. 직전 NAS TEST 배포의 상단 배치는 별도 배포 전까지 유지된다. 이번 변경에 대한 실제 브라우저 및 물리 모바일 검증은 수행하지 않았으며 기존 2026-10-17 RG-406 배포 검증과 구분한다. 단순 HTML 위치 변경이므로 새 테스트 코드나 API 검사를 추가하지 않았다.


## 사용자 배포 요청 후 NAS TEST 반영

사용자가 NAS 배포를 명시 요청하여 기존 TEST snapshot 7c1eb99c3762를 기준으로 index.html 한 파일만 overlay했다. 패키지141파일 해시, TEST DB 설정 동일·운영과 분리됨을 확인한 뒤 다음 명령으로 배포했다.

```sh
cd /home/kimdove/robingraph-rg406-8ffeb7734750
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh deploy
```

- 최종 이미지 `robingraph-api:test-rg406-8ffeb7734750`, healthy.
- snapshot `8ffeb7734750752ac20356128be9f0c36dd68954b2528a78c081d6cb85447807`.
- 실행 이미지의 src/scripts101파일 SHA-256이 manifest와 모두 일치.
- 실제 NAS HTTP/API/DB 및 배포 자산을 SSH 포워딩으로 연결한 Chromium1280/390/320 검증: 기본 접힘·고급 옵션 내부 위치·펼침·국내 선택·가로 넘침 없음 모두 통과. PC에서 실제 청둥오리 채팅1회도 scope=korea 전파와 answer 응답 확인.
- UI 단위317통과·실패0·건너뜀0 재확인. HTML 배치 변경이므로 Python 전체/DB 통합 검사는 다시 실행하지 않았다.
- 최초 비대화형 SSH 공개키 인증은 실패했고 기존 사용자가 제공한 비밀번호로 비공개 연결 후 성공했다. 임시 인증 파일은 즉시 삭제했다. 최종 배포/브라우저 검증 실패 없음.
- Production 컨테이너 ID·시작 시각·이미지는 직전 검증과 동일하다. 운영 배포·DB 쓰기·commit/push/병합 없음. 이전 TEST 이미지를 보존했다.
- SSH 포워딩과 control master는 검증 후 종료했다. 물리 모바일·Safari/Firefox·공개 도메인 프록시 경로는 미검증이다.

증거는 `docs/verification/assets/2026-10-17-rg406-advanced/`의 nas-release.json, browser.json, 화면3개, frontend.log, deploy.log, package.json에 저장했다. Obsidian에도 같은 상세 기록을 저장하고 재조회했다.
