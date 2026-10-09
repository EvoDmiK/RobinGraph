# 전체 종 source → TEST DB → read_traits/API 감사

작성: 2026-10-09 · 담당: GPT-6.1-sol worker · 범위: 읽기 전용 실측과 감사 도구/오프라인 테스트

## 요청 배경과 목표

까치 카드의 먹이 구성·먹이 활동 위치 차트가 비어 있다는 제보에서 전체 종 자료 신뢰성과 누락 검토로 확장되었다. 최신 소스 `4c62562eca085122c0edd399149f5d179928303b`를 읽고 원본 보존, 활성 릴리스, 형질 claim 연결, 실제 조회 제외, 매핑 미해결을 구분했다. IUCN 평가 검증과 분류 개념 교차표 판단은 다른 담당자의 범위이며 이 감사에서 평가 등급·비율을 새로 만들거나 분할 전 자료를 새 종에 상속하지 않았다.

## 확인한 결론

1. AviList 11,131종은 활성 TEST Neo4j와 PostgreSQL 모두에 있다. 원본→DB와 DB→원본 종 key-set 차이, 종 sequence/ID/학명 중복, 학명 불일치, 비활성/비허용 종은 모두 0이다. 원본 캐시 둘의 SHA-256도 동일하며 활성 Neo4j concept set 체크섬과 일치한다.
2. EltonTraits 9,993개 유효 프로필·AVONET 11,009개 프로필의 PostgreSQL 원기록 ID 누락은 0이다. 고유 정확학명 연결 프로필은 각각 7,752개·9,879개이고, 실제 Neo4j claim은 46,512개·128,331개다. 이 연결 범위에서 원본값 불일치와 중복 claim은 0이다.
3. EltonTraits 2,241개·AVONET 1,130개 프로필은 현재 종에 정확학명으로 연결되지 않은 mapping candidate다. 후보 미생성/원본에 없는 후보/후보 ID 중복 여부는 결과 JSON으로 확인하며, 아래 후보 값 보존 결과를 별도로 기록한다.
4. DB가 가진 모든 형질을 UI가 표시하는 것은 아니다. `pelagic_specialist` 7,752종은 read_traits의 LABELS 미지원으로 제외된다. `nocturnal` 2종은 reviewed_activity가 `activity_pattern`으로 변환하고 원래 claim을 source_claims에 보존한다. 이 두 변환을 유실로 부르지 않는다.
5. 두 비율 차트는 각각 7,752종에서 원본값과 같은 값이 반환된다. 현재 종 학명에 해당하는 Elton 행이 없는 종은 3,379종이다. 이 수를 원본에 생물학적 정보가 전혀 없는 종 수로 해석하면 안 된다. 옛 학명/광의 개념 자료는 후보 목록과 Claude 교차표 검토를 함께 봐야 한다.

## 실제 수집·검증 방법

