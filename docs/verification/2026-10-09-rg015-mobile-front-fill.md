# RG-015 모바일 앞면의 큰 빈 공간 제거

- 작업일: 2026-10-09
- 요청: 사진과 기본 정보 글씨를 조금 확대한 뒤에도 모바일 카드 앞면이 여전히 휑하다.

## 원인과 배포 상태 확인

사용자가 제공한 주소는 NAS TEST의 /chat과 같았다. 같은 주소를390×844 모바일 Chrome 조건으로 열어 HTML의 no-cache/must-revalidate 및 DYNAMIC 응답, 해시가 붙은 CSS URL과 이전 구현bb7739c의 CSS 바이트 일치를 확인했다. 새 스타일이 서버에 없다고 추정하거나 사용자 캐시가 원인이라고 단정하지 않는다. [배포 전달 확인](assets/2026-10-09-RG015-front-density-before-delivery.json).

실제 문제는 앞·뒷면의 공통 높이에서 생긴 앞면 여유 공간을 관찰 포인트의 margin-top:auto가 전부 흡수한다는 점이었다. 사진 높이를 고정 상한 안에서 조금 늘려도 이 구조는 그대로였다. [변경 전 실제 서버 실측](assets/2026-10-09-RG015-front-density-before-browser.json)에서390×844의 사진 높이는197.92px, 기본 정보 하단556.23px와 관찰 포인트 상단701.12px 사이에는144.90px이 비어 있었다.

## 변경 전후와 구현 파일

`src/robingraph/api/static/styles.css`의 모바일 규칙만 변경했다. 사진 영역이 flex로 남는 높이를 채우고 media가 그 영역을 사용한다. figure를 기준으로 이미지를 absolute·높이100%·object-fit:cover로 배치해 이미지 자체도 커지게 한다. 이미지의 intrinsic 높이가 카드 자연 높이를 다시 키우는 순환은 피한다. 일반240px/짧은 화면200px 관련 규칙은 사진 영역의 최소 크기로 유지하며 이미지 최대 높이는 해제한다. 사진 없음 placeholder도 같은 공간을 사용한다.

기본 정보 네 행에는 위아래6px의 패딩과 옅은 구분선을 추가한다. 글씨는 직전 .95rem을 유지한다. 관찰 포인트의 자동 상단 여백을0으로 바꿔 기본 정보 다음에 일정한 간격으로 이어지게 한다. 관찰 포인트의 내용·글씨는 그대로다. PC 규칙·JS·API·DB·전체 카드 맞춤·양면 높이·내부 무스크롤·사진/본문 넘김·출처·kg 표시는 수정하지 않는다.

사진 비율을 강제로 보존하는 contain은 큰 사진 틀 안에 빈 띠만 늘릴 수 있으므로 cover를 사용한다. 비율이 다른 사진은 일부 가장자리가 잘릴 수 있으며 대표 사진의 실제 시각 결과를 브라우저에서 확인한다.

## 협업과 자동 검증

pc_drag_popup_fix가 CSS 구현·회귀·graphify를 담당하고 card_selection_review가 읽기 전용 독립 검토를 맡았다. root는 변경 전 재현·전후 실제 크기·사진 잘림 확인·NAS TEST 배포·문서·Obsidian·Git을 담당한다. 검토에서 차단 결함은 발견하지 않았다.

- frontend전체244통과/실패0/건너뜀0. [실제 로그](assets/2026-10-09-RG015-front-density-frontend-tests.txt).
- node --check chat.js와 git diff --check 통과. JS는 변경하지 않았다.
- graphify update . exit0, AST15/15,3827 nodes/8163 edges/239 communities. 기존SQL 의존성 경고4개·무심볼 안내2개·community label 변경 안내가 있다. AST 갱신만 실행하고 의미 추출 API는 사용하지 않았다.

## 브라우저 검증

[로컬 새 CSS 전후 비교](assets/2026-10-09-RG015-front-density-local-browser.json)는6설정 모두 통과했다. 실제 NAS API/DB의 청둥오리 PC1280×900·모바일390×844/375×667/320×568/가로844×390의5설정과 자료 없음 모의 API390×844의1설정이다. [추가 사진 오류 모의 API](assets/2026-10-09-RG015-front-density-edge-local-browser.json)1설정도 통과했다. 총7설정 가운데 실제 API/DB5와 모의 API2를 구분한다.

| 화면 | 사진 실제 높이 전→후(px) | 정보 다음 빈 간격 전→후(px) | 전체 fit |
|---|---:|---:|---:|
|PC1280×900|216→216|18.94→18.94|1 유지|
|390×844|197.92→291.15|144.90→8.33|0.833333 유지|
|375×667|158.72→169.98|57.29→4.76|0.793590 유지|
|320×568|113.59→142.79|67.86→4.00|0.666667 유지|
|가로844×390|50.10→75.44|50.18→2.57|0.428205 유지|

