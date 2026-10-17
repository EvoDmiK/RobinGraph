# 천둥오리 입력의 청둥오리 후보 누락 수정·NAS TEST 배포

## 요청 배경과 목표

사용자가 배포된 TEST에서 `천둥오리`를 질문했는데 없다는 응답을 받았다고 보고했다. 의도한 청둥오리를 자동으로 확정하는 것이 아니라, 그래프 조회 실패 후 이름 벡터 후보를 제시하고 사용자 확인으로 이어져야 한다. 실제 NAS에서 재현하고 일반 후보 기준을 무작정 낮추지 않는 최소 보완을 구현·검증·TEST 배포했다.

공개 `robin-test.dove-nest.com`은 앞선 외부 접근에서 403이어서 공개 프록시를 통한 응답을 직접 검증하지 못했다. 이번 현상은 NAS TEST 컨테이너 API와 로컬 검증 앱 양쪽에서 동일하게 재현했다. 따라서 이 보고를 공개 사이트 라우팅 문제로 추정해 처리하지 않았다.

## 원인과 실제 근거

배포 전 실제 API에서 `천둥오리에 대해 알려줘`는 mention=천둥오리, status=not_found, disposition=abstain이었다. 반면 `청둥오려에 대해 알려줘`는 청둥오리 후보를 반환했다. 질문 파서가 이름을 추출하지 못한 문제가 아니었다.

실제 NAS Jina로 검토 국명 850개 벡터를 비교했다. `천둥오리`의 1위는 검둥오리 0.2201, 2위는 청둥오리 0.2138로, 모두 일반 후보 하한 0.25 미만이었다. 정답 후보가 벡터 순위에 있었지만 일괄 하한에서 제외된 것이 이번 누락의 직접 원인이다. 비교 입력 천둥의 최고값은 0.1127, 우주선은 음수, 아무새는 0.2008, 아무오리는 0.2116이었다. 전역 하한을 0.20대로 낮추면 관련 없는 입력도 통과할 수 있었다. 수치는 실제 probe 기록 `before-calibration.json`에 보관한다. 작은 조정 사례이며 독립 정확도 평가나 정답 확률이 아니다.

## 협업과 판단

Codex가 실제 재현·벡터 측정·구현·검증·배포를 담당했다. Claude에게 read-only 독립 검토를 맡겼고 Task `task_cb6f51af7248` / Dispatch `ctx_a92bf1b2d838`가 성공 보고로 완료됐다. Claude는 같은 resolver의 하한 필터를 확인하고, 로컬 850개 검토 이름에서 천둥오리→청둥오리의 자모 편집 거리가 1인 점과 짧은 일상어·유사 이름 오인 위험을 검토했다. 이 조사는 로컬 이름 JSON 기준이며 실제 NAS 벡터 검증으로 표현하지 않는다.

Claude는 더 넓은 자모 편집 거리 후보 보완을 제안했지만, 이번 구현은 실제 실패 범위에 맞춰 동일 길이·자모 한 개 치환·최소 4음절·벡터 상위 10개·최소 cosine까지 요구하는 좁은 조건으로 제한했다. Claude는 파일을 수정하지 않았다. 완료 보고를 처리한 뒤 worker-release로 정산했고 외부 사용자 터미널은 유지했다. 회수 대기 worker는 0개였다.

## 변경 파일과 변경 전후

앱 코드 변경은 `src/robingraph/retrieval/taxon_name_resolution.py` 하나다. API·UI 계약이나 DB를 바꾸지 않았다.

1. 그래프 정확·공백 정규화 조회를 우선하는 동작은 그대로다. 한국어 공백 이름이 그래프에서 실패한 뒤 벡터를 조회할 때도 공백을 정리한 이름 표현을 사용한다. 원문 질문과 응답 mention은 보존한다.
2. 일반 벡터 후보 하한 0.25는 유지한다. 벡터 상위 10개 중 이 하한을 넘는 후보가 전혀 없을 때만 철자 보완을 적용한다.
3. 보완 후보는 cosine 0.20 이상, 한국어 이름의 공백 제외 길이 최소 4음절·동일 음절 수, NFD 자모 분해 길이 동일, 정확히 한 자모만 다른 조건을 모두 만족해야 한다. `천둥오리`와 `청둥오리`는 ㄴ/ㅇ 한 글자 차이지만, 점수가 더 높은 검둥오리는 이 조건을 만족하지 않는다.
4. 보완 후에도 기존 그래프 ID·학명·species rank·활성 분류판을 재확인한다. status=candidates/method=vector와 실제 cosine 점수를 반환하며 자동 matched나 영구 별칭으로 바꾸지 않는다. 모델·그래프가 불능일 때 철자만으로 후보를 만들지 않는다.

