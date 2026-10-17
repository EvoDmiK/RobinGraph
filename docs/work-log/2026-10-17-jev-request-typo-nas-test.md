# Jev 요청 표현 오타 수정 NAS TEST 배포

## 요청 배경과 목표

사용자가 앞서 구현·로컬 검증한 Jev 오타 의도 분류 수정을 NAS에 배포하도록 요청했다. 대상은 NAS TEST이며 Production은 별도 승인 대상이다. 사용자 사례 `청둥오리에 대해 일고 깊어`가 실제 배포 서비스에서도 청둥오리 소개로 이어지는지 확인했다.

## 사전 확인과 변경 범위

NAS TEST의 이미지·컨테이너가 직전 국명 표시 배포 기록과 일치함을 직접 확인했다. 이전 allowlist 스냅샷을 기반으로 jev_router.py만 교체했으며 해시 비교에서 변경 파일이 이 하나뿐임을 확인했다. 후보 UI·Neo4j 이름 벡터·MRR·기존 협업 변경은 보존했다. AGENTS·MCP·인증 파일은 아카이브에 포함하지 않았다.

SSH 키 인증은 실패했고 사용자 제공 인증으로 연결을 복구했다. 인증 정보와 임시 인증 파일은 기록하지 않았으며 임시 파일은 삭제했다. 패키지·런타임 해시 확인의 첫 시도는 Dockerfile 등 이미지에 복사되지 않는 패키지 파일까지 검사해 실패했다. 배포 서비스 코드 이상으로 판단하지 않고 검사 범위를 실제 이미지의 src/와 scripts/로 바로잡아 98개 파일 모두 일치함을 확인했다. 원격 릴리스 디렉터리에서는 패키지 138개 파일 전체를 검증했다.

## 실제 배포와 소스

- 스냅샷 SHA-256: 0629aa1e9f4a6e12bba2091c1c30768b643cb95a76ea6e8bdd384b725d219d9d.
- 아카이브 SHA-256: 56beeaa86ae203ed2811b6916de6c614edf561aefa506ad007d8ffda8c61f5dd.
- TEST 이미지: robingraph-api:test-jev-typo-0629aa1e9f4a.
- 이미지 ID: sha256:259adf7d9b40969834c71c8342ae19afb3d1633e32063569931fff3d428d459e.
- OCI revision: 434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-jev-typo-0629aa1e9f4a.
- TEST 컨테이너: 37b6e3b8449e83fda49f2561efe2b8d7afe1bfde0b2301281d52ea68f4ce90d6.
- 시작: 2026-10-17T04:17:46.909882131Z, running·healthy.

기준 커밋과 미커밋 변경을 포함한 스냅샷이며 commit/push/병합은 수행하지 않았다. 기존 TEST 환경을 권한 0600으로 복사하고 이미지·revision만 변경했다. 환경 사본과 실행 중 TEST의 DB 설정이 일치하고 TEST와 운영 DB 대상이 다름을 값 출력 없이 확인했다. 새 릴리스에서 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh deploy`를 실행해 TEST api만 빌드·교체했다.

## 실제 HTTP/API 검증

배포된 컨테이너 안에서 verify_http.py로 실제 HTTP 5요청을 실행했다. 가짜 Jev나 DB를 사용하지 않았다.

| 질문 | 결과 |
|---|---|
| 청둥오리에 대해 일고 깊어 | Jev → answer, Anas platyrhynchos |
| 청둥오리에 대해 알고 싶어 | deterministic → answer, 같은 종 |
| 청둥오리에 대해 알고 시퍼 | Jev → answer, 같은 종 |
| 오타 소개 질문 + 까치 먹이 요청 | clarify 유지 |
| 그 새에 대해 일고 깊어 | clarify 유지 |

5건 모두 통과했다. 배포 컨테이너의 `python scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json`도 passed=true였다. 배포된 src/·scripts/ 98개 해시를 새 manifest와 대조해 모두 일치했다. 이전 로컬 회귀 57개와 전체 898개(860 통과·38 제외)는 선행 검증이며 이번 원격에서 전체 테스트를 다시 실행한 것은 아니다.

## 운영 불변·롤백·한계

운영 컨테이너 ID 03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd, 시작 2026-10-10T06:07:33.413088244Z, 이미지 robingraph-api:prod-approved-ui-0681747은 전후 동일했다. 운영 배포·재시작·DB 변경은 없으며 TEST 재색인·DB 쓰기도 하지 않았다.

직전 TEST 이미지 robingraph-api:test-name-neo4j-71b1b0f58a62는 보존했다. 필요 시 새 릴리스에서 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh rollback robingraph-api:test-name-neo4j-71b1b0f58a62`로 복구할 수 있으나 실제 롤백은 실행하지 않았다.

이번 검증은 NAS 컨테이너의 실제 HTTP 서비스이며 공개 도메인 프록시·브라우저·물리 모바일 검증은 수행하지 않았다. 프롬프트 기반 분류이므로 모든 오타의 성공을 보장하지 않는다. Obsidian과 백로그 상태는 이번 배포에서 변경하지 않았다.

증거는 docs/verification/assets/2026-10-17-jev-nas/의 release.json, nas-state.json, nas-http.json, nas-api-contract.json, verify_http.py에 있다. 빌드 로그는 /tmp/robingraph-jev-nas-deploy.log이며 임시 파일의 영구 보관은 보장하지 않는다. 앞선 구현 문서의 미배포 설명은 당시 이력으로 읽으며 본 배포 결과가 최신 상태다.
