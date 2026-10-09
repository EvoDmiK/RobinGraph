# 도넛 차트 아래 `항목·비율` 토글도 스크롤 — 2026-10-09

## 요청 배경과 목표

사용자가 뒷면 도넛 차트 아래의 `▶ 항목·비율` 토글(스크린샷)을 열어도 카드가 축소되지 않고 비율을 유지한 채 스크롤되도록 해 달라고 요청했다.
"ponytail을 이용해서"라는 지시에 따라 Ponytail 방식(공식 저장소 `DietrichGebert/ponytail` revision `9cc65d0`의 `ponytail` SKILL, "요청을 완전히 해결하는 가장 작은 변경, 새 추상화·옵션 없음")으로 진행했다.
Ponytail SKILL.md는 새 빈 임시 디렉터리에 받아 읽기만 했고 설치하거나 그 안의 코드를 실행하지 않았다.
완료 범위는 코드와 TEST 배포·검증까지이며 PROD 배포와 `main` 병합은 하지 않았다.

## 원인과 접근

앞서 `측정값 더 보기`·`분류 계통 보기`에 적용한 스크롤 모드(`2026-10-09-card-toggle-scroll.md`)는 `fitCard()`가 `.card-details-scroll` 표식이 붙은 열린 토글을 찾을 때만 켜진다.
`항목·비율`은 `species-distribution-values` 클래스의 `<details>`라 표식이 없어 기존 방식(카드 전체를 프레임 높이에 맞춰 축소)이 그대로 적용됐다.

Ponytail 판단(가장 작은 완전한 변경):

1. 새 기능이 아니라 기존 스크롤 모드의 대상 확대다 → 새 로직·옵션 없이 기존 메커니즘 재사용.
2. 처음에는 `항목·비율` `<details>`에 `card-details-scroll` 클래스를 추가하려 했으나, 기존 테스트가 `className === "species-distribution-values"`로 정확히 비교한다
   (`tests/frontend/chat_ui.test.js:1955`). 클래스를 바꾸면 테스트와 스타일 선택자까지 건드리게 되므로 **클래스는 그대로 두고 `fitCard()`의 선택자만 한 줄 확장**했다.

## 변경 내용

| 파일 | 내용 |
|---|---|
| `src/robingraph/api/static/chat.js` | `scrollToggleOpen()`의 `card.querySelectorAll(".card-details-scroll")`를 `".card-details-scroll, .species-distribution-values"`로 변경. 설명 주석에 `항목·비율` 추가 |
| `tests/frontend/chat_ui.test.js` | 가짜 DOM이 기대하는 선택자 문자열을 갱신하고, 소스에 확장된 선택자가 있는지 확인하는 단정 1줄 추가 |

CSS는 바꾸지 않았다(`data-fit-scroll="true"` 규칙이 이미 있다). 새 분기·옵션·의존성은 없다. 변경은 2개 파일, 4줄 추가·3줄 삭제다.

## 변경 전후 동작

| 상황 | 변경 전 | 변경 후 |
|---|---|---|
| `항목·비율`(먹이 구성 / 먹이 활동 위치) 열림 | 카드 전체가 프레임 높이에 맞게 더 축소 | 너비 기준 크기 유지(PC는 100%), 프레임이 세로 스크롤 |
| 닫음·뒤집기·카드 다시 열기 | — | 맞춤 상태 복귀, 스크롤 맨 위 |
| 다른 토글(출처 등) | 기존 축소 | 동일 |

## 검증 (실제 실행 결과)

| 항목 | 결과 |
|---|---|
| 프런트엔드 `node --test tests/frontend/*.test.js` | 252개 통과, 실패 0(모의 DOM) |
| Python 전체 | 641개 중 통과, 건너뜀 35(기존 DB 옵트인), 실패 0 |
| 실제 Chrome(헤드리스, CDP), 로컬 서버가 TEST Neo4j를 읽음(외부 LLM·MLflow 비활성), 청둥오리 카드, 두 `항목·비율` 모두 열고 측정 | **PC 1280×800**: 닫힘 scale 0.966·스크롤 없음 → 열림 scale 1·`scrollHeight 958 > clientHeight 744`·`overflow-y: auto`. 마우스 휠로 `scrollTop 214`(끝까지), 카드 아래 테두리와 프레임 아래가 0px 차이. 뒤집으면 `scrollTop 0`, 닫으면 scale 0.966·`overflow-y: clip`·`scrollTop 0` 복귀. 스크린샷에서 두 항목 목록(11개·7개 항목)과 아래 두 토글까지 잘리지 않음. **모바일 390×844 에뮬레이션**: scale 0.833 유지, 열어도 내용이 카드 높이 여유 안에 들어가 `scrollHeight 796 = clientHeight`(스크롤 불필요), 스크롤 모드와 복귀는 정상 |
| NAS TEST 배포 | 이미지 `robingraph-api:test-chartscroll-c305f7f`, healthy, 재시작 0, OCI revision `c305f7f…`, `verify` ok(`deployment_target: test`), 서빙되는 `chat.js`에 확장 선택자 확인 |

## 배포·커밋 정보

- 구현 커밋 `c305f7f39b235e80c919f90852fa16102015d313`(`dev-claude`). 릴리스 묶음 SHA-256 `b49c7963a7f47a1f7de4a0ad714becedfd61ae16f828a5ab272ae1d5602bd034`, NAS 일치·MANIFEST 불일치 0.
- NAS 체크아웃 `~/RobinGraph-c305f7f`. TEST env는 직전 TEST env(`~/RobinGraph-5fb401e/.env.nas.test`)를 복사해 이미지 태그와 `ROBINGRAPH_VCS_REF`만 변경했다.
- **PROD 배포와 `main` 병합은 하지 않았다.** 현재 PROD는 `robingraph-api:prod-5fb401e`다.

## 남은 한계

- Ponytail SKILL이 요구하는 "한 줄 한계 보고"에 따라: 스크롤바는 기존 방침대로 숨겨져 있어 스크롤 가능 여부는 카드 하단이 잘려 보이는 것으로만 알 수 있다.
- 모바일은 에뮬레이션이고, 이 종은 내용이 카드 높이 여유 안에 들어가 실제 스크롤은 PC에서만 측정했다. 실제 휴대폰·Safari는 확인하지 못했다.
- 선택자 방식이라 앞으로 새 토글을 같은 방식으로 다루려면 `card-details-scroll` 클래스를 붙이거나 이 선택자에 추가해야 한다.
- 한 차트의 `항목·비율`만 열어도 스크롤 모드가 켜지며, 닫으면 곧바로 맞춤 상태로 돌아간다(카드 크기가 바뀌는 순간이 있다).
- 사용자가 이 사이 변경한 화면을 PROD에서 보려면 별도 배포가 필요하다.
