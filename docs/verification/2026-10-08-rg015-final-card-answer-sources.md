# RG-405 카드 버튼 제거·답변 출처 통합·먹이 비율·영어 보조 이름

- 작업일: 2026-10-08
- 구현 커밋: `ddf002f78932633ba49ea68c3b7ab2c4a8212873` (`origin/dev` push 완료)
- 사용자 요청: 앞/뒤 전환 버튼을 없애고 카드 출처를 설명의 ‘답변 출처 보기’ 하나로 옮기며, 먹이 구성 시각화와 한국어 이름 옆 작은 영어 이름을 추가한다.

## 배경과 확인한 원인

직전 TEST `cb18d1f`는 카드의 `.species-card-flip` 버튼과 `.species-card-sources` 출처 토글을 제공했다. 설명의 `.species-answer-sources`와 별개라 같은 자료를 두 위치에서 확인해야 했다. 먹이 구성은 긴 퍼센트 문자열이었다. 카드 제목은 speciesLabel을 사용해 한국어 또는 영어 하나만 표시했고 학명은 별도로 제공했다.

기존 appendAnswerMessage는 초기 설명의 출처만 메시지 끝으로 옮겼다. buildDeferredEnrichment는 추가 설명에서 별도 출처 토글을 생성할 수 있었고 사진 갱신은 카드 내부 photoSourcesSlot만 바꿨다. 따라서 단순 DOM 이동만 하면 지연 설명의 출처가 분리되거나 사진 교체·삭제 뒤 오래된 근거가 남을 수 있었다. 앞뒤 버튼 또한 flip.disabled와 애니메이션 상태가 연결돼 버튼을 삭제하면서 독립 상태와 키보드 입력을 마련해야 했다. graphify 관계 질의 및 해당 소스·테스트를 확인했다.

## 변경 전후 동작과 구현 파일

`src/robingraph/api/static/chat.js`에서 뒤집기 버튼 DOM과 카드 내부 출처 토글을 제거했다. 카드는 좌우 마우스 드래그·터치 스와이프로 넘기며, 카드 본인에 포커스한 Enter/Space도 전환한다. tabindex0·role group·aria-roledescription·aria-keyshortcuts·data-face·aria-busy와 면별 aria-label로 상태를 표시한다. summary·링크·사진 조작 등 자식에 입력한 키는 가로채지 않는다. 키보드 전환이 진행 중 포인터 드래그를 정리하고 기존 캡처·취소·재열기·유광 및 accidental backdrop 방지를 보존한다. 전환 버튼을 숨겨 남기는 구현이 아니다.

카드 근거 원본은 DOM 밖의 card.sourceMaterial에 보관하고 단일 답변 출처 패널에서 복제·통합한다. buildCombinedAnswerSources가 같은 텍스트·URL의 행 fingerprint를 제거하고 같은 안전 URL은 한 번만 링크로 표시한다. 서로 다른 값·라이선스·release·locator·evidence_id·creator·credit·아종의 종 수준 scope·검토 메모·상충 원자료는 보존한다. 다른 문맥의 같은 링크는 텍스트로 남아 사실과 근거의 대응을 잃지 않는다. 재계산 시 원본에서 다시 복제하므로 사진을 삭제해 첫 링크가 사라져도 다른 근거 위치의 같은 URL이 링크로 다시 표시된다. 출처 토글의 open 상태를 유지하고 고유 안전 URL 수(라이선스 링크 포함)를 다시 계산한다.

초기 설명·질문별 targeted 답변·citations·지연 추가 설명·사진 retry/update/remove 및 하위 종/아종/비교 팝업 경로에 동일 출처 통합을 연결했다. 일반 DB/API·질문 라우팅 정책은 변경하지 않았다. 아종 직접 자료와 종 수준 참고 확정 불가 안내, 활성 warnings는 카드 본문에 남기고 상세 서지·사진 라이선스·IUCN·분류·자료 해석 안내를 설명 아래에서 확인한다. 기존 '출처는 뒷면' 안내와 뒷면 제목도 최종 구조에 맞췄다.

먹이 구성은 `.species-diet-composition` 안에서 개별 항목명·실제 퍼센트·막대를 제공한다. 변온/온혈/기타 척추동물과 물고기를 원자료대로 개별 표시한다. 기존 먹이 아이콘의 상위 묶음과 별개의 표현이며 서로 다른 자료의 비율을 합산하거나 임의로100%로 환산하지 않는다. 0%는 작은 칩, 미등록 항목·잘못된 비율·추정값은 안내로 구분한다. 자료가 여러 개면 자료1/2로 출처 항목 제목과 대응시킨다. 카드에는 긴 citation을 붙이지 않고 서지는 답변 출처에 둔다.