`tests/test_taxon_name_resolution.py`에 두 회귀 검사를 추가했다. 실제 실패와 같은 mock cosine 순위에서 청둥오리만 후보로 나오는지, 공백 입력의 벡터 질의가 같은지, 후보는 자동 일치가 아닌지, 그래프에서 취소된 후보는 제외되는지, 낮은 점수·짧은/먼 이름은 통과하지 않는지, 기존 일반 벡터 후보를 이 보완으로 바꾸지 않는지를 확인한다. ADR-0008과 실제 HTTP·브라우저 검증 자산도 추가·갱신했다.

## 검증 방법과 결과

- 관련 단위·계약: `PYTHONPATH=src /tmp/robingraph-qa-python/bin/python -m unittest tests.test_taxon_name_resolution tests.test_entity_resolution_api tests.test_taxon_name_catalog tests.test_question_entities tests.test_species_questions` — 59개 통과, 실패·제외 0. mock/fixture 검증이다.
- 최종 전체 Python: `PYTHONPATH=src /tmp/robingraph-qa-python/bin/python -m unittest discover -s tests` — 886개 중 848개 통과, 38개 제외, 실패 0, 20.679초. opt-in 실제 통합 검사는 제외된 상태이며 전체를 실제 DB 검사로 표현하지 않는다.
- 첫 로컬 실제 검사에서 붙여 쓴 천둥오리는 통과했지만 공백 입력 `천둥 오리`는 벡터 점수가 달라져 실패했다. 공백 정규화를 벡터 질의에도 적용한 뒤 최종 단위 검사와 전체 검사 및 실제 12회 HTTP를 다시 실행해 통과했다. 이 실패는 최종 NAS 배포 전에 발견·수정했다.
- 최종 로컬 실제 TEST DB/Jina/API: `live-smoke.py` 12회 통과. API route mock이나 가짜 벡터를 쓰지 않았다.
- 최종 NAS 실제 TEST DB/Jina/API: 같은 `live-smoke.py` 12회 통과. 아래 결과와 시간을 기록했다.

| 입력/행동 | NAS 실제 결과 | 시간 |
|---|---|---:|
| 천둥오리에 대해 알려줘 | 청둥오리만 확인 후보, profile 없음 | cold 29.052초 |
| 위 후보 확인 | Anas platyrhynchos 그래프 정확 조회 | 0.507초 |
| 천둥 오리에 대해 알려줘 | 같은 후보 | 1.254초 |
| 위 후보 확인 | 동일 taxon ID | 0.482초 |
| 천둥오리는 뭘 먹어? | 청둥오리 후보 | 0.948초 |
| 위 후보 확인 | 동일 종의 diet 답변 | 0.446초 |
| 천둥 / 우주선 / 아무새 / 아무오리 | 네 입력 모두 후보 없이 abstain | 각각 0.959 / 1.024 / 1.128 / 0.797초 |
| 청둥오리에 대해 알려줘 | graph_exact 답변 | 0.445초 |
| 청둥오려에 대해 알려줘 | 기존 청둥오리 후보 유지 | 0.949초 |

배포된 `scripts/verify_api_deployment.py`를 컨테이너 안에서 실행해 passed=true, backend_reachable=true, contract_parity_ok=true를 확인했다. 실제 NAS 컨테이너에 SSH 포워딩으로 연결한 Chromium에서도 1280·390·320px 각 3회 요청(총 9회)이 통과했다. 공백 정상 이름 → 천둥오리 먹이 질문 → 청둥오리 후보 Enter 선택을 확인했고, 과거 고급 필터가 까치여도 선택한 청둥오리를 조회했다. diet 주제 유지·자동 전송 없음·후보 44px 높이·가로 넘침 없음·pageerror 0이었다. 포워딩은 검사 후 해제했다. 물리 모바일 검사가 아니라 화면 폭 에뮬레이션이다. 공개 프록시 도메인 경유 브라우저 검사로 표현하지 않는다.

## NAS TEST 배포와 소스 일치

