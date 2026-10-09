# RG-405 카드 뒷면 압축·출처 통합 및 NAS TEST 배포

- 작업일: 2026-10-08
- 요청: 뒷면 오른쪽 스크롤바를 감추고 정보를 컴팩트하게 배치하며 출처를 하나의 토글로 통합한다.
- 구현 커밋: `cb18d1fc0ab19686711c25fc033f94045803d562` (`origin/dev` push 완료).

## 배경과 확인한 원인

기존 뒷면은 각 형질에 자료 출처 details를 붙이고 사진·먹이 아이콘·멸종위기 등급 출처도 별도 details로 표시했다. 넓은 행 간격과 본문에 항상 표시된 종 평균·날개폭 해석 안내가 세로 길이를 더했다. dialog의 `overflow:auto`는 필요한 스크롤과 브라우저의 기본 스크롤바를 함께 제공했다.

실제 이전 NAS TEST `b58be10`의 API/DB/JS/CSS를 사용하는 Chrome Pixel 7 터치 에뮬레이션(390×844 CSS px)에서 청둥오리를 조회했다. 기본 뒷면의 dialog clientHeight는 812px, scrollHeight는 1,525px, scrollbar-width는 auto였다. 사진 2개, API 형질 18개가 동일값 통합 후 17개 행으로 렌더링됐으며 측정값 더보기 7개를 포함한 details가 총22개였다. 실제 브라우저 스크롤바 노출은 운영체제 설정에도 영향을 받는다. [기존 측정 결과](assets/2026-10-08-RG015-compactback-before.json), [기존 화면](assets/2026-10-08-RG015-compactback-before-390.png).

## 변경 전후 동작과 구현

`src/robingraph/api/static/chat.js`에 카드 전용 buildCardTraitGrid를 추가했다. 공용 buildTraitGrid의 본문은 변경하지 않고, 카드에서는 이미 생성된 안전한 출처 링크와 provenance 노드를 값에 대응하는 항목 제목 아래로 이동한다. 형질 본문에는 값·단위·추정값 표시가 남는다. 원자료 상충과 검토 메모를 현재 결론으로 바꾸거나 삭제하지 않는다.

단일 details `.species-card-sources`의 ‘출처 · 자료 기준’ 아래 사진·형질·먹이 아이콘·IUCN·분류 및 이름·자료 해석 안내를 section/h4/h5로 모았다. 내부에 중첩된 출처 details는 없다. 각 사진의 원본·제작자·라이선스 링크·credit과 각 형질의 원자료 URL을 보존한다. 사진 비동기 갱신은 같은 photoSourcesSlot만 갱신하므로 출처 토글의 열림 상태와 카드 면을 유지하며, 사진이 제거되면 이전 출처도 남기지 않는다.

종 평균·날개폭 주석과 vegetation_note는 ‘자료 해석 안내’로 옮겼다. 활성 profile warnings, 아종에 직접 연결된 자료라는 범위 및 종 수준 참고값을 아종 측정값으로 확정할 수 없다는 안내는 본문에 남겼다. 측정값 더보기와 분류 계통 보기는 정보용 토글로 유지하고 그 근거 링크만 통합했다. 백엔드·DB·검색·국명 우선 정책은 변경 대상이 아니다.

`src/robingraph/api/static/styles.css`는 뒷면에 한정해 행 간격·글씨 크기를 줄이고 긴 값의 줄바꿈을 유지한다. 뒷면의 반복 드래그 안내는 숨겼다. dialog에 scrollbar-width:none 및 WebKit scrollbar 숨김을 적용하면서 overflow:auto·overscroll-behavior·touch-action은 유지했다. 작은 화면이나 출처를 펼친 상태에서도 휠·터치로 읽을 수 있다. 기존 글씨 선택 차단·PC 전체 표면 드래그·유광 반사·정상 backdrop/X/Escape 닫기 로직은 보존한다.

## 협업과 로컬 검증

pc_drag_popup_fix가 JS/CSS/모의 회귀검사 및 graphify 갱신을 담당했다. card_selection_review가 읽기 전용으로 출처 손실·아종 scope·비동기 슬롯·스크롤/드래그 상호작용과 최종 diff를 독립 검토했고 차단 결함을 발견하지 못했다. root는 실제 기존 화면 측정·브라우저 검사·배포·문서·Git을 담당했다. 실제 워커 모델명은 별도 확인하지 않았다.

- 전체 frontend `node --test tests/frontend/*.test.js`: **213 통과, 0 실패, 0 건너뜀**. 기존210 + 출처 통합·비동기 사진 갱신·아종 scope 신규3개이며 모의 DOM 검사다.
- node --check 구현/테스트 파일, git diff --check: 통과.
- 실제 NAS TEST API/DB + 수정 로컬 JS/CSS 대체 검사: 1280×900 마우스, 390×844 터치, 320×640 터치, 390×844 reduced-motion 터치 **4설정 통과**. 모든 실제 형질 값·형질 원자료 URL·사진 원본 및 라이선스 보존, 단일 출처 토글/내부 details0, 안전 링크, 키보드 Enter/Space, native 휠·touch 세로 스크롤, 맨 아래 접근, 스크롤 중 면 유지, PC 뒷면 드래그 전환 및 Escape를 확인했다. pageerror0·runner exit0. [로컬 자산 결과](assets/2026-10-08-RG015-compactback-local-browser.json).
- 로컬 자산 기존 드래그·닫힘 검사: PC1280/1440 일반·1280 reduced 및390 touch 일반/reduced **5설정·내부→외부 해제30건** 유지, 외부→내부 유지, 보통 거리 본문 전환, 이후 정상 backdrop/X/Escape/재열기 통과. 극단적인 화면 가장자리 해제는 팝업 유지가 합격 조건이며 면 전환은 별도 검사한다. pageerror0·runner exit0. [로컬 회귀 결과](assets/2026-10-08-RG015-compactback-drag-local.json).

