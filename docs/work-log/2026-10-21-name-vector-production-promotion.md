# 종 이름 벡터·카탈로그 TEST → Production 한정 반영 — 2026-10-21

> **문서 상태: 완료 — 실제 Production 반영과 검증 통과 (Root 최종 승인 2026-10-21 07:22 KST).** Root(Codex)가 원천 export, Production 계획·반영, 실제 벡터·API·브라우저 검증을 실행했다. 문서 담당은 dev-codex `docs/verification/assets/2026-10-21-name-vector-promotion/` 산출물과 `/tmp/rg-name-promotion/` 운영 스크립트를 **읽기만** 해서 대조했다. 문서 담당은 DB·서비스·Git·코드·환경 설정을 조작하지 않았다.

## 요약

- 사용자 승인 범위: TEST의 **종 이름 벡터(TaxonNameVector)와 그 카탈로그만** Production에 반영한다. **TEST DB 전체 복사가 아니다.** 사용자는 팀 작업을 명시적으로 요청했다(Root 총괄, 독립 검토자, 문서 담당).
- 실행: Root가 만든 명시적·가드 포함 일회성 운영 스크립트 `/tmp/rg-name-promotion/promote.py`(`--plan`·`--apply`)와 검증 모듈 `common.py`. dev-claude의 독립 Claude 검토자가 사전 검토했다.
- 결과(실제 Production):
  - 이름 벡터 **0 → 855**, 카탈로그 1개(fingerprint `a96ed6f8…1919f4c1`). 이름 전용 인덱스(512차원, cosine, ONLINE)와 entry key 유일성 constraint를 새로 만들었다. `state: verified`.
  - 벡터는 TEST에서 **복사**했다. 복사용 외부 임베딩 호출은 0회다. 원시 export 대비 성분별 최대 차이는 2.78e-17이다(허용 1e-12).
  - 운영 스크립트의 모델 호출은 호환성 probe 텍스트 6개(plan 3 + apply 3)다. 실제 API·브라우저 오타 검사도 일반 질의 임베딩을 호출했고, 전체 요청 수는 계측하지 않았다. 카탈로그는 재생성하지 않았다.
  - 실제 벡터 인덱스 질의 6/6, 실제 Production API 4/4, 공개 URL 브라우저 2/2(1280·390px) 통과.
  - Taxon 33,694와 속성 해시, PostgreSQL ingest 상태 해시는 반영 전후가 같다. 다만 **감시 범위 비교이며 DB 전체 체크섬은 아니다.**
  - 앱 배포·재시작, PostgreSQL 쓰기, TEST DB 전체 복사, commit/push, 자동 롤백 **없음**.
- 진행 중 NAS SSH 연결 거부로 첫 계획이 Production을 읽기 전에 중단됐다. 사용자가 SSH를 복구한 뒤 재실행했다(아래 이력).

## 요청 배경과 목표

- 배경:
  - 2026-10-15 이름 벡터를 Neo4j 영구 저장·인덱스 검색으로 옮겼다(dev-codex `docs/work-log/2026-10-15-neo4j-name-vector-migration.md`). 그때는 TEST에만 색인했고 Production 반영은 범위 밖이었다.
  - 2026-10-19 RG-406 후속으로 TEST 카탈로그가 850 → 855종으로 늘었다(dev-codex `docs/work-log/2026-10-19-rg406-outside-name-search.md`: inventory 855 / reused 849 / embedded 6).
  - 2026-10-20 RG-701 Production 배포 때 운영 DB 감시 범위에서 TaxonNameVector 0과 빈 카탈로그를 확인했다. 사용자는 TEST DB 전체 복사를 하지 않고 데이터셋별로 따로 검토·승인하기로 했다(`docs/work-log/2026-10-20-main-production-django.md`). 그래서 운영의 그래프 우선 이름 해소에서 벡터 후보 경로는 데이터가 없어 보류 상태였다.