한국어·영어 이름이 모두 유효하면 `.species-card-names`에 한국어 주제목과 작은 `.species-english-name`을 함께 표시한다. 한국어가 없거나 기계번역 상태이면 기존 영어 주제목 정책을 유지해 영어를 중복하지 않는다. 공백·긴 이름·공격 문자열은 trim/textContent 및 반응형 줄바꿈으로 처리한다. 학명은 기존 별도 행에 유지한다.

`src/robingraph/api/static/styles.css`는 작은 영어 제목과 줄바꿈, 먹이 비율 바·0% 칩·자료 안내를 추가하고 카드 버튼 스타일을 제거했다. 출처 스타일을 본문 토글로 옮겼으며 스크롤바 숨김·overflow:auto·touch-action·본문 글씨 선택 차단을 유지한다. 뒷면에는 버튼이나 반복 넘기기 안내 footer를 표시하지 않는다. 작은 화면과 펼친 측정값은 여전히 스크롤할 수 있다.

## 협업과 검증

pc_drag_popup_fix가 JS/CSS 및 모의 회귀검사·graphify 갱신, card_selection_review가 읽기 전용 독립 검토를 맡았다. 검토자는 초기/지연 설명·사진 슬롯·동일 URL의 서로 다른 메타·키보드 자식 예외를 확인했고 최종 영어 제목과 자료 번호 대응까지 차단 결함을 발견하지 못했다. root는 실제 브라우저·fixture 통합검사·NAS 배포·문서·Git을 담당했다. 워커 모델명은 별도로 확인하지 않았다.

- 전체 frontend `node --test tests/frontend/*.test.js`: **225 통과, 0 실패, 0 건너뜀**. 이전213 + 신규12이며 모의 DOM 검사다. 단일 패널·중복 제거와 메타 보존·사진 삭제 뒤 링크 재표시·deferred·키보드/캡처 정리·분포별 실제 비율과 invalid/unknown·영어 보조 제목을 검증한다.
- node --check 구현/테스트, git diff --check: 통과.
- 실제 NAS TEST API/DB + 로컬 JS/CSS 대체: 1280×900 마우스,390×844 터치,320×640 터치,390×844 reduced-motion 터치,1280px targeted 먹이 질문 **5설정 통과**. 버튼·카드 출처 없음, 한국어/영어/학명, 양면 키보드·포인터 전환, 식단5개 양의 비율40/20/20/10/10, 개별 항목명, 단일 설명 출처와 모든 실제 형질·사진 원본 URL1회 및 라이선스 보존, 측정값 토글, 맨 아래 접근·Escape·안전 링크·pageerror0을 확인했다. [로컬 실제API 결과](assets/2026-10-08-RG015-finalcard-local-browser.json).
- 실제 NAS API/DB + 로컬 자산 드래그/닫힘 회귀 **5설정·내부→밖 해제30건 통과**. PC1280/1440 일반·1280 reduced,390 touch 일반/reduced에서 밖에서 놓아도 유지, 밖→안쪽 유지, 보통 거리 전환, 정상 backdrop/X/Escape/재열기 초기화를 확인했다. [로컬 회귀 결과](assets/2026-10-08-RG015-finalcard-drag-local.json).
- 실제 Chrome DOM + **모의 초기/지연 API·사진 SVG fixture**로 deferred 통합을 검사했다. 같은 URL의 서로 다른 locator·evidence·license가 유지되고 링크는1개였다. 추가 설명·사진 creator/credit/license가 같은 열린 토글에 합쳐졌고 출처 URL 개수19→23, 별도 토글0, 카드 버튼/출처0, pageerror0이다. 이는 실제 외부 API/사진 전송 검증이 아니다. [로컬 모의API 통합 결과](assets/2026-10-08-RG015-finalcard-deferred-local.json).

이번 검사 실패·건너뜀은 없었다. Python·전체 DB 회귀는 JS/CSS 변경이므로 재실행하지 않았다. 실제 API/DB 질문 검증은 전체 DB 회귀를 대신했다는 뜻이 아니다. 물리 기기에서 실행한 것이 아니라 Chrome/Pixel 7 CDP 터치 에뮬레이션이다.

## NAS TEST 배포와 서버 검증

