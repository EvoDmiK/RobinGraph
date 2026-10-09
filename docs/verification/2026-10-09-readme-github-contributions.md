# README 현행화와 GitHub 기여도 누락 점검

- 작업일: 2026-10-09
- 요청: 현재 구현에 맞게 README를 수정하고 GitHub 기여도 그래프에 커밋이 표시되지 않는 원인을 점검한다.
- 시작 기준: main·dev·origin/main·origin/dev가 `13b5361ff1a2b2cb943a478562f0b894200a11f1`로 일치하고 작업공간은 깨끗했다.

## 배경과 확인한 근거

기존 README는 카드 뒷면에 출처·라이선스를 표시하고 `출처 보기 ↻` 버튼으로 뒤집는다고 설명했다. 일반 소개에 TOP 3를 자동 제공한다는 설명도 남아 있었다. 현재 구현은 카드 전체 영역의 드래그·스와이프, 답변의 통합 출처 토글, 첫 종 설명 뒤 선택적 관계 탐색을 제공한다. Jev 의도 분석과 MLflow 결과 구분, 최종 PC·모바일 카드 동작도 README에 충분히 반영되지 않았다.

graphify query로 관련 파일을 찾고 `src/robingraph/cli.py`, `api/app.py`, `api/jev_router.py`, `api/static/chat.js`, `api/static/styles.css`, `tracing.py`, 환경 변수 예시, CI workflow와 최신 검증 기록을 대조했다. 과거 설계 문서의 설명보다 실제 코드·최근 검증 기록을 우선했다.

GitHub 저장소는 공개 저장소이고 fork가 아니며 기본 브랜치는 main이다. 점검 시 main에는 195개 커밋이 있었다. GitHub REST API의 각 커밋 `author.login`과 원본 이메일을 비교한 결과는 다음과 같다.

| 작성자 이메일 | main 커밋 수 | GitHub author.login |
| --- | ---: | --- |
| `kimdove@gimdulgiui-Macmini.local` | 59 | null |
| `dovekim-32@gimdulgiui-Macmini.local` | 4 | null |
| `kimhippowork@gmail.com` | 58 | EvoDmiK |
| `93193661+EvoDmiK@users.noreply.github.com` | 74 | EvoDmiK |

