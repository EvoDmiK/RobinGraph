# Jenkins + GHCR 배포 운영 방법

## 2026-10-21 사용자 승인 후 실제 운영 앱 교체 완료

[RobinGraph-PROD #6](http://dove-jenkins/job/RobinGraph-PROD/6/) SUCCESS. 사용자 명시 승인에 따라 main `7267df697fc0912752b9b2a848d42fb8baa80b85`를 검사·빌드하고 기존 admin 승인을 API로 제출했다. NAS `robingraph-nas-deploy` 노드가 SSH 없이 로컬 Docker로 운영 앱을 교체했다. 배포 digest는 `sha256:b8d68a53064e893c9f23f182e71c81ab33bd84cba00cf4da209ba3393d3003c3`다.

- Python 1,031 실행 / 993 통과 / 38 건너뜀 / 0 실패, Node UI 317 통과, AMD64 fixture 기동 통과.
- 신규 운영 컨테이너 `3e5cda21d1b8…`, 시작 `2026-10-21T07:42:57.518338114Z`, healthy. 기존 env는 배포 영수증의 0600 백업 경로에 보존했다.
- NAS 읽기 검사 #2 SUCCESS, 내부 health/OpenAPI/lineage GET 계약 통과. 공개 Chromium 동일 출처 GET 3/3과 1280·390px 후보 선택 흐름 2/2 통과. Python urllib의 첫 공개 요청은 edge HTTP403이었으며 별도 Chromium 검사로 확인했다.
- DB 마이그레이션·백필·자료 갱신 명령과 실제 롤백은 실행하지 않았다. 전체 DB 체크섬 불변 검증, 물리 기기·호스트 재부팅은 미실행이다.
- 실제 배포 근거: `docs/verification/assets/2026-10-21-nas-agent-production/`. 아래 에이전트 설치 당시의 미배포·미커밋 설명은 과거 이력이다. 배포 후 문서·증거 커밋은 앱 이미지의 revision을 바꾸지 않는다.

## 2026-10-21 SSH 없는 NAS 배포 에이전트 전환

현재 Jenkins Inline PROD 정의는 검사·빌드를 Mac `robingraph-mac16`에서 실행하고, 기존 admin 승인 후 배포 단계만 NAS `robingraph-nas-deploy`에서 실행한다. `robingraph-nas-ssh` credential은 새 배포 단계에서 사용하지 않는다. 기존 SSH credential은 다른 사용처를 확인하지 않아 삭제하지 않았다.

- NAS 에이전트는 `jenkins/inbound-agent:jdk21` 기반 이미지에 Docker CLI·Compose·Python을 추가한다. 정의는 `ci/nas-agent/Dockerfile`, `ci/nas-agent/compose.yml`이다.
- 최초 설치는 기존 SSH를 사용했다. 이후 에이전트는 NAS에서 Jenkins의 `http://127.0.0.1:8080/`로 WebSocket 연결한다. 별도 SSH 접속이나 agent TCP 포트가 배포에 필요하지 않다. SSH 서비스 설정은 변경하지 않았다.
- 노드: exclusive, executor 1, label `robingraph-nas-deploy`. 컨테이너: `robingraph-jenkins-agent`, uid 1000 / Docker socket gid 121, host network, root filesystem read-only, cap-drop ALL, no-new-privileges, restart unless-stopped.
- NAS 설치 디렉터리: `/volume3/Birds-Nest/docker-data/robingraph-jenkins-agent`. `agent.env`의 노드 인증값은 0600 파일에만 보관한다. `.env`에 `NAS_DEPLOY_ROOT`, `NAS_AGENT_UID`, `NAS_DOCKER_GID`를 설정한다. 인증값은 문서·Git에 넣지 않는다.
- `/var/run/docker.sock` 및 기존 Production compose 디렉터리를 같은 절대 경로로 연결한다. Docker socket은 호스트 제어 권한이므로 신뢰하는 배포 작업만 이 노드를 사용한다. exclusive 라벨은 보안 격리 경계가 아니다.
- 배포 helper는 저장소 `scripts/deploy_registry_prod.py`를 NAS `helper/deploy_registry_prod.py`에 동기화하고 컨테이너 `/opt/robingraph-deploy/deploy_registry_prod.py`에 읽기 전용 마운트한다. helper 변경 시 사본과 해시도 함께 확인한다.
- 실제 교체 명령은 `python3 /opt/robingraph-deploy/deploy_registry_prod.py --local --image "$IMMUTABLE_IMAGE" --revision "$REVISION"`이다. GHCR 인증은 Jenkins credential binding을 사용하며 기존 immutable digest·revision·Production DB 대상 가드·영수증·실패 복구를 유지한다.
- 읽기 전용 확인은 `--local --check-only`다. GHCR/SSH 자격증명 없이 운영 대상과 compose 경로·Compose 실행 가능 여부만 확인하고 배포하지 않는다.

실제 검증: [RobinGraph-NAS-Agent-Check #1](http://dove-jenkins/job/RobinGraph-NAS-Agent-Check/1/) SUCCESS. SSH 호출 없이 NAS 노드에서 helper 읽기 검사 및 운영 health/OpenAPI/청둥오리 lineage GET을 실행해 모두 200·계약 검사 통과했다. 기존 운영 앱 ID·시작 시각·이미지는 전후 동일하며 healthy다. 이번에 운영 앱 교체·DB 쓰기·Production 빌드 실행은 하지 않았다. 실제 SSH 없는 이미지 교체/실패 복구·호스트 재부팅 검증은 미실행이며 운영 배포는 별도 사용자 승인이 필요하다.

로컬 관련 단위 검사 5개 통과·실패 0·건너뜀 0. Jenkins declarative lint 통과. 저장소 파일은 미커밋이며 commit/push/병합하지 않았다. 현재 Jenkins Inline 정의는 적용했으므로 Git의 main 정의와는 다음 승인된 커밋 반영 전까지 차이가 있다. 아래 이전 기록은 당시 SSH 구조의 이력이다.


## main 기준 운영 배포 (2026-10-20)

사용자의 커밋·푸시·main 병합·Production 배포 지시에 따라 운영 파이프라인의 checkout과 SCM polling 기준을 `main`으로 변경했다. 아래 2026-10-18의 `dev-codex` 기준 설명은 당시 이력이다. 저장소 `Jenkinsfile`과 `ci/Jenkinsfile.production`, Jenkins의 Inline Pipeline 정의를 함께 맞추고, 운영 승인 단계에는 배포할 main 커밋과 immutable 이미지 digest를 표시한다. RobinGraph-PROD #3이 main 커밋 `770495a`의 Django 이미지를 NAS에 배포하고 실제 API 검사까지 SUCCESS로 완료했다. 상세 결과는 [운영 배포 기록](work-log/2026-10-20-main-production-django.md)을 따른다.

## 현재 상태 (2026-10-18, 운영 대상 정정)

사용자가 지정한 배포 대상은 **NAS Production**이다. 기본 `Jenkinsfile`과 `ci/Jenkinsfile.production`은 동일한 운영 파이프라인이며 **RobinGraph-PROD**에 등록했다. **RobinGraph-TEST는 비활성**이고 SCM polling을 제거했다. TEST에 먼저 배포해야 운영 배포가 가능한 이전 승격 구조를 제거했다. 수동 TEST 레시피는 `ci/Jenkinsfile.test`에 보존한다.

- Jenkins 내부 접속: http://192.168.219.99:8080/ . 기본 http://dove-jenkins/ 는 Mac Tailscale 중단 시 DNS 실패를 관측했으나 연결 복구 후 응답과 관리 agent 재연결을 확인했다.
- 운영 job: http://192.168.219.99:8080/job/RobinGraph-PROD/ . dev-codex 변경을 5분 간격 polling한다.
- 빌드·Python/UI 검사·멀티 아키텍처 게시·AMD64 fixture 검사는 M4 16GB의 robingraph-mac16 agent에서 실행한다.
- 운영 앱 교체는 NAS `192.168.219.99`, `robingraph-api`에서 수행한다. 공개 주소는 https://robingraph.dove-nest.com 이다.
- 향후 운영 앱 교체 전에는 commit/digest를 표시하는 admin 승인 단계를 유지한다. polling은 운영 앱 교체의 자동 승인을 의미하지 않는다.
- job은 Inline Pipeline이다. 저장소 Jenkinsfile 변경만으로 job 정의가 자동 갱신되지 않으므로 등록 내용과 파일을 함께 대조한다.
- TEST 앱과 TEST DB 위치는 변경하지 않는다. Production DB 마이그레이션·수집·volume 변경도 포함하지 않는다.

RobinGraph-PROD #2의 실제 NAS 배포·내부/공개 API 검증이 SUCCESS로 완료됐다. TEST 컨테이너는 변경되지 않았다. 실제 실행 결과와 제한은 [운영 대상 정정 기록](work-log/2026-10-18-jenkins-production-target.md)을 기준으로 한다. [초기 TEST 연결 기록](work-log/2026-10-18-jenkins-ghcr-setup.md)은 당시 이력이다.

## GHCR 인증 등록

[GitHub 공식 안내](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)에 따라 PAT **classic**을 사용한다. [write:packages만 선택하는 발급 화면](https://github.com/settings/tokens/new?scopes=write:packages)을 사용할 수 있다. 공개 Git 저장소 checkout에는 별도 repo 권한을 요구하지 않는다. delete:packages 권한은 필요 없다.

Jenkins → Manage Jenkins → Credentials → System → Global credentials에 다음으로 등록한다.

- Kind: Username with password
- Username: EvoDmiK
- Password: 발급한 PAT
- ID: robingraph-ghcr

[등록 화면](http://dove-jenkins/credentials/store/system/domain/_/newCredentials). 토큰 본문은 문서·Git·작업 로그에 기록하지 않는다. Jenkins binding으로만 전달하고 docker login은 password-stdin을 사용한다. 빌드별 임시 Docker config에 **OrbStack context도 함께 import**하여 인증 파일 분리가 Docker 연결을 가리지 않도록 한다. post에서 로그아웃하고 임시 config를 제거한다.

NAS SSH용 `robingraph-nas-ssh` credential을 binding한다. 인증 정보는 SSH argv·문서에 포함하지 않는다. 기존 known_hosts와 StrictHostKeyChecking=yes를 사용한다.

## 운영 실행 흐름

1. 공개 Git 저장소 dev-codex checkout 후 실제 전체 commit을 확인한다. 이전 metadata/receipt를 삭제한다.
2. locked Python 전체 검사, Node UI 검사, Docker 연결 검사를 실행한다.
3. ARM64/AMD64 이미지를 GHCR에 게시하고 buildx metadata의 immutable manifest digest를 얻는다.
4. M4에서 AMD64 fixture health/openapi를 검사한다. 이는 실제 운영 DB 검증과 구별한다.
5. commit/digest를 표시하고 admin 승인을 기다린다. 현재 단일 agent를 점유하며 전체 60분 timeout이 적용된다.
6. NAS에서 기존 컨테이너 target=prod와 DB endpoint 일치를 확인하고 AMD64 image/revision을 검사한다.
7. private env를 0600으로 백업한 뒤 image/revision만 변경한다. `docker compose up -d --no-build --no-deps api`로 운영 앱을 교체한다. 소스 tar 전달이나 NAS 빌드는 없다.
8. container health와 실제 API 계약 검사를 실행한다. 실패하면 원래 env/이미지 복구를 시도하고 검증한다. rollback receipt에 실제 상태를 남긴다.
9. 성공한 경우에만 `production-release.json`을 archive한다.

`CHECK_ONLY=true`는 이미지 게시·승인·배포를 건너뛴다. TEST job은 비활성 상태이므로 자동 실행되지 않는다. 운영 파이프라인은 TEST artifact나 TEST_BUILD 매개변수에 의존하지 않는다.

helper 원본 `scripts/deploy_registry_prod.py`와 관리 호스트 `/Users/kimdove/robingraph-test/deploy_registry_prod.py`를 대조했다. 관리 폴더명에 test가 포함되어 있지만 실제 목적지는 helper의 NAS Production guard로 확인한다. 관리 호스트 사본을 변경할 때는 원본과 검증 결과를 함께 맞춘다.

실제 실패 복구 검사는 mock subprocess/임시 파일 검사이며 운영 rollback을 일부러 유발하지 않는다. 재부팅·로그인 전 agent 복구와 물리 모바일 검증은 별도 미검증 범위다.
