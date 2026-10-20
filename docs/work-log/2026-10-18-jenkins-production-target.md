# 2026-10-18 Jenkins 배포 대상을 NAS Production으로 정정

## 배경과 목표

사용자는 Jenkins 도입을 기존 NAS 운영 배포 대체로 요청했다. 앞선 구성은 RobinGraph-TEST를 자동 대상으로 설정했고 Production을 비활성 승격 job으로 남겼다. 사용자가 TEST가 아니라 운영에 배포해야 한다고 재차 정정했다. 이번 요청은 이미 TEST 결과를 보고 받은 현재 릴리스의 운영 반영 지시로 적용한다. 미래 릴리스의 포괄적 승인으로 확대하지 않는다.

## 원인과 변경 전후

변경 전에는 루트 Jenkinsfile이 Mac TEST 배포를 포함하고 5분 polling으로 실행됐으며, Production은 TEST_BUILD/latest successful TEST artifact를 요구했다. 변경 후에는 루트 Jenkinsfile과 ci/Jenkinsfile.production이 직접 Production 파이프라인이다. M4 검사·이미지 빌드·AMD64 fixture 검사 후 admin 승인으로 NAS 앱만 교체한다. TEST job은 비활성이고 polling을 제거했다. 수동 레시피는 ci/Jenkinsfile.test에 보존한다.

NAS 앱의 compose label이 가리키는 /home/kimdove/RobinGraph-approved-ui-e7ad221 폴더에는 기존 compose/env 파일이 없었다. 실행 중 컨테이너의 환경과 이미지 기본 환경을 대조해 앱 환경을 복원하고 private .env.nas.prod를 0600으로 생성했다. compose 렌더링 결과의 47개 환경값 보존과 proxy_manager 네트워크를 확인했다. 이 준비 과정에서 기존 컨테이너 ID가 바뀌지 않았다. 원래 운영 이미지와 환경은 배포 helper의 private backup/receipt에 보존한다. 인증값은 문서에 기록하지 않는다.

## 구현 파일

- Jenkinsfile: 기본 배포를 NAS Production으로 교체, TEST artifact 의존성 제거, 승인과 production-release.json archive 추가.
- ci/Jenkinsfile.production: 루트와 동일한 실행 정의.
- ci/Jenkinsfile.test: 기존 TEST 파이프라인을 수동 보관, polling 제거.
- docs/jenkins-deployment.md, docs/deployment-profile.md: 현재 대상과 실행 절차 정정.
- AGENTS.md: 운영 대상·TEST 비활성·미래 명시 승인 유지 기록을 다른 세 워크트리에 해당 문단만 전파. 다른 지침 보존.
- 앱 Python/JS/CSS와 DB 스키마 변경은 없다. 기존 production helper는 원본과 관리 호스트 사본이 동일함을 확인했다.

## 실행과 검증

- Jenkins Pipeline model converter: 실제 서버에서 문법 통과.
- 등록된 Production Inline Pipeline과 로컬 Jenkinsfile 재조회 비교: 일치. Git 파일만 수정해 job이 자동 갱신된다고 가정하지 않는다.
- uv run --locked --extra test python -m unittest tests.test_registry_prod_deployment tests.test_registry_test_deployment: 6개 통과. subprocess mock/임시 파일 검증이며 실제 운영 rollback 검증이 아니다.
- Production #1: 오래된 agent 연결에서 checkout이 진행되지 않아 중단했다. 운영 앱 변경 전에 중단됨.
- Mac Tailscale BackendState=Stopped와 dove-jenkins DNS 해석 실패를 확인했다. NAS LAN의 기존 Jenkins 8080 포트로 접속 경로를 변경했다. 재연결 시 기존 stale 채널을 disconnect한 후 WebSocket 연결을 회복했다.
- Production #2: commit bc643ee9edef0fc58c605adde70b4808b7622ac5 checkout. Python 928개 실행, 890개 통과·38개 skip. ARM64/AMD64 GHCR 게시 완료. AMD64 fixture health/openapi 시작 검사 통과.
- manifest digest: sha256:100e4aa30fd8981ebb631ced8c4bfecd95e71fcdb6d90cc5026e42f11b333ead. 같은 소스라도 build provenance 등으로 이전 TEST manifest와 digest가 다를 수 있다. image revision label로 실제 소스를 검증한다.
- #2 admin input: 현재 사용자의 명시적 운영 배포 요청에 따라 이 commit/digest에 한해 진행했다. 이후 실행의 승인 gate는 유지한다.

