# RG-405 후속 — PC 카드 전체 표면에서 드래그 뒤집기

작업일: 2026-10-08 KST. 구현 커밋: `719e5bcf44e920a5cb9a3d8639279bd1f7b3d066`.

## 요청 배경과 목표

사용자가 PC에서 카드 앞·뒷면을 잘 넘길 수 없다고 제보한 뒤 카드 전체 영역에서 넘길 수 있게 요청했다. 카드의 제목·본문·중첩 글씨·사진·장식·빈 표면에서 마우스 드래그를 시작하도록 확대한다. 버튼·링크·출처 펼치기·입력 등의 클릭 기능과 이전의 글씨 선택 차단, 모바일 터치 정책은 유지한다.

## 원인과 재현 근거

이전 구현의 `isDragExempt`는 마우스 입력을 카드 자체와 지정된 layout class에서만 허용하고 p·dd·h3·span·사진 등은 제외했다. 직전 작업은 CSS로 글씨 선택만 차단했으므로 이 시작 범위 제한이 남아 있었다. 카드의 넓은 사진·본문 영역에서 드래그하면 이벤트가 시작되지 않아 빈 테두리를 찾아야 했다.

실제 NAS TEST `570fd3f`·Chrome 1280px에서 앞면 제목과 뒷면 h3에 카드 폭 38%만큼 마우스를 이동했다. 두 경우 모두 data-dragging이 없고 앞·뒷면이 바뀌지 않았다. [수정 전 실제 재현](assets/2026-10-08-RG015-pcdrag-before.json).

## 변경 전후와 구현 파일

- `src/robingraph/api/static/chat.js`: PC의 layout class 허용 목록과 관련 미사용 helper를 제거하고 일반 본문 및 중첩 요소에서 시작하도록 했다. PC는 img/picture/canvas/svg 및 role=img도 허용한다. 부모를 따라 올라가 button/a/summary/input/select/textarea/label/video/audio·편집 영역·명시적 draggable·role button/link/textbox가 있는 경우 계속 제외한다. 모바일은 사진·그림 시작 제외를 유지한다.
- 사진의 브라우저 native drag가 카드 드래그 활성화 전에 시작할 수 있어, 추적 중인 mouse gesture에서는 pending 단계의 dragstart도 preventDefault한다. 드래그 외부와 조작 요소의 native drag는 가로채지 않는다.
- `src/robingraph/api/static/styles.css`: PC 본문의 cursor:auto 예외를 제거해 카드 표면에 grab, 진행 중에는 grabbing을 보여 준다. 버튼·링크의 기존 pointer와 글씨 선택 금지는 유지한다.
- `tests/frontend/chat_ui.test.js`: 과거 ‘마우스 글씨 시작 거부’ 기대를 새 정책으로 갱신했다. 양면·양방향·중첩 글씨·reduced-motion, 사진/장식의 PC 허용과 touch 제외, 중첩 조작 예외와 pending native drag를 보강했다.
- PC 안내를 ‘카드의 사진·글씨·빈 곳을 좌우로 끌어 뒤집어 보세요’로 바꿨다.

회전 임계값·애니메이션·유광 수식·pointer capture·취소/정리·native 스크롤/확대 정책은 변경하지 않았다. 버튼·링크 등 조작 요소 자체에서 시작한 드래그는 제외하므로 해당 요소의 클릭과 키보드 기능을 보존한다.

## 협업

`pc_card_drag_fix`가 UI/CSS·테스트 구현과 전체 frontend 검사를 담당했다. `card_selection_review`는 읽기 전용 독립 diff 검토로 양면·사진·중첩 조작 예외·touch 분기·native drag·cleanup을 확인했고 차단 결함을 발견하지 못했다. root는 실제 수정 전 재현, 로컬 자산/배포 자산 브라우저 검증, 패키지·NAS 배포·문서·Git을 담당했다. 이번 협업의 실제 워커 모델명은 별도로 확인하지 않았다.

## 검증 방법과 실제 결과

구문 검사와 `git diff --check` 통과. 전체 `node --test tests/frontend/*.test.js`는 **205 통과, 0 실패, 0 건너뜀**이다. 단일 chat UI는 202개이며 기존 단일200/전체203 대비 신규2개다. 변경된 기존 검사도 포함되지만 검사 삭제는 없다. 모의 DOM 검사이며 실제 브라우저·GPU 검증과 구분한다. JS/CSS 변경이므로 Python·전체 DB 회귀는 재실행하지 않았다.

### 로컬 자산 검사와 실제 NAS 배포 자산 검사

| 범위 | 실행 환경 | 실제 결과 |
| --- | --- | --- |
| 배포 전 PC | 1280·1440px 일반, 1280px reduced-motion | 3설정·설정당 11회 드래그 통과 |
| 배포 후 PC | 같은 3설정, 실제 서버 JS/CSS | 3설정·설정당 11회 드래그 통과 |
| 배포 전/후 모바일 회귀 | 320·390·768px 일반, 390px reduced-motion | 각각 4설정 통과 |
| 배포 전/후 모바일 기존 조작 | 390px touch | 각각 사진 터치 제외·다음 사진·긴 누름 미뒤집힘·초기화 통과 |