따라서 기존 main의 **63개 커밋은 로컬 이메일 때문에 계정에 연결되지 않은 상태**다. 기본 브랜치 병합은 이미 끝났으므로 최근 커밋의 원인을 dev 미병합만으로 설명할 수 없다. GitHub 공식 문서는 계정에 연결된 이메일과 기본 브랜치 조건을 요구하고, `.local` 같은 일반 로컬 이메일을 계정에 추가할 수 없다고 설명한다. [누락된 기여도 문제 해결](https://docs.github.com/en/account-and-profile/how-tos/contribution-settings/troubleshooting-missing-contributions).

로그인 계정 API의 ID는 `93193661`, login은 `EvoDmiK`였다. 기존 main 커밋 `834ddd28c12bda819209be3cda715076d773ffce`의 noreply 이메일이 실제로 EvoDmiK에 연결된 것도 REST API로 확인했다. 비공개 이메일 목록 API는 현재 토큰에 user scope가 없어 HTTP 404를 반환했다. 권한을 추가 요청하지 않았고, 공개 커밋 귀속 결과로 필요한 주소를 검증했다. API 토큰이나 인증 정보를 산출물에 저장하지 않았다.

## 변경 내용과 전후 동작

### README.md

- 목차를 추가하고 기능·빠른 실행·실제 데이터 환경·외부 API/MLflow·API·검색·배포·테스트·문서 안내로 나눴다.
- 초기 종 설명에 가용 사진과 추가 설명을 포함하고, `더 알아보기`는 관계 탐색 메뉴라는 현재 동작을 반영했다. 브라우저 요청의 `defer_discovery: true`와 서버 프로필 흐름을 대조했다.
- PC·모바일 카드 양면 드래그, 키보드 조작, 유광 반사, 화면 맞춤, 내부 스크롤 제거, 관찰 포인트, 체중 kg 표시, 두 도넛과 PC 호버를 설명했다. 삭제한 앞면·출처 버튼 안내를 제거했다.
- 출처를 답변 토글로 통합하는 정책과 국명 후보 우선·동일 그룹 점수순 TOP 3를 반영했다. 계통 50%·분류 30%·서식 10%·먹이 10% 및 점수 해석 한계를 설명했다.
- Jev, 임베딩, Gemini, MLflow 설정을 추가했다. LCEL autolog와 Jev의 명시적 자식 span을 구분하고 Gemini REST 경로에는 SDK가 필수가 아님을 명시했다.
- 합성 fixture와 실제 종 환경의 기능 범위를 구분했다. fixture gold 질문은 `/v1/answers` 예시로 안내하고, 실제 종 채팅에는 Neo4j 데이터와 PostgreSQL 활성 상태가 모두 필요함을 설명했다.
- NAS Compose가 기존 인프라를 전제로 한다는 점, Git push와 NAS 배포의 차이, 미구현 독립 설치 패키지·HippoRAG·한국 서식종 토글을 명시했다.
- 중복 NAS 런북과 과거 날짜별 작업 기록 나열을 분야별 문서 표로 정리했다.

### 저장소 Git 설정

공유 저장소의 로컬 `.git/config`에 `user.name=김둘기`, `user.email=93193661+EvoDmiK@users.noreply.github.com`을 설정했다. Git이 자동 추론하던 Mac 로컬 이메일 대신 GitHub에 귀속되는 주소를 사용한다. main·dev 작업트리는 같은 저장소 설정을 공유한다. 전역 설정과 다른 저장소는 변경하지 않았다.

이 설정은 이후 작성할 커밋에 적용된다. 기존 63개 커밋의 작성자 이메일은 그대로다. 이미 공개된 main·dev 이력과 배포 기록이 커밋 ID를 참조하므로, 점검 요청만으로 과거 이력을 재작성하거나 강제 push하지 않았다. 과거 기여도를 복구하려면 별도로 범위를 정한 이력 수정이 필요하다. [Git 이메일 설정의 적용 범위](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address).

## 협업 검토

`card_selection_review`가 읽기 전용으로 기존 README와 갱신본을 구현에 대조했다. 첫 응답의 사진·추가 설명, fixture 질문의 API 경로, Gemini SDK 선택성, MLflow SDK 검색 식을 지적했고 최종본에 반영했다. 구현·설정 변경·통합 검증·Git 반영은 주 담당이 수행했다. 실제 실행 모델 이름은 추정하지 않는다.

## 실제 검증 결과

| 검증 | 결과·범위 |
| --- | --- |
| README 로컬 링크 | 43개 존재 확인, 누락 0 |
| README 목차 | 10개 앵커 일치, 오류 0 |
| CLI 명령 등록 대조 | 13개 일치, 미등록 명령 0 |
| Markdown 코드 블록 | fence 18개로 짝 일치 |
| `git diff --check` | 통과 |
| `validate-fixture` | 종 10·허용 관찰 100·문서 2·청크 4 유효 |
| `evaluate-fixture` | gold 질문 15/15 통과, 실패·건너뛰기 0 |
| fixture FastAPI TestClient | `/health`, `/chat`, `/docs` 모두 HTTP 200 |
| fixture 답변 예시 | `/v1/answers`에 참새 질문: HTTP 200·answer |
| fixture 채팅 범위 | 같은 질문 `/v1/chat`: HTTP 200·clarify. 제한 안내와 일치 |
| Git 작성자·커미터 | `git var`로 모두 noreply 주소 확인 |
| GitHub 신규 커밋 귀속 | REST API에서 author·committer 모두 EvoDmiK 확인 |

로컬 Python 실행은 기존 `/tmp/rg010-venv/bin/python` 환경을 사용했다. uv CLI가 이 셸에 없어서 uv 환경 신규 설치는 수행하지 않았고, README의 명령은 등록된 CLI·잠금 설정·CI 명령과 대조했다. TestClient는 인프로세스 합성 데이터 검증이며 외부 DB/API·실제 브라우저 시험이 아니다. 문서와 로컬 Git 설정만 변경했으므로 전체 제품 회귀·실제 DB·Jev·NAS 배포는 이번 작업에서 재실행하지 않았다.

초기 문서 검증기의 명령 추출 정규식이 숫자 `4`를 제외해 `neo4j`를 `neo`로 잘라 오류를 보고했다. 검증기를 숫자 포함으로 고쳐 재실행하니 13개 명령이 모두 일치했다. 제품 CLI 오류가 아니었다. 실제 제품 테스트 실패는 없다.

## 커밋·배포

README 변경 커밋은 [`08fb621838fe757b60d3790a409723e692173b51`](https://github.com/EvoDmiK/RobinGraph/commit/08fb621838fe757b60d3790a409723e692173b51)이다. dev에서 작성하고 깨끗한 main 작업트리를 fast-forward한 뒤 `git push --atomic origin dev:dev main:main`으로 두 원격 브랜치에 함께 반영했다. 강제 push는 사용하지 않았다. 이 상세 기록은 후속 문서 커밋으로 보존한다.

GitHub API는 신규 커밋의 `author.login`·`committer.login`을 모두 **EvoDmiK**로 반환했다. 이는 계정 귀속 수정의 실제 확인이며 프로필 잔디 UI가 즉시 갱신됐다는 뜻은 아니다. 공식 문서상 조건을 충족한 기여도 반영에 최대 24시간이 걸릴 수 있다. 새 push의 CI 결과는 [Actions](https://github.com/EvoDmiK/RobinGraph/actions)에서 확인하며, 이번 로컬 검증을 새 원격 CI 통과로 기록하지 않는다.

NAS TEST·PROD의 컨테이너·DB·환경 파일은 변경하지 않았다. 이번 작업은 README·검증 기록·저장소 Git 설정 수정이다. RG 백로그 우선순위와 보류 상태도 변경하지 않는다.

## 남은 사항

- 기존 로컬 이메일 커밋 63개의 과거 기여도는 아직 복구되지 않았다.
- 다른 저장소는 별도 Git 설정을 사용하므로 이번 로컬 수정의 적용 대상이 아니다.
- 과거 설계·검증 문서의 당시 상태를 전부 다시 쓰지 않았다. README는 최신 구현과 최신 검증 기록을 함께 확인하도록 안내한다.
- 독립 설치 패키지·HippoRAG·한국 서식종 토글은 이번 요청에 구현하지 않았다.