- 목표: TEST에서 검증된 이름 벡터·카탈로그만 Production Neo4j에 반영해 운영 이름 후보 경로를 활성화한다. 다른 운영 데이터와 서비스는 바꾸지 않는다.
- RG-701(Django 전환)은 이미 완료됐다. 이 작업은 그 상태와 기록을 다시 열거나 바꾸지 않았다.

## 범위

| 포함 | 제외 |
|---|---|
| `TaxonNameVectorEntry`·`TaxonNameVector`(`name_vector` 속성)·`NAME_VECTOR_OF` 연결, `TaxonNameVectorCatalog`, 이름 전용 vector index·constraint | TEST DB 전체 복사, 다른 TEST 데이터, 운영 PostgreSQL 쓰기, Taxon·Document·Chunk 등 다른 그래프 데이터, 문헌 벡터 인덱스 |
| 원천·대상의 활성 분류 문맥과 프로필 대응 확인, 반영 전 백업, 반영 후 실제 회귀 | 앱 이미지 교체·컨테이너 재시작·Jenkins·n8n 변경, 저장소 코드·환경 설정 변경, commit/push |

- **운영 분류는 그대로 썼다.** 벡터 entry를 운영 DB에 이미 있는 Taxon 노드에 연결만 했다. 운영 Taxon은 생성하거나 수정하지 않았다. 원천과 대상 모두 활성 문맥이 `rg:concept-set:avilist-v2025b` / `v2025b`이고 Taxon이 33,694개이며, 반영 전후 Taxon 속성 해시가 같다(`apply.json` `taxon_properties_unchanged: true`).
- 대상이 비어 있어야만 반영한다(empty-destination compare-and-swap). 그래서 재실행하면 거부된다.

## 역할 분담

| 역할 | 워크트리 / Dispatch | 이번 담당 |
|---|---|---|
| Root (Codex, 총괄) | dev-codex | 원천 export, `promote.py`·`common.py` 작성, `--plan`·`--apply` 실행, 실제 벡터·API·브라우저 검증, 증거 산출, 최종 승인 |
| 독립 검토자 (Claude) | dev-claude, 전체 검토 `ctx_e052f00236e5`, 파서 후속 검토 `ctx_7521c6cf3c3e` | 운영 스크립트 읽기 전용 검토와 오프라인 mock 검증. DB·모델·SSH 호출 0 |
| 문서 담당 (Claude) | main-2 (dev), 이 Dispatch `ctx_a3e762715d81` | 이 문서, Obsidian 작업기록·백로그(단독 쓰기). 산출물 읽기·해시 대조만 했다 |

## 원천(TEST)·대상(Production) 확인 — 2026-10-21 새 확인

| 항목 | TEST (원천) | Production 반영 전 (`--plan`, 07:15) | Production 반영 후 (`--apply`, 07:17) | 근거 |
|---|---|---|---|---|
| 이름 벡터 수 | 활성 855, inventory 855 | 0 (feature·entry·catalog 없음) | 855, 카탈로그 1 | `source-export.json`, `plan.json`, `apply.json`, `summary.json` |
| 카탈로그 fingerprint | `a96ed6f8e2ff224b9adfc2148e8b4144829b71c7fdaf27d0d9dce8591919f4c1` | 없음 (`catalog_current: false`) | 같은 값, `catalog_current: true` | 위 파일 |
| 활성 분류 문맥 | `rg:concept-set:avilist-v2025b`, `v2025b` | 동일 | 동일 | `plan.json`, `apply.json` |
| 임베딩 프로필 | `jinaai/jina-embeddings-v3`, 512, 정규화 true (사용자 자체 호스팅 모델, Jina 호환 API — `summary.json`) | 동일. 임베딩 엔드포인트 해시도 동일 | 동일 | `plan.json` (`source_endpoint_equals_destination: true`: `common.py`의 `endpoint_sha256`은 임베딩 클라이언트 엔드포인트 해시임을 문서 담당이 코드에서 확인) |
| 저장소 모듈 해시 | `e843a127…a505d` | 동일 | — | `source-export.json`, Root 전달, `independent-review.md` |
| Taxon 수 | 33,694 | 33,694 | 33,694, 속성 해시 불변 | `plan.json`, `apply.json` |
| 이름 index / constraint | 존재 | 없음 (`absent` / `absent`) | 새로 만듦: VECTOR ONLINE 512 COSINE, `TaxonNameVectorEntry.key` 유일성 | `plan.json`, `apply.json` |
| PostgreSQL ingest 상태 해시 | `04e72da0…8e34f` | 비공개 사전 snapshot에 저장 | 불변 | `source-export.json`, `apply.json` `ingest_states_unchanged: true` |
| 대상 식별 | — | 연결 식별자(PG 호스트·포트·DB·사용자, Neo4j URI·DB) 해시 `4f628bf4…536275`로 고정 | 같은 식별자로 반영 | `plan.json` `destination_identity_sha256` |
| 대상 상태 해시 | — | `69e60bdd…5b6b39` | `59b74a0a…7311a0c` | `plan.json`, `apply.json` |

