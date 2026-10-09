# RG-405 후속 — 모바일 터치로 조류 카드 뒤집기

작업일: 2026-10-08 KST. 구현 커밋: `a2a9bad62ee70426b6947b639a7f09e01d2c7e93`. 배포 대상: NAS TEST.

## 요청 배경과 목표

사용자가 “모바일에는 적용 안되어있는거 같은데 모바일 환경에도 적용해줘”라고 요청했다. 직전 RG-405는 마우스 드래그가 기본 범위였고, 320·390px 검증도 작은 화면에서 **마우스**를 사용한 시험이었다. 실제 손가락 스와이프를 지원하거나 검증한 것으로 볼 수 없었다. 이번 후속 작업은 터치 입력을 지원하고 세로 스크롤·확대·기존 버튼·사진 조작을 유지하는 것이다.

RG-202 HippoRAG, RG-406 한국 서식 토글과 기존 최후순위 보류 작업은 수행하지 않았다. 최초 RG-405·RG-602 결과는 [직전 작업 기록](2026-10-08-rg015-rg016-trace-tags-drag.md)에 당시 범위대로 보존했다.

## 원인과 변경 전후 근거

기존 `buildSpeciesCard`의 pointerdown은 `pointerType === "mouse"`만 받았다. 모바일에서 화면이 작아지는 것과 터치 입력을 받는 것은 별개의 조건이다. CSS에 터치 제스처 방향을 선언하지 않아 브라우저의 기본 제스처 판정도 적용됐다.

실제 변경 전 NAS TEST를 Chrome 모바일 에뮬레이션에서 열고 CDP `Input.dispatchTouchEvent`로 수평 이동했다. `isTrusted=true`, `pointerType=touch`인 pointerdown/move 이후 pointercancel이 발생했고 뒷면은 표시되지 않았다. 계산된 `touch-action`은 `auto`였다. [변경 전 증거](assets/2026-10-08-RG015-mobile-before.json).

