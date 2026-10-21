# [RG-7xx-NAS-AGENT] SSH 없는 NAS Jenkins WebSocket 배포 에이전트 구성 및 읽기 검증 — 2026-10-21

> **문서 상태: 완료 — 실제 NAS WebSocket 에이전트 온라인 및 읽기 전용 검증 통과 (Codex 검토 대기).** 사용자 승인에 따라 NAS 인바운드 WebSocket 에이전트(`robingraph-nas-deploy`)를 구성하고 Jenkins를 통한 읽기 검증을 성공적으로 마쳤다. 문서 담당(Writer)은 dev-codex 산출물(`docs/verification/assets/2026-10-21-jenkins-nas-agent/` 및 `docs/jenkins-deployment.md`)을 읽기 전용으로 대조하여 기록했다. 문서 담당은 앱, DB, 서비스, Git 형상을 조작하지 않았다.

---

## 요약

- **배경 및 요구사항**: 기존 Jenkins Production 배포 파이프라인은 M4 Mac 에이전트(`robingraph-mac16`)에서 빌드·검사 후, SSH(`robingraph-nas-ssh`)를 통해 NAS 운영 서버에 접속하여 배포 스크립트를 원격 실행하는 구조였다. SSH 연결은 네트워크 지연, 키 관리, 세션 실패 위험이 있어, 사용자 승인 하에 NAS에서 Jenkins 컨트롤러로 직접 연결하는 **Inbound WebSocket 에이전트(`robingraph-nas-deploy`)**를 구성하고 SSH 없는 로컬 컨테이너 배포 구조로 전환을 추진했다.
- **아키텍처 및 구현**:
  - 베이스 이미지 `jenkins/inbound-agent:jdk21`에 Docker 27 CLI, Compose v2.33.0, Python 3를 포함한 경량 에이전트 이미지(`robingraph-nas-agent:20261021`)를 빌드했다.
  - 최초 1회 설치(bootstrap)에는 기존 SSH를 사용했으나, 이후 에이전트는 NAS 내부에서 Jenkins 컨트롤러(`http://127.0.0.1:8080/`)로 WebSocket 인바운드 연결하여 온라인 상태(`robingraph-nas-deploy`, executor 1, exclusive)를 유지한다.
  - 컨테이너 보안: `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`, `restart: unless-stopped`, `user: 1000:121`(초기 권한 오류를 uid 1000 / docker socket gid 121로 정정).
  - Docker socket(`/var/run/docker.sock`)과 호스트 Production compose 디렉터리를 동일한 절대 경로(`${NAS_DEPLOY_ROOT}`)로 마운트하여 Compose 경로 해석 일관성을 확보했다.
  - 배포 helper(`scripts/deploy_registry_prod.py`)에 `--local` 및 무변경 컨텍스트 확인용 `--check-only` 모드를 추가하고, Jenkins 파이프라인에서 SSH 자격증명 바인딩을 제거하고 GHCR 자격증명만 사용하도록 변경했다.
