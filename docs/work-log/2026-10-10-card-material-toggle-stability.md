# 카드 뒷면 토글과 소재 반사 무늬 안정화 — 2026-10-10

## 요청과 목표

카드 뒷면의 상세 토글을 열 때 빛 반사가 미세하게 움직인다는 사용자 보고를 조사했다. 앞선 카드 확대 수정과 별개로, 같은 화면 위치의 소재 무늬를 토글 전후 고정하고 드래그로 넘길 때 반사광은 유지하는 것이 목표다. PC와 모바일을 모두 검증하며, 이번 변경은 TEST에 먼저 배포한다. Production은 별도 승인 전 변경하지 않는다.

## 원인과 실제 근거

실제 TEST 원앙 프로필과 Chrome으로 토글 전후 카드 배율·너비·위치·스크롤·반사광 상태 및 배경 픽셀을 비교했다. 카드 배율은 유지됐고 정지 상태 `.species-card-gloss`의 opacity는 0, 실행 애니메이션은 0이었다. 반사광 애니메이션 자체가 원인은 아니었다.

카드 높이가 늘어날 때 percentage gradient의 타원 중심·무늬가 다시 계산되는 것이 첫 원인이다. 기존 LC 배경에는 반복 방사형 무늬, 타원형 하이라이트, 선형 그라데이션이 함께 있다. 다른 등급도 같은 유형의 배경을 사용한다. 기존 TEST PC 배경 비교에서 채널 평균 차이 약 3.69/255, 최대 16/255가 측정됐다. 배경 크기만 고정하는 실험도 평균 약 1.53/255, 최대 13/255 차이가 남아 최종 수정으로 채택하지 않았다. 높이가 바뀌는 paint surface에서 브라우저가 gradient를 재래스터화하는 영향까지 분리해야 했다.

## 구현과 변경 전후

- `src/robingraph/api/static/chat.js`: 앞선 확대 수정의 닫힌 카드 기준 `fitHeight`를 소재 기준 높이로 CSS 변수에 전달한다. 숨긴 복제 카드에서 모든 details를 열어 최대 콘텐츠 높이를 측정하고, 너비·기준 높이가 같은 동안 캐시한다. 실제 카드의 토글·스크롤·이벤트 상태는 바꾸지 않는다. 측정 복제본은 즉시 제거한다.
- `src/robingraph/api/static/styles.css`: 모든 카드 등급에 공통 소재 `::before` 레이어를 만든다. 전체 상세 높이로 소재 레이어를 고정하고 해당 면 전체에 배경을 한 번 그린다. 카드의 overflow clip으로 레이어가 추가 스크롤 공간을 만들지 않도록 하고, isolation·paint containment·별도 합성 레이어로 토글에 따른 재래스터화 영향을 줄인다. 최대 콘텐츠 높이까지 소재를 표시하며 pointer-events none으로 드래그나 토글 클릭을 가로막지 않는다.
- `tests/frontend/chat_ui.test.js`: 토글 높이가 늘어도 소재 기준/paint surface 높이가 유지되는 검사 및 공통 팔레트 CSS 경로 검사를 추가했다.
- `docs/verification/assets/2026-10-10-card-material-stability.cjs`: 실제 원앙 API 프로필에서 팔레트 검사용 grade fixture를 파생해 PC/모바일의 배경 픽셀과 반사광 동작을 비교한다. PNG 필터를 복원한 실제 픽셀을 비교하며 단순 압축 파일/필터 scanline 비교를 사용하지 않는다.

변경 전에는 토글로 늘어난 카드에 맞춰 소재의 빛 무늬가 이동했다. 변경 후에는 토글 내용만 늘고 소재 기준은 유지된다. 화면 크기를 바꾸면 새 너비·기준 높이에 맞춰 측정한다. 카드 드래그의 `.species-card-gloss` 및 CR/EW/EX 프레임의 기존 foil 애니메이션은 유지한다.

## 로컬 검증 결과

