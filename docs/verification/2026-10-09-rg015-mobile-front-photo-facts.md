# RG-405 모바일 앞면 사진·기본 정보 글씨 확대

- 작업일: 2026-10-09
- 사용자 요청: 모바일 카드 앞면이 휑하므로 사진을 조금 키우고, 관찰 포인트는 유지하며 체중·먹이 유형·서식 환경·주 생활 방식의 글씨를 조금 키운다.
- 첫 메시지가 기본 정보 목록 중간에서 끊겨 확인한 뒤, 사용자가 네 항목의 폰트 확대라고 보완한 범위에 맞춰 진행했다.

## 원인과 변경 전후

직전198ebca는 카드 전체를 화면 안에 비례 맞추고 내부 스크롤을 제거했지만, 사진에는 이전의 작은 화면용 높이 제한이 남아 있었다. 일반 모바일 사진은 마지막 공통 규칙의 min(240px,24dvh), 높이740px 이하 화면은 더 구체적인 min(160px,23dvh)가 적용됐다. 실제 viewport를 기준으로 제한한 사진이 전체 카드 fit에서도 축소되어 앞면 사진이 작아졌다. 기본 정보는 폭420px 이하에서 .82rem, 그 외 .9rem이었으며, 관찰 포인트는 margin-top:auto로 하단에 남아 중간 공간이 넓어 보였다.

모바일 사진과 자료 없는 사진 자리는 일반 화면 min(240px,30dvh), 짧은 화면 min(200px,30dvh)로 맞춘다. 사진의16:10 비율은 유지하고 폭에 따른 자연 높이를 초과하도록 강제하지 않는다. 기본 정보 네 항목의 제목·값을 .95rem으로 표시한다. 관찰 포인트의 내용·글씨·하단 배치와 PC 규칙은 수정하지 않는다. 전체 카드 비례 맞춤·양면 높이·내부 무스크롤·사진/본문 스와이프·출처 분리·체중 kg 표시는 유지한다.

## 변경 파일과 협업

`src/robingraph/api/static/styles.css`의 모바일 media query만 변경했다. 일반·짧은 화면의 사진 영역/placeholder 최소 높이와 이미지 최대 높이를 일치시키고 모바일 quick-facts에만 .95rem을 지정한다. 사진 selector를 공통 규칙보다 구체적으로 작성해 후순위의24dvh 규칙이 다시 적용되지 않게 한다. JS·API·DB·관찰 포인트 데이터는 변경하지 않는다.

root가 구현·브라우저 전후 실측·NAS TEST 배포·문서·Git을 담당했다. card_selection_review는 CSS와 fit의 관계를 읽기 전용으로 검토하고, 사진이 커져 카드 전체가 더 축소되는지 함께 검사하도록 제안했다. 검토에서 차단 결함은 발견하지 않았다. 리뷰어는 소스·Vault를 수정하거나 배포하지 않았다.

## 검증 범위와 결과

- 기존 frontend 전체244통과/실패0/건너뜀0. [실제 로그](assets/2026-10-09-RG015-front-size-frontend-tests.txt). CSS 수치를 반복하는 새 단위 테스트는 추가하지 않았다.
- git diff --check 통과. graphify update . exit0, AST15/15,3819 nodes/8156 edges/228 communities. 기존SQL 의존성 경고4개·무심볼 안내2개·community label 변경 안내가 있었다. AST 갱신만 실행하고 의미 추출 API는 사용하지 않았다.
- [실제 NAS API/DB+로컬 CSS 전후 검사](assets/2026-10-09-RG015-front-size-local-browser.json): **6설정 통과**. 실제 API/DB의 청둥오리 PC1280×900, 모바일390×844·375×667·320×568·가로844×390의5설정과 자료 없는 모의 API390×844의1설정을 구분한다. 동일 응답/DOM에서 이전 CSS를 먼저 측정하고 새 CSS를 적용해 자료 차이가 크기 비교에 영향을 주지 않게 했다.
- 사진·앞면 본문·뒷면 스와이프, 세로 터치 무스크롤, 카드/닫기 viewport 포함, 양면 높이, 상세 펼침, resize, 차트 키보드 조작, 닫기/재열기, pageerror0을 확인했다. 모든 설정에서 관찰 포인트의 텍스트·computed 글씨 크기가 같았고 모바일 fit scale도 이전과 같았다. PC 전후 사진·기본 정보·관찰 포인트의 실측/글씨가 같았다.

