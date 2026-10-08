# RG-015 후속 — 회전 각도를 따라 움직이는 유광 반사광

작업일: 2026-10-08 KST. 구현 커밋: `f8a3771e3fab1ff98dd0b22cf51629d534ba4ed6`.

현재 상태: **구현·프런트엔드 및 로컬 자산 브라우저 검증 완료, NAS TEST 배포 대기**. 새 코드는 `origin/dev`에 push했다. NAS SSH 연결이 거부되어 새 릴리스의 업로드·이미지 빌드·컨테이너 교체·배포 후 검증은 수행하지 못했다.

## 요청 배경과 목표

사용자는 유광 소재의 실물 카드처럼 카드를 넘기는 각도에 따라 빛이 따라 움직이기를 요청했다. 마우스·모바일 스와이프를 되돌리면 반사광도 함께 되돌아가고, 앞·뒷면 및 기존 버튼/키보드 뒤집기에도 같은 표현을 적용하는 것이 목표다. 이전 답변은 효과 이해를 확인한 것이며 구현 착수는 사용자의 후속 “진행중이야?” 요청을 받은 뒤 시작했다.

직전 [모바일 터치 작업](2026-10-08-rg015-mobile-touch-swipe.md)의 입력 정책과 기존 카드 접근성을 유지한다. RG-014·RG-017 및 최후순위 보류 작업은 수행하지 않았다.

## 확인한 원인과 변경 전후

기존 CSS는 `.species-popup[data-flipping="true"]::after`에 고정된 대각 gradient를 두고 `species-flip-glint`로 opacity만 660ms 동안 변화시켰다. 카드 각도와 빛의 위치를 연결하지 않아 드래그 중에는 빛이 이동하지 않았고, 짧은 드래그 복귀와 버튼의 두 회전 단계에도 개별 동기화가 없었다.

변경 후에는 `.species-card` 안의 `.species-card-gloss`가 현재 회전 각도에 따라 반사광의 위치·강도를 바꾼다. 기존 opacity-only popup 효과는 제거했다. 별도의 idle 애니메이션이나 자동 반복 sweep은 없다.

## 변경 파일과 구현 내용

| 파일 | 내용 |
| --- | --- |
| `src/robingraph/api/static/chat.js` | 반사광 overlay 생성, 각도에 따른 위치·강도, 드래그·복귀·전환·버튼 애니메이션과 동기화, 취소/초기화 정리 |
| `src/robingraph/api/static/styles.css` | 기존 popup glint 제거, 카드에 붙는 밝은 중심·부드러운 가장자리와 넓은 반사층, 비조작 영역·reduced-motion 처리 |
| `tests/frontend/chat_ui.test.js` | 각도·대칭·복귀 시작점·동일 timing·정리·터치·강도·0도 교차의 모의 회귀 검사 10개 추가 |
| 이 문서와 `docs/verification/assets/2026-10-08-RG015-gloss-*` | 실제 실행 범위, 화면·검증 결과·배포 대기 근거 |

위치는 `50 + angle / 90 × 30` 퍼센트로 계산해 각도에 비례한다. 양수·음수 회전과 되돌아오는 이동에 따라 위치가 반대로 변한다. 강도는 `(abs(angle) / 90)^0.6 × 0.95`로 정면에서 0이며 20~35도에서도 반사광이 보이도록 했다. 21.6도에서 약 0.404, 9.6도에서 약 0.248이다. 이 값은 물리 기반 재질 렌더링의 측정치가 아니라 현재 카드 표현을 위한 UI 파라미터다. 배경이 카드보다 큰 CSS gradient이므로 background-position 값 증가를 실제 화면상의 ‘오른쪽 이동’과 동일시하지 않는다.

반사광은 `aria-hidden=true`, `pointer-events:none`인 카드의 마지막 자식이다. 카드 안에서 absolute inset과 border-radius를 적용해 텍스트·사진 위를 덮지만 클릭/터치를 받지 않는다. 팝업의 바깥 금속 테두리는 효과 대상에 포함하지 않는다. 기존 색상·도감 정보 구조·사진·출처 링크는 유지했다.

