# 더 알아보기 네 버튼 크기 통일 — TEST 전용

## 요청 배경과 목표

사용자는 profile 답변의 더 알아보기 내부에서 근연 관계, 같은 서식 환경·먹이 생태, 아종, 통칭·가축형 네 탐색 버튼의 크기가 서로 다른 화면을 제시하고 크기를 맞추도록 요청했다. 글꼴·높이·폭·내부 여백을 통일하고 PC와 모바일 모두 같은 네 버튼 크기를 유지한다. 변경별 운영 승인 지시를 따라 이번 작업은 TEST에만 반영했다.

## 원인과 구현 근거

`graphify query`로 관련 탐색 코드와 스타일을 먼저 확인했다. 기존 `.species-related button`과 `.species-name-relations > button`은 font 상속을 지정하지 않았다. `.species-subspecies > button`과 `.species-ecological-related button`은 font: inherit를 사용했고, 아종 버튼의 padding도 다른 값이었다. 브라우저 기본 버튼 폰트와 답변 폰트가 섞여 글씨 크기와 높이가 달라졌다.

`src/robingraph/api/static/styles.css`에 네 탐색 컨테이너의 직접 자식 버튼만 선택하는 공통 규칙을 추가했다. box-sizing: border-box, width: 100%, font: inherit, .95rem 글자, line-height: 1.4, .65rem .75rem padding, .25rem 위아래 margin, 최소 높이 3.25rem을 공유한다. 420px 이하에서는 .9rem 글자와 최소 4rem 높이를 적용해 긴 생태 탐색 문장이 두 줄이 되더라도 네 버튼 높이가 같도록 했다. 긴 문구의 줄바꿈을 허용한다. 후보 선택 버튼이나 카드 팝업 버튼까지 영향을 주는 광범위한 버튼 선택자를 추가하지 않았다. 탐색 조회·키보드 동작·상태 표시는 기존 구현을 유지한다.

## 검증 방법과 결과

`node --test tests/frontend/*.test.js`: 303개 통과, 실패·취소·건너뛰기 0. 기존 fake DOM 회귀이며 실제 DB 검증으로 계산하지 않는다. 이번 변경은 CSS 표시 수정이므로 스타일 선언을 그대로 복제하는 새 단위 테스트 대신 실제 브라우저 치수를 검사했다.

Chrome 320·390·768·1280px × diet·magpie·habitat·profile 4종 응답 형식, 총 16사례를 로컬 최종 자산으로 확인했다. 입력 데이터는 이전 작업에서 실제 TEST에서 받은 응답을 재생했다. 매 사례에서 네 버튼 수가 4인지, getBoundingClientRect의 높이·폭과 computed style의 font-size·line-height·padding이 각각 동일한지 검사했다. 버튼 내부 세로 넘침·페이지 가로 넘침 없음, 페이지 오류 0이었다. 390px profile 스크린샷을 직접 열어 동일 높이·줄바꿈·여백을 확인했다. 이 16사례는 UI 재생 검증이며 새 실제 채팅 API 요청 16건으로 기록하지 않는다.

배포된 TEST 자산으로 같은 16사례를 재실행해 모두 통과했다. 모바일·태블릿·PC 네 폭에서 네 버튼의 실제 치수와 폰트·여백 일치, 넘침 없음, 페이지 오류 0을 다시 확인했다. 공개 chat.js·styles.css는 로컬 최종 파일과 바이트 단위로 일치했다. 별도 실제 health와 청둥오리 profile 채팅 API도 정상 응답했으며 학명 Anas platyrhynchos·영문명 Mallard를 확인했다.

증거: `docs/verification/assets/2026-10-10-discovery-size-local.json`, `2026-10-10-discovery-size-test.json`, `2026-10-10-discovery-size-test-assets.json`. 도구: `/tmp/rg-answer-names-browser/discovery-size.cjs`. 스크린샷: 같은 폴더의 discovery-size-{local,test}-{320,390,768,1280}.png.

`git diff --check` 통과. `graphify update .` 완료: 5119 nodes, 10603 edges, 308 communities. SQL 파서 미설치로 4개 SQL 추출 생략 경고는 기존 제한이며 이번 수정은 CSS 하나뿐이다.

## 배포·Git 정보

앱 커밋 `3a24dc98d99df71dbda79d1edf873207c89c6785`, origin/dev-codex push 완료. 표준 release 아카이브 SHA-256 `9c477412d84fb615183e11f5443ab130efe8ff76038dcf423f9cd46305960f76`을 NAS에서 검증했다. 이전 TEST 환경만 복사했고 PG가 robingraph_test인지 확인했다. 인증 정보는 출력·문서에 포함하지 않았다.

릴리스 `/home/kimdove/RobinGraph-discovery-size-3a24dc9`, 이미지 `robingraph-api:test-discovery-size-3a24dc9`. ROBINGRAPH_DEPLOY_TARGET=test로 표준 preflight → deploy → verify를 실행했다.

TEST 이미지 ID `sha256:18803b5bd96b648361a498f21424041276ea9f24fa55a74d4909c50031fbf90f`, 시작 시각 2026-10-10T05:58:00.787542086Z, health healthy. 배포 전후 실제 docker inspect로 운영 컨테이너 ID·이미지·시작 시각이 모두 동일한지 비교했고 운영 불변을 확인했다. buildx 경고 이후 classic builder가 정상 완료했다.

운영 배포·운영 환경 변경·운영 DB 변경은 하지 않았다. main/dev 병합도 하지 않았다. 상세 문서와 배포 검증 결과는 후속 기록 커밋에 저장하며 같은 본문을 Obsidian 작업기록에 저장하고 재조회해 일치 여부를 확인한다.

## 남은 한계와 후속 사항

실제 휴대전화와 iOS Safari, 전체 종 HTTP, 전체 backend 테스트, 새 CI 실행은 이번 범위에 포함하지 않았다. 최소 높이를 공유하고 줄바꿈을 허용하므로 매우 긴 미래 문구나 사용자 임의 확대 설정에서는 텍스트를 자르지 않고 버튼이 더 커질 수 있다. 현재 네 문구와 확인한 네 화면 폭에서는 실제 치수가 모두 동일하다. 운영 반영은 이번 변경에 대한 사용자 승인 후 별도로 진행한다.
