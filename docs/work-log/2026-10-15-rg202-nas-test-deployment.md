# RG-202 변경 NAS TEST 배포 완료

## 요청 배경과 목표

사용자가 선행 감사 도구와 MRR 수정 결과를 NAS 테스트 서버에 올리도록 지시했다. NAS의 TEST 스택에만 배포하고 컨테이너 상태, 이미지 출처, 수정된 평가 계산 및 실제 검색 API를 확인하는 것이 목표다. 현재 Mac의 로컬 TEST 재배포로 대체하지 않는다. Production 반영은 승인되지 않았다.

## 현재 상태와 접속 결과

NAS SSH의 기본 포트 접속은 Connection refused였다. 런북에 기록된 별도 SSH 포트에서는 서버 응답과 호스트 키 확인까지 성공했으나 키 인증과 기존 비밀번호 1회 인증이 실패했다. 사용자가 NAS 전용 인증 정보를 제공한 후 접속에 성공했다. 인증 정보는 기록하지 않는다.

**NAS TEST 배포와 실제 검증을 완료했다.** NAS TEST 컨테이너만 교체했고 Production 컨테이너의 ID와 시작 시각은 배포 전후 동일함을 확인했다. 현재 Mac의 로컬 TEST는 재시작하지 않았다.

## 배포 묶음과 변경 전후

현재 작업 트리의 미커밋 변경을 누락하지 않도록 HEAD의 검증된 runtime allowlist 패키지를 만든 뒤 이번 작업의 두 파일만 덮어쓴 별도 스냅샷을 만들었다. 이전 AGENTS.md·MCP 설정·다른 작업 문서·비밀 환경 파일은 포함하지 않았다. 기본 환경 예제 파일은 포함한다.

- 기준 커밋: 434b6a4be8493f9b8bd85f477cbe8aca65ec7413.
- 덮어쓴 파일: src/robingraph/retrieval/evaluation.py, scripts/audit_retrieval_readiness.py.
- 변경 효과: 실패한 답변 가능 질문의 RR=0을 MRR 평균에 포함하고 TEST 전용 읽기 감사 스크립트를 이미지에 포함한다. HippoRAG/PPR 구현이나 화면 변경은 없다.
- 최종 아카이브: /tmp/robingraph-rg202-nas-package/robingraph-rg202-098d5f2da352.tar.gz.
- 최종 아카이브 SHA-256: 1b47a3b687e38f629d487b1a786da34d0bc0d8b2108ae0f8a6b91123f48e6f20.
- 파일 스냅샷 SHA-256: 098d5f2da352fdad80c5569e9114826f3401f7a41de99419e65fd8ac44ed364c.
- 실제 배포 이미지: robingraph-api:test-rg202-098d5f2da352.
- runtime 파일 135개의 해시와 기준 커밋·미커밋 덮어쓰기 목록을 SOURCE_MANIFEST.json에 보관했다. 이를 포함한 최종 tar의 각 파일 해시를 다시 검사해 모두 일치했다.

기준 커밋만으로 배포됐다고 표현하지 않는다. 아직 커밋하지 않은 두 파일을 포함하는 명시적 스냅샷이며 Git commit/push는 하지 않았다.

## 검증 방법과 실제 결과

기존 RG-202 작업에서 관련 단위·계약 33개 통과, 실제 로컬 TEST 읽기 감사와 검색 API warmup 포함 32회 호출을 완료했다. 이 결과는 NAS 배포 후 검증이 아니다. 상세는 2026-10-15-rg202-retrieval-readiness.md에 있다.

이번 배포에서는 scripts/package_nas_release.sh --ref HEAD 실행 성공, 최종 tar 경로 안전성·환경 비밀 파일 제외·135개 파일 SHA-256 재검사 통과를 확인했다. 원격에서도 아카이브 SHA-256 및 파일 135개 해시가 일치했다. 최초 기본 scp 전송은 Connection closed였고 stdin 전송 시도는 원격 파일이 없어 준비 단계가 실패했다. scp -O의 legacy 전송으로 원격 파일 존재와 해시를 다시 확인해 해결했다.

기존 TEST의 Compose working_dir 라벨 경로는 실제 파일 이동 후 유효하지 않았다. 현재 /home/<nas-user>/robin_tmp/RobinGraph-related-arrow-0681747/.env.nas.test를 찾아 실행 중 TEST 컨테이너의 Neo4j·PostgreSQL 연결 값과 메모리에서 비교해 일치함을 확인했다. 새 릴리스에는 이 TEST 파일만 복사하고 이미지 태그와 VCS_REF만 변경했다. 파일 권한은 0600이며 비밀값을 출력하지 않았다.