드래그 중에는 카드와 같은 angle로 즉시 갱신한다. 놓을 때는 현재 angle에서 시작하는 반사광 keyframe을 카드의 WAAPI와 동일한 duration/easing/fill로 실행한다. 짧은 이동 복귀는 200ms, 버튼의 나가는 단계는 270ms, 들어오는 단계는 390ms다. 드래그 완료의 첫 단계는 남은 회전량에 따라 시간을 줄인다. 버튼의 0.82 offset에서의 작은 반동도 공유한다.

강도 곡선은 비선형이라 각 구간을 4개로 나눈 keyframe으로 근사하고, 위치와 각도는 같은 진행률로 유지한다. -90도→+5도처럼 정면을 통과하는 구간에는 정확한 0도 keyframe을 추가했다. 따라서 해당 순간의 위치는 50%, 강도는 0이고 기존 순서·offset·easing은 유지한다. 취소·capture 상실·blur/resize·닫기/재열기·대화 초기화에서 inline 강도와 위치, 진행 중 반사광 애니메이션을 해제한다. 새 전역 이벤트 리스너나 상시 requestAnimationFrame은 추가하지 않았다.

‘동작 줄이기’에서는 움직이는 반사광을 `display:none`으로 숨기며 드래그의 반사광 갱신을 건너뛴다. 기존 즉시 앞·뒷면 전환과 버튼·키보드 사용은 유지한다.

## 협업과 수정 이력

Orca run `run_0c10f54dd3b5`에서 Claude가 UI/CSS/테스트를 구현하고 Antigravity가 읽기 전용 독립 검토를 맡았다. Codex는 원인·상태/보간 검토, 실제 Chrome·CDP 입력과 화면 확인, 패키지·NAS 시도, 문서·Git을 담당했다. 워커의 모델 필드가 null이므로 실제 실행 모델명은 확인하지 않았다.

최초 구현의 모의 테스트 200개가 통과했지만 root 화면 검토에서 반사광이 너무 약해 원래 담당자에게 강도·빛 띠 조정을 다시 배정했다. 조정 단계는 202개 통과였다. 이후 버튼의 들어오는 회전이 정면을 통과할 때 비선형 강도가 0이 되지 않는 보간 문제를 root가 찾아 원래 담당자에게 수정하도록 했다. 정확한 0도 keyframe과 양방향 회귀 검사를 추가한 최종 결과는 203개 통과다.

초기 독립 검토 보고서는 200개 단계의 원본 수치만 설명했으므로 최종 승인으로 사용하지 않고 후속 독립 검토를 배정했다. Antigravity는 최종 소스·203개 검사와 root의 실제 브라우저 증거를 다시 검토하고 추가 차단 결함 없이 승인했다. 최종 보고서는 `/tmp/rg015-gloss-review-final.md`다. 실제 브라우저/CDP 입력은 root가 실행하며 검토자가 실행한 것으로 바꾸어 기록하지 않는다. 완료된 워커는 후속 Dispatch 재사용 또는 release로 정산했고 reclaimable worker 0개를 확인했다.

## 실제 검증 결과

### 구문과 모의 프런트엔드 검사

- `node --check src/robingraph/api/static/chat.js`: 통과.
- `node --check tests/frontend/chat_ui.test.js`: 통과.
- `node --test tests/frontend/*.test.js`: **203 통과, 0 실패, 0 건너뜀**. 기존 193개와 새 유광 관련 10개다. root의 최종 재실행 결과도 동일하다.
- fake DOM과 stub animate가 논리·keyframe·CSS 계약·cleanup을 검증하며 실제 합성/GPU/물리 기기를 검증한 것은 아니다.
- 변경은 JS/CSS와 프런트엔드 테스트에 한정되어 Python 전체 및 Neo4j/PostgreSQL 전체 회귀는 재실행하지 않았다. 직전 작업의 633개 결과를 이번 실행 수치로 합산하지 않는다.