- SSH: 지정된 NAS `kimdove@192.168.219.99`, port 99, BatchMode, ControlPath `/tmp/rg-conservation-ssh.sock`를 사용했다.
- 대상은 고정된 `robingraph-api-test` 컨테이너다. 기존 활성 환경을 컨테이너 내부에서 설정 객체로 읽으며 환경값·자격증명은 출력/JSON/보고서에 직렬화하지 않는다. `.env`를 로컬로 복사하지 않았다.
- PostgreSQL은 `default_transaction_read_only=on`을 연결 옵션에 지정하고 실제 `transaction_read_only=on`을 확인했다. 데이터베이스 이름이 TEST임을 확인하지 못하면 수집기를 중단한다. schema search_path와 조회 시간 제한만 설정하며 INSERT/UPDATE/DDL은 실행하지 않는다.
- Neo4j는 고정 MATCH 템플릿과 `READ_ACCESS` / `execute_read`를 사용했다. 이 드라이버 모드가 DB 사용자의 서버 권한을 읽기 전용으로 바꾸는 것은 아니다. 실제 실행 쿼리는 읽기 전용이며 MERGE/CREATE/SET은 없다.
- PostgreSQL 활성 reference-taxonomy-traits/reference-avonet context를 읽고, 활성 concept set의 모든 species를 수집했다. 원본 species sequence·학명과 DB key-set을 양방향 비교했다.
- Elton 원본 TSV를 고정 해시로 내려받아 저장소의 실제 NORMALIZE_ELTON JavaScript를 Node에서 실행했다. AVONET는 고정 XLSX의 AVONET1_BirdLife 시트를 기존 파서·normalize_row로 메모리에서 읽었다. 원본 다운로드 파일을 새로 저장하지 않았다.
- 전체 종 조회는 배포된 TRAIT_QUERY의 gate를 유지하고 taxon_id를 추가한 일괄 DB 조회 후, 실제 배포된 read_traits 함수에 종별 실제 rows를 입력해 replay했다. 이 단계의 repository adapter는 이미 수집한 실 DB rows를 반환한다. 전체 종 11,131개 HTTP 호출을 한 것은 아니다.
- 배포된 read_traits 함수·TRAIT_QUERY 해시는 로컬 함수/쿼리와 일치한다. DB reader query rows는 174,843개이며 replay 오류 0, 종별 100행 LIMIT에 걸리는 종 0이다.
- 별도로 실제 TEST loopback `/v1/taxa/profile` HTTP GET 7개를 실행했다. photo enrichment 등 API 흐름도 실제 배포 앱을 경유했다. 세부 traits·원본 claim과 API 비교 결과는 JSON samples에 보존했다.

## 고정 원본과 활성 릴리스

| 원본 | SHA-256 | 원본/유효 행 |
|---|---|---|
| AviList v2025b | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` | 33,684 전체 / 11,131 species |
| EltonTraits BirdFuncDat.txt | `97216eb1797da077169ebb1ebea275db293b09fc62f8bb8911f9beb98c50d321` | 9,995 원본 / 9,993 유효 |
| AVONET AVONET1_BirdLife | `eb645e83dddb40f1654a3e8d721998dbca76eff540231b7b809267c1e96f8d3e` | 11,009 프로필 |

Elton 원본 바이트는 UTF-8로 완전히 해독되지 않아 cp1252로 해독했다. 바이트 SHA-256은 해독 전 원본에 대해 계산하며 저장소 고정값과 일치해야 감사가 진행된다. 무효 두 행의 사유는 JSON source_snapshots.elton.invalid_rows에 보존했다.

원본 URL: AviList 캐시의 원본 `https://explore.avilist.org/data/avilist-2025b.json`, Elton `https://ndownloader.figshare.com/files/5631081`, AVONET `https://ndownloader.figshare.com/files/34480856`. 원본 개별 값은 고정된 source identity에 묶어서 비교하며 활성 PostgreSQL bundle SHA는 개별 원본 해시와 다른 bundle identity라는 점을 구분한다.

| pipeline | 활성 release | version |
|---|---|---|
| reference-taxonomy-traits | `reference-bundle:sha256-fd3749be71afd154155b46c3e065e32485bd4106c1883b928a2064aa5c39822f` | 1 |
| reference-avonet | `figshare-article-16586228-v7:file-34480856` | 1 |

활성 분류: `v2025b` / `rg:concept-set:avilist-v2025b`. 활성 context cursor 전체, 허용 정책, source release ID/해시는 JSON contexts에 있다.

## 전체 종 형질 커버리지

아래 표의 분모는 AviList 현재 11,131종이다. 프로필 연결과 원본 필드 자체가 없는 경우를 구분한다. 의미 있는 누락은 단일 자료 소스별로 판정하고, Elton 체중과 AVONET 체중처럼 여러 출처가 같은 형질을 제공해도 한 출처의 유실을 다른 출처로 감추지 않는다.

