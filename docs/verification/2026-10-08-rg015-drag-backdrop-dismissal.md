# RG-015 후속 — 드래그 해제 시 팝업이 닫히는 문제 수정

작업일: 2026-10-08 KST. 구현 커밋: `b58be10f3905eea1a13fbe1f2653469b18066d38`.

현재 상태: **수정·검증·NAS TEST 배포 및 실제 서버 자산 검증 완료**. 최초 SSH 연결 거부 후 사용자가 SSH를 다시 열어 동일 구현을 배포했다. 구현 소스는 origin/dev push 완료다.

## 요청 배경과 목표

사용자가 PC에서 카드를 드래그하다가 카드가 닫히기도 한다고 제보했다. 내부에서 시작한 드래그를 카드 밖에서 놓더라도 팝업이 열린 상태를 유지하고, 의도한 바깥 클릭·닫기 버튼·Escape는 계속 동작하도록 수정한다.

## 원인과 실제 재현

이전 popup click handler는 event.target이 dialog이고 마지막 click 좌표가 현재 dialog bounds 밖이면 닫았다. press 시작 위치를 확인하지 않아 안쪽 테두리/padding에서 시작해 바깥으로 해제된 제스처도 backdrop click으로 처리했다. 카드 내부의 클릭 억제만으로는 dialog 자신이 target인 경우를 처리하지 못한다.

실제 NAS TEST `719e5bc`·API/DB/JS/CSS와 Chrome 1280px에서 확인했다. 앞면 제목·뒷면 h3에서 좌우 ±530px 이동한 캡처 드래그 4건은 팝업이 유지됐고, dialog 테두리/padding에서 시작해 바깥으로 놓은 앞·뒷면 2건은 닫혔다. 따라서 모든 카드 드래그가 실패한다고 기록하지 않는다. [수정 전 실제 재현](assets/2026-10-08-RG015-dragclose-before.json).

## 변경 파일과 전후 동작

`src/robingraph/api/static/chat.js`의 `buildSpeciesPopup`에 popup별 backdropPress 상태를 추가했다. dialog capture 단계에서 primary 왼쪽 포인터의 pointerdown이 실제 bounds 밖인지 확인하고, 같은 pointerId의 pointerup도 실제 backdrop일 때만 released 상태를 만든다. 이어지는 click도 해당 pointer 및 실제 backdrop 조건을 만족할 때만 닫고 상태를 한 번 소비한다.

카드 자식·테두리/padding에서 시작한 내부→외부 해제, backdrop→내부 해제, 취소·불완전한 시퀀스·다른 포인터·추가 touch·오른쪽 버튼은 닫기를 실행하지 않는다. pointercancel·close·opener에서 상태를 초기화한다. X의 직접 close와 브라우저 native Escape는 기존 경로를 사용한다. 전역 이벤트 리스너는 추가하지 않았다. 카드 회전·유광·PC 전체 표면 드래그·글씨 선택 차단·터치 정책은 변경하지 않았다.

`tests/frontend/chat_ui.test.js`의 기존 backdrop close 검사는 실제 press/release 순서를 보내도록 정정하고 의미 있는 회귀 검사 5개를 추가했다. 변형되는 bounds·양면·사진/글씨/padding·정상 mouse/touch backdrop·내부 해제·cancel·ID 불일치·재열기·X 등을 검증한다.

## 협업과 검증

`pc_drag_popup_fix`가 JS·모의 검사·graphify 갱신을 담당했고 `card_selection_review`가 읽기 전용 독립 diff 검토로 capture 순서·touch implicit capture·조작 요소와 reset 경로를 확인했다. 차단 결함을 발견하지 못했다. root는 실제 재현·브라우저 검증·패키지·NAS 시도·문서·Git을 담당했다. 실제 워커 모델명은 별도로 확인하지 않았다.

- `node --check` JS·테스트: 통과.
- `node --test tests/frontend/*.test.js`: **210 통과, 0 실패, 0 건너뜀**. 이전205+신규5이며 모의 DOM 검사다.
- `git diff --check`: 통과.
- Python·전체 DB 회귀는 JS 이벤트 변경이므로 재실행하지 않았다. 실제 API/DB 응답을 사용하는 브라우저 검사와 전체 DB 회귀를 구분한다.

실제 NAS TEST API/DB/CSS를 사용하고 chat.js만 수정 로컬 파일로 대체한 실제 Chrome 검사다. **1280·1440px 마우스 일반, 1280px reduced-motion, 390px CDP touch 일반/reduced-motion 5설정 통과**, runner exit0·pageerror0. 물리 모바일 검사나 새 파일의 NAS 배포 증거는 아니다. [로컬 자산 브라우저 결과](assets/2026-10-08-RG015-dragclose-local-browser.json).