NAS 기존 TEST의 앱 소스와 준비한 소스의 SHA-256를 비교해 패키지 생성용 egg-info를 제외하면 evaluation.py만 다름을 확인했다. 이름이 다른 기존 이미지에 반영된 화면을 이전 버전으로 되돌리지 않는지 검토한 결과다. 새 감사 스크립트도 함께 추가했다.

## 실제 배포와 검증 결과

- 릴리스 경로: /home/<nas-user>/RobinGraph-rg202-098d5f2da352.
- ROBINGRAPH_DEPLOY_TARGET=test로 scripts/deploy_nas.sh preflight·deploy·verify를 실행했다. Compose 프로젝트 robingraph-test의 api만 빌드·교체했다.
- 이미지 ID: sha256:fa81fc81d7706b98f85243910f9cddda18232f3a2c3f91f749998269ae23446f (linux/amd64).
- OCI revision: 434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-rg202-098d5f2da352. 기준 커밋과 미커밋 스냅샷임을 구분한다.
- 컨테이너 running·healthy, /health status=ok·mode=neo4j·deployment_target=test를 확인했다.
- 이미지 안 evaluation.py와 감사 스크립트의 SHA-256가 배포 manifest와 일치했다.
- scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json은 passed=true, backend_reachable=true, contract_parity_ok=true였다. 실제 health·OpenAPI·국명 계통 조회 계약 검사다.
- nas-smoke.py의 10개 검사 모두 통과했다. 실제 HTTP 7개는 TEST health, 채팅 HTML, 청둥오리 국명 계통, 프로필, 자연어 프로필 채팅, 전문 검색, 하이브리드 검색이다. 검색은 두 모드 모두 결과 4개를 반환했고 요청 모드를 유지했으며 hybrid에는 fulltext·vector 채널이 있었다. 검색 데이터는 기존 합성 fixture이고 종 프로필·계통은 실제 TEST 자료다. 나머지 3개는 배포된 평가 함수에 합성 입력을 넣어 혼합 MRR=0.5, 전체 누락=0.0, 답변 가능한 질문 없음=None을 확인한 자체 검사다. 10개 모두를 실제 DB 테스트로 표현하지 않는다.
- 배포된 scripts/audit_retrieval_readiness.py를 실제 TEST DB에 읽기 실행했다. 문서 2개·청크 4개, 벡터 2개, manifest SHA-256 a32d31c8972b6cb7d851bc1e196386fa0e411064367bcc105e108d2d400f6622로 로컬 선행 감사와 일치했다. PPR 도입의 문헌 부족 조건은 그대로다.
- Production은 컨테이너 ID·시작 시각이 배포 전후 동일했고 기존 이미지 robingraph-api:prod-approved-ui-0681747을 유지했다.

검증 증거는 docs/verification/assets/2026-10-15-rg202/nas-deployment.json, nas-smoke.py·nas-smoke.json, nas-readiness.json, nas-release.json에 보관한다. 빌드 로그는 /tmp/robingraph-rg202-nas-deploy.log다. /tmp 파일의 영구 보관은 보장하지 않는다. 기존 스냅샷 hash와 원격 이미지 소스 hash를 함께 확인했으며 검증 자산은 이미지에 넣지 않았다.

## 배포·커밋·후속 사항

직전 TEST 이미지 robingraph-api:test-related-arrow-0681747은 삭제하지 않았다. 필요 시 새 릴리스 디렉터리에서 ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh rollback robingraph-api:test-related-arrow-0681747로 되돌릴 수 있다. 실제 롤백은 실행하지 않았다. 외부 프록시·공개 TEST 도메인은 변경하거나 검증하지 않았으며 브라우저·물리 모바일·전체 종 검증도 이번 범위에 없다.

TEST 이미지 빌드·컨테이너 교체와 새 TEST 환경 사본의 이미지·revision 값 변경만 수행했다. Production 배포·재시작, DB 쓰기·스키마·인덱스 변경, commit/push/병합은 하지 않았다. 소스는 미커밋이다. 새 검증 코드 자산 추가 후 Graphify AST 갱신은 5,314노드·10,913엣지·331커뮤니티로 완료됐고 git diff --check가 통과했다. SQL 추출 의존성 부재와 문서 의미 추출 제외는 기존 한계로 유지되며 커뮤니티 변경으로 일부 이름은 hub 기준으로 재지정됐다. Obsidian에도 같은 결과를 기록한다.