| 소스 | 형질 | 직접 반환 | 검토 변환 보존 | 정확 현재학명 원본행 없음 | 원본 필드 없음 | reader 미지원 | 기타 조회 제외 |
|---|---|---:|---:|---:|---:|---:|---:|
| elton | `body_mass` | 7,752 | 0 | 3,379 | 0 | 0 | 0 |
| elton | `diet_category` | 7,752 | 0 | 3,379 | 0 | 0 | 0 |
| elton | `diet_distribution` | 7,752 | 0 | 3,379 | 0 | 0 | 0 |
| elton | `foraging_strata_distribution` | 7,752 | 0 | 3,379 | 0 | 0 | 0 |
| elton | `nocturnal` | 7,750 | 2 | 3,379 | 0 | 0 | 0 |
| elton | `pelagic_specialist` | 0 | 0 | 3,379 | 0 | 7,752 | 0 |
| avonet | `beak_depth` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `beak_length_culmen` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `beak_length_nares` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `beak_width` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `body_mass` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `habitat` | 9,796 | 0 | 1,252 | 83 | 0 | 0 |
| avonet | `habitat_density_category` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `primary_lifestyle` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `tail_length` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `tarsus_length` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |
| avonet | `trophic_level` | 9,875 | 0 | 1,252 | 4 | 0 | 0 |
| avonet | `trophic_niche` | 9,870 | 0 | 1,252 | 9 | 0 | 0 |
| avonet | `wing_length` | 9,879 | 0 | 1,252 | 0 | 0 | 0 |

AVONET habitat 83종·trophic_level 4종·trophic_niche 9종은 정확학명 연결 프로필이 있어도 원본 필드가 비어 있다. 이를 ingest 누락이나 DB 조회 오류로 분류하지 않는다. `pelagic_specialist`를 화면에 추가할지는 별도 제품 결정이며 이번 감사는 조회 구현을 수정하지 않았다.

### 누락 분류의 의미

- `source_record_missing_postgres`: 원본 프로필은 있는데 동일 ID의 PostgreSQL 원기록이 없다.
- `source_present_claim_missing_graph`: 고유 현재학명 연결 대상과 원본 값이 있는데 graph claim이 없다.
- `graph_claim_not_returned_by_reader`: graph claim이 있으나 실제 reader 결과에 없다. 활성 source release/분류판/증거 policy·dataset·record gate 사유를 JSON query_gate_reasons에 기록한다.
- `reader_trait_not_supported`: 조회 LABELS에 해당 형질이 없다. 원본/DB 값이 없어졌다는 의미가 아니다.
- `preserved_in_reviewed_trait`: 검토된 활동시간 출력으로 변환되고 원형질 값·출처가 source_claims에 남는다.
- `source_field_absent`: 원본의 현재 정확학명 프로필에 그 형질 값이 없다.
- `source_absent_exact_current_name`: 현재 종 이름의 원본행은 없으나 옛 학명/이전 분류개념 행 존재 가능성까지 부정하지 않는다. 실제 원본 자체 미존재와 매핑 실패 최종 분리는 분류 교차표 검토가 필요하다.
- `unresolved_profiles`: 원본에 값 있는 프로필이 존재하나 현재 종에 고유 정확학명 연결이 실패했다. 각 source record ID·이름·보유형질·후보 사유를 JSON에 보존했다.

## 미해결 후보의 값 보존

실 TEST Neo4j 후보 profile_json 전체를 고정 원본의 정규화 형질값과 대조했다. Elton 2,241개·AVONET 1,130개 모두 허용 policy이며, 후보값 불일치/미해독/누락 0, 후보 source record ID 중복 0, 원본 미해결 프로필인데 후보가 없는 경우 0, 원본에 해당 프로필이 없는 후보 0이다. 현재 후보값은 재수집 없이 분류개념 허용 매핑의 복구 입력으로 사용할 수 있다. 이는 source profile 값 전체 비교이며 실제 학명 연결/DB mutation을 실행했다는 뜻이 아니다. PostgreSQL trait_profile payload는 식별자/선택 메타데이터 중심이고 형질값 전체를 저장하지 않으므로, PostgreSQL record 존재만으로 값을 복구할 수 있다고 단정하지 않는다.