## 최종 실제 결과

- **RobinGraph-PROD #2 SUCCESS**: http://dove-jenkins/job/RobinGraph-PROD/2/ (LAN 대체 http://192.168.219.99:8080/job/RobinGraph-PROD/2/).
- Node UI 검사 317개 모두 통과, 실패/skip 0. Python 928개 중 890개 통과·38개 skip. skip을 실제 DB 통합 성공으로 간주하지 않는다.
- NAS 앱은 immutable digest sha256:100e4aa30fd8981ebb631ced8c4bfecd95e71fcdb6d90cc5026e42f11b333ead, OCI revision bc643ee9edef0fc58c605adde70b4808b7622ac5, architecture amd64, target prod, health healthy. NAS receipt state verified. 이전 이미지는 robingraph-api:prod-approved-ui-0681747이며 private env backup을 남겼다.
- NAS 내부 실제 API: health/OpenAPI/청둥오리 lineage 200, contract parity/canary 통과. 공개 https://robingraph.dove-nest.com 에서 같은 GET 검증을 별도 실행해 passed=true 확인. fixture 프로세스 release와 lineage 참조 taxonomy release의 차이는 서로 다른 데이터 영역이므로 혼동하지 않는다.
- 운영 컨테이너 env와 compose 렌더링 env 일치를 확인했고 Neo4j bolt://neo4j:7687, PG database robingraph를 유지했다. DB 내용 전체 비교는 실행하지 않았다.
- 공개 Chromium 1280/390/320: 고급 조회 옵션·outside 선택·작성 중 질문 유지·가로 넘침 없음·pageerror 없음 확인. 실제 운영 정적 자산에 접속했으며 POST는 차단했다. 초기 검사에서 차단된 POST를 모두 0으로 예상해 assertion이 실패했으나 실제 경로는 Cloudflare /cdn-cgi/rum telemetry였다. chat POST가 0인지 구분하도록 검사 자체를 바로잡아 재실행 통과했다. 답변 생성·그래프 쓰기를 운영에서 수행한 검증이 아니며 물리 모바일도 아니다.
- TEST 컨테이너의 배포 전후 ID·image·StartedAt 완전 일치. TEST job disabled=true. 운영 앱만 교체했다.
- 기존 Mac Tailscale 연결을 up으로 복구한 후 BackendState Running, dove-jenkins 응답을 확인했다. LAN에서 LaunchAgent Java의 NoRouteToHostException을 관측했으므로 원래 Tailscale 주소로 관리 agent를 복귀했다. LaunchAgent bootstrap 후 WebSocket Connected 및 Jenkins offline=false/idle=true 확인. 임시 foreground agent는 종료했다. 재부팅·로그인 전 실행은 여전히 미검증이다.
- 증거: docs/verification/assets/2026-10-18-jenkins-production/ 의 production-2.json/.txt, production-release.json, image-metadata.json, public-api.json, production-before/after.json, test-unchanged.json, pipeline-readback.json, approval.json, browser-readonly.json 및 스크린샷.


## 커밋과 한계

현재 앱 소스는 원격 bc643ee9edef0fc58c605adde70b4808b7622ac5이다. 이번 파이프라인·문서 정정은 새 commit/push 지시 없이 로컬 변경과 Jenkins inline 등록으로 반영했다. NAS DB migration·대량 수집·DB 쓰기 검사는 실행하지 않았다. 운영 rollback을 일부러 유발하지 않았으며 물리 재부팅·모바일 실기기 검증도 실행하지 않았다. graphify update . 는 AST 갱신 성공, SQL parser 미설치 경고와 community label 재생성 안내가 있었다.