| 화면 | 사진 높이 전→후(px) | 기본 정보 CSS 글씨 전→후(px) | 전체 fit scale |
|---|---:|---:|---:|
| PC1280×900 |216→216|14.4→14.4|1 유지|
|390×844|168.79→197.92|13.12→15.2|0.833333 유지|
|375×667|121.74→158.72|13.12→15.2|0.793590 유지|
|320×568|87.08→113.59|13.12→15.2|0.666667 유지|
|가로844×390|38.40→50.10|14.4→15.2|0.428205 유지|

폰트 열은 transform 전 computed size이며 실제 글씨도 동일한 scale로 커진다. 사진 높이는 transform 후 실제 표시 크기다. 모의 자료 없음의 사진 placeholder는196.93→200px, 카드 전체는 실제 자료와 공통 크기를 유지했다.

처음 비교 검증기에서 새 CSS 뒤에 이전 CSS를 덧붙였으나 새 selector의 높은 specificity가 남아 전후 글씨가 같다고 기록됐다. 검증기를 이전 CSS로 시작하고 새 CSS를 적용하는 순서로 고쳤으며 앱 소스 변경으로 해결한 실패가 아니다. 최종6설정은 수정한 검증기에서 통과했다.

## 배포 후 실제 브라우저

배포 자산으로 같은6설정이 모두 통과했다. 실제 API/DB5·모의 자료 없음1을 구분하며 양면 높이·전체fit·세로 무스크롤·사진/본문 넘김·닫기/재열기·resize·차트/상세 조작·pageerror0을 확인했다. 모든 설정에서 공개 JS/CSS가 소스와 바이트 단위로 같고 health status=ok였다. [실제 배포 서버 결과](assets/2026-10-09-RG015-front-size-browser.json). 물리 휴대폰 검증으로 합산하지 않는다.

[390px 앞면](assets/2026-10-09-RG015-front-size-mallard-front-390x844.png)과 [320px 앞면](assets/2026-10-09-RG015-front-size-mallard-front-320x568.png)을 직접 열어 커진 사진·기본 정보·하단 관찰 포인트·닫기의 화면 포함을 확인했다.

## 커밋·배포

구현 커밋 `bb7739c1c0a7c2c7cc7edce43fac94d0f45f380c`를 origin/dev에 push했다. 소스 패키지 SHA256은 `136d0640e0f899ffbd07d36c9aee54b425e7e8b0748bf8b6c8789bf8836d4421`이다. 원격 archive SHA256·MANIFEST를 검증하고 이전 TEST 환경파일을0600으로 재사용했다. 이미지와 VCS ref만 변경했으며 deploy_nas.sh deploy/verify exit0이다. robingraph-api-test는 running/healthy, OCI revision은 구현 전체 커밋과 일치하고 API health는 status=ok/mode=neo4j/deployment_target=test다. 이미지 `robingraph-api:test-rg015frontsize-bb7739c`, 릴리스 `/home/kimdove/RobinGraph-rg015frontsize-bb7739c`다. 이전 `robingraph-api:test-rg015noscroll-198ebca`는 보존했다. PROD는 배포하지 않았다. [배포 무결성·health](assets/2026-10-09-RG015-front-size-deployment.json).

## 한계·후속 사항

모바일 검증은 Chrome CDP 에뮬레이션이며 물리 휴대폰·Safari/WebKit·실제 노치/주소창 이동은 확인하지 않는다. 사진의 외부 전송 전체 성공과 모든 조류 자료를 보장하지 않는다. 짧거나 가로인 화면에서는 카드 전체가 비례 축소되므로 물리 글씨 크기에도 한계가 있다. Python 전체 DB 회귀는 CSS 표시 변경 범위가 아니어서 새로 실행하지 않는다. 인증 정보는 문서에 기록하지 않는다.

저장소와 Obsidian 작업기록·백로그·작업기록 index의 핵심 변경과 검증 결과를 맞춘다. 앞서 나눈 검토자료 폴더와 신규 대기/최후순위 보류 작업 상태는 유지한다.

이번 작업의 SSH master를 종료했고 남은 headless Chrome은0개다. 구현과 검증 문서는 별도 커밋으로 origin/dev에 저장한다.

Obsidian 상세·백로그·작업기록 index를 저장 후 다시 읽어 계획한 내용과 일치함을 확인했다. RG 상세17개 중복 없음·목차 내부 링크 누락0·신규 대기/최후순위 보류6개 상세 불변을 확인했다. 저장소 증거 링크는 실제 파일 존재를 검사한다.
