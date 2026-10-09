# 도감 카드 뒷면 토글을 열면 스크롤 — 2026-10-09

## 요청 배경과 목표

사용자가 뒷면 스크린샷(집비둘기 카드, `측정값 더 보기 (7)` 열림)을 보내며, "측정값 더 보기"와 "분류 계통 보기" 토글을 열었을 때는
카드가 스크롤되었으면 좋겠다고 요청했다. 범위는 코드와 TEST 배포·검증까지이며 PROD 배포와 `main` 병합은 하지 않았다.

## 원인

카드는 항상 "프레임 높이에 맞춰 통째로 축소"되도록 만들어져 있었다(이전 RG-405 작업에서 카드 내부 스크롤을 없애고 맞춤으로 바꿨다).
`chat.js`의 `fitCard()`가 `scale = min(1, 프레임너비/카드너비, 프레임높이/카드높이)`로 계산한다. 토글을 열면 카드 높이가 늘어
`프레임높이/카드높이`가 작아지고, 그 결과 카드 전체가 작아져 글씨가 읽기 어려워졌다. 스크롤은 `.species-card-fit-frame { overflow: clip; }`으로
막혀 있었고, 모바일에서는 `touch-action: pinch-zoom`이라 세로 팬도 막혀 있었다.

## 변경 전후 동작

| 상황 | 변경 전 | 변경 후 |
|---|---|---|
| 두 토글 닫힘 | 프레임에 맞춰 축소, 스크롤 없음 | 동일(변화 없음) |
| 두 토글 중 하나라도 열림 | 카드 전체가 프레임 높이에 맞게 더 축소 | 너비 기준 크기를 유지(PC는 보통 100%)하고 프레임이 세로 스크롤 |
| 토글 닫음 / 면 뒤집기 / 카드 다시 열기 | — | 맞춤 상태로 복귀, 스크롤 위치는 맨 위로 |
| 다른 토글(출처, 항목·비율) 열림 | 기존 축소 방식 | 동일(변화 없음) |

## 구현

| 파일 | 내용 |
|---|---|
| `src/robingraph/api/static/chat.js` | 두 토글(`측정값 더 보기`, `분류 계통 보기`)에 `card-details-scroll` 표식 클래스를 추가. `fitCard()`는 표식 토글이 열려 있으면 너비만 기준으로 scale을 정하고(`scrollToggleOpen()`), 프레임에 `data-fit-scroll="true"`를 설정한다. scale이 1 미만이면 축소된 높이만큼 `margin-bottom`을 음수로 줘서 스크롤 범위가 실제로 보이는 크기와 같게 한다. 맞춤 모드로 돌아가거나 면을 뒤집거나 다시 열면 스크롤을 0으로 되돌린다(`card.resetFitScroll`). 프레임 스크롤 시 도넛 툴팁을 닫는다 |
| `src/robingraph/api/static/styles.css` | `.species-card-fit-frame[data-fit-scroll="true"]`에서만 `overflow-y: auto`, `overscroll-behavior: contain`, 스크롤바 숨김(기존 디자인 방침 유지). 그 안의 카드에는 `touch-action: pan-y pinch-zoom`을 줘서 세로 스크롤은 브라우저가 처리하고 좌우 스와이프 뒤집기는 그대로 JS가 처리한다 |
| `tests/frontend/chat_ui.test.js` | 신규 4개: 토글 열림 시 축소 안 함·닫으면 복귀·스크롤 0 복귀, 좁은 프레임에서 너비 기준 scale과 `margin-bottom` 보정, 뒤집기 시 스크롤 초기화, 표식 클래스와 CSS 규칙 존재(기본 프레임의 `overflow: clip`은 유지) |

설계 결정: 기본 상태의 `overflow: clip`은 그대로 두고 토글이 열린 동안에만 스크롤을 허용했다. 그래서 이전 작업들이 검증한 "평소엔 스크롤 없음" 동작은 바뀌지 않는다.
카드 DOM을 조회하는 `querySelectorAll`이 없는 환경(기존 테스트의 가짜 DOM)에서는 예전 동작으로 처리하도록 방어했다.

