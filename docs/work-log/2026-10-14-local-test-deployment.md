# 현재 서버 TEST 배포

## 요청과 목표

현재 환경 변수로 TEST를 배포하라는 요청을 처음에는 NAS 배포로 해석했다. 사용자는 이 서버의 TEST를 향후 구현 완료 후 검증할 환경으로 지정했다. 사용자가 현재 서버에 배포하도록 명확히 지정한 후 이 Mac의 Docker에 TEST API를 실행했다.

## 준비와 원인

현재 서버 Docker는 사용 가능했고 기존 RobinGraph 컨테이너는 없었다. .env.nas.test가 지정한 외부 Docker 네트워크 proxy_manager가 없어 생성했다. 최초 preflight는 환경 파일의 CRLF 줄바꿈 때문에 API 모드를 잘못 읽어 실패했다. TEST 파일의 줄바꿈만 LF로 정규화했으며 비밀값은 출력하지 않았다. .env.nas.prod는 변경하지 않았다. 파일 권한은 600이며 Git 제외 상태다.

## 구현과 배포

소스 커밋 ec9112903169f9abe9438660f04539c2292a1201을 기반으로 표준 scripts/deploy_nas.sh의 TEST preflight와 build를 수행했다. 이미지 robingraph-api:test-local을 생성했다. Compose 프로젝트 robingraph-test, 컨테이너 robingraph-api-test로 시작했다. 기본 Compose는 expose만 사용하므로 /tmp/robingraph-local-test-ports.yml에 로컬 포트 설정을 추가하고 원본 compose.nas.yml과 함께 사용했다. 호스트 바인딩은 127.0.0.1:8000이며 현재 서버에서 http://127.0.0.1:8000/chat으로 접속한다. 외부 도메인·프록시는 구성하지 않았다.

배포 방식은 두 Compose 파일과 TEST 환경 파일로 up -d --no-build api를 실행한 것이다. 재생성할 때도 같은 포트 override와 TEST 프로젝트·컨테이너·환경 선택을 유지해야 한다. 표준 deploy만 사용해 재생성하면 호스트 포트가 빠질 수 있다. 소스 런타임 코드 변경은 없었다.

## 실제 검증 결과

TEST preflight와 이미지 빌드 통과. 컨테이너 시작 직후 첫 verify는 프로세스 준비 전 연결 거절로 실패했으며, 재시도 이후 /health HTTP 200, status=ok, mode=neo4j, deployment_target=test를 확인했다. scripts/verify_api_deployment.py를 컨테이너 안에서 실행해 passed=true를 확인했다. 이는 실제 DB/API 계약 검증이다. /chat HTTP 200, 실제 POST /v1/chat의 청둥오리 프로필 질문 HTTP 200, disposition=answer, Anas platyrhynchos 포함을 확인했다. Docker 상태는 running·healthy였다. 배포 준비 중 프런트엔드 회귀 303개 통과, 실패·건너뛰기 0이었다. 이는 단위 회귀이며 실제 DB 검증과 구별한다.

## 증거와 한계

빌드 로그 /tmp/robingraph-local-test-build.log, API 검증 JSON /tmp/robingraph-local-test-api-check.json, 포트 설정 /tmp/robingraph-local-test-ports.yml에 기록했다. 인증 정보는 이 문서에 포함하지 않는다. Production 배포·재시작·DB 변경은 수행하지 않았다. 전체 종·관계·문헌·모델 API 기능, 실제 브라우저와 모바일 검증은 수행하지 않았다. 이번 문서는 미커밋으로 남긴다. Obsidian 저장은 요청되지 않아 수행하지 않았다. 문서 외 런타임 소스 변경이 없으므로 Graphify AST 갱신은 추가 실행하지 않았다.
