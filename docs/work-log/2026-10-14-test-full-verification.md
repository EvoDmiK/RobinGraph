# 로컬 TEST 전체 기능·브라우저 검증

후속 상태: [OrbStack 재시작 후 점검](2026-10-14-orbstack-restart-check.md)에서 직접 DB·임베딩 연결을 확인하고 임시 중계를 제거했다. 아래의 중계 사용·미해결 내용은 당시 상태 기록이다.


## 요청 배경과 목표

사용자는 현재 서버에 배포한 TEST를 향후 구현 완료 후 검증할 환경으로 지정하고 전체 기능과 실제 브라우저 검증을 요청했다. 이후 로컬 OrbStack 재시작 진행을 승인했다. 대상 소스는 ec9112903169f9abe9438660f04539c2292a1201, 환경은 .env.nas.test, 이미지 robingraph-api:test-local, 컨테이너 robingraph-api-test, 접속 주소는 http://127.0.0.1:8000/chat이다. 운영 NAS와 운영 환경 파일은 변경 대상이 아니다.

## 확인한 문제와 근거

배포 이미지에는 tests 디렉터리가 없어 최초 docker exec unittest discover가 ImportError로 실패했다. 저장소를 읽기 전용으로 연결한 별도 테스트 컨테이너를 시작한 이후 Docker와 TEST HTTP가 응답하지 않았다. Docker API ping과 테스트 컨테이너 stop도 시간 초과였다. OrbStack vmgr 로그에서는 CPU 동기화·BPF/seccomp 관련 커널 대기 스택을 확인했다. 정확한 근본 원인은 확정하지 않았으며 애플리케이션 오류로 단정하지 않는다.

사용자 승인 후 orb stop, orb start로 로컬 OrbStack을 재시작했다. 기존 TEST와 portainer_agent가 다시 실행됐고 별도 테스트 컨테이너는 사라졌다. 재시작 후 컨테이너는 인터넷에 연결할 수 있었지만 LAN의 TEST Neo4j·PostgreSQL 연결은 시간 초과였다. 호스트의 시스템 Python에서는 같은 DB에 연결됐다. 컨테이너의 직접 LAN 접근 문제이며 macOS 로컬 네트워크 권한 확인을 사용자에게 요청했다. 권한이 실제 원인인지 확정하거나 시스템 권한을 임의로 변경하지 않았다.

## TEST 복구와 변경 전후

원본 .env.nas.test의 값은 유지하고 호스트 loopback의 임시 TCP 중계를 만들었다. 호스트의 Python3가 기존 TEST Neo4j·PostgreSQL·임베딩 서버로 연결하며 컨테이너는 host.docker.internal로 중계에 접속한다. 원격 DB·모델 응답을 가로채거나 모의하지 않는다. 중계는 127.0.0.1의 17687·15433·18765 포트에만 바인딩하고 인증값을 출력하지 않는다.

/tmp/robingraph-browser-qa/local-test-relay-compose.json에 TEST 전용 런타임 연결 주소와 127.0.0.1:8000:8000 포트를 설정했다. 원본 compose.nas.yml과 함께 robingraph-test 프로젝트의 API만 --no-build로 재생성했다. Production 파일·컨테이너·DNS·프록시·데이터는 변경하지 않았다. 런타임 소스 변경은 없으며 이미지도 동일하다.

중계의 최초 구현은 120초 무통신 시 연결을 닫아 Neo4j의 유휴 연결을 끊었다. 그 상태에서 /v1/answers 첫 요청이 500을 반환했다. 서버 로그의 defunct connection과 중계 유휴 제한을 대조해 중계에서 유휴 상태를 유지하도록 수정하고 TEST를 재시작했다. 후속 동일 API 검사 18개는 모두 통과했다. 최초 실패를 숨기거나 코드 결함으로 바꿔 기록하지 않는다.

## 자동 테스트: 실행 범위와 실제 결과