- 원천 패킷 해시: 동결 원천의 canonical digest는 `a46d0bb4b3a1573c29ace2e7b91cada00333ff5c5f7fe783661d61fd637b4a1d`이다(`source-export.json` `export_sha256`, `plan.json` `source_sha256`). 반영 후 TEST snapshot도 같은 값이다(`source-after.json` `unchanged_from_preflight: true`, 활성 855, Taxon 33,694). 07:03 첫 시도의 export digest `b755c2a0…`는 `feature_count` 등 필드가 추가되기 전 형식이라 대체됐다(`independent-review.md`).
- 전일 기록의 "Production 0"을 새 확인으로 옮겨 적지 않았다. 위 Production 열은 이번 실제 읽기 결과다.

## 운영 스크립트와 가드

- 위치: 저장소 밖 `/tmp/rg-name-promotion/`. 증거 사본은 dev-codex 자산 폴더에 있다. 저장소 코드 변경은 아니다.
- 최종 해시(문서 담당이 `shasum -a 256`로 `/tmp` 원본과 자산 사본이 같은지 확인): `promote.py` `4ad04729670b74d98bef6020eb67380f48245b4fa3f06000c71e2b43fd329767`, `common.py` `07a17f950c9eb868a2d2991d49f26cc9a47ed555245bfdbd406caa776dc9a156`. `plan.json`의 `operator_sha256`·`validation_sha256`과 같다.
- 동작(문서 담당이 `promote.py`를 읽어 확인):
  - `--plan`과 `--apply` 중 하나만 지정해야 한다. 로컬·원격 모두 최적화 실행(`python -O`, assert 제거)을 거부한다.
  - `--plan`: TEST snapshot을 찍고 `validate_source`로 검증한다. TEST export와 Production 사전 snapshot을 Git 밖 비공개 디렉터리에 저장한다(디렉터리 700, 파일 600, 덮어쓰기 금지). Production에서 `validate_destination`과 모델 호환성 probe를 실행하고 `plan.json`에 영수증을 남긴다.
  - Production 접근 가드: NAS 컨테이너 `robingraph-api`에 `ROBINGRAPH_DEPLOY_TARGET=prod`가 있어야 한다. 또 실효 compose 설정의 Neo4j·PostgreSQL 연결값이 컨테이너 환경과 같아야 하고 고정된 식별자와 정확히 일치해야 한다. 값은 출력하거나 기록하지 않는다.
  - `--apply`: 운영 스크립트·검증 모듈 해시와 원천·대상 식별 해시가 plan 영수증과 같아야 한다. 현재 TEST snapshot이 검토 시점과 같아야 한다. NAS에 배타 lock을 잡고, 반영 직전 Production snapshot이 plan 때 해시와 같을 때만 NAS 백업을 저장한 뒤 `apply_source`를 실행해 영수증을 남긴다.
