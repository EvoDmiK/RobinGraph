# 그래프 우선 이름 해소·벡터 후보 확인: NAS TEST 배포

## 요청 배경과 목표

사용자가 Claude·Antigravity·Codex 협업 구현의 NAS 배포를 지시했다. 앞선 작업에서는 NAS SSH 연결 거부로 로컬 TEST 검증과 패키지 준비까지만 끝냈다. 이번에는 접속을 다시 확인하고 준비한 정확한 스냅샷을 NAS TEST에 배포하여 실제 DB/Jina/API 및 브라우저 동작을 검증했다. 일반 배포 지시는 TEST 대상으로 해석했고 Production은 변경하지 않았다.

## 확인한 상태와 배포 경계

NAS의 SSH 포트 99 연결이 복구되어 인증과 명령 실행에 성공했다. 이전 연결 거부 원인은 이번 작업으로 확정할 수 없다. 인증 정보는 출력하거나 문서·패키지에 넣지 않았다. 처음 운영 컨테이너를 `robingraph-api-prod`로 조회해 없다는 응답을 받았고, 기존 배포 스크립트에서 실제 이름 `robingraph-api`를 확인한 뒤 배포 전 상태를 읽었다. 컨테이너 이름 조회 실패를 운영 서비스 장애로 판단하지 않았다.

- 직전 TEST 이미지: `robingraph-api:test-rg202-098d5f2da352`.
- 직전 TEST 컨테이너 ID: `5d2a9c78514d3c960206ae636cdf4257c8dbc48b4145c5a84e53eb238954f83d`.
- 운영 이미지: `robingraph-api:prod-approved-ui-0681747`.
- 운영 컨테이너 ID: `03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd`.
- 운영 시작 시각: `2026-10-10T06:07:33.413088244Z`.

TEST Compose 프로젝트 `robingraph-test`의 api만 빌드·교체했다. DB 쓰기·재색인·수집·운영 컨테이너 변경·Git commit/push/병합은 하지 않았다. 기존 TEST DB 연결 값과 새 TEST 환경 사본을 메모리에서 비교해 일치함을 확인했다. 환경 파일은 0600이며 이미지·revision 관련 값만 변경했다.

## 배포 파일과 변경 전후 동작

새 기능은 질문에서 이름 표현을 분리해 그래프 정확 조회 → 한국어 내부 공백 정규화 조회 → 미일치 시 검토 국명 이름 벡터 후보로 진행한다. 벡터는 종을 자동 확정하지 않으며 사용자가 최대 3개 후보 중 선택하면 원래 질문 주제를 유지한 학명 질문으로 그래프를 다시 조회한다. 요청별 이름-노드 정보만 응답하며 영구 별칭이나 Query 노드를 만들지 않는다. 상세 구현·역할·단위 검증은 `2026-10-15-graph-first-name-resolution.md`와 ADR-0008을 따른다.

준비된 allowlist 아카이브를 legacy scp(`scp -O`)로 전송했다. 원격에서 아카이브 SHA-256와 runtime 파일 136개 각각의 해시를 다시 확인했다. 비밀 환경 파일·AGENTS·MCP 설정·개발 문서는 패키지에 포함하지 않았다. 기준 커밋에 미커밋 source 변경을 명시적으로 덮어쓴 스냅샷이며, 기준 커밋만 배포했다고 표현하지 않는다.

- 기준 커밋: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413`.
- 스냅샷 SHA-256: `1f6a427222c379791aea94df3550c554cbffe081404bff2b71d705215decef7a`.
- 아카이브 SHA-256: `dec78177217f8adbbbac9a2f938c5ed3a3cb804bbcd4cc9a3479008255f630f7`.
- 원격 릴리스: `/home/<nas-user>/robingraph-name-resolution-1f6a427222c3`.
- 최종 이미지: `robingraph-api:test-name-resolution-1f6a427222c3`.
- 최종 이미지 ID: `sha256:d385753c329cc2043bd0991b115165de44d599f29f8607d27f8c92ceb424cff5`.
- OCI revision: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-name-resolution-1f6a427222c3`.
- 최종 TEST 컨테이너 ID: `1bcb948ca78a00475437ac4cfcd3d9f81707e5d31bd13c325dbdc42e2f1c157b`.
- 최종 TEST 시작 시각: `2026-10-15T08:38:06.83641988Z`.

`ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh preflight`와 `deploy`를 실행했다. 첫 빌드에서는 새 코드가 올라왔지만 환경 사본의 이전 `ROBINGRAPH_VCS_REF`가 이미지 revision에 남았다. 단순 `VCS_REF` 값만 바꾸어서는 Compose build argument가 갱신되지 않는 것을 확인했다. 올바른 `ROBINGRAPH_VCS_REF`를 스냅샷 값으로 수정하고 같은 TEST 이미지를 재빌드·재배포해 최종 OCI revision을 직접 대조했다. 최종 컨테이너는 running·healthy다. 이 과정에서 TEST만 두 차례 교체했으며 운영은 그대로다.

## 검증 방법과 실제 결과