### 실제 Chrome에서 로컬 수정 자산을 적용한 검사

실제 NAS TEST의 `/v1/chat` API/DB 응답을 사용하되 `/static/chat.js`와 CSS만 로컬 수정 파일로 대체했다. 따라서 아래 결과는 **실제 브라우저 동작 검증이며 NAS에 새 파일이 배포됐다는 증거는 아니다**. 물리 모바일 기기도 아니다.

| 검사 | 실행 환경 | 결과 |
| --- | --- | --- |
| 반사광 각도·역방향·짧은 복귀·앞/뒷면·취소·버튼 두 단계 | 1280px Chrome 마우스, 390px Pixel 7 CDP touch | 2개 설정 통과 |
| 반사광 숨김·즉시 스와이프/버튼 전환 | 390px, reduced-motion | 통과 |
| 기존 터치 스와이프·세로 스크롤·멀티터치·닫기/재열기·버튼 | 320·390·768px 및 390px reduced-motion | 4개 설정 통과 |
| 기존 마우스 드래그·텍스트 선택·Enter/Space·Escape·정리 | 1280px 일반/reduced-motion | 2개 설정 통과 |
| 사진 위 터치 제외·다음 사진·긴 누름 미뒤집힘·대화 초기화 | 390px 터치 | 통과 |

반사광의 실제 계산값은 ±21.6도에서 background-position **57.2% / 42.8%**, opacity **0.404**, 되돌린 9.6도에서 **53.2% / 0.248**였다. 짧은 복귀는 놓은 위치에서 시작하며 카드·반사광의 duration/easing이 같았다. 버튼의 나가는/들어오는 실제 WAAPI timing도 각각 270/390ms로 일치했다. 이는 브라우저 timeline을 pause/currentTime/finish로 표본 추출한 검사이므로 실제 시간의 프레임 속도 성능 시험으로 표현하지 않는다.

버튼이 정면을 통과하는 offset `0.82 × 90 / 95 = 0.7768421052631578`에서 easing을 역산해 실제 브라우저 시간축을 표본 추출했다. 1280·390px 모두 계산된 위치 **50%**, opacity **약 1.63e-10(사실상 0)**를 확인했다. 정리 후 반사광 animation 0개·opacity 0, 기존 popup ::after 제거, 페이지 가로 넘침 없음, pageerror 0을 확인했다. [반사광 브라우저 결과](assets/2026-10-08-RG015-gloss-local-reflection.json).

세로 스크롤은 실제 touch 입력 후 scrollTop **0→20/50/89/50**, 390px pinch 확대는 visualViewport scale **1→약 1.50**이었다. CSS `pan-y pinch-zoom`과 native 제스처를 유지했다. [터치 회귀 결과](assets/2026-10-08-RG015-gloss-local-touch.json), [마우스 회귀 결과](assets/2026-10-08-RG015-gloss-local-mouse.json).

사진 ‘다음’ 버튼으로 보이는 figure가 0에서 1로 바뀌고 사진 위 터치가 카드를 뒤집지 않는 것을 확인했다. 외부 이미지 파일의 완전 로딩은 합격 조건에 포함하지 않았다. 긴 누름은 미뒤집힘만 확인했으며 에뮬레이터에서 실제 selection/contextmenu가 발생하지 않아 운영체제의 선택 핸들·메뉴까지 검증됐다고 주장하지 않는다. [기존 터치 조작 결과](assets/2026-10-08-RG015-gloss-local-controls.json).

### 초기 검증 도구 정정

첫 모바일 검사에서 한 번의 큰 CDP 이동 직후 CSS를 읽으면 브라우저의 coalesced pointermove 반영을 기다리지 못했다. 이어서 스크린샷을 저장할 때도 마지막 이동과 해제 시점 사이 값이 달라 초기 복귀 시작점 검사가 실패했다. 입력을 여러 단계로 나누고 두 requestAnimationFrame 후 값을 읽도록 검사기의 입력/표본 추출을 수정했다. 최종 동일 조건을 재실행해 통과했으며 제품 코드의 pointer 처리를 임의로 우회하지 않았다. 초기 모의 200→202→203개는 단계별 통과 수이고 최종 수치는 203개다.