- 스크립트 변경 경과(Root 전달): 처음 가드는 Production 환경 파일을 직접 읽었다. 이 파일의 `NEO4J_DATABASE`가 따옴표로 저장되어 있어 실효 설정이 같은데도 잘못 거부했다. 지금은 `docker compose config --format json` 결과를 메모리에서만 읽어 비교하며 비밀값은 기록하지 않는다. 이 파서 변경으로 `promote.py`가 `723736e1…`에서 `4ad04729…`로 바뀌었고 후속 검토를 따로 받았다(아래).

## 독립 검토

| 항목 | 결과 | 종류 | 근거 |
|---|---|---|---|
| 모듈 단위 검사 (`tests.test_taxon_name_vectors_neo4j`, `test_index_taxon_name_vectors`, `test_embeddings`, `test_taxon_name_resolution`) | 61 OK | 오프라인 mock | `independent-review.md`, `review-clearance.json` |
| 원천 측 음성 사례 (NaN, 511차원, 프로필·문맥 불일치, 외부·fixture taxon 연결, 연결 누락, inventory 행 누락·텍스트 수정, entry 제거, 카탈로그 수, index 1024차원·POPULATING, feature 856 등) | 16/16 거부 | 오프라인 mock | 동일 |
| 대상 측 음성 사례 (문맥·모듈 해시 불일치, 비어 있지 않은 대상 등) | 4/4 거부 | 오프라인 mock | 동일 |
| mock apply (실제 TEST export 파일, 메모리 내 가짜 Neo4j) | verified, 855, cache_calls 1, reused 0, 최대 차이 2.8e-17 | 오프라인 mock | 동일 |
| 재실행·오래된 기준선·고정 식별자 없음 | 모두 거부 | 오프라인 mock | `independent-review.md` |
| 원격 wrapper 재구성 | 10,464,392 bytes, placeholder 왕복 일치 | 오프라인 | `independent-review.md` |
| compose 파서 후속 검토 (`promote.py` 4ad04729) | 16/16 통과 (가짜 env, DB 없음) | 오프라인 mock | `review-clearance.json` (`ctx_7521c6cf3c3e`) |
| 검토자의 DB·모델·SSH 호출 | 0 | — | `review-clearance.json` |

- 판정: "cleared for guarded --apply; actual Production verification belongs to root" (`review-clearance.json`).
- **해시 경과**: `independent-review.md`는 전체 검토 당시 기록이다. 해제 대상을 `promote.py` `723736e1…`로 적었고 "이후 수정 시 무효"라고 했다. 그 문서의 표에는 `0c8162dc…`도 최종본으로 나온다(검토 중 개정 이력). 실제 plan·apply에 쓴 `4ad04729…`는 후속 파서 검토 Dispatch `ctx_7521c6cf3c3e`가 해제했다. 근거는 `review-clearance.json`과, Root가 Orca inbox에서 수정 없이 내보낸 그 Dispatch의 원본 완료 보고 `compose-parser-review-event.json`(`msg_c758b5880088`, `worker_done`, outcome `succeeded`, 2026-10-21 07:16:16 KST)이다. 문서 담당이 원본 파일을 읽어 확인한 내용은 다음과 같다. 검토자는 새 파서 블록을 옛 줄로 되돌리면 이전 해제 해시 `0f1ff373…24e8`과 정확히 같아진다는 점으로 변경 범위가 compose 설정 읽기뿐임을 확인했다. `common.py`는 바뀌지 않았다. 실제 로컬 docker compose v5.5.0과 가짜 env 파일로 16/16 통과했다(DB·SSH·모델 호출 없음). 남은 비차단 사항은 두 가지다. compose 파일 경로를 label이 아니라 `working_dir/compose.nas.yml`로 정하고, NAS compose가 `--format json`을 거부하면 진행을 막는다(fail closed). 이 원본 이벤트가 옛 해시만 적은 첫 검토를 대체한다.
- 검토자의 비차단 권고(`independent-review.md`):
  1. 반영 커밋 뒤 사후 검증이 실패하면 NAS 영수증 없이 "커밋됨·미검증" 상태가 될 수 있다. 0이 아닌 종료는 재시도 전에 점검해야 한다.
  2. 데이터 트랜잭션이 실패하면 먼저 자동 커밋된 DDL이 빈 schema로 남는다.
  3. PG 호스트·사용자는 "plan 이후 불변"으로 고정할 뿐 별도의 알려진 값과 대조하지 않는다.
  4. 환경 파일 값이 따옴표로 저장되거나 생략되면 가드가 잘못 거부할 수 있다. 실제로 발생했고 compose 설정 비교로 바꿨다.
  5. 인덱스 반영이 늦으면 사후 self-query가 실패할 수 있다.