변경 후에는 primary 한 손가락의 수평 스와이프가 카드 앞·뒷면을 전환한다. 세로 이동은 브라우저 스크롤에 맡기고 두 번째 터치가 들어오면 카드 제스처를 취소한다. `pan-y pinch-zoom`을 CSS에 미리 선언했다. 제스처 시작 전에 `touch-action`으로 직접 조작 정책을 선언해야 한다는 근거는 [W3C Pointer Events 명세](https://www.w3.org/TR/pointerevents3/#the-touch-action-css-property)를 따른다.

## 변경 파일과 구현

| 파일 | 구현 내용 |
| --- | --- |
| `src/robingraph/api/static/chat.js` | primary 한 손가락 터치 지원, 축 판정·임계값·취소·선택·capture·후속 click 정리, 모바일 안내 영역 생성 |
| `src/robingraph/api/static/styles.css` | `touch-action: pan-y pinch-zoom`, coarse pointer에서 너비 전체·최소 높이 44px의 스와이프 안내 |
| `tests/frontend/chat_ui.test.js` | 터치 상태 전환·취소·제외 영역·리스너 해제·빠른 연속 제스처·동작 줄이기 모의 회귀 검사 |
| 이 문서 및 `docs/verification/assets/2026-10-08-RG015-mobile-*` | 원인, 검증 단계별 결과와 화면 증거 |

터치는 카드 본문 글자 위에서도 시작할 수 있다. 마우스는 기존 빈 영역 시작 규칙을 유지해 텍스트 선택을 보존했다. 버튼·링크·summary·입력·사진·미디어·편집 가능 요소·native draggable 요소 등은 시작 대상에서 제외했다. 펜은 이번 지원 대상에 포함하지 않았다.

터치 이동의 slop은 10px이며 가로 이동량이 세로의 1.2배 이상일 때 수평으로 판정한다. 전환 기준은 `max(40px, 카드/팝업 폭의 25%)`이고 해제 시 순이동량으로 결정한다. 짧게 움직이거나 되돌아온 이동·탭은 원래 면에 머문다. 움직임 줄이기에서는 연속 회전 없이 기존 전환 결과를 유지한다.

터치 down/move에 preventDefault를 호출하지 않으며, 브라우저의 implicit pointer capture를 사용한다. 추적한 pointer의 cancel/capture 상실, 다른 pointer 추가, selection/contextmenu, blur/resize, 닫기·다시 열기·대화 초기화에서 임시 스타일과 리스너를 정리한다. 터치의 buttons=0을 마우스 버튼 해제로 오인하지 않는다. 터치 후 400ms click 억제에는 generation을 적용해 이전 타이머가 다음 스와이프의 억제를 해제하지 않게 했다.

## 협업과 검토

실제 Orca run `run_bfb68f6544af`에서 Claude가 UI·CSS·회귀 테스트를 구현하고 Antigravity가 독립적으로 읽기 전용 검토를 수행했다. Codex는 통합 검토, 실제 브라우저 입력·NAS 배포·문서·Git을 담당했다. 런타임의 모델 필드가 null이므로 두 워커의 실제 모델명은 확인되지 않았다.

통합 검토에서 터치 implicit capture 상실 처리와 이전 click 억제 타이머의 경쟁 가능성을 찾아 원래 구현 담당자에게 전달했다. 담당자가 두 항목을 수정하고 회귀 테스트를 추가한 최종 소스를 검증했다.

Antigravity의 최종 읽기 전용 검토는 위 구현 커밋의 touch-action·축 판정·pointer ID·멀티터치·click 가드·기존 마우스 선택 동작을 확인하고 추가 차단 결함 없이 승인했다. 프런트엔드 193개 통과와 root의 실제 NAS 브라우저 결과를 검토했으며, 실제 CDP/NAS 입력 시험 실행 주체는 root다. 물리 단말기·Safari 검증은 이 승인으로 대체하지 않는다. 원본 워커 보고서는 `/tmp/rg015-mobile-review.md`이며 이 문단에 검토 요지를 영구 기록했다. 두 워커는 완료 결과 수락 후 release했고 reclaimable worker 0개를 확인했다.

## 검증 범위와 실제 결과

### 구문·모의 프런트엔드 회귀

- `node --check src/robingraph/api/static/chat.js`: 통과.
- `node --check tests/frontend/chat_ui.test.js`: 통과.
- `node --test tests/frontend/*.test.js`: **193 통과, 0 실패, 0 건너뜀**. root 재실행 결과도 동일하다.
- 테스트의 fake DOM·synthetic pointer event는 로직과 리스너 정리를 검증한다. 이 193개를 실제 모바일 브라우저 시험으로 표현하지 않는다.

변경은 JS/CSS 및 프런트엔드 테스트에 한정됐다. Python 전체·Neo4j/PostgreSQL 전체 회귀는 이번에 재실행하지 않았다. 직전 633개 통과는 직전 작업의 결과이며 이번 수치에 합산하지 않는다. 실제 NAS API/DB 확인은 아래 브라우저 시험에서 별도로 수행했다.

### 배포 전 실제 브라우저 입력

실제 NAS API 응답을 사용하되 JS/CSS 요청만 로컬 수정 파일로 대체했다. 320·390·768px와 390px 움직임 줄이기, **4개 설정 모두 통과**했다. 이는 배포 전 기능 검사이며 NAS에 새 파일이 반영됐다는 증거로 사용하지 않았다. [로컬 자산 대체 결과](assets/2026-10-08-RG015-mobile-local-assets.json).

### 실제 NAS TEST 자산·API·DB를 사용한 터치 검사

배포 후에는 JS/CSS 요청 대체 없이 `https://robingraph-test.dove-nest.com/chat`을 열었다. “청둥오리에 대해 알고 싶어” 요청의 실제 `/v1/chat` 응답과 도감 팝업을 사용했다. Chrome Pixel 7 모바일 에뮬레이션에 CDP touch 입력을 보내 `isTrusted=true`인 touch pointer 이벤트를 확인했다. DOM pointer 이벤트만 직접 dispatch한 시험과 구분한다.

| 설정 | 본문·하단 안내의 좌우 스와이프 | 실제 세로 scrollTop 변화 | 취소·두 번째 터치·닫기/재열기·버튼 | 연속 회전 |
| --- | --- | --- | --- | --- |
| 320px | 통과 | 0 → 42 | 통과 | 적용 |
| 390px | 통과 | 0 → 50 | 통과 | 적용 |
| 768px | 통과 | 0 → 89 | 통과 | 적용 |
| 390px, 움직임 줄이기 | 통과 | 0 → 50 | 통과 | 억제 |

모든 설정에서 짧은 이동·역방향 복귀·탭은 뒤집지 않았으며, 안내 영역 높이 44px 이상, 계산된 `touch-action: pan-y pinch-zoom`, 수평 페이지 넘침 없음, pageerror 0을 확인했다. 390px에서 native pinch 입력 후 `visualViewport.scale`이 **1 → 약 1.50**으로 증가했고 앞면 상태를 유지했다. 확대 후 후속 테스트 좌표를 위해 에뮬레이터 배율을 1로 복원한 단계는 시험 준비 동작이다. [배포 후 터치 결과](assets/2026-10-08-RG015-mobile-browser.json).

### 기존 조작 회귀

1280px 일반·움직임 줄이기에서 실제 Playwright 마우스로 좌우 드래그·짧은 이동 복귀·텍스트 선택·Escape 닫기/재열기·Enter/Space 버튼 조작을 확인했다. blur/resize/pointercancel 경로는 DOM 이벤트로 발생시켜 정리 상태를 검사했다. **2개 설정 모두 통과**, 수평 넘침 없음, pageerror 0. [데스크톱 결과](assets/2026-10-08-RG015-mobile-mouse-browser.json).

390px 실제 NAS UI에서 사진 위 수평 터치가 카드를 뒤집지 않음, ‘다음 사진’ 터치로 보이는 figure가 0번에서 1번으로 변경, 긴 누름 후 뒤집힘 없음, 대화 초기화로 팝업·카드 제거를 확인했다. 사진은 외부 제공자 로딩이 포함되므로 이미지 바이너리의 로딩 완료를 합격 조건으로 삼지 않았다. 긴 누름에서 실제 selection/contextmenu가 발생하지 않았으므로 이 결과로 모바일 native 텍스트 선택 UI가 검증됐다고 주장하지 않는다. 해당 취소 로직은 모의 회귀 검사 범위다. [기존 터치 조작 결과](assets/2026-10-08-RG015-mobile-controls.json).

### 초기 검증 실패와 정정

로컬 CSS 대체 URL 패턴이 실제 자산 요청을 놓쳐 첫 계산값 검사가 auto로 실패했다. 쿼리 접미사까지 포함하도록 검증기의 요청 패턴을 수정하고 재실행했다. 두 손가락 입력으로 실제 확대된 뒤 Playwright locator tap 좌표가 어긋난 검사도 배율을 복원하도록 정정했다. 사진 전환은 제공자 오류 문구가 같을 수 있어 caption text 비교 대신 실제 표시 figure의 인덱스를 비교했다. 모두 시험 도구의 가정을 정정한 사항이며 제품 코드의 검사를 생략한 것이 아니다. 최종 프런트엔드·배포 후 브라우저 결과에는 실패·건너뜀이 없다.

## 화면 확인

[320px](assets/2026-10-08-RG015-mobile-320.png), [390px](assets/2026-10-08-RG015-mobile-390.png), [768px](assets/2026-10-08-RG015-mobile-768.png), [390px 움직임 줄이기](assets/2026-10-08-RG015-mobile-390-reduced.png). 저장된 320px 화면에서 본문·사진·한국어 스와이프 안내가 팝업 폭 안에 표시되는 것을 직접 확인했다.

## 배포·커밋·지식 그래프

- 구현 커밋: `a2a9bad62ee70426b6947b639a7f09e01d2c7e93`.
- 패키지 SHA256: `85d8791bedb3421f641eba7afa510585f0596ce3ac97f095ff5ad0ddbcf5bd96`.
- NAS TEST 이미지: `robingraph-api:test-rg015mobile-a2a9bad`.
- 릴리스 경로: `/home/kimdove/RobinGraph-rg015mobile-a2a9bad`.
- 이전 이미지: `robingraph-api:test-rg015016-75377ca`. 기존 릴리스를 보존했다.
- `ROBINGRAPH_DEPLOY_TARGET=test`로 deploy 및 verify를 실행했다. API healthy, health status ok·mode neo4j·deployment_target test를 확인했다. 이미지 OCI revision도 구현 커밋과 일치했다. PROD는 배포하지 않았다.
- `graphify update .` AST 갱신 완료: 3,659 nodes·7,935 edges·214 communities. SQL 파서 미설치 경고와 무심벌 파일 안내는 남았으며 의미 추출 API는 호출하지 않았다. 생성물은 기존 Git 추적 정책을 따른다.

문서·증거의 커밋은 구현 커밋 다음에 분리하며 `dev`로 함께 push한다. 배포된 코드의 기준은 위 구현 커밋이다.

## 사용법·남은 한계와 후속

모바일에서 페이지를 새로고침하고 도감 카드를 연 뒤 본문 또는 하단의 “카드를 좌우로 밀어 뒤집어 보세요” 영역을 좌우로 민다. 사진·버튼·출처 링크에서 시작하는 제스처는 뒤집기에서 제외된다. 기존 ‘출처 보기/앞면 보기’ 버튼도 사용할 수 있다.

이번 실제 터치 입력 시험은 Chrome 모바일 에뮬레이션이다. 물리 Android·iPhone/iPad와 Safari/WebKit·Firefox는 미검증이며 완료 범위로 적지 않는다. 긴 누름의 실제 선택 핸들·운영체제 context menu, assistive technology와 펜 동작도 별도 기기 검증이 필요하다. 카드 내부 가로 native pan은 pan-y 선언에 의해 제한된다.

Obsidian에는 `Work/RobinGraph/2026-10-08-RG015-모바일터치스와이프-NAS-TEST배포.md`로 같은 핵심 구현·검증·배포·한계를 기록하고 백로그 RG-405 상세·현황·변경 이력, 프로젝트 index를 연결했다. 세 문서를 저장 후 다시 읽어 내용 일치를 확인했다. RG 상세 ID 17개가 각각 한 번 존재하고 모든 내부 제목 링크가 유효한지, RG-102·RG-503·RG-504·RG-505·RG-202·RG-406의 기존 상세 본문이 보존됐는지 확인했다. 완료 수와 남은 작업의 대기·보류 설정은 유지했다. 이전 문서의 당시 마우스 전용 범위와 테스트 수치는 역사 기록으로 남겼다.
