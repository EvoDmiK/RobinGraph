# 로컬 TEST 실행 설정과 자동 시작 준비

후속 상태: [OrbStack 재시작 후 점검](2026-10-14-orbstack-restart-check.md)에서 직접 DB·임베딩 연결을 확인하고 임시 중계를 제거했다. 아래의 중계 사용·미해결 내용은 당시 상태 기록이다.


## 요청 배경과 목표

전체 기능·브라우저 검증 후 남은 임시 중계 의존성과 재부팅 후 실행 문제를 수정하라는 요청이다. 컨테이너 직접 DB 연결 복구, 저장소에 로컬 TEST 포트 설정 보존, 로그인 후 OrbStack·TEST 자동 실행 준비를 목표로 했다. 사용자에게 로컬 네트워크 권한 변경이 필요함을 설명했고 사용자는 집에서 확인하겠다고 했다. 현재 중계 환경은 유지했다.

## 확인한 원인과 근거

OrbStack 인터넷 통신은 정상이나 현재 TEST Neo4j에 컨테이너 직접 TCP 연결은 다시 실패했다. 호스트 중계로는 실제 DB를 사용할 수 있다. 기존 OrbStack 설정은 app.start_at_login=false였고 컨테이너는 unless-stopped였다. 로컬 포트·중계 설정은 /tmp Compose 파일에만 있어 표준 NAS 배포로 컨테이너를 재생성하면 로컬 접속 포트가 빠졌다.

OrbStack 공식 설정 문서는 network_bridge가 Mac에서 컨테이너 IP로 접속하는 기능이라고 설명하므로 이 값을 LAN egress 해결책으로 임의 변경하지 않았다. 공식 저장소의 유사 이슈에는 macOS 로컬 네트워크에서 OrbStack·Helper 허용을 껐다 켜는 사례가 있다. 이를 참고하되 이번 환경의 원인을 확정하거나 결과를 보장하지 않는다. 시스템 설정의 해당 패널을 열었으나 이 세션의 System Events GUI 조회가 응답하지 않아 직접 토글하지 못했다. 사용자가 집에서 변경할 수 있도록 안내했다.

참고: https://docs.orbstack.dev/settings, https://docs.orbstack.dev/headless, https://github.com/orbstack/orbstack/issues/2341.

## 변경 전후와 구현 파일

- compose.local-test.yml: 원본 compose.nas.yml과 합쳐 localhost의 8000 포트를 제공한다. 비밀값과 중계 주소를 포함하지 않는다.
- scripts/deploy_local_test.sh: deploy/start/verify/status/stop 실행 경로를 추가했다. 외부 셸이 prod를 지정해도 프로젝트 robingraph-test, 컨테이너 robingraph-api-test, .env.nas.test, TEST 이미지로 고정한다. 표준 NAS preflight와 build를 재사용하고 deploy에서 이미지 빌드 후 API만 재생성한다. start는 빌드 없이 기존 이미지를 사용한다. 잘못된 인자는 Docker를 호출하기 전에 실패한다.
- tests/test_local_test_deployment.py: fake Docker를 사용하는 3개 회귀 검사로 TEST 고정, 로컬 포트 override 포함, 빌드 후 실행 순서, 잘못된 인자의 무동작을 확인한다.
- docs/service-startup.md: 현재 Mac의 실행 명령, 자동 시작 조건과 권한 변경 후 검증 순서를 추가했다.

OrbStack의 app.start_at_login을 true로 변경하고 조회해 확인했다. 기존 TEST 재시작 정책 unless-stopped도 실제 inspect로 확인했다. 설정은 사용자 로그인 후 자동 시작을 위한 것으로 로그인 전 서비스 실행이나 물리 재부팅 검증을 뜻하지 않는다. 명시적으로 stop한 컨테이너는 자동 재시작 대상이 아니다.

## 검증 방법과 실제 결과

sh -n scripts/deploy_local_test.sh 통과. Python unittest의 새 회귀 3개 통과, 실패·건너뛰기 0. 이 검사는 실제 배포가 아닌 fake Docker 검증이다. 실제 sh scripts/deploy_local_test.sh status는 preflight를 통과하고 현재 TEST의 healthy와 127.0.0.1:8000 포트를 확인했다. orb config get app.start_at_login=true, Docker inspect의 재시작 정책 unless-stopped를 확인했다. git diff --check 통과. 코드 추가 후 graphify update .을 수행한다.

기존 전체 기능·브라우저·실제 DB 검증은 이전 작업 기록에 있으며 이번에는 해당 전 범위를 다시 실행하지 않았다. 컨테이너 직접 LAN 연결은 아직 실패했으므로 새 start/deploy를 실제로 실행해 중계를 제거하지 않았다. 실제 Mac 재부팅·로그아웃 로그인·자동 복구 검사는 수행하지 않았다. 새 DB/API 쓰기는 수행하지 않았다.

## 배포·커밋·한계와 다음 작업

현재 TEST 컨테이너와 호스트 중계는 유지했고 운영 파일·NAS·운영 컨테이너·운영 DB는 변경하지 않았다. 변경은 미커밋으로 남긴다. Obsidian 저장은 요청되지 않아 수행하지 않았다.

사용자가 집에서 로컬 네트워크 설정을 변경하면 컨테이너의 원본 TEST Neo4j·PostgreSQL·임베딩 연결을 재확인해야 한다. 직접 접속이 확인된 후 새 로컬 TEST start 명령으로 포트 설정과 원본 .env.nas.test를 적용해 중계 override를 제거하고 health·배포 검증·실제 채팅·벡터 검색을 확인한다. 확인 후 임시 중계를 종료한다. 권한 변경으로 해결되지 않으면 방화벽·OrbStack 네트워크 경로를 추가 조사한다. 현재 상태를 완전한 수정 완료나 재부팅 후 동작 보장으로 기록하지 않는다.