- 이번 실제 실행에서 1·2·5는 발생하지 않았다(`apply.json` `state: verified`).

## 실행 이력 (2026-10-21, KST)

| 시각 | 내용 | 근거 |
|---|---|---|
| 07:03경 | 첫 `--plan`(동결 전 버전): TEST export 후 NAS SSH 포트 99 `Connection refused`, ssh exit 255. Production snapshot 읽기 전에 중단 | `/tmp/rg-name-promotion/plan.log` |
| 07:08 | 재확인: 포트 99·22 모두 `ConnectionRefusedError`. Production DB 쓰기 0, 대상 호환성 미확인, 대상 백업 없음, 모델 호출 0, NAS 설정 변경 없음 | `access-status.json` |
| 07:10 | 새 원천 export(855, digest `a46d0bb4…`) | `source-export.json` |
| 07:12경 | 사용자가 NAS SSH를 복구함(`resolved_by_user: true`) | `access-status.json`, Root 전달 |
| 07:15 | `--plan` 통과(실제 Production 읽기와 모델 probe), `production_written: false` | `plan.json` |
| 07:17 | `--apply` 통과, `state: verified` | `apply.json` |
| 07:18 | 반영 후 TEST 원천 불변 확인 | `source-after.json` |
| 07:19 | 공개 URL 브라우저 2/2 | `browser.json`, `promotion-{1280,390}.png` |
| 07:20 | 실제 Production API 4/4 + 별도 관찰 1 | `live-api.json`, `verification-adjustment.json` |
| 07:22 | 최종 요약, 검토 해제 기록 | `summary.json`, `review-clearance.json` |

- Root와 문서 담당은 NAS SSH·서비스 설정을 바꾸지 않았다. SSH를 다시 연 것은 사용자다.

## 백업

- 로컬 비공개 백업(Git 밖): TEST export와 Production 사전 snapshot. 이번 plan 디렉터리는 `name-vector-promotion-20261021-8ffd9df9`이다(디렉터리 700, 파일 600). 검토자가 확인한 동일 digest의 원천 export는 `…-06a7a825`에 있고, 07:03 첫 시도의 디렉터리는 `…-ad361c90`이다.
- NAS 백업: 반영 직전 Production snapshot(대상 상태 해시 `69e60bdd…` 일치를 확인한 뒤 저장)과 영수증을 NAS 앱 작업 디렉터리 아래 `.name-vector-promotions/name-vector-promotion-20261021-8ffd9df9/`에 저장했다(파일 600, `apply.json` `nas_backup_directory`).
- 반영 전 Production에는 이름 벡터가 0이었다. 따라서 백업은 "비어 있던 상태"와 함께 Taxon·ingest 상태의 기준 해시를 보존한다.
- 인증 정보와 환경 파일 값은 기록하지 않았다.

## 복사 정밀도: 복사한 벡터 vs 원시 export

- 반영한 855개 벡터는 TEST export 값이다. 저장소 `index_names` 경로가 임베딩 함수를 부르지만, 그 함수는 TEST 벡터 캐시를 돌려준다(`cache_calls: 1`, `external_embedding_calls_for_copy: 0`). `repository_result.embedded: 855`는 캐시에서 받은 벡터를 쓴 수이며 모델로 재생성한 수가 아니다.
- 성분별 최대 차이는 `2.7755575615628914e-17`이다(`apply.json`). 저장소의 단위 벡터 재정규화에서 생기는 부동소수 오차이며 허용 기준 1e-12 아래다. 원시 export의 노름 편차는 최대 1.1e-16이다(`independent-review.md`).

