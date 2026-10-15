# OrbStack 재시작 후 직접 연결 복구 확인

## 요청 배경과 목표

사용자가 OrbStack을 재시작했다고 알리고 점검을 요청했다. 직전 TEST는 임시 호스트 중계로 DB와 임베딩 서버에 연결했으며 직접 LAN 연결 복구가 남아 있었다. 재시작 후 직접 연결과 자동 시작 상태를 확인하고 정상일 경우 중계를 제거하는 것이 목표다.

## 확인한 상태와 근거

OrbStack은 Running, app.start_at_login=true였다. 재시작 후 robingraph-api-test와 portainer_agent가 다시 실행됐고 TEST는 healthy였다. 컨테이너 안에서 .env.nas.test에 기록된 원본 Neo4j·PostgreSQL·Jina 주소로 TCP 연결을 수행해 세 대상 모두 성공했다. 비밀값은 출력하지 않았다. 사용자가 macOS 권한 토글을 수행했는지는 확인되지 않아 재시작 후 정상화라는 결과만 기록한다.

## 변경 전후와 적용 내용

sh scripts/deploy_local_test.sh start로 TEST만 재생성했다. 원본 .env.nas.test와 compose.nas.yml, 저장소의 compose.local-test.yml을 사용했다. 새 빌드는 수행하지 않아 기존 robingraph-api:test-local 이미지를 유지했다. localhost:8000 포트를 유지하고 런타임 Neo4j URI, PostgreSQL host·port, Jina endpoint가 원본 TEST 파일과 일치함을 docker inspect로 비교해 확인했다. 이후 임시 lan-relay.py 프로세스를 종료했다. 현재 TEST는 host.docker.internal 중계 포트나 /tmp Compose 파일을 사용하지 않는다.

변경 파일은 docs/service-startup.md의 현재 환경 안내와 본 기록, 검증 자산의 direct-api.json·restart-check.json이다. 런타임 소스·환경 파일의 비밀값·DB 데이터는 수정하지 않았다.

## 검증 방법과 실제 결과

원본 세 대상의 컨테이너 직접 TCP 연결 성공. sh scripts/deploy_local_test.sh verify 통과. /health HTTP 200, status=ok, mode=neo4j, deployment_target=test를 확인했다. 컨테이너 재시작 정책 unless-stopped와 OrbStack 로그인 자동 시작 true를 확인했다.

실제 API 검사 18개 모두 통과했다. 프로필·국명/학명 계통·관련/유사/생태/아종/통칭·관찰·fulltext/hybrid 문헌 검색·문헌 채팅·fixture 답변과 잘못된 입력의 기대 404·422를 확인했다. 이 검사는 실제 TEST DB와 실제 임베딩 설정을 사용했으며 API 응답을 모의하지 않았다. 별도 Chromium 브라우저에서 /chat 접속, 청둥오리 입력·전송, /v1/chat HTTP 200, 프로필 응답과 도감 진입 버튼 렌더링을 확인했다. 직접 연결로 바뀐 뒤 기본 채팅 흐름을 재검증한 것이며 직전 51개 브라우저 검사를 전부 다시 실행한 것은 아니다.

직전 전체 단위·프런트엔드·실제 DB 쓰기 통합 테스트는 코드 변경이 없어 반복하지 않았다. 새 DB 쓰기 검사는 실행하지 않았다. 기록 자산은 docs/verification/assets/2026-10-14-local-test/direct-api.json과 restart-check.json이며 임시 브라우저 로그는 /tmp/robingraph-direct-browser-check.log다.

## 배포·커밋·남은 한계

이 서버의 TEST만 재생성했으며 운영 NAS·운영 파일·운영 컨테이너·운영 DB에는 작업하지 않았다. 변경 문서는 미커밋이며 Obsidian 저장은 요청되지 않아 수행하지 않았다. 코드 변경이 없으므로 Graphify AST 갱신은 추가 실행하지 않았다.

OrbStack 재시작 후 컨테이너 자동 재실행은 실제 확인했으나 Mac의 물리 재부팅·로그인과 복구는 수행하지 않았다. 자동 시작 설정과 Docker restart policy가 준비됐다는 사실과 실제 재부팅 검증을 구분한다. 현재 직접 접속과 중계 제거는 완료됐다.