| 검증 | 실제 결과 | 의미 |
|---|---|---|
| 프런트엔드 node --test tests/frontend/*.test.js | 303 통과, 실패·취소·건너뛰기 0 | fake DOM·단위 회귀 |
| 별도 Python 환경의 기본 전체 스위트 | 825개 중 776 통과, 실패 0, 49 건너뛰기 | tracing 미설치 상태의 최초 실행 |
| tracing 포함, DB 설정을 주입하지 않은 전체 스위트 | 825개 중 787 통과, 실패 0, 38 건너뛰기 | 최종 전체 단위·계약·회귀 실행 |
| 현재 TEST DB와 호환되는 실제 통합 스위트 | 20개 모두 통과, 실패·건너뛰기 0 | 실제 Neo4j·PostgreSQL 연결과 제한된 fixture·격리 데이터 쓰기 검사 |

Python 환경은 /tmp/robingraph-qa-python에 uv.lock 기준으로 준비했으며 test·tracing 추가 의존성을 포함한다. 실제 통합 검사는 tests.test_neo4j_integration, tests.test_related_species_integration, tests.test_postgres_ingest_integration을 실행했다. PostgreSQL 이름에 test가 포함됨을 검사하고 TEST 설정을 주입했으며 localhost 중계를 사용했다. Neo4j fixture 검사는 커밋된 합성 fixture를 재적재·복원하고, PostgreSQL 검사는 고유한 테스트 데이터와 스키마 준비를 사용한다. 운영 DB에는 쓰지 않았다. 따라서 이 작업에는 TEST DB의 제한된 테스트 쓰기가 포함된다.

전체 스위트에 실제 환경 파일과 통합 플래그를 한 번에 주입한 중간 실행은 816개 실행, 실패 1·오류 2·건너뛰기 6이었다. 임베딩 흐름과 hybrid 클래스가 요구하는 3차원 벡터 인덱스가 기존 TEST의 512차원 인덱스와 충돌해 안전하게 거절됐다. 기존 인덱스를 삭제하지 않았다. 다른 실패는 실제 Jev 설정이 semantic 라우터를 기대하는 mock 단위 테스트에 섞인 환경 오염이었다. 이후 단위 스위트를 깨끗한 환경에서 실행하고 현재 DB와 호환되는 통합 테스트만 분리해 통과를 확인했다. 3차원 인덱스를 요구하는 검사는 별도 일회용 Neo4j가 필요하므로 이번 TEST에서 통과했다고 기록하지 않는다.

최종 전체 실행의 건너뛰기 38개에는 실제 DB opt-in 검사와 원자료 부재 검사가 포함된다. 그중 호환되는 20개는 위 별도 실제 DB 스위트로 검증했다. 원자료가 필요한 분석과 별도 일회용 DB·분류/이름 수집 계약 검사는 남아 있다. 구체적인 건너뛰기 사유는 검증 자산의 skips.json에 보관한다. 각 계층의 결과는 겹치는 내용이 있어 합쳐 하나의 고유 테스트 수로 표현하지 않는다.

## 실제 브라우저 검증

Playwright Chromium을 설치해 실제 TEST UI를 사용했다. API route interception과 모의 응답은 사용하지 않았다. 1280×900, 390×844, 320×568에서 기본 레이아웃, 실제 청둥오리 채팅, 카드 열기·앞뒤 전환·닫기, 답변 출처 링크, 더 알아보기, 근연종 조회와 비교, 생태·아종·통칭 탐색, 대화 삭제를 확인했다. 실제 입력창 경로로 프로필을 조회하고 각 탐색 버튼의 실제 HTTP 응답을 기다렸다.

브라우저 주 검사는 39개 모두 통과했다. 이 수에는 화면 검사, 직접 채팅 API 경로 검사, JS·동일 origin 서버 오류 집계가 함께 포함된다. 분류·먹이·서식·활동·아종·근연·관찰·문헌·미확인 이름 채팅과 별도 /birds 페이지도 포함한다. JS pageerror 0, 동일 origin 서버 5xx 0, 세 화면 폭에서 가로 넘침 없음이다. 비교 도감 카드 진입 버튼은 2개였다. 최초 비교 검사 3건은 테스트 코드가 카드 내부의 숨김 버튼까지 세어 12개로 판단해 실패했으므로 선택자를 실제 도감 진입 버튼으로 수정하고 전체 검사를 다시 실행해 통과했다. 제품 코드는 수정하지 않았다.

확장 검사는 12개 모두 통과했다. 데스크톱·모바일에서 예시 질문 클릭, 실제 사진 로딩, 마우스 드래그·CDP 터치 뒤집기, Shift+Enter 줄바꿈·Enter 전송, 까치 프로필과 고급 분류 필터를 확인했다. 실제 기기 터치나 iOS Safari 검증과는 구별한다. 카드 앞·뒤, 모바일 비교와 birds 화면 스크린샷을 직접 확인했다.

## 실제 API·외부 서비스 검증

API 직접 검사 18개 모두 통과했다. 관련·유사·생태·아종·통칭·프로필, 국명·학명 계통, 필터를 지정한 관찰 API와 채팅, 문헌 fulltext·hybrid 검색, 명시적 문헌 채팅, 기존 fixture 답변을 확인했다. 알 수 없는 종 404, 계통 파라미터 누락·빈 질문·역전 날짜 범위 422도 기대 상태로 검증했다. 잘못된 입력의 기대 오류를 정상 요청 성공처럼 기록하지 않는다.

실제 필터 관찰 조회는 1건을 반환했고 일반화된 좌표 비공개 경고를 유지했다. 필터 없는 자연어 관찰 질문은 clarify로 추가 조건을 요청했으며 오류가 아니다. mallard의 fulltext 검색 결과는 0건, hybrid는 vector 채널 결과 2건과 경고 없음이었다. 이는 해당 fixture 문헌 범위와 구별해 기록한다. fixture를 검색한 별도 fulltext 검사는 4건을 반환했다.

Jev가 실제 아종·관찰·문헌·미확인 이름 질문에서 route_method=jev로 동작했다. Gemini는 fixture 호수·하천의 관찰 문헌 질문에서 검색 근거 3건을 사용해 단순 기본 문구와 다른 답변과 fixture-chunk 근거 ID를 반환했다. 이는 실제 외부 생성 호출과 서버 근거 검증의 결과이며 합성 fixture 문헌을 사용했으므로 운영 논문 전체의 품질 검증은 아니다. 실제 벡터 검색은 TEST 설정의 임베딩 서버를 호스트 중계를 통해 호출했다.

MLflow 실험과 최근 30분의 trace 10건을 HTTP API로 확인했다. status는 OK 9건·ERROR 1건이므로 전체 trace 무오류라고 기록하지 않는다. 초기 기본 urllib User-Agent 확인은 HTTP 오류였고 식별 가능한 User-Agent로 재조회해 실험·trace를 확인했다. ERROR trace의 개별 원인은 이번 검사에서 추가로 확정하지 않았다.

최종 배포 검증기는 passed=true였으며 /health의 status=ok, mode=neo4j, deployment_target=test와 Docker running·healthy를 확인했다.

## 변경 파일·검증 증거·재실행

이 작업은 런타임 구현을 바꾸지 않았다. docs/work-log/2026-10-14-local-test-deployment.md에 향후 검증 환경이라는 사용자 지정을 추가하고 본 문서를 최종 결과로 갱신했다. docs/verification/assets/2026-10-14-local-test/에는 summary.json, skips.json, browser.json, extended.json, api.json, deployment.json, mlflow.json과 실제 스크린샷·검증 스크립트 3개를 보관한다. 인증 파일과 원본 서버 로그는 Git에 넣지 않는다.

브라우저 재실행 예시는 현재 준비된 임시 Playwright 설치를 사용한다.

```sh
NODE_PATH=/tmp/robingraph-browser-qa/node_modules QA_OUTPUT=/tmp/robingraph-browser-rerun node docs/verification/assets/2026-10-14-local-test/full-browser.cjs
NODE_PATH=/tmp/robingraph-browser-qa/node_modules node docs/verification/assets/2026-10-14-local-test/extended.cjs
node docs/verification/assets/2026-10-14-local-test/api-check.cjs
```

임시 단위 로그는 /tmp/robingraph-clean-full-tests.log, 실제 DB 로그는 /tmp/robingraph-compatible-integration-tests.log이며 /tmp 자료는 영구 보관을 보장하지 않는다. 재실행에 Playwright와 Chromium 설치가 필요하다. 서비스가 8000번에서 응답하는지 먼저 확인한다.

## 배포·커밋·운영 영향과 남은 사항

현재 TEST는 실행 중이며 로컬 OrbStack만 승인 후 재시작했다. portainer_agent도 다시 실행됐다. 원격 운영 배포·운영 컨테이너 재시작·운영 DB 변경·운영 DNS 변경은 수행하지 않았다. 작업 문서와 검증 자산은 미커밋으로 남긴다. Obsidian 저장은 요청되지 않아 수행하지 않았다. 검증 스크립트 자산 추가 후 Graphify AST를 갱신한다.

중요한 환경 한계는 직접 LAN 연결이 복구된 상태가 아니라 임시 Python 중계와 Compose override로 TEST가 동작한다는 점이다. 중계가 종료되거나 서버가 재부팅되면 현재 TEST의 DB·임베딩 연결은 끊길 수 있다. 시스템 설정에서 OrbStack 로컬 네트워크 허용과 방화벽·경로를 확인한 뒤 컨테이너 직접 접속을 재검증하고 중계를 제거해야 한다. 원본 deploy_nas.sh만 재실행하면 이번 로컬 포트와 중계 override가 적용되지 않는다. 현재 실행 파일은 /tmp/robingraph-browser-qa/lan-relay.py와 local-test-relay-compose.json이다.

모든 종·원자료 전체, 실제 모바일 기기·Safari·Firefox, 장시간 부하·재부팅 후 자동 복구, 원격 수집 스케줄과 일회용 DB 전용 테스트는 이번 결과에 포함하지 않는다. 현재 검증 범위에서 앱 기능 오류는 남지 않았지만 환경 직접 접속 문제와 위 범위는 후속 확인이 필요하다.
