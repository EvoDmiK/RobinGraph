# Jenkins·GHCR 배포 구성과 사전 검증 — 2026-10-18

## 요청 배경·목표

사용자가 수동 tar NAS 배포를 Jenkins로 자동화하는 방안을 요청하고 Jenkins 주소·접속 정보를 제공했다. Registry는 GHCR을 선택했다. TEST 자동 배포와 사용자 승인 후 Production 승격을 준비하되 운영 반영은 실행하지 않는 범위다. 인증 값은 기록하지 않는다.

## 초기 확인

실제 Jenkins2.580.1/Linux amd64/Java21.0.12.1, job0·plugin0·controller executor2였다. admin 인증 성공을 확인했다. 로컬 GitHub 계정은 EvoDmiK이며 repo/workflow 등의 기존 OAuth scope만 있고 write:packages가 없어 GHCR 업로드에 사용할 수 없었다. Git 저장소는 공개이며 default branch main, 현재 작업 브랜치는 dev-codex다. GHCR credential robingraph-ghcr 등록을 사용자에게 요청했고 현재 미등록이다.

## 변경 내용

- workflow-aggregator/git/credentials-binding/junit 및 copyartifact와 의존성, 총68개 플러그인 설치. 캐시된 Pipeline option descriptor 갱신을 위해 유휴 Jenkins만 safeRestart하고 정상 복귀·agent 재연결을 확인했다.
- M4 16GB에 Homebrew openjdk@21·uv 설치. robingraph-mac16 inbound WebSocket agent·1executor/exclusive·로그인 LaunchAgent를 구성했다. controller executor는0으로 바꿔 빌드를 실행하지 않게 했다. agent secret은0600 파일, LaunchAgent는 secret 파일 참조만 가진다.
- Jenkinsfile: checkout/tests·임시 registry 인증·ARM64/AMD64 build/publish·AMD64 fixture smoke·digest TEST 배포·검증 receipt. CHECK_ONLY 지원, TEST5분 polling, concurrent build 금지.
- ci/Jenkinsfile.production: 성공한 최신 TEST artifact를 읽고 번호/검증 flag/commit/digest 확인 후 admin input 승인, 이후 NAS pull·앱교체·검증 경로. 자동 트리거 없음.
- scripts/deploy_registry_test.py: digest/revision/기존 TEST target 및 image architecture 확인, private release·atomic current·공개 health 포함 검증, 실패 시 이전 TEST 복구. 관리 호스트에도 설치했다.
- scripts/deploy_registry_prod.py: 승인 후 실행할 SSH/NAS 코드. 실제 prod target·DB 설정 유지·AMD64/revision 확인, image-only compose 교체·API 검증·환경/이미지 rollback, 임시 Registry 인증 정리. 관리 호스트에 설치했지만 운영 실행하지 않았다.
- tests/test_registry_test_deployment.py, tests/test_registry_prod_deployment.py: 임시 파일과 mock subprocess로 private env 유지·mutable/foreign image 거절·target 거절·rollback 복구 검증.
- docs/jenkins-deployment.md: 실제 상태·credential 등록·운영 절차·한계.

job은 RobinGraph-Preflight(실행), RobinGraph-TEST(비활성), RobinGraph-PROD(비활성) 세 개다. 초기 TEST/PROD job은 로컬 Jenkinsfile과 같은 inline source를 저장하고 API로 재조회해 일치함을 확인했다. 앱은 원격 공개 dev-codex에서 checkout한다. 새 CI 파일은 현재 commit/push하지 않았으며 원격에 없으므로 Pipeline from SCM으로 등록했다고 표현하지 않는다. helper host 사본은 source와 함께 관리한다.

## 실제 검증·실패 보정