- `node --test tests/frontend/*.test.js`: 298 통과, 실패 0, 건너뜀 0. Node의 DOM 모의 검사이며 실제 DB/API 검사로 표현하지 않는다.
- Chrome 소재 검사: 실제 TEST 원앙 프로필을 새로 조회하고 로컬 JS/CSS만 interception. 9 팔레트(LC/NT/VU/EN/CR/EW/EX/DD/미확인) × PC 1280×900·모바일 390×640 = 18 사례 통과, 실패 0, 건너뜀 0. grade를 바꾼 사례는 UI fixture이며 해당 종의 실제 평가 검증이 아니다.
- 최종 소재 픽셀은 18개 사례 모두 완전히 동일했다(최대·평균 차이 0). 앞선 tile 고정 실험에서는 채널 최대 1/255, 평균 약 0.000162/255가 남았지만, 최종 구현은 전체 고정 면에 배경을 한 번 그린다. 합성/반올림의 미세한 차이를 허용하기 위해 최대 1/255 및 평균 0.01/255 미만 기준을 사용했다. 허용 오차 기준과 실제 측정치 0을 구분한다. 소재 canvas 높이 유지 및 레이어가 실제 카드보다 긴 빈 스크롤 영역을 만들지 않는 검사도 통과했다. 토글 전후 정지 반사광 opacity 0 유지; 실제 PC 드래그 중 반사광 활성화 및 손을 뗀 뒤 0 복귀 통과.
- 확대 수정 회귀: TEST에서 이전에 실제 조회한 원앙·청둥오리·까치 프로필을 캐시 재사용하고 로컬 JS/CSS를 적용했다. 3종 × 6 PC/모바일/가로 뷰포트 = 18 사례, 실제 summary 클릭 60개 토글 검사 통과. 배율·너비 유지, 열린 내용 맨 아래 접근, 여러 토글 동시 열림, resize 및 닫힘 후 scrollTop 0 복귀를 확인했다. native PC 휠/모바일 CDP pan은 이전 도구의 동일 기준으로 실행했다. 결과 JSON에서 개별 실행 여부를 확인할 수 있다.
- 재현/로컬/회귀 JSON은 `docs/verification/assets/2026-10-10-card-material-{before,local,toggle-local}.json`에 저장했다. 스크린샷·API 임시 파일은 `/tmp/rg-material-*`에 있으며 저장소에 PNG를 추가하지 않았다.
- JS 문법 검사, git diff check 통과. `graphify update .` 실행 완료. SQL parser dependency 부재 등 기존 graphify 경고는 앱 오류와 구분한다.

## 배포와 기록

구현 및 검증 결과를 dev에 커밋·push한 뒤 TEST에 배포하고 실제 서버 검사를 수행한다. 이 절은 구현 커밋 시점의 계획이며, 배포가 끝난 뒤 아래에 실제 커밋·이미지·검증 결과를 추가한다. Production 재시작 및 DB 데이터 수정은 이번 작업 범위에 없으며 실행하지 않는다.

Obsidian `Work/RobinGraph/작업기록/2026-10-10-카드소재-토글반사무늬-안정화.md`에 최종 같은 본문을 저장하고 작업기록·프로젝트 index에 연결한다.

## 한계와 후속

모바일은 Chrome 에뮬레이션이며 실제 iPhone/Android 또는 Safari 실행 검증이 아니다. 토글을 열면 정보를 읽기 위한 내부 스크롤은 앞선 수정대로 유지한다. 소재 안정화 검사는 카드 렌더러를 직접 실행한 검사이며 질문 의도 분석 전체의 검사가 아니다. 보전 등급 데이터·체중 중복 등의 데이터/UI 문제는 별도 작업이며 이번에 변경하지 않았다.

## 첫 TEST 배포 후 시각 검토와 후속 수정

첫 구현 `a7f5e63e8df3efede882e00546e22c8688df02de`를 TEST 이미지 `robingraph-api:test-material-a7f5e63`로 배포했다. 기본 픽셀·배율 검사는 통과했으나, 실제 모바일 스크린샷을 열어 고정 소재 레이어가 긴 빈 스크롤 공간을 만드는 문제와 반복 tile 경계를 발견했다. 이 버전을 최종 완료로 안내하지 않았다.

후속으로 공통 카드에 `overflow: clip`을 적용해 소재가 카드 안에서만 표시되게 했고, 반복 tile 대신 고정 최대 면 전체에 배경을 그려 경계를 없앴다. 브라우저 도구에 소재 canvas 높이 유지와 `scrollHeight <= max(clientHeight, 실제 카드 높이) + 3px` 검사를 추가했다. 이 검사 없이 픽셀 비교만으로 스크롤 영역 정상 여부를 판단할 수 없다는 점을 기록한다. 후속 로컬 소재 18사례·배율 회귀 18사례 및 Node 298 검사를 재실행해 통과했고, 모바일 펼친 화면을 직접 열어 빈 공간 제거를 확인했다. 이 후속 수정까지 TEST에 다시 배포한 최종 정보는 아래 추가한다.