모든 설정에서 사진/본문 양면 스와이프·프레임과 닫기의 화면 포함·공통 양면 높이·내부 무스크롤·resize·상세 토글·차트 조작·닫기/재열기·pageerror0을 확인했다. 전후 관찰 포인트 텍스트와 글씨 크기는 같고, 모바일 전체 fit 배율도 같았다. PC의 사진·기본 정보·관찰 포인트 실측과 글씨는 변하지 않았다. 대표 청둥오리의 커진 실제 사진을 직접 열어 두 새의 시각 결과와 하단 정보 포함을 확인했다.

자료 없음에서는 사진 자리도 남는 공간을 채우고 기존 미확인 안내를 보존한다. 사진 오류 모의 응답은 Wikimedia 이미지 URL 요청을 의도적으로 abort하여 data-photo-state=error와 재시도 UI를 확인했으며 실제 사진 제공처 장애 성공으로 합산하지 않는다.

초기 자료 없음 검사에서는 자료 없음 안내 문장의 높이까지 빈 공간으로 센 검증기 조건이 실패했다. 기본 정보 다음에 안내가 있으면 그 안내 하단부터 관찰 포인트까지 측정하도록 고쳤고, 앱 소스 변경 없이 최종6설정을 다시 통과했다. 실제 텍스트를 빈 공간으로 세지 않는다.

## 배포 후 실제 브라우저

배포 자산으로도 기본6설정과 사진 오류1설정의 **총7설정이 모두 통과**했다. 실제 API/DB5·모의 API2를 구분한다. 모든 설정에서 공개 JS/CSS는 소스와 바이트 단위로 같고 health status=ok였다. 앞/뒷면과 닫기의 화면 포함·양면 높이·내부 무스크롤·사진/본문 swipe·resize·상세/차트 조작·닫기/재열기·pageerror0을 확인했다. [기본6설정](assets/2026-10-09-RG015-front-density-browser.json), [사진 오류 모의1설정](assets/2026-10-09-RG015-front-density-edge-browser.json).

[배포된390px 앞면](assets/2026-10-09-RG015-front-density-mallard-front-390x844.png)을 직접 열어 커진 대표 사진과 네 기본 정보·하단 관찰 포인트의 배치, 큰 빈 공간 제거를 확인했다. 물리 휴대폰 검증으로 합산하지 않는다.

## 커밋·배포

구현 커밋 `1d0647cabb993f2506fdb297c7636223a48edeac`를 origin/dev에 push했다. 소스 archive SHA256은 `14d6ac702613ff108b67e5da4a5172ad8be3ab60d03ca7eafa10022f0d36dbfc`다. 원격 archive SHA256과 MANIFEST를 검증하고 이전 TEST 환경파일을0600으로 재사용했다. 이미지와 VCS ref만 변경했으며 deploy_nas.sh deploy/verify exit0이다. robingraph-api-test는 running/healthy, OCI revision은 구현 전체 커밋과 같고 health는status=ok/mode=neo4j/deployment_target=test다. 이미지 `robingraph-api:test-rg015frontfill-1d0647c`, 릴리스 `/home/kimdove/RobinGraph-rg015frontfill-1d0647c`다. 이전 `robingraph-api:test-rg015frontsize-bb7739c`는 보존했으며 PROD는 배포하지 않았다. [배포 무결성·health](assets/2026-10-09-RG015-front-density-deployment.json).

## 한계와 후속 사항

Chrome CDP 모바일 에뮬레이션이며 물리 휴대폰·Safari/WebKit·실제 노치/주소창 이동은 확인하지 않는다. 모든 사진의 피사체와 외부 전송 성공을 전수 검증하지 않는다. 짧은 화면에서는 전체 카드 fit이 글씨와 사진을 함께 축소하며, cover는 사진 비율에 따라 가장자리를 자를 수 있다. 상세 사진의 원본은 기존 답변 출처에서 확인할 수 있다. CSS 배치 변경이므로 Python 전체 DB 회귀는 새로 실행하지 않는다. 인증 정보는 기록하지 않는다.

저장소와 Obsidian 작업기록·백로그·작업기록 index의 핵심 변경과 실제 결과를 맞춘다. 이전 배포 이력 및 신규 대기/최후순위 보류 작업 상태는 유지한다.

이번 작업의 SSH master를 종료했고 남은 headless Chrome은0개다. 구현과 검증 문서는 별도 커밋으로 origin/dev에 저장한다.

Obsidian 상세·백로그·작업기록 index를 저장 후 다시 읽어 계획한 내용 일치·RG 상세17개 중복 없음·목차 내부 링크 누락0·신규 대기/최후순위 보류6개 상세 불변을 확인했다. 저장소 증거 링크는 실제 파일 존재를 검사한다.