## 까치와 대표 다른 종: raw DB 대 reader 대 실제 API

| 요청 | raw claim | API HTTP | read_traits 값과 동일 | 근거/차이 |
|---|---:|---|---|
| Pica serica | 0 | 200 | False | 배포 profile의 검토된 4개 형질 추가; raw claim 없음 |
| Pica pica | 19 | 200 | True | 동일 |
| Anas platyrhynchos | 19 | 200 | True | 동일 |
| Struthio camelus | 19 | 200 | True | 동일 |
| Nycticorax nycticorax | 19 | 200 | True | 동일(활동시간 검토 변환 포함) |
| Cyanopsitta spixii | 19 | 200 | True | 동일 |
| 까치 | 0 | 200 | False | 배포 profile의 검토된 4개 형질 추가; raw claim 없음 |

`Pica serica`와 국명 `까치`는 모두 `avilist-taxon:v2025b:20193` / 까치 / Oriental magpie로 응답했다. raw trait claim은 0이며 read_traits도 빈 배열이다. 실제 profile API는 검토된 출처 기반 body_mass=220.64 g, habitat=Human Modified, diet_category=Omnivore, primary_lifestyle=Terrestrial 4개를 별도 제공했다. 두 비율 형질은 API에도 없다. 이것은 read_traits와 profile 결과 차이이며 조회 유실이 아니다.
`Pica pica`는 `avilist-taxon:v2025b:20198` / Eurasian magpie로 응답하고 국명 까치로 표시되지 않았다. raw claim 19개 중 pelagic_specialist를 제외한 18개를 reader/API가 반환한다. Elton 비율은 DB/원본/현재 조회가 같다는 사실만 검증했다. 이 원본이 현재 좁은 Pica pica 개념을 정당하게 대표하는지까지 보장하지 않는다. Claude의 /tmp/rg-all-species-claude-review.md는 분할 전 광의 개념 문제를 별도로 지적하고 있으므로 후속 수정에서 출처 분류개념 범위를 드러내야 한다.
Nycticorax nycticorax의 원 nocturnal=False는 activity_pattern=True 검토 결과의 source_claims 안에 보존됐다. 검토 설명과 원자료 provenance가 함께 반환된다.

## 변경 파일과 동작

- `scripts/audit_trait_coverage.py`: 재현 가능한 TEST 전용 읽기 감사 CLI. 원본 해시 검증·원본 normalizer 재사용·활성 PostgreSQL context와 원기록 조회·Neo4j 종/claim/후보 수집·배포 read_traits replay·실 HTTP 표본 조회·원인별 커버리지 JSON을 제공한다. 이전에는 이 전수 연결/조회 감사 도구가 없었다.
- `tests/test_trait_coverage_audit.py`: 분류 key-set 차이·중복, 원기록/claim/조회/원본필드 구분, 분할 전 무조건 상속 방지, False/0 보존, 검토 변환 원claim 보존, 후보 profile 값과 오류, release/evidence gate, 다중 증거의 claim 중복 오인 방지, API 검토 overlay 차이를 검증한다.
- `/tmp/rg-all-species-sol-report.json`: 실제 실측 결과와 전체 미해결 source 프로필·개별 source형질 제외·API 표본값을 보존한다.
- `/tmp/rg-all-species-sol-report.md`: 상세 작업 기록이며 핵심 수치와 테스트 범위를 JSON과 일치시킨다.
기존 runtime/UI/ingest 코드는 변경하지 않았다. DB mutation·commit·deploy는 실행하지 않았다. PROD에는 연결/변경하지 않았다. Obsidian 문서는 소유 범위에 없어 작성하지 않았다. graphify query는 실행했지만 graphify update는 소유권이 허용한 파일 두 개와 /tmp 보고서 외 graphify-out을 변경하므로 실행하지 않았다.