[배포 전 PC](assets/2026-10-08-RG015-pcdrag-local-browser.json), [실제 서버 PC](assets/2026-10-08-RG015-pcdrag-browser.json), [배포 전 터치](assets/2026-10-08-RG015-pcdrag-local-touch.json), [실제 서버 터치](assets/2026-10-08-RG015-pcdrag-touch-browser.json), [배포 전 조작](assets/2026-10-08-RG015-pcdrag-local-controls.json), [실제 서버 조작](assets/2026-10-08-RG015-pcdrag-controls.json).

PC 검사는 실제 NAS TEST API/DB 응답을 사용하며 외부 사진 파일만 SVG fixture로 대체했다. 로딩된 img에서도 native 사진 드래그에 빼앗기지 않고 넘겨지는지 확인하려는 목적이다. API 응답·사진 메타데이터를 모의 처리하지 않았으며 실제 외부 사진 전송 성공으로 해석하지 않는다. 배포 전에는 JS/CSS도 로컬 파일로 대체했고 배포 후에는 실제 서버 JS/CSS를 사용했다.

PC 각 설정에서 제목 오른쪽→뒷면, 뒷면 h3 왼쪽→앞면, 학명 짧은 이동 복귀, 앞면 dd·뒷면 설명·먹이 label span·출처의 중첩 span·로딩된 사진·SVG 장식 시작 등 **11회 드래그**를 확인했다. 드래그 중 cursor=grabbing, 일반 motion의 반사광 opacity>0, 선택 문자열 없음과 종료 후 정리를 확인했다. 사진 다음 버튼·출처 details·링크 포커스와 링크 드래그 제외·Enter/Space·Escape/재열기·가로 넘침 없음·pageerror0도 확인했다. 링크 native dragstart는 defaultPrevented=false로 유지됐다.

실제 서버 모바일 스크롤은 scrollTop 0→20/50/89/50, 390px pinch 확대는 scale 1→1.499999761581421이었다. CSS pan-y pinch-zoom·본문 좌우 스와이프·짧은 복귀·멀티터치 취소·닫기/재열기를 유지했다. 사진 터치는 뒤집기를 시작하지 않았고 다음 버튼은 figure 0→1로 바뀌었다. 이미지 complete=false/naturalWidth=0이었으므로 외부 사진 전송 성공으로 기록하지 않는다. 긴 누름은 미뒤집힘만 확인했으며 native selection/contextmenu는 관찰되지 않았다.

검사 도구 종료 상태도 구분한다. 배포 전 PC·터치는 모든 assertion과 JSON 저장 후 Chrome 프로세스가 종료됐으나 Node가 남아 TERM으로 정리했다(exit143). 배포 전/후 조작 검사는 exit0이었다. 배포 후 PC·터치는 모든 assertion 완료 후 browser.close 대기를 10초로 제한한 검사기로 exit0으로 종료했으며 teardown timeout 경고가 있었다. 이를 정상적인 browser.close 완료로 기록하지 않는다. 제품 동작 검사 실패는 없다. PC와 터치의 초기 출력 파일명이 겹쳐 각 검사의 독립 원본 로그에서 JSON을 복구해 별도 파일로 저장했으며 PC3설정/터치4설정의 내용·수치를 확인했다.

## 배포·Git·그래프

구현 `719e5bc`는 `origin/dev` push 완료. 소스 패키지 SHA256은 `d9cb1515034b83b6a15e2c9abf95bff115ffd9859cb44f74da935f8f7fccb92d`다.

NAS TEST 이미지 `robingraph-api:test-rg015pcdrag-719e5bc`, 릴리스 `/home/kimdove/RobinGraph-rg015pcdrag-719e5bc`를 배포했다. 원격 패키지 SHA256·MANIFEST 확인, `deploy_nas.sh deploy`·`verify` 통과, 컨테이너 healthy와 이미지 OCI revision 전체 커밋 일치를 확인했다. 공개 /health는 status=ok·mode=neo4j·deployment_target=test이며 브라우저 fetch로 공개 JS/CSS와 로컬 구현의 바이트 일치를 확인했다. [배포·자산 증거](assets/2026-10-08-RG015-pcdrag-deployment.json). 이전 `robingraph-api:test-rg015noselect-570fd3f`와 릴리스는 롤백용으로 보존했고 PROD는 변경하지 않았다. 이번 SSH master는 종료했다. 인증 정보는 문서에 포함하지 않는다.

`graphify update .` AST 갱신 완료: 3,701 nodes·7,981 edges·218 communities. 기존 SQL 파서·커뮤니티 라벨 경고는 남아 있으며 의미 추출 API는 호출하지 않았다. 그래프 생성물은 기존 추적 정책을 따른다.

## 한계와 후속 사항

물리 Android·iPhone/iPad·Safari/WebKit·Firefox·펜·스크린 리더·FPS/배터리는 검증하지 않았다. PC 사진은 로딩 fixture 기반 입력 검증이며 외부 사진 제공자 품질/접속 검증을 대신하지 않는다. 모바일 사진 파일의 완전 로딩과 실제 운영체제의 긴 누름 선택 메뉴도 이번 합격 범위에서 제외한다. 임계값 조정이나 버튼·링크에서의 드래그 시작 확장은 이번 변경에 포함하지 않는다.

Obsidian의 RG-405 상세·현황과 프로젝트 index에 같은 원인·구현·검증·TEST 배포 결과를 연결한다. 기존 대기·최후순위 보류 작업을 재개하지 않는다.