- **검증 및 최종 상태**:
  - 로컬 단위 테스트 5개 전수 통과(mock), Jenkins declarative lint 통과.
  - Jenkins 검증 잡 [RobinGraph-NAS-Agent-Check #1](http://192.168.219.99:8080/job/RobinGraph-NAS-Agent-Check/1/) SUCCESS: SSH 호출 없이 NAS 에이전트 노드에서 helper `--local --check-only` 및 운영 API(`/health`, `/openapi.json`, `/v1/taxa/lineage?name=청둥오리`) GET 200 정상, 스키마/응답 drift 0건, 계약 검사 통과.
  - 운영 컨테이너(`robingraph-api`, id `a4d2ce5232a9...`, 기동 시각 `2026-10-20T08:55:43Z`, Django digest `sha256:336ace79...`)는 검증 전후 완벽히 동일하며 `healthy` 유지.
  - 운영 앱 교체, DB 쓰기, Production 빌드, commit/push/merge 없음. 실제 SSH 없는 이미지 교체/실패 복구/호스트 재부팅은 미실행(check-only 읽기 검증 완료).

---

## 작업 및 변경 결과 요약

| 구분 | 변경 사항 | 상세 내용 |
| --- | --- | --- |
| **원인 규명 / 요구사항** | 배포 시 SSH 의존성 제거 | M4 → NAS 원격 SSH 연결 대신 NAS에서 Jenkins 컨트롤러로 직접 연결하는 WebSocket 에이전트 도입 요구 |
| **설계 및 해결 방안** | Inbound WebSocket 에이전트 | `jenkins/inbound-agent:jdk21` 기반 컨테이너, Docker socket + 동일 절대경로 compose 마운트, helper `--local` 실행 |
| **보안 및 권한 설계** | 최소 권한 및 파일 격리 | root 파일시스템 읽기 전용, cap-drop ALL, no-new-privileges, uid 1000/gid 121, `agent.env` 0600 권한 격리 |
| **코드 / 설정 수정** | helper 및 Jenkinsfile 갱신 | `scripts/deploy_registry_prod.py`(`--local`/`--check-only`), `Jenkinsfile`, `ci/nas-agent/` 신설 |
| **실서비스 배포 현황** | 검증 잡 통과 / 운영 앱 불변 | `RobinGraph-NAS-Agent-Check #1` SUCCESS, 운영 앱 ID/기동시각/이미지 전후 불변 healthy |
| **검증 및 테스트** | 자동화/실서버 검증 | 단위 테스트 5/5 통과, lint 통과, 실제 NAS 에이전트에서 health/openapi/lineage GET 200 통과 |
| **형상 관리** | Git 미커밋 / Inline 적용 | Jenkins Inline 파이프라인은 갱신 적용 완료, Git dev-codex/main은 미커밋 상태 (commit/push 없음) |

---

## 1. 작업 배경 및 문제 분석

### 발생 현상 및 한계
- 기존 운영 배포 절차(`RobinGraph-PROD`)는 M4 Mac(`robingraph-mac16`)에서 검사 및 멀티아키텍처 이미지를 GHCR에 게시한 후, `robingraph-nas-ssh` Jenkins 자격증명을 사용하여 NAS 호스트(`192.168.219.99`)로 SSH 원격 접속해 `deploy_registry_prod.py`를 파이프로 주입·실행했다.
- 이 방식은 다음과 같은 구조적 한계와 잠재적 취약점을 내포하고 있었다:
  1. **SSH 연결 취약성**: 네트워크 순단, SSH 데몬 설정 변경, 또는 Tailscale/DNS 이상 시 배포 단계 실패 위험.
  2. **자격증명 분산**: Jenkins 컨트롤러에 NAS 호스트 계정의 SSH 인증 정보를 보관해야 함.
  3. **비표준 런타임 제어**: SSH 파이프로 파이썬 스크립트를 주입하는 임의성.

### 요구사항 및 설계 검토
- NAS가 직접 Jenkins 마스터로 연결되는 인바운드 WebSocket 에이전트를 상시 컨테이너로 구동하여:
  1. 외부에서 NAS로의 SSH 인바운드 포트 접속 없이 배포 작업을 수행한다.
  2. 배포 시 SSH 자격증명을 파이프라인에서 완전히 배제하고 레지스트리(GHCR) 자격증명만 사용한다.
  3. 기존 admin 승인 단계, immutable image digest 검증, Production DB 가드, 영수증 생성 및 실패 복구 로직을 100% 무손실 보존한다.

---

## 2. 해결 방안 및 설계

### 1) Inbound WebSocket 에이전트 구조
- **컨테이너화**: 공식 `jenkins/inbound-agent:jdk21`을 베이스로 하고, Docker CLI 27, Compose v2.33.0, Python 3를 포함한 전용 이미지 `robingraph-nas-agent:20261021` 빌드.
- **통신 프로토콜**: HTTP/HTTPS 포트(Jenkins `http://127.0.0.1:8080/`)를 통해 WebSocket 터널로 연결. 별도의 Jenkins agent TCP 포트 개방이나 NAS SSH 포트 접속 불필요.
- **노드 속성**:
  - Node Name: `robingraph-nas-deploy`
  - Executor: 1
  - Usage Mode: `exclusive` (이 노드 라벨을 명시적으로 요구하는 잡만 실행)

### 2) 호스트 마운트 및 보안 격리 설계
- **Docker Socket 마운트**: `/var/run/docker.sock:/var/run/docker.sock`를 마운트하여 컨테이너 내부에서 호스트 Docker 데몬을 직접 제어.
  - *보안 주의*: Docker socket 권한은 호스트 루트 수준의 제어권을 의미하므로, 이 노드는 신뢰된 운영 배포 잡 전용으로 격리함. `exclusive` 라벨은 젠킨스 스케줄링 제한이며 리눅스 커널 보안 경계가 아님.
- **Compose 디렉터리 절대 경로 일치**: Compose v2는 에이전트 컨테이너 내부와 호스트 간 경로가 다르면 볼륨 바인딩 시 혼선이 발생하므로, 호스트의 Production compose 디렉터리(`${NAS_DEPLOY_ROOT}`, `/volume3/Birds-Nest/docker-data/...`)를 동일한 절대 경로로 컨테이너에 마운트함.
- **컨테이너 보안 제약**:
  - `read_only: true`: 에이전트 컨테이너의 루트 파일시스템을 읽기 전용으로 보호.
  - `cap_drop: [ALL]`: 컨테이너 내 모든 Linux capability 드롭.
  - `security_opt: [no-new-privileges:true]`: 자식 프로세스의 권한 상승 방지.
  - `user: 1000:121`: uid 1000(`jenkins`), gid 121(`docker` 소켓 그룹)로 실행하여 소켓 권한 정정.
  - `tmpfs: [/tmp]`: 임시 파일 처리를 위한 tmpfs 마운트.
  - `agent.env`: Jenkins 노드 시크릿은 `0600` 권한의 파일에만 저장하며 Git/문서에 노출하지 않음.

### 3) 로컬 배포 도우미 (`scripts/deploy_registry_prod.py`) 개선
- `--local` 옵션 신설: SSH 파이프 전송 대신 NAS 로컬 환경에서 직접 Docker compose 프로젝트를 조작.
- `--check-only` 옵션 신설: GHCR/SSH 자격증명 없이 Production 컨테이너의 `ROBINGRAPH_DEPLOY_TARGET=prod` 환경, compose 마운트 유효성, compose 버전을 무변경(read-only, mutations=0)으로 검사.
- 동기화 검증: 저장소 소스 파일과 NAS `./helper/deploy_registry_prod.py`의 해시가 일치하는지 상시 검증 (`8d93a0daefe552d0ec71280c4ebff39b07ad0a7037569309c05ae9b3162337f1`).

---

## 3. 주요 구현 내용

### 수정 및 추가 파일 목록

1. **`ci/nas-agent/Dockerfile`** (신규)
   - Docker CLI 27 바이너리 및 cli-plugins 복사, Python 3 설치.
2. **`ci/nas-agent/compose.yml`** (신규)
   - Inbound 에이전트 서비스 정의 (`robingraph-jenkins-agent`).
   - `network_mode: host`, `read_only: true`, `cap_drop: [ALL]`, `security_opt: [no-new-privileges:true]`.
   - Docker socket, workspace(`./work`), helper(`./helper:ro`), compose root 동등 마운트.
3. **`scripts/deploy_registry_prod.py`** (수정)
   - `production_context()` 추출 및 검증 로직 재사용.
   - `--local` 및 `--check-only` CLI 플래그 추가.
   - 로컬 실행 시 SSH 없이 GHCR 자격증명만으로 Docker login 및 compose pull/up 실행.
4. **`tests/test_registry_prod_deployment.py`** (수정)
   - `test_local_check_needs_no_credentials_and_does_not_mutate` 단위 테스트 추가.
   - `test_local_deploy_does_not_require_ssh_credentials` 단위 테스트 추가.
5. **`Jenkinsfile` & `ci/Jenkinsfile.production`** (수정)
   - `Deploy and verify NAS Production` 스테이지에 `agent { label 'robingraph-nas-deploy' }` 지정.
   - `when { beforeAgent true; expression { !params.CHECK_ONLY } }` 추가.
   - `withCredentials`에서 `robingraph-nas-ssh` 제거 및 `robingraph-ghcr`만 바인딩.
   - 명령을 `python3 /opt/robingraph-deploy/deploy_registry_prod.py --local`로 변경.
6. **`docs/jenkins-deployment.md`** (수정)
   - 최상단에 `2026-10-21 SSH 없는 NAS 배포 에이전트 전환` 운영 문서 추가.

### 핵심 설정 스니펫

```yaml
# ci/nas-agent/compose.yml
services:
  agent:
    image: robingraph-nas-agent:20261021
    container_name: robingraph-jenkins-agent
    init: true
    user: ${NAS_AGENT_UID:?Set deployment account uid}:${NAS_DOCKER_GID:?Set Docker socket gid}
    restart: unless-stopped
    network_mode: host
    read_only: true
    cap_drop: [ALL]
    security_opt: [no-new-privileges:true]
    tmpfs:
      - /tmp
    env_file: agent.env
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - ./work:/home/jenkins/agent
      - ./helper:/opt/robingraph-deploy:ro
      - ${NAS_DEPLOY_ROOT:?Set the existing Production compose directory}:${NAS_DEPLOY_ROOT}
```

```groovy
// Jenkinsfile (배포 스테이지 변경)
stage('Deploy and verify NAS Production') {
    agent { label 'robingraph-nas-deploy' }
    when { beforeAgent true; expression { !params.CHECK_ONLY } }
    environment {
        DOCKER_CONTEXT = 'default'
        DOCKER_HOST = 'unix:///var/run/docker.sock'
    }
    steps {
        withCredentials([
            usernamePassword(credentialsId: 'robingraph-ghcr', usernameVariable: 'GHCR_USERNAME', passwordVariable: 'GHCR_TOKEN')
        ]) {
            sh '''#!/bin/sh
set -eu
python3 /opt/robingraph-deploy/deploy_registry_prod.py --local   --image "$IMMUTABLE_IMAGE" --revision "$REVISION"
printf '{"revision":"%s","image":"%s","production_verified":true}
'   "$REVISION" "$IMMUTABLE_IMAGE" > production-release.json
'''
        }
        archiveArtifacts artifacts: 'production-release.json'
    }
}
```

---

## 4. 검증 및 테스트 결과

### 1) 자동화 테스트 (단위 및 린트)
- **명령어**: `.venv/bin/python -m unittest tests.test_registry_prod_deployment`
- **결과**: `5 통과 / 0 실패 / 0 건너뜀` (오프라인 mock)
  - 기존 SSH 배포 가드 테스트 3건 통과.
  - 신규 로컬 체크(`--local --check-only`) 무변경·무자격증명 검증 통과.
  - 신규 로컬 배포(`--local`) SSH 자격증명 불요 검증 통과.
- **Jenkinsfile Declarative Lint**: 문법 및 구조 유효성 통과.

### 2) NAS 로컬 사전 검증 (`--check-only`)
- **실행**: NAS 에이전트 컨테이너 내부에서 helper 사전 점검 실행.
- **결과**:
  - Docker Compose version `v2.33.0` 확인.
  - `production_context_verified: true`, `mutations: 0`.
  - 컨테이너 ID: `a4d2ce5232a9159806c15563ea0d30c46247766fa299513b160ce401129c4913`.
  - 기동 시각: `2026-10-20T08:55:43.816773705Z`.

### 3) Jenkins 실서버 검증 잡 (`RobinGraph-NAS-Agent-Check #1`)
- **실행 URL**: `http://192.168.219.99:8080/job/RobinGraph-NAS-Agent-Check/1/`
- **실행 결과**: `SUCCESS` (노드 `robingraph-nas-deploy` 점유, 타임아웃 3분 가드 적용)
- **세부 검증 내용**:
  1. **Helper 사전 점검**: 무변경 상태(`mutations: 0`) 및 compose 연동 정상 확인.
  2. **운영 API 계약 검사**:
     - `http://127.0.0.1:8000/health`: HTTP 200 OK
     - `http://127.0.0.1:8000/openapi.json`: HTTP 200 OK
     - `http://127.0.0.1:8000/v1/taxa/lineage?name=청둥오리`: HTTP 200 OK
       - 기대 학명 `Anas platyrhynchos`, 국명 상태 `source-reference` 일치.
     - `structural_errors: []`, `schema_drift: []`, `response_drift: []`, `canary_issues: []`.
     - `backend_reachable: true`, `contract_parity_ok: true`, `passed: true`.
  3. **운영 컨테이너 무결성**:
     - 기존 운영 컨테이너(`robingraph-api`) ID, 이미지 다이제스트(`336ace79...`), 기동 시각 불변 확인.
     - 상태: `healthy`.

---

## 5. 배포 및 형상 관리

- **Jenkins 파이프라인**:
  - Inline Pipeline 정의(`RobinGraph-PROD`)에 새 에이전트 라벨(`robingraph-nas-deploy`) 및 `--local` 배포 명령 적용 완료.
  - 검증용 잡 `RobinGraph-NAS-Agent-Check` 구성 및 빌드 #1 통과 완료.
- **Git 저장소 상태**:
  - `Jenkinsfile`, `ci/Jenkinsfile.production`, `scripts/deploy_registry_prod.py`, `tests/test_registry_prod_deployment.py`, `ci/nas-agent/` 변경 사항은 dev-codex 워크트리에 미커밋 상태로 존재.
  - 신규 commit, push, main 병합은 수행하지 않음 (`commit_push_merge: false`).
  - 다음 사용자 승인된 릴리스 커밋 반영 전까지 Jenkins Inline 정의와 Git main 간에 파이프라인 정의 차이가 존재함.
- **자격증명 관리**:
  - `robingraph-nas-ssh` Jenkins 자격증명은 신규 배포에서 참조되지 않으나, 타 용도 확인 전까지 시스템에서 임의 삭제하지 않고 유지함.
  - NAS 에이전트 인증 정보(`agent.env`)는 `0600` 권한으로 NAS 로컬에만 보관.
  - 최초 부트스트랩에 사용된 임시 SSH/로컬 파일은 정리 완료됨.

---

## 6. 한계 및 후속 과제

1. **실제 이미지 교체 미실행**:
   - 이번 작업은 에이전트 구동 및 `--check-only` 읽기 검증만 수행했음. 실제 SSH 없는 운영 컨테이너 이미지 교체(pull/up) 및 롤백/복구 테스트는 실행하지 않음. 실제 운영 교체는 별도의 명시적 배포 승인 시점에 검증 예정.
2. **호스트 재부팅 미실행**:
   - NAS 물리 재부팅 시 에이전트 컨테이너 자동 재시작(`restart: unless-stopped`) 및 WebSocket 재연결은 검증하지 않음.
3. **Docker Socket 호스트 제어 권한**:
   - 에이전트에 마운트된 Docker socket은 호스트 루트 수준의 권한을 가짐. `exclusive` 라벨은 젠킨스 스케줄링 제약일 뿐 보안 샌드박스가 아니므로, 오직 승인된 신뢰 배포 잡만 실행되도록 관리해야 함.
4. **Git main 동기화 대기**:
   - Jenkins Inline 파이프라인은 갱신되었으나 Git `main` 브랜치는 미커밋 상태이므로, 후속 작업 시 Git 커밋·푸시 조율이 필요함.

---

## 관련 문서

- [[Work/RobinGraph/RobinGraph 작업 백로그|RobinGraph 전체 작업 백로그]]
- [[Work/RobinGraph/작업기록/7xx 배포·인프라/작업 백로그|7xx 배포·인프라 작업 백로그]]
- [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-20-RG701-main-Production-Django-배포|RG-701 main 병합·Production 배포 (2026-10-20)]]
- [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-18-Jenkins-Production-배포-대상-정정|Jenkins 배포 대상을 NAS Production으로 정정 (2026-10-18)]]
- [[Work/RobinGraph/작업기록/7xx 배포·인프라/2026-10-18-Jenkins-GHCR-배포-구성-사전검증|Jenkins·GHCR 배포 구성과 사전 검증 (2026-10-18)]]
- 저장소 운영 가이드: `docs/jenkins-deployment.md`