## 모델 호출: 검증 vs 재생성

- 운영 스크립트의 호환성 probe 텍스트는 6개다(plan 3 + apply 3, `summary.json` `validation_model_probe_texts: 6`). Production 앱 컨테이너에서 사용자 자체 호스팅 임베딩 API를 **호출**해 임베딩했고, 복사 대상 TEST 벡터와 비교한 cosine은 0.9999990853756634 / 0.99999879160047 / 0.9999992185122778이다. 모델이 앱 컨테이너나 NAS 안에서 물리적으로 실행되는지는 확인하지 않았다. 같은 프로필 ID 메타데이터와 엔드포인트 해시 일치만 확인했으며, 가중치의 독립 검증도 하지 않았다.
- 실제 API·브라우저 오타 검사(천둥오리·Keaa 등)도 앱이 질의 이름 임베딩을 요청하므로 일반 질의 임베딩 호출이 추가로 있었다. 전체 네트워크 요청 수는 계측하지 않았다.
- 목적은 같은 모델·프로필인지 확인하는 것이다. 카탈로그를 재생성하지 않았다(`regenerated_catalog: false`, `purpose: compatibility validation only`).

## 실제 벡터·API·브라우저 회귀

### 벡터 인덱스 (실제 Production Neo4j)

| 학명 | 전체 검색에서 자기 자신 | 범위 검색 | 근거 |
|---|---|---|---|
| Anas platyrhynchos | 통과 | 통과 | `apply.json` |
| Anas zonorhyncha | 통과 | 통과 | 동일 |
| Nestor notabilis | 통과 | 통과 | 동일 |

- 합계 6개 질의 통과(`actual_vector_index_queries_passed: 6`).

### API (실제 Production 앱, NAS 컨테이너 내부 `127.0.0.1:8000`, 응답 mocking 없음)

`live-api.py`는 `/health`의 `deployment_target == prod`를 확인한 뒤, 실제 UI처럼 `filters: {kind: profile, name: …}`를 넣어 `/v1/chat`을 호출한다(문서 담당이 스크립트를 읽고 확인).

| 질의 | 범위 | disposition | 해소 방식 | 기대 학명 | 결과 |
|---|---|---|---|---|---|
| Anas platyrhynchos | korea | answer | graph_exact | Anas platyrhynchos | 통과 |
| 흰뺨 검둥 오리 | korea | answer | graph_normalized | Anas zonorhyncha | 통과 |
| 천둥오리 | korea | clarify | vector | Anas platyrhynchos (후보) | 통과 |
| Keaa | outside | clarify | vector | Nestor notabilis (후보) | 통과 |

- **검증 기대값 정정** (`verification-adjustment.json`): 첫 API 검사는 띄어 쓴 한국어 이름을 `filters.name` 없이 보내고 `answer`를 기대했다. 실제 응답은 `clarify`였다(HTTP 오류 아님). 이 요청은 이름 해소 전에 clarify 단계로 간다. 검사를 실제 UI의 요청 형태(명시적 이름 필터)로 고쳤고, 필터 없는 입력이 `clarify`(이름 해소 전, `entity_resolution` 없음)로 남는 것은 따로 관찰해 기록했다. 앱 코드는 고치지 않았고 반영도 되돌리지 않았다. Root는 이 결과를 이번 반영의 결함으로 분류하지 않았다. 문서 담당도 새 결함이나 요구사항으로 등록하지 않는다.

### 공개 URL 브라우저 (`https://robingraph.dove-nest.com/chat`, 응답 mocking 없음)

| 폭 | 흐름 | 결과 |
|---|---|---|
| 1280 | `천둥오리` → 응답 `clarify`·`entity_resolution.method = vector`, 후보에 Anas platyrhynchos → "청둥오리" 후보 클릭 → `answer`에 Anas platyrhynchos | 통과, page error 0, 가로 넘침 없음 |
| 390 | 같은 흐름 | 통과, page error 0, 가로 넘침 없음 |

