# n8n 한국어 이름 수집 파이프라인 작업 중단 기록

- 기록일: 2026-09-11 (아래 "2026-09-11 재개 기록" 절 기준 최신)
- 상태(2026-09-11 시점): **오프라인 구현·테스트 완료(220/220 통과로 기록했으나, 2026-09-12 재확인 결과 정확한 수치는 222회 실행/22 조건부 skip/200 통과였다 — 아래 "2026-09-12 후속 기록" 참고). 이 시점에는 실제 n8n/Neo4j 라이브 검증이 아직 없었다 — 배포 준비 완료로 간주하지 않았다.**
- **이 상태는 2026-09-12에 갱신됐다.** 라이브 n8n 실행과 운영 API 200 확인이
  실제로 끝났다 — 최신 상태는 아래 "2026-09-12 후속 기록"과
  [런북의 "현재 검증 상태"](korean-vernacular-ingest.md#현재-검증-상태-정직하게-보고)를
  본다. 이 문서의 나머지 절은 2026-09-11 시점 기록을 그대로 보존한다(역사적
  정확성을 위해 수정하지 않음).
- 저장 브랜치: `EvoDmiK/dev-2` (작업 시작 커밋: `b6625da`)
- 역할: Claude 구현, GPT-5.6 Sol 독립 평가, Codex 통합 확인.
- 이번 저장은 구현·테스트·문서의 중간 체크포인트이며 운영 배포, 데이터 적재, `product` 병합을 의미하지 않는다.

## 2026-09-12 후속 기록

- canonical workflow `Hmjfi1zAIOKR5YE5`를 n8n Public API로 inactive 상태로
  생성·갱신했다(32개 노드; Neo4j 노드 12개 + Discord 노드 2개 credential
  연결 확인). Public API에 수동 실행 endpoint가 없어 webhook trigger를 붙인
  임시 활성 복사본으로 실제 실행하고 매번 제거하는 방식을 썼다.
- 임시 복사본의 execution `18066`에서 실제 재검증: Wikidata binding
  948건(잘못된 행 0건) → `VernacularName` write 846개, candidate 102개로
  정확히 분류, 적재 합계 일치로 `load_ok=true`/`finalize_ok=true` 종료.
  canonical은 계속 inactive로 유지했다.
- 운영 API `GET /v1/taxa/lineage?name=청둥오리`가 실제로 `200`과
  `Anas platyrhynchos` 역조회 결과를 반환함을 확인했다 — 위 상태 줄의
  "라이브 검증 아직 없음"은 이 시점부터 더 이상 사실이 아니다.
- 같은 확인 중 별도 문제를 발견했다: 공개 도메인
  `https://aviary.dove-nest.com`의 `/openapi.json`과 실제 `/v1/taxa/lineage`
  응답 모두 `korean_name_status` 필드가 없다 — NAS가 이 필드를 추가하기
  이전 이미지를 그대로 서비스 중이라는 뜻이며, 이 workflow 자체의 결함이
  아니라 이미지 재배포가 필요한 상태다. 이를 자동으로 잡아내는 읽기 전용
  검증기 `scripts/verify_api_deployment.py`를 추가했다
  ([NAS 배포 런북 §8](../nas-deployment.md) 참고).
- 오프라인 스위트를 2026-09-12에 다시 실행해 실제 수치를 재확인했다:
  **222회 실행, 22개 조건부 skip, 200개 통과, 0개 실패**(이 문서 상단의
  "220/220 통과"는 부정확했다 — 실행 총량에서 skip을 뺀 값이 통과 수다).
  이 세션 동안 이 workflow의 생성기·테스트·JSON이 계속 진행 중인 별도
  작업으로 수정되고 있어 전체 스위트 총 개수는 이후에도 계속 바뀔 수
  있다(관찰: 222 → 239, 일부 중간 시점에서 `test_n8n_workflows.py`의
  Korean vernacular 테스트 1건이 간헐적으로 실패/오류). 최신 수치는 항상
  `uv run --locked --extra test python -m unittest discover -s tests`로
  직접 확인한다.
- 실제 배포·재배포는 이 세션에서 수행하지 않았다(범위 제약, 읽기 전용
  조사만 수행). 재배포·재검증 명령은 [NAS 배포 런북 §7, §8](../nas-deployment.md)에
  정리했다.

## 2026-09-11 재개 기록 (별도 worktree, `EvoDmiK/finish-korean-vernacular`)

`dev` 최신 커밋(`d818c46`) 위에 이 체크포인트(`4888759`)를 fast-forward로 이어붙인
별도 worktree/브랜치에서 아래 항목만 마무리했다. 원래 `dev-2`/`dev` worktree는
건드리지 않았다.

- **고쳤다**: `scripts/generate_n8n_korean_vernacular_ingest.py`의
  `status_node` `NameError`(정의되지 않은 이름 호출). 두 알림 노드를 이미 import돼
  있던 `discord()` 헬퍼(`generate_n8n_reference_ingest.py`, `reference ingest`의
  알림 노드와 동일 패턴)로 바꾸고, 메시지를 n8n 표현식(`={{ ... }}`)으로 다시 썼다.
- **고쳤다**: 알림이 Discord credential 없이도 안전하게 동작하도록
  `scripts/deploy_n8n_reference_ingest.py`에 워크플로우별 `DISCORD_REQUIRED` 표를
  추가했다. `korean-vernacular`는 `False`(선택)로, 기존 `reference`는 표에
  없으므로 그대로 필수로 남는다(`test_reference_requires_notification_credentials_before_deployment`
  불변). `--remote`/`--apply` 모두 Discord credential 조회가 실패해도
  선택 워크플로우면 예외를 던지지 않고 `discord_credential=None`으로 계속 진행한다.
  Discord 알림 노드 자체는 계속 `onError: continueRegularOutput`이라 실행 중에도
  그 노드 하나만 실패하고 전체 workflow가 멈추지 않는다.
- **고쳤다**: `tests/test_n8n_workflows.py`의
  `test_korean_vernacular_normalize_computes_idempotent_content_addressed_dataset_id`.
  "서로 다른 본문" 케이스가 이전 케이스와 동일한 `hash` 상수를 그대로 재사용해
  "동일 hash인데 본문만 다르다"는, 실제로는 일어날 수 없는 입력(hash는 항상 실제
  본문 바이트의 SHA-256이므로 본문이 다르면 hash도 다르다)을 계약 위반인 것처럼
  단언하고 있었다. `hash2`(이미 스크립트에 정의돼 있던 두 번째 해시 상수)로
  바꿔 "다른 본문 == 다른 해시 == 다른 `wikidata_dataset_id`"라는 실제 계약에
  맞췄다.
- `n8n/robingraph-korean-vernacular-ingest.json`을 재생성했다. 생성기를 연속
  두 번 실행해도 SHA-256이 동일(멱등)함을 확인했고, `git diff --check`도
  깨끗하다.
- 동시성/동명 충돌/malformed binding 집계/QID provenance/이전 snapshot 퇴역
  경계를 재검토했다. 후속 독립 리뷰에서 **첫 활성화 경합**의 실제 빈틈을
  발견했다: 이전 `FINALIZE_STATEMENT`는 상태 노드가 없는 두 실행이 모두
  `''`를 읽고 비교를 통과할 수 있었다. 이제 상태를 먼저 `MERGE`해 유일 ID
  잠금을 얻은 뒤 `last_successful_run_id`를 비교하므로, 기다린 실행은 첫
  실행의 ID를 보고 fail-closed 된다. 동명/잘못된 binding/QID/활성 snapshot
  경계는 기존 구현과 테스트가 계속 보장한다.
- Discord가 선택 사항이 됐다는 새 계약을 검증하는 테스트
  (`test_korean_vernacular_deployment_succeeds_without_a_discord_credential`)를
  추가했다.
- 오프라인 전체 스위트: `uv run --locked --extra test python -m unittest
  discover -s tests` → **220개 실행, 220개 통과, 0개 오류, 22개 skip**(모두
  `ROBINGRAPH_NEO4J_INTEGRATION_TESTS=1` 같은 명시적 opt-in이 없어 조건부로
  건너뛴 live 통합 테스트; 이 재개 세션에서 opt-in하지 않았으므로 실행하지
  않았다 — 아래 "아직 검증하지 않은 것" 참고).
- **아직 검증하지 않은 것(변경 없음)**: 실제 n8n import/Manual Trigger 실행,
  운영 Neo4j batch 적재, 실제 API `청둥오리` 200 응답. 이번 재개 세션에서도
  운영 n8n import/실행, 운영 Neo4j 쓰기는 수행하지 않았다(작업 범위 제약).

## 목적과 현재 구현

기존 한국어 lineage 조회는 코드가 있어도 Neo4j에 한국어 이름이 없으면 404를 반환한다. 이를 보완하기 위해 Wikidata의 CC0 조류 종 한국어 label을 수집하고, 활성 AviList 분류의 학명과 정확히 매칭하는 별도 n8n 워크플로우를 구현 중이다. 이름은 공식 국명이 아닌 `community-sourced`로 구분한다.

- 생성기: `scripts/generate_n8n_korean_vernacular_ingest.py`
- n8n import JSON: `n8n/robingraph-korean-vernacular-ingest.json`
- 배포 선택자: `scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular`
- 수집 포인트·소스 레지스트리, NAS 배포 설정, API의 `korean_name_status`, Neo4j 읽기 경로와 관련 테스트를 추가·수정했다.
- Claude는 Sol 1차 지적에 따라 동명 충돌 격리, 잘못된 입력 집계, 불변 스냅샷 식별자, 활성 스냅샷 읽기 제한, 적재 완료 시점의 분류 상태 재확인 등을 수정하다 중단했다. 수정 완료나 최종 검증 통과로 간주하지 않는다.

## 확인한 증거

- 실제 Wikidata 무제한 SPARQL 조회: HTTP 200, 당시 948 bindings. `Q25348 / Anas platyrhynchos / 청둥오리` 포함. 이는 원본 응답 수이며 AviList 매칭 수나 Neo4j 적재 수가 아니다.
- 초기 artifact 로컬 검증: `ready-local: nodes=30, active=False`. 이후 수정본에 대한 최종 결과가 아니다.
- n8n 읽기 전용 원격 사전 확인: 서버 및 Neo4j credential 조회는 가능했으나, 설정된 이름의 Discord credential이 없어 실패했다. 원격 변경은 하지 않았다.
- 중단 시점 실행: `.venv\Scripts\python.exe -m unittest discover -s tests`
- 결과: **219개 실행, 196개 통과, 22개 skip, 1개 error**.
- 오류 테스트: `test_korean_vernacular_normalize_computes_idempotent_content_addressed_dataset_id`. 내부 Node 실행이 0이 아닌 종료 코드를 반환했다. 서로 다른 본문 테스트가 동일한 hash를 전달하는 부분부터 확인할 것. 이번 중단 저장에서는 고치지 않았다.
- `git diff --check`는 통과했다(LF/CRLF 안내만 출력).
- 실제 n8n import/Manual Trigger 실행, 운영 Neo4j batch 적재, 실제 API `청둥오리` 200 응답은 **검증하지 않았다**.

## Sol 평가와 남은 작업

Sol 1차 평가는 완료했으며 다음 문제를 보고했다. Claude의 수정이 일부 들어갔지만 최종 재평가는 완료되지 않았다. 재평가 터미널은 ORCA 명령 PATH 문제로 멈췄고 사용자 요청으로 작업을 중단했다.

1. ✅ 서로 다른 종의 동일 한국어 이름을 임의로 한 종으로 선택하지 않는지 확인 — `classifyWikidataRows`의 두 번째 패스(homonym 격리)와
   `test_korean_vernacular_classify_wikidata_rows_quarantines_cross_taxon_homonyms`로 오프라인 검증됨(2026-09-11 재개 세션에서 재검토, 코드 변경 없음).
2. ✅ 스냅샷·출처 레코드 불변성, 재실행 멱등성, 새 스냅샷에서 삭제된 이름의 조회 제외 확인 — `NORMALIZE_WIKIDATA`의 content-addressed id와
   `taxonomy_lineage_neo4j.py`의 `active_dataset_id` 스코프 조회로 오프라인 검증됨.
3. ✅ 잘못된 binding의 누락 없는 집계와 실패 정책 확인 — `malformed_row_count` 집계와 `ASSEMBLE_GATES_JS`의 fail-closed 사유로 오프라인 검증됨.
4. ✅ 매칭 후 활성 taxonomy가 바뀌거나 동시 실행이 경합할 때 활성화 차단 확인 — `START_STATEMENT`/`BATCH_STATEMENT`/`FINALIZE_STATEMENT`의
   `active_concept_set_id` 재확인, 그리고 상태를 먼저 잠근 뒤 `expected_prior_run_id`를 비교하는 낙관적 동시성 가드로 검증됨. 첫 활성화 경합의
   회귀 순서도 `test_korean_vernacular_workflow_never_touches_reference_taxonomy_state_or_gbif_taxa`가 검사한다.
5. ✅ 모든 QID의 출처 연결과 후보 레코드 추적성 확인 — `BATCH_STATEMENT`가 write row와 candidate 양쪽에서 `row.qids`마다 별도 `SourceRecord`를 생성함.
6. ✅ 오류 테스트(`test_korean_vernacular_normalize_computes_idempotent_content_addressed_dataset_id`)를 고치고 전체 오프라인 테스트 재실행 — 220/220 통과.
   Sol 최종 재평가는 이 세션에서 실행하지 않았다(별도 외부 도구 호출이 필요하며 이번 작업 범위 밖).
7. ✅ 생성기와 체크인 JSON을 재생성·비교해 동기화 확인 — 재생성 결과가 체크인 JSON과 바이트 단위로 일치하고, 연속 재실행도 멱등(SHA-256 동일).
8. ✅ 한국어 워크플로우에서 Discord를 선택 사항으로 만들고, NAS 한국어 워크플로우 단독 배포 경로를 마무리 — `deploy_n8n_reference_ingest.py`의
   `DISCORD_REQUIRED` 표로 `korean-vernacular`만 선택 사항으로 만들었고, `reference`는 여전히 필수(기존 테스트 불변). `--workflow korean-vernacular`
   단독 배포 경로(`ready-local`)는 그대로 동작함을 확인.
9. ✅ 이 작업 기록과 [런북](korean-vernacular-ingest.md)의 "현재 검증 상태"를 최종 코드와 대조해 갱신함(아래 참고).
10. ⬜ 준비가 끝난 뒤 실제 환경에서 import → 수동 실행 → Neo4j count/활성 상태 → API 조회를 검증하고 그때 실행 증거를 기록 — **여전히 미검증**.
    이번 재개 세션은 운영 n8n import/실행과 운영 Neo4j 쓰기를 명시적으로 범위 밖으로 뒀다(라이브 opt-in 없음).

## 소스 결정 및 재개 주의사항

Wikidata 채택과 NIBR 비활성 유지는 기존 라이선스 허용 목록에 따른 코디네이터의 구현 판단이다. 사용자가 NIBR 예외를 명시적으로 거부한 사실은 없다. 확인한 NIBR 데이터셋의 공공누리 제3유형은 현재 기본 허용 목록 밖이므로 예외를 임의로 만들지 않았다.

- Wikidata 정책: https://www.wikidata.org/wiki/Wikidata:Licensing
- 확인한 NIBR 데이터셋: https://www.data.go.kr/data/15048041/fileData.do
- 실행·배포 시 `.env` 등의 비밀정보를 저장소에 넣지 않는다.
- 기존 `graphify-out/`는 작업 시작 때부터 존재한 로컬 미추적 산출물이다. 이번 체크포인트 커밋에서는 제외하고 로컬에 보존한다.
- ORCA는 승인된 AppData 절대경로를 사용한다. `.venv/orca-bridge`와 이전 실패 Dispatch를 재사용하지 않는다.
- 중단된 작업을 자동 재시작하지 않는다. 재개 요청 시 이 문서와 실제 diff부터 확인한다.