1. Jenkins Preflight#1: 원격 commit b7c787e27811e17a41e7a33d9561bde71d109ad2 checkout. Python922개 중884통과·38건너뜀, Node317통과. 이후 임시 DOCKER_CONFIG에 OrbStack context가 없어 Docker 연결 실패, build FAILURE.
2. registry 인증만 임시 분리할 때 context도 import하도록 수정. Preflight#2는 docker context export가 기본 파일로 내보내는 동작을 잘못 사용하여 metadata 없는 stdin import로 실패했다. 앱·DB 변경 없음.
3. export에 `-`를 명시하여 stdout tar stream을 import했다. 실제 임시 Docker config에서 orbstack daemon arm64 연결을 먼저 확인한 뒤 Preflight#3 전체를 재실행했다. **SUCCESS**. Python884통과/38건너뜀(922개), UI317통과/실패0/건너뜀0, Docker arm64 확인. 38개는 외부/통합 조건부 skip이며 전체 실 DB 검사로 표현하지 않는다.
4. TEST helper 최초 단위3개 중2개는 macOS /var→/private/var 경로 비교 fixture 오류로 실패했다. tempfile path를 resolve하여 고친 뒤 Production helper 검사와 함께 **6개 통과**했다. 실제 서비스·DB rollback 검증은 아니다.
5. Jenkinsfile과 Production Pipeline 모두 실제 Jenkins model converter validate 통과. TEST/PROD job disabled 및 저장 source 일치를 readback 확인했다. 새로운 CI helper6개는 로컬에서 실행했으며 원격 체크아웃922개 결과에 합산하지 않는다.
6. 최종 source에는 이전 workspace의 image metadata/test receipt 삭제를 추가해 stale artifact 보존을 막았다. public TEST health 실패도 helper rollback 범위에 포함했고 해당 변경 후6개 단위를 재실행·통과했다.

증거: docs/verification/assets/2026-10-18-jenkins/jenkins-status.json, preflight-{1,2,3}.json/.txt, deployment-unit.txt. status에는 plugin버전·node/job 상태·credential ID/종류만 기록하고 비밀값은 포함하지 않는다.

## 초기 credential 대기 시점의 완료 경계

Jenkins 서비스·agent·job 구성과 사전 검사는 완료했다. **GHCR credential 미등록으로 실제 image publish·Registry 기반 TEST 배포는 아직 안 했다.** TEST/PROD job을 모두 비활성으로 남겨 자동 publish/배포를 하지 않게 했다. NAS SSH credential은 Jenkins 암호화 credential에 등록했지만 Production job은 실행하지 않았다. TEST와 Production 앱·DB/Neo4j/n8n을 이 작업으로 재시작하거나 변경하지 않았다. 새 Git commit/push/병합 없음.

GHCR 등록 후에는 credential 확인→TEST 전체1회 실행→image digest/platform·실제 TEST API/UI 검증을 진행해야 한다. Production은 이 결과를 제시하고 별도 명시적 승인 전까지 비활성/미실행을 유지한다. approval step 문법 검증은 실제 사용자의 승인/배포 검증이 아니다. 운영 rollback의 실제 성공도 추정하지 않는다.

## 초기 대기 단계의 후속·한계

- PAT classic write:packages 필요. 저장소 공개라 repo scope는 필요 없다. secret 본문을 채팅이나 문서로 재출력하지 않는다.
- native agent는 로그인 LaunchAgent와 Java21이 필요하다. Mac 물리 재부팅·로그인 전 복구·Jenkins 장기부하는 미검증이다.
- 코드와 host helper·inline job 버전이 함께 바뀌어야 한다. 추후 사용자 Git 게시 지시 후 Pipeline from SCM 전환 가능하다.
- 이 초기 단계에서는 ARM64/AMD64 게시와 NAS native AMD64/Production DB 경로를 확인하지 않았다. 이후 게시·TEST 성공은 아래 최종 결과를 따르며 운영은 여전히 미실행이다.
- 상세 운영 절차와 권한 ID는 docs/jenkins-deployment.md를 따른다. Writer에게 확정 증거와 실제 완료/미완료 경계를 전달해 로컬·Obsidian 기록을 맞춘다.

## GHCR 등록 후 최종 TEST 배포 결과

위 미등록·미배포 설명은 초기 대기 상태다. 사용자가 credential 등록을 알린 뒤 ID·종류만 확인하고 TEST job을 활성화했다. Production job은 비활성으로 유지했다.

### 첫 실제 실행의 실패와 보정

TEST#1은 GHCR 로그인 성공 후 docker buildx의 --platform flag 오류(exit125)로 실패했다. 임시 Docker config가 ~/.docker/cli-plugins에 있는 buildx/compose 탐색 경로까지 가린 것이 원인이었다. 앱 교체 단계에 도달하지 않았다.

임시 config에서 CLI plugin 경로를 참조하도록 수정하고 실제 buildx v0.37.2·Compose v5.5.0 실행을 확인했다. 매 실행 config를 새로 만들고 post에서 제거한다. NAS helper도 사용자 CLI plugin 경로가 있으면 임시 config에서 유지한다. 공개 TEST health 실패도 rollback에 포함했고, Production env 원본은0600 백업으로 보존하도록 추가했다. 최종 helper 단위6개 재실행 통과.