## 검증 (실제 실행 결과)

| 항목 | 결과 |
|---|---|
| 프런트엔드 `node --test tests/frontend/*.test.js` | 252개 통과, 실패 0(기존 248개 + 신규 4개). 모의 DOM 검증 |
| Python 전체 `unittest discover` | 641개 중 통과, 건너뜀 35(기존 DB 옵트인), 실패 0 |
| 실제 Chrome(헤드리스, CDP) — 로컬 서버가 TEST Neo4j를 읽음, 외부 LLM·MLflow 비활성, 흰뺨검둥오리 카드, 토글 2개 모두 열고 측정 | **PC 1280×800**: 닫힘 scale 1·스크롤 없음(`overflow-y: clip`) → 열림 scale 1 유지·`scrollHeight 988 > clientHeight 744`·`overflow-y: auto`. 마우스 휠로 `scrollTop 244`(끝까지). 끝에서 카드 아래 테두리가 프레임 아래와 0px 차이로 정확히 닿음. 뒤집으면 `scrollTop 0`. 토글을 닫으면 다시 `clip`·`scrollTop 0`. 스크린샷으로 분류 계통 목록까지 잘리지 않음을 확인. **모바일 390×844(터치 에뮬레이션)**: scale 0.833(너비 기준) 유지, 터치 스와이프로 `scrollTop 17`(끝까지), 뒤집기·닫기 후 복귀 동일 |
| NAS TEST 배포 | 이미지 `robingraph-api:test-cardscroll-5fb401e`, healthy, 재시작 0, OCI revision `5fb401e…`, `verify` ok(`deployment_target: test`). 서빙되는 `chat.js`에 `card-details-scroll` 3곳, CSS에 `data-fit-scroll` 규칙 확인 |

변경 전의 수치는 실측하지 않았다. 예를 들어 PC 열림 상태의 이전 scale은 `min(1, 744/988)`≈0.75로 계산되는 값이며 실제 브라우저에서 재현하지 않았다.

## 배포·커밋 정보

- 구현 커밋 `5fb401ebbe9963baa9e8fa56ba8da4ffbfb21bd2`(`dev-claude`). 릴리스 묶음 SHA-256 `fa949c6db69e7417d425f9e2af4ae05ce4ad6c7813baf83a345eaf2e19f44a04`, NAS 일치·MANIFEST 불일치 0.
- NAS 체크아웃 `~/RobinGraph-5fb401e`. TEST env는 직전 TEST env(`~/RobinGraph-336d987/.env.nas.test`)를 복사해 이미지 태그와 `ROBINGRAPH_VCS_REF`만 변경했다.
- **PROD 배포와 `main` 병합은 하지 않았다.** 사용자가 TEST를 확인한 뒤 결정한다. 현재 PROD는 `robingraph-api:prod-336d987`이다.

## 남은 한계

- 사용자가 보낸 스크린샷의 종(집비둘기)은 TEST 분류에서 조회되지 않아(`Species not found in active taxonomy`) 흰뺨검둥오리로 검증했다. 측정값 7개와 분류 계통을 가진 같은 구조의 카드다.
- 모바일은 에뮬레이션이다. 이 종은 카드 높이 여유가 커서 스크롤 범위가 17px뿐이었다. 내용이 더 긴 종이나 실제 휴대폰·Safari에서는 확인하지 못했다.
- 다른 토글(출처 보기, 먹이 항목·비율)은 기존 축소 방식 그대로다. 같은 방식으로 바꾸려면 해당 `details`에 `card-details-scroll` 클래스를 붙이면 된다.
- 스크롤바는 기존 디자인 방침대로 숨겼다. 스크롤할 수 있다는 시각 표시는 카드 하단이 잘려 보이는 것뿐이다.
- 이 이후 `main`·PROD에 반영되지 않은 상태라 사용자 화면(PROD)에는 아직 변화가 없다.