개발 중 첫 브라우저 검사는 종 평균 안내를 아직 출처 안으로 이동하기 전 실행되어 해당 위치 기대가 불일치했다. 안내 이동 후 위 4설정을 다시 실행해 통과했다. 이 중간 실패를 최종 통과에 합산하거나 배포 실패로 기록하지 않는다.

Python·전체 DB 회귀는 JS/CSS 변경이므로 재실행하지 않았다. 위 실제 API/DB 조회는 전체 DB 회귀나 물리 휴대전화 테스트를 뜻하지 않는다. 비동기 사진 갱신·아종 합성 입력 검증은 모의 검사이며 실서비스 아종과 새 사진 제공처 장애 복구를 실제로 재현한 것은 아니다. 사진 출처 보존을 확인했으며 모든 외부 사진 파일의 완전 전송을 검증한 것은 아니다.

## 실제 배포·배포 후 검증

커밋에 고정된 소스 패키지 SHA256은 `1601070c3f15122b0faf94c96bed6d712a77981f10cf61829ccf3666681c2d9a`다. 원격 SHA256·MANIFEST 검사 후 기존 TEST 환경을 권한0600으로 재사용하고 이미지·VCS ref만 변경했다. `deploy_nas.sh deploy` 및 `verify` 통과, 이미지 `robingraph-api:test-rg015compactback-cb18d1f`, 릴리스 `/home/kimdove/RobinGraph-rg015compactback-cb18d1f`, 컨테이너 `robingraph-api-test` healthy 및 Docker 이미지 OCI revision 전체 커밋 일치를 확인했다. 이전 `robingraph-api:test-rg015dragclose-b58be10` 이미지·릴리스는 롤백용으로 보존했다. PROD 배포는 수행하지 않았다.

로컬 대체 없이 실제 NAS TEST API/DB/JS/CSS로 동일 화면 검사 **4설정**, 드래그·닫힘 회귀 **5설정·30건**을 재실행해 모두 통과했다. 각 화면 검사에서 공개 JS/CSS와 로컬 구현 파일의 바이트 일치를 확인했다. 공개 /health는 status=ok·mode=neo4j·deployment_target=test다. 두 runner 모두 exit0·pageerror0이고 browser.close timeout 로그가 없었다. 배포 후 390·1280px 캡처를 직접 열어 출처 토글·앞면 버튼·줄바꿈을 확인했다.

[실제 서버 화면·스크롤 결과](assets/2026-10-08-RG015-compactback-browser.json), [실제 서버 드래그·닫힘 결과](assets/2026-10-08-RG015-compactback-drag-browser.json), [배포·파일 무결성 증거](assets/2026-10-08-RG015-compactback-deployment.json), [모바일 화면](assets/2026-10-08-RG015-compactback-390.png), [PC 화면](assets/2026-10-08-RG015-compactback-1280.png), [작은 화면](assets/2026-10-08-RG015-compactback-320.png).

`graphify update .` AST 갱신은 exit0·3,723 nodes·8,006 edges·221 communities다. 기존 SQL parser 미설치 경고가 있고 의미 추출 API는 호출하지 않았다. 그래프 생성물은 기존 추적 정책을 따른다.

## 한계와 기록 관리

390×844 기본 뒷면 높이는 1,525→808px로 약47% 줄었고 모든 기본 항목·출처 토글·앞면 버튼이 한 화면에 들어왔다. PC1280×900도833px로 기본 스크롤이 필요 없었다. 320×640는 콘텐츠828px/뷰포트608px이므로 스크롤을 유지한다. 출처를 펼치거나 경고·긴 이름·추가값이 많아지면 스크롤이 필요할 수 있다. 스크롤바 숨김은 모든 내용이 항상 한 화면에 들어간다는 보장이 아니다.

물리 모바일·Safari/WebKit·Firefox·스크린 리더·확대 글꼴·모든 종의 화면 조합은 검사하지 않았다. reduced-motion은 Chrome 설정 에뮬레이션이다. Obsidian 상세 기록·RG-405 백로그 현황 및 프로젝트 index에 같은 원인·검증·배포 상태를 연결했다. RG 상세17개가 중복 없이 유지되고 목차의 깨진 내부 링크가 없으며, 신규 대기 RG-202/RG-406 및 최후순위 보류4건의 상세 본문이 이전과 같음을 다시 읽어 검증했다. 인증 정보는 기록하지 않는다. 이번 배포에 사용한 SSH master 연결을 종료했다.