앞선 로컬 단위·계약 검증은 Python 884개 중 846 통과·38 제외, 프런트엔드 fake DOM 306개 통과였다. 이번 원격 배포에서 해당 전체 검사를 다시 실행한 것은 아니다. 실제 NAS 검증을 별도로 수행했다.

1. 배포된 이미지에서 overlay 10개 파일의 SHA-256를 `SOURCE_MANIFEST.json`과 비교해 전부 일치했다. API·파서·resolver·CLI·그래프 후보 목록·UI JS/CSS와 이전 MRR·감사 도구가 포함된다.
2. 컨테이너 안에서 `python scripts/verify_api_deployment.py --base-url http://127.0.0.1:8000 --json`을 실행했다. `passed=true`, `backend_reachable=true`, `contract_parity_ok=true`였다. 실제 health·OpenAPI·이름 조회 API 계약 검증이다.
3. 배포된 TEST 컨테이너 안에서 `live-smoke.py`를 `ENTITY_QA_BASE=http://127.0.0.1:8000`으로 실행했다. 아래 실제 HTTP 8회가 모두 통과했다. route mock이나 가짜 벡터를 사용하지 않았다.

| 요청/행동 | 결과 | 관측 시간 |
|---|---|---:|
| 흰뺨검둥오리에 대해 알고 싶어 | graph_exact·Anas zonorhyncha 답변 | 1.756초 |
| 흰뺨 검둥 오리에 대해 알고 싶어 | graph_normalized·동일 조류 | 0.719초 |
| 흰뺨검둥오려에 대해 알고 싶어 | vector·clarify·사용자 확인 후보 | cold 28.341초 |
| 위 후보 확인 질문 | graph_exact·동일 taxon ID | 0.432초 |
| 흰뺨검둥오려는 뭘 먹어? | vector·clarify | warm 0.988초 |
| 위 먹이 후보 확인 | graph_exact·diet 답변 | 0.276초 |
| 우주선에 대해 알고 싶어 | 후보·profile 없이 abstain | 0.883초 |
| 까치에 대해 알려줘 | graph_exact·Pica serica | 0.593초 |

4. SSH 로컬 포워딩으로 NAS TEST 컨테이너의 API에 연결한 실제 Chromium에서 1280·390·320px를 검증했다. 각 화면에서 공백 이름·오타 먹이 질문·Enter 키 후보 선택의 3회 요청(총 9회)이 모두 통과했다. 후보 렌더링만으로 자동 요청하지 않았고, 고급 필터에 까치를 남겨도 선택한 Anas zonorhyncha로 조회했다. diet 주제·원래 대화 유지, 후보 44px 터치 높이, 선택 전후 가로 넘침 없음, JS pageerror 0을 확인했다. 물리 모바일 테스트가 아닌 화면 폭 에뮬레이션이다. 검증용 포워딩은 끝난 뒤 해제했다.
5. 운영 컨테이너의 ID·시작 시각·이미지가 배포 전후 동일함을 직접 확인했다. 운영이 재시작되지 않았음을 이 식별 정보로 검증했다.

증거는 `docs/verification/assets/2026-10-15-entity-resolution/`의 `nas-release.json`, `nas-api-contract.json`, `nas-live-smoke.json`, `nas-browser-live.json`, `nas-candidates-*.png`, `nas-browser-*.png`에 있다. 원격 DB/Jina/API와 실제 브라우저 검사이며 fixture 결과를 실제 종 데이터로 대신 표현하지 않는다. 빌드 로그는 `/tmp/robingraph-name-nas-deploy.log`와 `/tmp/robingraph-name-nas-revision-deploy.log`에 있고 임시 파일의 영구 보관은 보장하지 않는다.

## 배포·롤백·한계와 후속

**NAS TEST 배포와 이번 이름 해소 흐름의 실제 검증을 완료했다.** 이전 문헌 감사만 배포된 상태에서 새 이름 해소·후보 선택 UI가 배포된 상태로 바뀌었다. Production 반영은 별도 사용자 승인이 필요하며 이번에 수행하지 않았다. 커밋·push·병합도 하지 않았다.

직전 TEST 이미지는 삭제하지 않았다. 필요하면 새 릴리스 경로에서 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh rollback robingraph-api:test-rg202-098d5f2da352`로 되돌릴 수 있다. 실제 롤백은 실행하지 않았다.

벡터 후보 범위는 검토 국명 850개 종이며 모든 종·아종·영어 오타 지원이 아니다. 프로세스 첫 이름 벡터 구축은 약 28초로 확인됐고 재시작하면 메모리 캐시를 다시 만든다. 후보 하한 0.25는 작은 조정 사례 기준이며 자동 종 확정이나 정확도 확률이 아니다. 운영 부하·물리 모바일·Safari·Firefox·물리 재부팅·공개 TEST 프록시 도메인은 이번 검증 범위 밖이다. 브라우저는 NAS 컨테이너에 직접 연결했으며 외부 공개 도메인까지 검증했다고 표현하지 않는다.

이번에는 앱 코드를 바꾸지 않아 전체 단위 검사·Graphify AST 갱신을 반복하지 않았다. 배포 증거·작업 기록만 추가하고 `git diff --check`를 확인했다. 저장소와 Obsidian에는 동일한 핵심 결과와 배포·검증 정보를 기록한다.