직전 배포 `robingraph-api:test-name-resolution-1f6a427222c3`와 새 runtime 스냅샷을 비교해 resolver 파일만 달라짐을 확인했다. 이전 협업 UI나 API 변경을 되돌리지 않았다. 준비 단계의 첫 중간 스냅샷 e3ce4e35bf2e는 공백 입력 수정 전으로 NAS에서 배포하지 않았다. 최종 2ef0b2b08937만 TEST 컨테이너에 반영했다.

- 기준 커밋: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413` + 명시된 미커밋 overlay.
- 최종 스냅샷 SHA-256: `2ef0b2b08937bb223574af1d4c09bf413a6ee99b9495cbdf70ac0224823ba0b5`.
- 아카이브 SHA-256: `69e918b22ab7e2eef4b31ac5fc5b230393552925f02b938bfa46644a95aef54b`.
- 릴리스: `/home/<nas-user>/robingraph-name-resolution-2ef0b2b08937`.
- 이미지: `robingraph-api:test-name-resolution-2ef0b2b08937`.
- 이미지 ID: `sha256:ffa06ce3472ccbdd91ae5ec350d62ba674a549e94a09ebf2d8ef6d0a0192c9d7`.
- OCI revision: `434b6a4be8493f9b8bd85f477cbe8aca65ec7413-dirty-name-resolution-2ef0b2b08937`.
- TEST 컨테이너 ID: `e573fb75a12bf6100fe0aeb773baa3dde8aec6687cc7026671431c71142ff930`.
- TEST 시작: `2026-10-15T09:36:22.314145594Z`, running·healthy.

legacy scp로 전송한 아카이브·runtime 136개 파일 해시를 원격에서 재확인했다. 기존 TEST 환경만 복사해 이미지·ROBINGRAPH_VCS_REF를 갱신했고 파일 권한은 0600이다. DB 연결 설정은 기존 TEST와 일치했다. `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh build`로 빌드 후 검증 통과를 확인하고 같은 대상의 `deploy`로 교체했다. 배포 컨테이너 안 overlay 10개 파일 해시도 manifest와 전부 일치했다.

운영 컨테이너 `robingraph-api`의 ID `03ce208b9f30a3242fd16dd2772935d45099d77aaba0c81d49240bb8699de8fd`, 시작 `2026-10-10T06:07:33.413088244Z`, 이미지 `robingraph-api:prod-approved-ui-0681747`이 그대로임을 확인했다. Production 배포·재시작·DB 쓰기·인덱스 변경·commit/push/병합은 하지 않았다.

직전 TEST 이미지는 보존했다. 필요하면 새 릴리스에서 `ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh rollback robingraph-api:test-name-resolution-1f6a427222c3`로 되돌릴 수 있다. 실제 롤백은 실행하지 않았다.

## 증거·문서와 남은 한계

증거는 `docs/verification/assets/2026-10-15-cheondung-fallback/`의 조정 전 측정, 재현 가능한 live-smoke.py·browser-live.js, local/nas 실제 HTTP 결과, NAS API 계약·배포·브라우저 JSON과 스크린샷이다. 단위 로그는 `/tmp/robingraph-cheondung-tests.log`, 전체 로그는 `/tmp/robingraph-cheondung-full-tests.log`, 빌드/배포 로그는 `/tmp/robingraph-cheondung-build.log`·`/tmp/robingraph-cheondung-deploy.log`다. 임시 파일 영구 보관은 보장하지 않는다. 저장소와 Obsidian에는 같은 상세 결과를 남긴다.

Graphify AST 갱신은 5,481노드·11,271엣지·322커뮤니티로 완료했다. SQL 4개는 tree_sitter_sql 부재로 제외되고 문서 의미 추출은 AST 갱신 범위 밖이다. 5,000노드 초과로 HTML은 커뮤니티 집계 화면이며 애플리케이션 DB 검증과 구분한다. `git diff --check`가 통과했다.

이 보완은 모든 오타를 고치는 기능이 아니다. 최소 4음절·자모 한 개 치환·동일 길이·최소 벡터 점수 조건 밖은 기존 벡터 기준에 따른다. 예를 들어 왜가릐는 이번 철자 보완 범위가 아니다. 검토 이름 850개 범위·첫 캐시 구축 약 29초·사용자 확인 필요 조건은 유지된다. 물리 기기·Safari·Firefox·운영 부하·공개 도메인은 이번에 추가 검증하지 않았다.