## 화면 확인

다음은 실제 NAS API와 **로컬 자산 대체**로 렌더링한 최종 화면이다. root가 1280px·390px 앞·뒷면을 직접 보고 반사광의 밝기·텍스트 가독성과 표면 범위를 확인했다.

- [1280px 앞면 회전](assets/2026-10-08-RG015-gloss-local-1280-right.png)
- [390px 앞면 양수 회전](assets/2026-10-08-RG015-gloss-local-390-right.png)
- [390px 앞면 음수 회전](assets/2026-10-08-RG015-gloss-local-390-left.png)
- [390px 뒷면](assets/2026-10-08-RG015-gloss-local-390-back.png)

## Git·패키지·NAS 상태

- 구현: `f8a3771e3fab1ff98dd0b22cf51629d534ba4ed6`, `origin/dev` push 완료.
- 소스 패키지 SHA256: `7a19864a029cfc632658282ae68cc681bfcc496063ccc103265a777dbab7b384`.
- 예정 이미지: `robingraph-api:test-rg015gloss-f8a3771`.
- 예정 릴리스: `/home/kimdove/RobinGraph-rg015gloss-f8a3771`.
- 이전 TEST 이미지: `robingraph-api:test-rg015mobile-a2a9bad`. 작업 초기에 이 이미지와 healthy 상태를 확인했다.
- 배포 시도는 SSH에서 `Connection refused`로 실패했다. 아카이브 업로드 이전 연결 단계이며 새 이미지 build·deploy·verify·OCI revision 검사·배포 후 브라우저 검증은 **미실행**이다. 원격의 새 환경변수 파일도 생성하지 않았다. 사용자에게 SSH 재개를 요청했다. PROD는 배포하지 않았다.
- `graphify update .` AST 갱신 완료: 3,680 nodes·7,962 edges·200 communities. SQL 파서 미설치 등의 기존 경고는 남았으며 의미 추출 API는 호출하지 않았다. 그래프 생성물은 기존 추적 정책을 따른다.

## 남은 한계와 후속

NAS SSH가 다시 열리면 준비한 소스 패키지를 TEST에 배포하고 실제 서버 JS/CSS로 반사광·터치·기존 조작을 다시 검사한다. 그 전까지 테스트 웹사이트는 새 효과가 배포된 것으로 안내하지 않는다.

현재 물리 Android·iPhone/iPad·Safari/WebKit·Firefox·스크린 리더·펜은 미검증이다. 이미지 외부 제공자 로딩과 실제 긴 누름 선택 UI도 이번 합격 범위에 포함하지 않았다. 반사광은 시각 효과이며 물리 재질의 정확한 반사/광원 계산은 아니다. 성능은 idle animation/RAF가 없음을 확인했으나 FPS·배터리·저사양 기기 장시간 수치는 측정하지 않았다.

Obsidian 기록은 `Work/RobinGraph/2026-10-08-RG015-회전연동-유광반사광.md`로 저장하고 RG-015 후속 상세·현황·변경 이력과 프로젝트 index에 연결했다. 핵심 구현·실제 검증·배포 대기 상태를 이 문서와 일치시켰다. 저장한 세 문서를 다시 읽어 내용 일치, RG 상세 ID 17개의 유일성, 모든 제목 링크 대상, 대기·보류 RG-002·RG-010·RG-011·RG-012·RG-014·RG-017 상세 보존을 확인했다. 큰 백로그의 전체 요청은 MCP HTTP 413으로 거부되어 정확히 일치하는 부분 치환으로 나눠 저장하고 전체 결과를 재조회했다. 이전 모바일 배포 완료 기록은 당시 결과로 보존했다.