소스에 고정된 배포 패키지 SHA256은 `037ef0ea484faf746b80daa0c8c41a3b63e0b9a0da3ecd7deb9f208d53cf6833`다. 원격 SHA256·MANIFEST 확인 후 기존 TEST 설정을 권한0600으로 재사용하고 이미지·VCS ref만 갱신했다. deploy_nas.sh deploy/verify 통과, 컨테이너 robingraph-api-test healthy, Docker 이미지 OCI revision 전체 커밋 일치를 확인했다. TEST 이미지 `robingraph-api:test-rg015finalcard-ddf002f`, 릴리스 `/home/kimdove/RobinGraph-rg015finalcard-ddf002f`이며 이전 cb18d1f 이미지·릴리스는 롤백용으로 보존했다. PROD는 배포하지 않았다.

로컬 대체 없이 실제 서버 API/DB/JS/CSS로 기본/targeted 화면 **5설정**과 드래그·닫힘 **5설정·30건**을 재실행해 통과했다. 추가한 native 휠/터치 세로 스크롤은 각각240/170/171/168/240px 이동하며 면을 유지했고, 펼친 측정값 맨 아래까지 접근했다. 공개 JS/CSS와 로컬 파일 바이트 일치, 공개 health status=ok·mode=neo4j·deployment_target=test를 확인했다. [실제 서버 화면·근거 검사](assets/2026-10-08-RG015-finalcard-browser.json), [실제 서버 드래그·닫힘](assets/2026-10-08-RG015-finalcard-drag-browser.json), [배포 무결성](assets/2026-10-08-RG015-finalcard-deployment.json).

서버 JS/CSS를 사용하면서 초기/지연 API·사진만 fixture로 대체한 Chrome 통합 검사도 통과했다. 출처 토글1개·open유지·고유 링크·서로 다른 locator/라이선스·새 사진credit 및 추가설명 근거를 확인했다. 이 검사는 실제 지연 API 제공처 성공으로 계산하지 않는다. [배포 자산+모의 API 검사](assets/2026-10-08-RG015-finalcard-deferred-browser.json).

모든 assertion·runner exit0·pageerror0이다. 배포 후 화면 검사 runner는 모든 결과 저장 후 browser.close의10초 제한 로그가1회 발생했다. 제품 검사 실패와 구분해 JSON에도 기록했으며 종료 뒤 남은 headless Chrome 프로세스가 없음을 확인했다. 드래그와 fixture runner에는 해당 로그가 없었다. [모바일 화면](assets/2026-10-08-RG015-finalcard-390.png), [PC 화면](assets/2026-10-08-RG015-finalcard-1280.png), [작은 화면](assets/2026-10-08-RG015-finalcard-320.png)을 저장했고 배포 후 모바일390px 캡처를 직접 열어 작은 영어 이름·비율 막대·버튼 제거를 확인했다.

최종 graphify update . AST 갱신은 exit0·3,740 nodes·8,047 edges·231 communities다. 기존 SQL parser 경고만 있으며 의미 추출 API는 호출하지 않았다. 생성물은 기존 추적 정책을 따른다.

## 한계와 기록 관리

먹이 막대는 원자료 비율의 표시이며 먹이 아이콘의 상위 묶음과 실제 비율의 항목을 혼동하지 않도록 개별 항목명을 유지한다. 기본 카드가 모든 화면에서 한 번에 다 보인다고 보장하지 않는다. 출처를 카드 밖으로 옮겼으므로 사진의 라이선스·자료 기준은 설명의 ‘답변 출처 보기’에서 확인한다. 키보드는 카드 본인에 포커스한 경우만 전환하고 외부 링크·summary의 기본 조작을 유지한다.

물리 모바일·Safari/WebKit·Firefox·스크린 리더·확대 글꼴·모든 조류/하위 팝업 화면·전체 DB 회귀는 검증하지 않았다. 하위 종/아종/비교 카드 경로는 소스 검토·모의 검증 범위이며 실제 브라우저 질문은 청둥오리 기본/먹이 질문이다. 외부 사진 전송 전체 성공을 확인한 것은 아니다. 기존 과거 검증·배포 기록을 보존하고 Obsidian 상세·백로그 RG-405·프로젝트 index에 같은 결과를 연결한다. 신규 대기 RG-202/RG-406 및 최후순위 보류4건은 변경하지 않는다. 인증 정보는 기록하지 않는다.

Obsidian 상세·현황·index 갱신 후 다시 읽어 RG 상세17개 중복 없음·목차 내부 링크 누락0·대기/보류6개 상세 본문 불변을 확인했다. 이번 작업의 SSH master 연결을 종료했다. 구현 및 검증 문서·PNG/JSON 증거는 dev에 커밋·push하며 실행 이미지는 위 구현 커밋에 고정한다.