## 검증과 재현 명령

저장소 root에서:

```sh
PYTHONPATH=src /tmp/rg010-venv/bin/python scripts/audit_trait_coverage.py \
  --snapshot /tmp/rg010-avilist.json \
  --output /tmp/rg-all-species-sol-report.json
PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest tests.test_trait_coverage_audit -v
git diff --check
```

| 검증 | 실행 범위 | 실제 결과 |
|---|---|---|
| 실 TEST DB 감사 | PostgreSQL 활성 원기록, Neo4j 전체 활성 species·claims·candidates | 완료; 위 실측 수치/JSON 참조 |
| 전체 read_traits replay | 11,131종의 실제 DB rows + 배포 함수 | 오류 0 / LIMIT 해당종 0 |
| 실 HTTP API | 7개 요청(6개 학명+까치 국명) | HTTP 200 7개; profile 검토 overlay 차이만 있음 |
| 오프라인 unit tests | tests.test_trait_coverage_audit 12개 | 통과 12 / 실패 0 / 건너뜀 0; 모의 입력 검증이며 DB/API 실검증 아님 |
| git diff --check | 작업 diff 공백 검증 | exit 0; 신규 untracked 파일은 이 명령만으로 모두 검증되지 않음 |
| collector syntax | 실제 원격 실행 문자열 compile | 통과 |
| 전체 저장소 suite | 배정 영역 밖 변경 없이 제한 감사 작업 | 미실행; 기존 runtime 수정 없음 |
| commit/deploy | 이번 작업은 감사 전용 | 미실행 |

## 남은 한계와 후속 결정

- 이 도구의 원본→대상 연결 판정은 현행 ingest의 고유 정확학명 규칙을 재현한 것이다. 학명이 같아도 분류개념이 광의일 수 있으므로 정상 반환과 개념 적합성은 별개다. Claude의 Avibase/교차표 검증을 후속 복구의 허용 목록으로 사용해야 한다.
- 각 현재 종의 정확학명 원본행 부재를 모두 신규 원자료 미존재로 분류하지 않는다. Elton 2,241·AVONET 1,130 기존값 후보와 현재 종 개념의 적합한 1:1 관계를 검토해야 한다. 별도 담당자의 복구가능 후보 수량을 이 DB 실측 수치로 둔갑시키지 않는다.
- Neo4j/PostgreSQL/HTTP는 같은 시점의 단일 분산 snapshot이 아니다. 조회 동안 활성 릴리스/데이터가 변할 가능성을 완전히 배제하지 않는다. 이번 수치는 기록된 활성 context와 체크섬에 대한 관측이다.
- 전체 종 API HTTP 테스트는 하지 않았고 reader replay만 전수 수행했다. API의 검토 overlay는 표본 범위만 확인했다.
- 실 DB/claim 값 보존이 원문 연구의 지역·표본·분류개념 범위를 검증해주지는 않는다. 특히 분할 전 Pica pica를 Pica serica에 자동 상속하면 안 된다.
- 후보 JSON에 완전한 원값·source record·릴리스 근거가 보존됨이 확인되면 재수집보다 기존 허용 후보의 공통 연결 복구가 타당하다. 기존 exact-match 대상과 충돌하거나 1:다·다:1인 후보는 자동 복구 대상에서 제외해야 한다. 확정 수정/적재/조회 구현은 후속 배정 사항이다. 사용자의 필요시 n8n 수집 허용 지시는 전달받았지만 이번 감사에서는 기존 후보 원값이 완전히 보존되어 있어 n8n 재수집/워크플로 실행·변경이 필요하지 않았고 실행하지 않았다.

실측 기준 시간(UTC): 2026-10-09T08:23:15.529849+00:00. 최초 전수 감사에 이어 후보값 보존 분류를 추가하고 실 TEST 감사를 재실행했다. 최종 JSON·표·후보 보존 수치는 이 마지막 실행 결과이며 12개 오프라인 테스트는 최종 코드에서 통과했다.