## 최종 NAS TEST 배포

후속 수정 커밋 `3ac07e2dedf3d3f69d99ae2b9ba76b2f4406bcc2`를 dev에 커밋하고 origin/dev에 push했다. 아래는 계획이 아닌 실제 NAS 결과다.

- TEST: https://robingraph-test.dove-nest.com/chat
- 최종 이미지: `robingraph-api:test-material-3ac07e2`.
- 실제 이미지 ID: `sha256:48e0e1114825b92be81dd870ae36910792addb8dbe51e3e0947b58c602eb9edc`, OCI revision은 후속 커밋과 일치.
- 컨테이너 `robingraph-api-test` healthy, 재시작 0, 시작 시각 `2026-10-10T02:53:56.57792025Z`(한국 시간 11:53:56).
- 릴리스 `/home/kimdove/RobinGraph-material-3ac07e2`, SSH stdin 전송 archive SHA-256 `fa00c125f8c98153f31a3ed4586be6ca77db1970615e5cf1713a24ca2cb7543f`를 NAS에서 확인 후 추출했다.
- 기존 TEST 환경 파일을 복사하고 이미지 태그만 바꿨다. PG DB `robingraph_test` 및 deploy target test를 확인했다. 표준 `deploy_nas.sh preflight`, `deploy`(내부 build 포함), `verify` 모두 통과했다. DB 마이그레이션·수집 작업은 실행하지 않았다.
- Production은 이미지 `robingraph-api:prod-card-photo-a2c8bcc`, ID `sha256:6d98571a254d1e686f11fc8a4b197da87b2b40ee449c9746a33ce9141d32ede2`, 시작 시각 `2026-10-09T13:53:00.901732645Z`, healthy·재시작 0으로 두 번의 TEST 배포 전후 동일했다.
- 최종 실제 TEST JS/CSS의 SHA-256이 로컬 파일과 일치했다. 직접 Python urllib 조회는 HTTP 403으로 거절됐으며 Chrome/Playwright request 경로로 다시 받아 검증했다. 성공한 비교 결과는 `…-asset-hashes.json`에 기록했다. 인증 정보는 기록하지 않는다.

## 최종 실제 TEST 브라우저 결과

최종 TEST API 프로필을 새로 조회하고 실제 배포된 JS/CSS를 사용했다. 로컬 interception이나 이전 프로필 캐시는 사용하지 않았다.

- 소재 검사 18사례 통과, 실패 0, 건너뜀 0. 17사례는 배경 픽셀 완전 동일, 나머지 NT PC 사례는 최대 채널 차이 1/255·평균 약 0.00002315/255로 사전 기준 이내다. 기존 LC처럼 타원/무늬가 이동하는 현상과 구분한다. 소재 canvas 높이 유지, 레이어로 인한 빈 스크롤 공간 없음, 정지 반사광 opacity 0 및 PC 실제 드래그 반사광 활성화·복귀 통과. 원앙 실제 API를 기반으로 한 다른 grade 사례는 팔레트 fixture다.
- PC/모바일/가로 18사례·실제 summary 클릭 60개 토글 회귀 검사 통과, 실패 0, 건너뜀 0. 확대 방지, 배율·너비 유지, 다중 토글/resize, 내용 끝 접근 및 모두 닫은 뒤 무스크롤 복귀를 확인했다. 첫 토글 native 입력은 PC 휠/모바일 CDP pan으로 총 16사례 실행했고, 2사례는 전체 내용이 이미 화면에 들어와 입력이 필요하지 않았다. page error 0.
- 실제 최종 모바일 펼친 화면의 스크린샷은 `/tmp/rg-material-toggle-final-deployed/`에 있다. 로컬 최종 화면도 직접 열어 소재 반복 경계와 하단 빈 공간 제거를 확인했다. 결과 JSON은 `…-deployed.json`, `…-toggle-deployed.json`에 저장했다.
- 최종 상세 문서와 검증 JSON은 별도 문서 커밋으로 dev에 push한다. Obsidian에는 같은 본문을 저장하고 전체 읽기로 일치를 확인한다. 최종 앱 revision은 `3ac07e2`이며 문서 커밋 때문에 앱을 다시 배포하지 않는다. 운영 반영은 사용자 승인 후 별도로 수행한다.
