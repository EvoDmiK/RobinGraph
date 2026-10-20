# Jenkins + GHCR 배포 운영 방법

## main 기준 운영 배포 (2026-10-20)

사용자의 커밋·푸시·main 병합·Production 배포 지시에 따라 운영 파이프라인의 checkout과 SCM polling 기준을 `main`으로 변경한다. 아래 2026-10-18의 `dev-codex` 기준 설명은 당시 이력이다. 저장소 `Jenkinsfile`과 `ci/Jenkinsfile.production`, Jenkins의 Inline Pipeline 정의를 함께 맞추고, 운영 승인 단계에는 배포할 main 커밋과 immutable 이미지 digest를 표시한다. 실제 배포 결과는 별도 작업 기록에 남긴다.

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
