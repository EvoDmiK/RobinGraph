# RG-015 앞면 하단 안내·구분선 제거와 대체 내용 추천

- 작업일: 2026-10-09
- 구현 커밋: `128da7f7c604e4ec3af032ee152921b4ec1559a5` (`origin/dev` push 완료)
- 요청: 카드 하단의 ‘수치는 종 평균 · 자료 출처는 답변 출처 보기’와 드래그 안내·구분선을 지우고 그 위치에 들어갈 내용을 추천한다.

## 배경과 원인

직전 TEST a8aa6c1의 앞면은 주요 특징 아래 고정 요약 문구와 sticky footer를 만들었다. footer는 PC의 사진·글씨·빈 곳 드래그 안내와 모바일 스와이프 안내를 포함했고 CSS의 double border가 구분선을 표시했다. 이미 답변 출처에서 자료 해석을 확인하고 카드 본문으로 뒤집을 수 있어 이 영역을 비워 달라는 요청이다. graphify 질의와 buildSpeciesCard·footer CSS·기존 검사를 확인했다.

## 변경 전후와 파일

`src/robingraph/api/static/chat.js`에서 앞면 고정 frontNote 생성 및 footer와 두 조작 안내 DOM을 제거했다. 다른 ‘자료 안내 n건’ warningNote가 같은 species-front-note 클래스를 쓰므로 이 경고는 유지했다. card tabindex·aria-label·aria-keyshortcuts·keydown과 포인터/터치 처리·유광·도넛 툴팁은 변경하지 않았다. 종 평균 해석은 기존 답변 출처의 자료 해석 안내에 남으며 아종 직접형질·종 수준 참고 확정불가 안내와 실제 warnings도 유지한다.

`src/robingraph/api/static/styles.css`에서 footer sticky 위치·배경·구분선·위험 등급별 footer 색상 변수와 안내 전용 스타일을 제거했다. 카드의 pan-y pinch-zoom, grab/grabbing 커서, 키보드 포커스 및 reduced-motion 피드백은 유지한다. 빈 footer 상자를 숨겨 남기는 구현이 아니다.

`tests/frontend/chat_ui.test.js`에서는 삭제된 footer 표면과 안내 DOM 존재를 요구하던 기존 검사만 새 표시 정책에 맞췄다. 카드 본문의 드래그·터치·키보드·출처 회귀를 제거하지 않았다. 프런트엔드 전체 검사 수는231개로 유지한다.

대체 내용은 **관찰 포인트 한 줄**을 우선 추천한다. 출처로 확인한 부리·깃털·날개 무늬 등 식별 특징을 짧게 보여주는 형태다. 다른 선택지는 검증된 재미있는 사실 한 줄이다. 이번 변경에는 새 콘텐츠를 삽입하거나 새 데이터를 만들지 않았으며 추천과 구현 범위를 구분한다.

## 협업과 검증

root가 구현·실행 검증·NAS TEST 배포·기록·Git을 담당했고 card_selection_review가 삭제 전 유의점 및 최종128da7f diff를 읽기 전용으로 검토했다. 경고 공유 클래스·touch-action·키보드 ARIA·출처 해석·아종 안내 보존을 확인했고 차단 문제나 범위 초과를 발견하지 못했다. 워커 모델명은 별도로 확인하지 않았다.

- `node --test tests/frontend/*.test.js`: **231 통과, 실패0, 건너뜀0**. 모의 DOM 검사이며 실제 DB 검사로 합산하지 않는다.
- node --check chat.js 및 git diff --check: 통과.
- graphify update .: exit0, **3767 nodes /8088 edges /234 communities**. 기존 SQL parser 경고와 community 변경에 따른 일부 hub 이름 자동 갱신 안내가 있었으며 의미 추출 API는 사용하지 않았다.
- 배포 후 실제 NAS TEST API/DB/JS/CSS를 사용한 Chrome1280×900 마우스·390×844 Pixel7 CDP 터치 **2설정** 검사가 통과했다. 고정 문구·footer 없음, 앞/뒷면 표시·본문 드래그·도넛 툴팁·키보드·답변 출처 원자료/종 평균 해석과 공개 자산 바이트 일치를 확인했다. pageerror0, runner exit0, 종료 timeout 로그 없음이다. [브라우저 결과](assets/2026-10-09-RG015-footer-browser.json), [frontend 실행 로그](assets/2026-10-09-RG015-footer-frontend-tests.txt).

## NAS TEST 배포와 증거

구현 커밋 고정 패키지 SHA256은 `e0850b2dfb6c3cec23cb5926b562a7a00f68830a20e96824b19ea1d059c682ed`다. 원격 archive·MANIFEST 검증 후 기존 TEST 설정을 권한0600으로 복사하고 이미지/VCS ref만 갱신했다. deploy_nas.sh deploy/verify exit0, TEST 컨테이너 healthy, 이미지 OCI revision이 구현 전체 커밋과 일치했다.

TEST 이미지 `robingraph-api:test-rg015footer-128da7f`, 릴리스 `/home/kimdove/RobinGraph-rg015footer-128da7f`다. 이전 a8aa6c1 이미지·릴리스는 보존했고 PROD는 배포하지 않았다. 공개 확인 주소는 https://robingraph-test.dove-nest.com/chat 이다. 인증 정보는 기록하지 않는다. [배포 무결성](assets/2026-10-09-RG015-footer-deployment.json), [PC 앞면](assets/2026-10-09-RG015-footer-front-1280.png), [모바일 앞면](assets/2026-10-09-RG015-footer-front-390.png), [모바일 뒷면](assets/2026-10-09-RG015-footer-390.png).

## 한계와 문서 관리

물리 휴대폰·Safari/WebKit·Firefox·스크린 리더·모든 조류/아종의 실제 브라우저 질문은 검사하지 않았다. 실제 DB 질문은 청둥오리 기본 정보이며 터치는 Chrome 에뮬레이션이다. Python 전체 DB 회귀는 이번 JS/CSS 표시 제거에 해당하지 않아 재실행하지 않았고 기존 결과를 이번 실행으로 계산하지 않는다. 추천 콘텐츠의 사실 선정·적재·표시는 아직 구현하지 않았다.

Obsidian 상세·백로그 RG-015·프로젝트 index에 같은 작업 결과를 연결하고 기존 이력과 신규 대기2건·최후순위 보류4건은 보존한다. Git에는 구현과 검증 문서·증거를 별도 커밋하며 실행 이미지는 구현 커밋에 고정한다.

최종 기록을 다시 읽어 RG 상세17개 중복 없음·목차 내부 링크 누락0·대기/보류6개 상세 본문 불변·저장소와 상세 검증 내용 일치를 확인했다. 배포 후390px 앞면 캡처를 직접 열어 문구와 footer·구분선이 사라진 것을 확인했다. 외부 사진 전송 전체 성공을 검증한 것은 아니다. 이번 작업의 SSH master 연결을 종료했다.
