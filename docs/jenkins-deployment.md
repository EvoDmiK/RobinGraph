# Jenkins + GHCR 배포 운영 방법

## 현재 상태 (2026-10-18)

Jenkins와 GHCR 연결을 완료했다. **RobinGraph-TEST #2가 ARM64/AMD64 게시·Mac TEST 배포·실제 API 검증까지 성공했다.** 공개 Chromium 검사도 통과했다. TEST job은 활성·dev-codex 5분 polling, Production job은 비활성·미실행이다.

| 작업 | URL | 현재 상태 |
|---|---|---|
| 사전 검사 | http://dove-jenkins/job/RobinGraph-Preflight/ | #3 SUCCESS. Registry 인증/배포 없이 Git checkout·Python·UI·Docker 연결 검사 |
| TEST | http://dove-jenkins/job/RobinGraph-TEST/ | 활성, #2 SUCCESS. dev-codex 5분 polling |
| Production | http://dove-jenkins/job/RobinGraph-PROD/ | 생성·비활성. TEST 검증과 별도 운영 승인 전 실행하지 않음 |

초기 job은 Jenkinsfile과 같은 내용을 Jenkins Inline Pipeline으로 등록하고 저장 결과를 대조했다. 초기 설정 당시에는 CI 파일이 원격에 없어 inline을 사용했다. 이후 사용자 지시로 CI 파일을 Git에 게시한다. job은 현재 inline 방식이므로 Jenkinsfile의 Git 수정만으로 job 정의가 자동 갱신되지는 않는다. Pipeline from SCM 전환 전까지 파일과 job 내용을 함께 대조한다. 현재 앱 체크아웃은 공개 저장소 https://github.com/EvoDmiK/RobinGraph.git 의 dev-codex만 대상으로 한다.

## 배치

- Controller: dove-jenkins, Jenkins2.580.1·Linux amd64·Java21.0.12.1. controller executor0.
- Agent: robingraph-mac16, label robingraph-mac16 arm64 test, executor1·exclusive. 현재 M4 16GB(192.168.219.97).
- Java: `/opt/homebrew/opt/openjdk@21/bin/java`, uv와 Node/Docker CLI 사용.
- agent home: `/Users/kimdove/jenkins-agent/robingraph`, native WebSocket inbound agent.
- 로그인 LaunchAgent: `~/Library/LaunchAgents/com.robingraph.jenkins-agent.plist`, RunAtLoad/KeepAlive. agent secret은 별도0600 파일이며 문서/저장소에 포함하지 않는다.
- TEST 앱: 기존 `/Users/kimdove/robingraph-test/manage.sh`와 current release 사용.
- TEST Neo4j/n8n 및 PostgreSQL 위치는 변경하지 않는다. 운영 앱·DB도 별도 승인 전 변경하지 않는다.

## GHCR 인증 등록