- `browser.cjs`의 assert 항목은 문서 담당이 스크립트에서 확인했다. 데스크톱 Chromium의 폭만 바꾼 검사이고 **물리 모바일 기기 검사가 아니다**(`physical_mobile: false`). 스크린샷은 `promotion-1280.png`·`promotion-390.png`이다.

## 관련 없는 변경 없음

| 항목 | 결과 | 근거 |
|---|---|---|
| Production Taxon 수·속성 해시 | 33,694, 불변 | `apply.json` |
| Production PostgreSQL ingest 상태 해시 | 불변 (읽기만 함) | `apply.json`, `summary.json` |
| TEST 원천 전체 snapshot | 불변 | `source-after.json` |
| 다른 TEST 데이터 복사 | 없음 | `summary.json` `other_test_data_copied: false` |
| 앱 배포·재시작 | 없음 | `summary.json` `service_restart_or_deployment_performed: false` |
| NAS 설정 변경 | 없음 | `access-status.json` |

- 감시 범위만 비교했다. Production DB 전체(예: 문헌 Chunk·벡터 인덱스 전체)의 동일성을 체크섬으로 확인하지는 않았다.

## 변경 전후 동작

| 항목 | 변경 전 | 변경 후 |
|---|---|---|
| Production 이름 벡터 | 0, 카탈로그·인덱스·constraint 없음 | 855, 카탈로그 1, 인덱스 ONLINE 512 cosine, constraint 있음 |
| 운영 이름 후보 경로 | 그래프에서 못 찾은 이름은 벡터 데이터가 없어 후보 없이 보류 | 오타 이름(예: 천둥오리, Keaa)에 벡터 후보를 확인 요청으로 제시 |
| 그래프 정확·정규화 해소 | graph_exact·graph_normalized | 같음 |
| 앱·이미지·PostgreSQL | — | 변경 없음 |

- "변경 전"의 운영 보류 동작은 2026-10-20 기록과 코드 설계(인덱스가 없으면 보류)에 근거한다. 이번에 반영 전 상태로 API를 따로 호출해 확인하지는 않았다.

## 실제 사용한 명령 (Root 전달·자산 기준)

아래는 이번 증거를 만든 **당시 명령의 기록**이다. 다시 실행하라는 지시가 아니다. `promote.py`는 일회성이며, 대상이 비어 있지 않으므로 재실행하면 거부된다. 문서 담당은 이 명령들을 실행하지 않았다.

```sh
# 원천 export: TEST 컨테이너에서 common.py snapshot('test') (promote.py --plan 내부, Python)
python3 /tmp/rg-name-promotion/promote.py --plan
python3 /tmp/rg-name-promotion/promote.py --apply
python3 /tmp/rg-name-promotion/live-api.py
node docs/verification/assets/2026-10-21-name-vector-promotion/browser.cjs
# 독립 검토(오프라인, dev-codex)
.venv/bin/python -m unittest tests.test_taxon_name_vectors_neo4j tests.test_index_taxon_name_vectors tests.test_embeddings tests.test_taxon_name_resolution
```

- 자산 폴더의 `graphify-update.log`는 Root가 dev-codex에서 그래프를 갱신한 로그다(6,724 nodes / 14,392 edges). main-2는 코드를 바꾸지 않아 graphify를 갱신하지 않았다.

## 검증 종류 구분