### TEST#2 실제 성공

- Jenkins 결과: **SUCCESS**, CHECK_ONLY=false.
- 원격 dev-codex commit: b7c787e27811e17a41e7a33d9561bde71d109ad2.
- Python922개 중884통과·38건너뜀, UI317통과·실패0·건너뜀0.
- 같은 commit을 ARM64/AMD64로 빌드·GHCR push. M4에서 AMD64 network-none fixture health/openapi 통과. 이는 NAS native AMD64 실 DB 검증이 아니다.
- Mac ARM64 image revision 확인, 실제 TEST 컨테이너 교체, health·실제 API 계약·공개 health 통과. test-release.json에 검증한 digest를 저장했다.
- 이미지: ghcr.io/evodmik/robingraph@sha256:9d3fbea038a9a4cdfb423a2de50d9ca923766af5891c24941f28f79cfbafcee6.
- TEST container: 5796debae46cafe293f62288a0e4c0a16cc5880d32ef6dafcab614f828c3d133.
- 시작: 2026-10-18T01:14:49.948571543Z, healthy/arm64.
- current: /Users/kimdove/robingraph-test/releases/ci-b7c787e27811-9d3fbea038a9-4ac5f0b7. RELEASE.json state=verified, previous release 보존.
- 이전 env와 비교해 바뀐 키는 ROBINGRAPH_IMAGE·ROBINGRAPH_VCS_REF 두 개뿐이다. DB·Neo4j·n8n 설정/위치는 변경하지 않았다.
- 배포 후 실제 공개 HTTPS Chromium1280/390/320 각3POST=9회와 /birds1건 통과, pageerror0. API/JS route mock 없음. 물리 모바일 검사는 아니다.

### 운영 보존과 재조회

TEST job source=Jenkinsfile·활성, PROD source=ci/Jenkinsfile.production·비활성을 readback 확인했다. host helper 두 파일도 source hash와 일치했다. Production lastBuild=null.

NAS 읽기 전용 SSH 로그인 후 Production ID 03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd, 시작2026-10-10T06:07:33.413088244Z, image robingraph-api:prod-approved-ui-0681747 동일을 확인했다. 이번 Jenkins 작업으로 운영 앱을 변경/재시작하지 않았다.

현재 NAS TEST 컨테이너는 없다. 처음 Production·TEST 동시 inspect는 없는 TEST 때문에 nonzero였고, Production만 재조회하고 TEST 존재 여부를 별도로 확인했다. 이번 작업으로 NAS TEST를 삭제/재생성하지 않았다. 2026-10-17 정지·보존 기록은 당시 상태다. 현재 롤백 기준은 Mac previous release다.

문서 갱신 도중 긴 셸 heredoc의 UTF-8 입력 오류가1회 발생해 문서 수정만 실패했다. apply_patch로 기록을 갱신했으며 앱·배포 결과에는 영향이 없었다.

### 최종 증거와 한계

증거 디렉터리에 test-{1,2}.json/.txt, test-release.json, image-metadata.json, deployed-test.json, environment-preserved.json, configuration-readback.json, browser-live.json 및 화면3개를 보존했다. 실제 Registry TEST 경로는 완료했다. 운영은 최신 성공 TEST artifact+admin 명시적 input 승인 전 비활성으로 유지한다. TEST polling은5분 간격이다.

최초 설정 완료 보고 시점에는 새 CI 구성 파일을 Git commit/push하지 않았다. 이후 사용자가 게시를 명시 지시했다. 실제 TEST/운영 rollback·NAS native AMD64 새 앱 검증·Production approval 런타임은 미검증이다. 저장소·Obsidian 기록을 이 최종 결과로 일치시키도록 Writer에게 전달한다.

## 후속 Git 게시 요청

사용자가 Jenkins 구성 파일의 commit/push를 명시 승인했다. CI 파이프라인·배포 helper·6개 단위 검사·상세 절차·검증 증거와 공통 지침을 dev-codex 브랜치에 묶어 게시하는 범위다. 게시 전 원격과 HEAD 일치(0 ahead/0 behind), helper6개 단위 통과, diff whitespace와 비밀값 검사를 확인했다. 초기 미게시 설명은 당시 상태이며 원격 게시의 최종 결과는 해당 Git 작업의 SHA 검증을 따른다. 운영 배포나 job 활성화는 이 요청에 포함하지 않는다.