[GitHub 공식 안내](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)에 따라 PAT **classic**을 사용한다. [write:packages만 선택하는 발급 화면](https://github.com/settings/tokens/new?scopes=write:packages)을 사용할 수 있다. 공개 Git 저장소 checkout에는 별도 repo 권한을 요구하지 않는다. delete:packages 권한은 필요 없다.

Jenkins → Manage Jenkins → Credentials → System → Global credentials에 다음으로 등록한다.

- Kind: Username with password
- Username: EvoDmiK
- Password: 발급한 PAT
- ID: robingraph-ghcr

[등록 화면](http://dove-jenkins/credentials/store/system/domain/_/newCredentials). 토큰 본문은 문서·Git·작업 로그에 기록하지 않는다. Jenkins binding으로만 전달하고 docker login은 password-stdin을 사용한다. 빌드별 임시 Docker config에 **OrbStack context도 함께 import**하여 인증 파일 분리가 Docker 연결을 가리지 않도록 한다. post에서 로그아웃하고 임시 config를 제거한다.

NAS SSH용 robingraph-nas-ssh credential은 Jenkins에 등록했다. 같은 계정으로 NAS 읽기 전용 SSH 로그인은 확인했다. 운영 작업은 이 credential만으로 실행되지 않으며 비활성과 admin 승인 단계를 함께 유지한다. Jenkins Production 배포 경로는 미실행이다.

## TEST 실행 흐름

Jenkinsfile 기준:

1. Git dev-codex checkout, 실제40자리 commit 확인. 이전 image metadata·release receipt를 지워 stale artifact 재사용 방지.
2. uv locked 환경에서 Python 전체 검사와 Node UI 검사. Docker 연결 확인.
3. 같은 소스로 linux/arm64 + linux/amd64 빌드 후 GHCR 업로드. 커밋 tag는 sha-<full commit>.
4. buildx metadata에서 **manifest digest**를 얻는다. 배포에는 tag 대신 ghcr.io/evodmik/robingraph@sha256:<digest> 사용.
5. M4에서 AMD64 fixture 컨테이너를 에뮬레이션으로 시작해 health/openapi 확인. network none·read-only·임시 /tmp로 실행한다. 이는 NAS 실 DB 검증이 아니다.
6. Mac TEST에 ARM64 digest를 pull하고 image revision label·architecture 확인.
7. 기존 TEST env의 DB값을 보존한 private release를 만들고 current를 atomic 전환. 컨테이너 시작·health·실제 API 계약·공개 TEST health를 검증한다.
8. 실패 시 previous release로 current를 복구하고 이전 앱 health/API를 다시 확인한다. 롤백도 실패하면 작업은 실패 상태로 남고 receipt에 rollback_started를 남긴다.
9. 검증 후에만 test-release.json을 작성·archive한다. 이 파일에 digest·commit·test_verified:true를 보존한다.

CHECK_ONLY=true는 publish/AMD64 smoke/TEST 변경을 모두 건너뛴다. Preflight는 이 모드 전용이며 polling이 없다. 실제 TEST job의 polling은 활성화 이후5분 간격이며 운영 job에는 자동 트리거가 없다. 같은 TEST job 동시 배포를 막고 agent도1executor로 직렬화했다.

TEST helper 원본은 scripts/deploy_registry_test.py이며 현재 host의 `/Users/kimdove/robingraph-test/deploy_registry_test.py`에 설치했다. helper 변경 시 원본을 검증하고 관리 호스트 사본을 함께 갱신한다. inline pipeline 자체 변경도 Jenkins job과 Jenkinsfile을 함께 대조한다.

## Production 실행 흐름과 승인

ci/Jenkinsfile.production 기준이며 아직 비활성·미실행이다.

1. TEST_BUILD에 **가장 최근 성공한 RobinGraph-TEST 번호**를 지정한다.
2. Copy Artifact가 latest successful build에서 test-release.json을 가져오고 선택 번호와 일치하는지 확인한다. 임의 JSON·실패 build·TEST가 확인되지 않은 이미지를 승격하지 않는다.
3. commit·immutable digest를 화면에 제시하고 **submitter=admin**의 명시적 승인 입력을 기다린다. approval stage는 agent를 점유하지 않는다.
4. 승인 후 NAS SSH와 GHCR credential을 binding한다. StrictHostKeyChecking=yes를 사용한다.
5. NAS에서 기존 Production target과 DB설정 일치를 먼저 확인한다. immutable AMD64 image를 pull하고 revision·architecture를 확인한다.
6. 기존 Production의 compose/env 위치를 inspect로 찾아 image/revision만 atomic 변경하고 --no-build --no-deps up으로 앱만 교체한다. 소스 tar 전달·NAS 빌드는 없다.
7. health/API 계약 실패 시 원래 env·이미지를 복원하고 복구를 검증한다. DB 마이그레이션·수집·volume 삭제·compose down은 없다.

원본 scripts/deploy_registry_prod.py는 관리 호스트 `/Users/kimdove/robingraph-test/deploy_registry_prod.py`에 설치했다. 원격 실행 코드는 SSH stdin으로 전달하며 소스 릴리스 tar를 NAS에 풀지 않는다. Registry 인증은 원격 private 임시 폴더에 두고 종료 시 제거한다. 실제 운영 실행 전에 TEST 전체 경로 성공과 사용자 결과 확인·별도 승인이 필요하다.

## 실제 완료와 남은 검증

GHCR login/push/pull·ARM64/AMD64 게시·M4의 AMD64 fixture 시작·Mac TEST digest 배포·API 계약·공개 Chromium 1280/390/320의9POST 및 /birds 검사가 통과했다. revision은 b7c787e27811e17a41e7a33d9561bde71d109ad2, image는 ghcr.io/evodmik/robingraph@sha256:9d3fbea038a9a4cdfb423a2de50d9ca923766af5891c24941f28f79cfbafcee6 이다.

실제 TEST rollback·Production approval 런타임·운영 배포/rollback·운영 DB에서 새 앱 검증은 미실행이다. rollback은 mock subprocess/임시 파일6개 검사로 확인했다. 운영 helper는0600 원본 env 백업과 receipt를 남기도록 준비했다. 물리 재부팅·로그인 전 agent 복구도 미검증이다.

현재 NAS에는 robingraph-api-test 컨테이너가 없다. 이전 NAS TEST 정지·보존 기록은 당시 상태이며 현재 롤백은 Mac previous release를 기준으로 한다. TEST 자동 배포 완료와 Production 운영 완료를 구분한다.

공식 참고: [Jenkins agents](https://www.jenkins.io/doc/book/using/using-agents/), [Pipeline syntax](https://www.jenkins.io/doc/book/pipeline/syntax/), [Copy Artifact](https://plugins.jenkins.io/copyartifact).