| 구분 | 범위 | 통과 / 실패 / 건너뜀 | 종류 |
|---|---|---|---|
| 독립 검토 단위 검사 | 61 | 61 / 0 / 0 | 오프라인 mock |
| 음성 가드 | 원천 16, 대상 4, 파서 16 | 모두 기대대로 거부·통과 | 오프라인 mock |
| mock apply | 855 | 통과 | 오프라인 mock (실제 TEST export 파일) |
| Production plan | 호환성·dry-run·probe 3 | 통과 | 실제 Production 읽기 + 모델 |
| Production apply | 855 반영, 사후 검증 | verified | **실제 Production 쓰기** |
| 벡터 인덱스 | 6 질의 | 6 / 0 / 0 | 실제 Production Neo4j |
| API | 4 기능 사례 + 1 관찰 | 4 / 0 / 0 (첫 기대값 오류는 위에 기록) | 실제 Production API |
| 브라우저 | 2 흐름 | 2 / 0 / 0 | 실제 공개 URL, 물리 기기 아님 |
| 실제 롤백 | — | 미실행 | — |

## 변경 파일과 구현 내용

- 저장소 코드·테스트·환경 설정: 변경 없음.
- 운영 데이터: Production Neo4j의 이름 벡터 entry·feature·연결·카탈로그와 이름 전용 index·constraint(위 범위).
- 운영 스크립트·검증 산출물(Root, dev-codex 미커밋 자산): `docs/verification/assets/2026-10-21-name-vector-promotion/`의 `access-status.json`, `source-export.json`, `plan.json`, `apply.json`, `source-after.json`, `live-api.json`, `live-api.py`, `browser.json`, `browser.cjs`, `promotion-1280.png`, `promotion-390.png`, `verification-adjustment.json`, `independent-review.md`, `review-clearance.json`, `summary.json`, `promote.py`, `common.py`, `compose-parser-review-event.json`, `graphify-update.log`.
- main-2(문서 담당): 이 문서만 새로 만들었다. 이전 작업 기록은 수정하지 않았다.

## 배포·커밋 정보

- 앱 배포·컨테이너 재시작·Jenkins 실행 없음. 운영 데이터 반영은 위 운영 스크립트로만 했다.
- commit/push는 이번 턴에 요청되지 않았고 수행하지 않았다(`git_commit_push_performed: false`). main-2 문서와 dev-codex 자산은 미커밋 상태다. Root가 검토한 뒤 dev-codex에 반영한다.

## 롤백 기준

- 자동 롤백은 수행하지 않았다(`automatic_rollback_performed: false`). 실제 롤백도 실행하지 않았다.
- 되돌려야 한다면 이번에 추가한 이름 벡터 entry·feature·`NAME_VECTOR_OF`·카탈로그와 이름 전용 index·constraint만 제거한다. 그러면 NAS 백업의 반영 전 상태(이름 벡터 0, 대상 상태 해시 `69e60bdd…`)로 돌아가며, 이것이 롤백 기준이다. Taxon과 PostgreSQL은 건드리지 않는다. 운영 이름 후보 경로는 다시 보류로 돌아간다.
- 롤백도 운영 DB 변경이므로 **별도 승인**이 필요하다. 롤백 스크립트는 이번에 작성·검증하지 않았다.

## 남은 한계와 후속 사항

- 운영 DB 비교는 감시 범위(Taxon 속성, ingest 상태, 이름 벡터 관련 노드·schema)만 다뤘다. DB 전체 동일성은 확인하지 않았다.
- Production 카탈로그는 TEST의 855종 검토 목록 그대로다. TEST 검토 목록이 바뀌면 Production 반영은 다시 별도 승인을 받아야 한다. 이 운영 스크립트는 비어 있는 대상에만 쓰므로 증분 갱신에 그대로 쓸 수 없다.
- 이번 검사는 물리 모바일·Safari·Firefox를 포함하지 않았다.
- 띄어 쓴 이름을 이름 필터 없이 보내면 이름 해소 전에 `clarify`가 된다. 이 관찰은 기존 요청 계약이며, 이번 범위에서 결함으로 판단하거나 바꾸지 않았다.
- 검토자의 비차단 권고(사후 검증 실패 시 부분 영수증, DDL 선커밋, PG 식별자 독립 고정)는 이 일회성 스크립트를 다시 쓸 때 고려할 사항이다. 이번 결과에는 영향이 없었다.
- RG-701은 완료 상태를 유지하며 이 작업으로 다시 열지 않았다.