각 설정에서 제목·뒷면 h3·테두리/padding의 좌우 바깥 해제 6건(총30건) 모두 열린 팝업을 유지했다. 바깥 시작→안쪽 해제도 닫히지 않았다. 보통 거리의 본문 드래그는 별도로 전환 성공을 확인했고, 이후 새 정상 backdrop click·X·Escape·재열기 앞면 초기화도 통과했다. 최종 browser.close 제한은 10초였으며 이번 최종 실행에는 teardown timeout 로그가 없었다.

배포 후에는 로컬 route 대체 없이 실제 NAS TEST API/DB/JS/CSS로 같은 **5설정·내부→밖 해제30건**을 실행해 모두 팝업 유지, 바깥→안쪽 유지, 보통 거리 본문 전환, 새 정상 backdrop·X·Escape·재열기 초기화 및 pageerror0을 확인했다. runner exit0이고 teardown timeout 로그는 없었다. 이는 실제 서버 자산 검증이며 물리 기기 검증은 아니다. [배포 후 실제 브라우저 결과](assets/2026-10-08-RG015-dragclose-browser.json).

초기 검사기는 극단적으로 화면 가장자리까지 이동하는 모든 제스처에 반드시 양면 전환까지 기대했다. 첫 실행 1440px, 다음 실행 모바일 가장자리 해제에서 회전 완료 기대가 timeout이었다. 두 실행 모두 해당 시점 팝업은 유지됐다. 최종 검사에서는 이 시나리오의 합격 조건을 ‘밖에서 해제해도 닫히지 않음’으로 명시하고 종료 face를 그대로 기록하며, 보통 거리의 본문 드래그 전환은 별도 검사로 확인한다. 이전 timeout을 팝업 닫힘 결함이나 통과 결과로 계산하지 않으며 native 취소와 단순 입력 표본 차이 중 어느 것이 원인인지 단정하지 않는다.

## Git·패키지·배포

구현 `b58be10`는 `origin/dev` push 완료. 준비한 소스 패키지 SHA256은 `cfef3a840f1c829ae32feec498833468adcb8c0a52cfe4b0f7b6244a2b047f0e`다.

최초 NAS SSH는 여러 차례 `Connection refused`로 업로드 이전 실패했다. 당시 공개 chat.js가 이전719e5bc와 일치하고 새 코드와 다름을 확인했다. [SSH 재개 전 상태](assets/2026-10-08-RG015-dragclose-deployment-pending.json)는 그 시점의 기록으로 보존한다. 사용자가 “열었어”라고 안내한 뒤 SSH 연결·기존 이미지 healthy·새 릴리스 경로 미존재를 확인하고 준비한 동일 패키지를 배포했다.

원격 패키지 SHA256·MANIFEST 검증, `deploy_nas.sh deploy`·`verify`가 통과했다. TEST 이미지 `robingraph-api:test-rg015dragclose-b58be10`, 릴리스 `/home/kimdove/RobinGraph-rg015dragclose-b58be10`, 컨테이너 `robingraph-api-test` healthy와 Docker 이미지 OCI revision 전체 커밋 일치를 확인했다. 실제 브라우저 fetch로 공개 JS/CSS와 로컬 구현 파일의 바이트 일치를 검증했고 /health는 status=ok·mode=neo4j·deployment_target=test다. [실제 배포·서버 자산 증거](assets/2026-10-08-RG015-dragclose-deployment.json). 이전719e5bc 이미지·릴리스는 롤백용으로 보존했고 PROD는 변경하지 않았다. 이번 SSH master는 종료했다.

`graphify update .` AST 갱신: 3,713 nodes·7,994 edges·206 communities. 기존 SQL 파서 경고가 있으며 의미 추출 API는 호출하지 않았다. 그래프 생성물은 기존 추적 정책을 따른다.

## 한계와 기록 관리

물리 휴대전화·Safari/WebKit·Firefox·펜·스크린 리더·실시간 FPS/배터리 검증은 수행하지 않았다. 이번 수정은 accidental backdrop 닫힘 방지이며 테두리/padding을 새 회전 시작 표면으로 확장하거나 극단적인 화면 가장자리 동작의 회전 완료를 보장하는 변경은 아니다.

Obsidian RG-015 후속 상세·현황·프로젝트 index에 같은 원인·검증·배포 상태를 연결한다. 기존 완료·대기·최후순위 보류 작업과 과거 배포 기록을 구분해 보존한다. 인증 정보는 기록하지 않는다.
