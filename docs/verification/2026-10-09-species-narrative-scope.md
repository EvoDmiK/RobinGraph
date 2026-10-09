# 종 설명과 아종군 참고 자료 분리 (2026-10-09)

> 최종 정책 변경: 사용자의 추가 요청에 따라 종 프로필의 아종군 형질 fallback 자체를 제거했다. 아래 최초 토글 구현은 변경 이력이며 현재 종 응답에 `subspecies_groups` 섹션을 생성하지 않는다. 추가 수정으로 백과 `source_scope_notes` 섹션도 제거했다. 356종의 관계 자료 존재만으로 백과 설명을 분리하지 않으며 일반 종 설명은 원래 외관·재미있는 사실에 표시한다. 아래 절들은 시간순 변경 이력이고 최종 계약은 마지막 절을 따른다.

### 요청과 확인 원인

사용자는 외관·생활과 먹이 본문에 아종군별 숫자가 연속으로 섞이고, 같은 먹이 범주와 백과 설명이 반복되어 읽기 어려운 문제를 지적했다. `species_sections()`는 종 범위 형질에서는 아종군을 제외했지만, 이후 별도 루프에서 그 아종군 값을 다시 기본·외관·생태 섹션에 삽입하고 있었다. `species_summary()`도 종 설명 뒤에 아종군 목록을 붙였다. 또한 Wikipedia 연결은 학명(P225), 종 계급, 단일 문서와 Wikidata ID, 고정 revision을 확인했으나 현재 AviList 종 개념 전체와 문서의 분류 범위가 같다는 근거는 없었다.

### 변경 내용과 API 계약

- `src/robingraph/retrieval/species_profile.py`: 종 설명과 기본 네 섹션에서는 종 범위 값만 사용한다. 아종군 값은 `sections[].key=subspecies_groups`, 제목 `아종군별 자료`, `collapsed=true`인 별도 섹션에 모두 보존한다. `description`에 종 전체 평균·공통 특징이 아니라는 안내를 한 번 넣는다. 각 item은 짧은 `text=label:value`, 원래 `source_scope`, `source_scope_kind`, 통계 종류, 추정 여부, 관계 근거·출처·라이선스 metadata를 보존한다. 임의 평균이나 대표 하위군 선택은 없다. 원래 `traits` 배열은 변경하지 않는다.
- 기존 `diet_category`가 있으면 `trophic_niche`를 일반 본문에 중복 노출하지 않는다. 백과 노트는 정규화한 같은 문장·같은 출처·같은 범위만 중복 제거한다. 출처나 범위가 다르면 제거하지 않는다.
- `src/robingraph/retrieval/species_notes.py`: 모든 백과 노트에 `source_scientific_name`, `source_scope`, `source_scope_kind=encyclopedia_taxon`, Wikidata ID와 `taxonomy_alignment.status=article_identity_only`를 추가한다. 이는 문서 식별 확인이며 종 개념 일치 확인이 아님을 `source_note`에 명시한다. 원문 revision·라이선스는 그대로 유지한다.
- 고정 eBird 관계 자료의 현재 종 356종(2개 이상 하위군 290종)은 필요한 형질이 모두 종 자료로 채워졌는지와 무관하게 범위 검토 대상으로 사용한다. 따라서 하위군 fallback 형질이 응답에 없다는 이유로 백과 범위 제한이 사라지지 않는다. 박새의 연결된 참고 하위군은 1개이므로 2개 이상 조건만 적용하면 누락되는 점도 방지했다.
- 위 대상의 백과 노트는 `source_scope_notes` 섹션으로 분리하고 `taxonomy_alignment.status=unverified`, `category`, `category_title`을 보존한다. 안내는 “이 설명은 출처가 다룬 분류 범위의 특징입니다. 현재 종 전체의 공통 특징으로 단정하지 않습니다.”이다. 기본 외관·재미있는 사실에 남는 항목 없이 참고 설명만 있다면 해당 빈 섹션을 생략하여 이미 있는 자료를 ‘찾지 못했다’고 표시하지 않는다. 완전히 자료가 없는 일반 종의 빈 상태는 유지한다.

### 검증과 범위

`tests/test_species_narrative_scope.py`를 추가하고 기존 아종군 테스트를 새 계약으로 수정했다. 고정 관계 자료의 전체 356종에 합성 백과 노트를 주입하여 일반 설명에서 제외되고 범위별 설명에 revision과 항목이 남는지 전수 구조 검증했다. 일반 대조 종, 같은 노트 중복, 복수 하위군 체중 보존, 추정값·출처 metadata 보존도 확인했다. 이것은 실제 원문 356종을 읽거나 LLM으로 재번역한 검증이 아니다.

실행: `PYTHONPATH=src ROBINGRAPH_TRAIT_RAW_DIR=/tmp/rg-trait503-raw /tmp/rg010-venv/bin/python -m unittest tests.test_species_narrative_scope tests.test_avonet_subgroups tests.test_species_profile tests.test_species_notes tests.test_avonet_ebird tests.test_birdbase_traits tests.test_trait_mapping tests.test_trait_crosswalk tests.test_ecological_relations tests.test_similar_species` — 122개 통과, 실패 0, 건너뛰기 0 (4.216초). 이후 중복 제거 키를 출처·범위까지 제한한 최종 변경과 생성 담당자의 추가 회귀를 포함한 집중 테스트 43개도 통과했다(실패 0, 건너뛰기 0, 0.198초). `git diff --check` 통과. 실제 HTTP·브라우저·배포 및 커밋은 통합 담당자가 별도로 검증하며 이 절에서는 완료로 주장하지 않는다.

### 한계

356은 이번에 확보한 고정 관계 자료가 입증하는 대상 수이며 전체 종의 모든 분류 변경을 포괄하는 수가 아니다. 일반 종의 백과 노트도 종 개념 전체 일치가 검증된 것으로 승격하지 않는다. 번역 품질 개선은 별도 생성 담당자의 원문 인용 검증·한국어 문장 처리와 함께 통합한다. 형질 원자료 수치나 관찰 사실은 이 변경에서 재작성하지 않았다.

박새의 형질·백과 범위 분리는 보전 평가의 종 개념 일치를 새로 입증하지 않는다. 현재 박새의 실제 평가 연결이 unknown인 상태를 이 작업이 LC 또는 검증 완료로 바꾸지 않는다. 보전 평가 상태는 별도 계약·근거에 따라 유지한다.

### 화면·한국어 생성 통합

`chat.js`는 일반 설명과 별도로 `subspecies_groups`, `source_scope_notes`를 기본 닫힌 HTML details로 렌더링한다. 같은 `source_scope`는 제목 하나 아래 모으고 범위 안내도 한 번만 표시한다. 기존 첫 네 section 제한 때문에 뒤의 새 섹션이 사라지지 않게 전체 section을 읽는다. 아종군의 자료 개수에는 일반 본문의 4~5개 표시 제한을 적용하지 않아 여러 군의 근거가 잘리지 않는다. 빈 참고 섹션은 생성하지 않는다. 원문·라이선스 링크는 기존 답변 출처 수집에 포함하며, 그룹 이름과 설명은 textContent로 출력한다. 카드 관찰 포인트는 분리된 참고 설명에서 가져오지 않는다. 토글 스타일은 `styles.css`에 추가했다.

`generation.py`는 외관 문장을 만들 때 원문 인용을 먼저 선정하고 성별·나이·계절·아종 범위를 유지하도록 지시한다. 검은 후드·뺨 패치·날개 바 같은 직역이 남으면 해당 항목만 한 번 자연스럽게 다시 쓰며, 인용·항목 순서·개수·수정 대상이 아닌 설명이 달라지면 거절한다. 인용이 실제 원문에 포함되는지는 검사하지만, 이것이 생물학적 분류 범위의 완전한 증명은 아니다. 백과 범위 분리를 별도로 유지하는 이유다. 요약 캐시는 프로세스 메모리에만 있고 API 재시작으로 초기화되므로 영구 캐시 이관은 수행하지 않았다.

최종 통합 로컬 검증은 Python 128개, 프런트 291개 모두 통과(실패·건너뛰기 0)했다. Python 최초 실행에서 존재하지 않는 `tests.test_generation` 이름을 지정해 수집 오류 1건이 났으나 실제 모듈 `tests.test_gemini_generation`으로 바로잡아 최종 실행했다. 위 담당자별 테스트와 중복되므로 합산하지 않는다. 356종 검증은 고정 관계 파일과 합성 설명을 사용하는 구조 검사다. `graphify update .` AST 갱신도 완료했다.

### 배포 검증

코드 커밋 `5acaf54696ce7d095a2cf3db7380e6c01f668573`. 배포 패키지 SHA-256 `b2d0bf74690f793a4f43f87aa74f72d60b1db224e358c951f230e8bb84ff09b3`. DB 형질·평가 자료를 변경하는 작업이 아니며 원래 값은 유지한다. 실제 환경 결과는 아래와 같다.


- TEST/Production 컨테이너 모두 `5acaf54` revision, 각각 `test-scope-5acaf54`/`prod-scope-5acaf54` 이미지이며 healthy 확인. TEST 이미지를 그대로 Production 태그로 승격했다. NAS 경로 `/home/kimdove/RobinGraph-scope-5acaf54`, 이전 운영 이미지 `prod-resolution-f70c997`는 롤백용으로 유지한다.
- 실제 HTTP 프로필 20건씩 양 환경 모두 통과. 기존 검증 스크립트로 국명·형질·평가 대표 사례가 그대로 유지되는지 확인했다. 이 20건은 노트 생성의 성공률 검사가 아니다.
- 실제 Chrome 1280px/390px에서 박새 질의 후 본문에 아종군 수치가 섞이지 않고 두 토글이 기본 닫힘이며 클릭 시 자료를 보여주는지 검증했다. 양 환경 각각 2건, 총 4건 최종 통과. 명시적 profile 의도이므로 Jev 자동분류 검증은 아니다.
- 배포 전후 실제 박새 응답의 traits 배열 및 conservation 객체는 동일했다. 아종군 형질 11항목이 전부 토글에 남았다.
- 운영에서 새로 생성된 외관: “이 새는 윗면이 회색이고 아랫면은 흰색이며, 검은색 머리와 뺨의 흰색 무늬, 날개의 흰색 띠가 특징입니다.” 본문 일반 사실로 승격하지 않고 출처 범위별 설명 안에 제공한다.
- 브라우저 최초 실행에서는 이미 모든 정보를 받은 명시적 profile 응답에도 `더 알아보기`가 있다고 테스트가 가정하여 실패했다. 일반/지연 흐름을 구분하도록 검사 스크립트를 수정했다.
- 운영 최초 박새 설명은 추가 자료 조회 경고로 참고 설명이 없어 브라우저 검사가 실패했다. 실제 재조회에서 경고 없이 노트가 생성됐고 최종 PC/모바일 검사가 통과했다. 프로필 오류 응답은 내부 예외 원인을 공개하지 않으므로 최초 실패를 특정 외부 장애나 인용 검증 실패로 단정하지 않는다. 외부 원문/생성 제공자의 가용성 및 생성 결과 검증에 따라 설명이 일시적으로 비어 있을 수 있다는 한계는 남는다.
- 검증 도구와 결과: `assets/2026-10-09-narrative-browser-check.cjs`, `assets/2026-10-09-narrative-runtime-checks.json`. 스크린샷은 로컬 `/tmp/rg-scope-browser-test`, `/tmp/rg-scope-browser-prod-final`에서 확인했고 저장소에 대량 추가하지 않았다.

이번 작업은 설명 구성·번역·범위 구분을 수정했다. 11,131종 DB를 다시 전수 조사하거나 356종 원문을 모두 새로 생성했다고 주장하지 않는다. 앞 작업의 전체 데이터 감사 결과와 이번 구조·대표 실환경 검증은 구분한다.


## 최종 수정: 종 프로필에서 아종군 형질 제외

### 배경과 변경 전후

사용자는 박새라는 종을 검색했는데 아종군 정보를 붙이는 것 자체가 원하지 않는 동작이라고 명확히 했다. 처음에는 별도 토글로 분리했지만 종 프로필에 하위군 값을 보충하는 정책이 남아 있었으므로 요구를 만족하지 못했다. 최종 변경에서는 해당 fallback을 런타임 경로에서 제거했다.

- `read_traits()`에서 `subgroup_traits()` 호출을 제거했다. 기존 종 범위의 DB 형질, AVONET 동일 개념 보완, BIRDBASE 문헌 자료와 종 생활 방식 검토 자료는 유지한다.
- 종 프로필 assemble 단계에서 외부 provider가 `source_scope_kind=subspecies_group` 형질을 주입하더라도 필터링한다. API `traits`, summary, sections 모두 같은 필터된 배열을 사용한다.
- `species_sections()`는 이제 `subspecies_groups` 섹션을 생성하지 않는다. 직접 전달된 아종군 수치도 기본 네 섹션에서 제외한다.
- 원자료 JSON, 관계 근거, 독립 추출 함수와 그 정확성 테스트는 감사·후속 연구를 위해 보존한다. 종 프로필의 보완값으로 사용하지 않는다.
- 백과 설명의 출처 범위를 제한하는 `source_scope_notes` 정책은 이번 변경에서 수정하지 않았다. 아종군 형질과 백과 설명의 분류 범위 검증은 별개다.

### 검증

고정 관계 자료의 전체 356종에 종 범위 habitat 하나와 해당 종의 모든 연결 아종군 mass를 함께 주입해 실제 LCEL `create_species_flow().invoke()` 경로를 실행했다. 종 형질은 유지되고 모든 subgroup 형질이 traits/summary/sections에서 제외되었다. 이는 외부 DB/API 호출을 대체하는 모의 provider 구조 전수 검증이다. 관련 37개 테스트 통과(실패 0, 건너뛰기 0, 0.546초). `git diff --check` 통과. 실제 배포·HTTP·브라우저 확인은 통합 담당자가 별도 기록한다.

### 종 범위 수정의 통합 검증 및 근거

코드 `48add3a9bb0d8a6f04b165a7ec1e56aaee6ddb28`은 종 조회에서 아종군 fallback 자체를 제거한다. API 조립 단계도 `source_scope_kind=subspecies_group`를 종 traits에서 제외하므로 카드뿐 아니라 종 비교·요약에 다시 흘러가지 않는다. 프런트는 이전 응답이 입력되더라도 아종군 카드값·비교값·`subspecies_groups` 섹션을 거절한다. 자료를 종 정보로 자동 보충하지 않는 정책이며, 원본 추출 파일과 관계 근거를 삭제한 것은 아니다.

최종 Python 129개와 프런트 291개 통과(실패·건너뛰기 0), 고정 관계 파일의 전체 356종에 종 형질과 하위군 형질을 함께 주입한 구조 검증도 통과했다. 이 숫자는 실제 356종의 HTTP 전수 호출이나 원문 전체 검토 수가 아니다.

독립 검토에서 BIRDBASE Data!row7501의 학명은 AviList·IOC·Clements 대응 열 모두 Parus cinereus로 확인됐다. 16.55g은 문헌 최소11g·최대22.1g의 범위값 평균이며 한국 개체를 측정한 표본 평균이라고 표현하지 않는다. 숲·무척추동물은 주요 서식지·먹이 범주다. 이 종 수준 원자료는 유지하고, AVONET 일부 아종군의 10.6/63.1/57.9mm 등을 종 값으로 보충하던 경로만 제거했다. 개별 원문 BOTW의 모든 표본 범위까지 독립 검증한 것은 아니다.

Wikipedia 고정 revision1379211352는 taxonomy에 minor도 포함한다. 따라서 아종군 연결이 있는356종이라는 사실만으로 백과 문서의 범위가 현재종과 반드시 다르다고 확정할 수 없다. 기존 `source_scope_notes`는 검토 전 참고 설명이며 실제 불일치 판정이 아니다. 개별 문장은 과거 문헌·특정 지역/아종 내용이 섞일 수 있어 모든 설명을 종 전체 사실로 승격하지 않는다. 이번 변경에서 보전 평가를 임의 확정하거나 학명·국명을 바꾸지 않았다.

배포 패키지 SHA-256: `08fc42e2b93e5f7dd7662053477ce27226fcf926791f0f5c41f11158c5718de2`. NAS 배포 결과는 아래에 실제 실행 결과로 기록한다.


최종 배포: NAS TEST/Production 모두 `48add3a` revision healthy. TEST는 `robingraph-api:test-species-only-48add3a`, 운영은 검증한 동일 이미지에 태그를 붙인 `robingraph-api:prod-species-only-48add3a`다. 이전 `prod-scope-5acaf54`는 롤백용으로 남겼다. DB 변경은 없었다.

실제 HTTP 프로필 20건씩 양 환경 모두 통과했다. 실제 Chrome에서 박새 질문을 PC1280px·모바일390px로 실행해 양 환경 각2건 모두 통과했다. 응답 traits는 `body_mass, habitat, diet_category` 3개이며 아종군11개는 더 이상 전달되지 않는다. 본문·카드에서 10.6/63.1/57.9mm와 아종군 토글이 나오지 않으며 체중16.55g은 유지된다. 백과 참고 설명은 별도 범위 정책을 유지한다. 테스트는 명시적 profile 의도로 실행했으므로 자동 의도분류의 추가 검증으로 해석하지 않는다.

재현 도구 `assets/2026-10-09-species-only-browser.cjs`, 증거 `assets/2026-10-09-species-only-runtime-checks.json`. 기존 narrative-browser 검증은 앞선 토글 구현의 역사적 증거이며 최종 동작은 species-only 검증을 기준으로 한다. 작업 문서의 최종 정책을 Obsidian 동일 문서에도 반영한다.


## 최종 백과 설명 수정: 근거 없는 일괄 범위 제한 제거

### 원인과 결정

아종군 관계가 있는 356종이라는 사실은 백과 문서의 설명 범위가 현재 종과 다르다는 증거가 아니다. 이전 구현은 관계 자료가 존재한다는 이유만으로 그 종의 모든 Wikipedia 노트를 `unverified`로 바꾸고 별도 토글에 옮겼다. 그 결과 사용자가 요청한 종 설명은 비어 보이고 경고와 출처 범위별 설명이 본문을 대신했다. 이 일괄 휴리스틱은 삭제했다.

### 현재 계약

- `article_identity_only`인 일반 백과 설명은 원래 `appearance`와 `fun_facts` 항목에 표시한다. source_scientific_name, revision, 라이선스, source_note, taxonomy_alignment 상태를 보존하며 상태를 임의 `unverified`로 바꾸지 않는다.
- `source_scope_kind=subspecies_group` 또는 실제 `taxonomy_alignment.status=unverified`인 항목만 별도로 취급한다. 명시적 `source_scope`가 있으면 `범위명: 원래 문장`으로 한정하여 원래 섹션에 표시한다. 범위가 없으면 임의로 현재 종 이름을 채워 넣지 않고 본문에 일반 사실로 표시하지 않는다.
- `profile.note_evidence` 배열에는 원래 appearance/fun_facts 항목을 보존한다. 본문에서 제외된 범위 불명 항목도 원문 출처와 상태를 잃지 않는다. UI는 해당 근거를 기존 답변 출처에 포함하며 새로운 본문 토글은 만들지 않는다.
- `source_scope_notes` 섹션은 더 이상 생성하지 않는다. 종 traits의 아종군 fallback 제거 및 assemble 필터는 그대로 유지한다. 알 수 없는 IUCN 상태를 새 등급으로 추정하는 변경은 없다.

### 검증

고정 관계 자료의 356종 모두에서 일반 백과 노트가 기본 네 섹션에 남고 article_identity_only와 revision이 보존되는 구조 회귀를 실행했다. 실제 범위 지정 노트의 접두사, 범위 불명 노트의 본문 제외·note_evidence 원본 보존, 아종군 형질 제외를 함께 검증했다. 집중 45개 테스트 통과(실패 0, 건너뛰기 0, 0.508초), git diff --check 통과. 외부 원문 356개를 실제로 새로 조회한 검증은 아니며 HTTP·브라우저·배포 결과는 통합 담당 기록을 따른다.

### 사용자 화면의 검토 문구 제거

`chat.js`에서 참고 평가도 연결되지 않은 AviList NE 상태는 빈 배지 문구로 처리하고, 등급이 없는 배지는 카드·본문에서 숨긴다. CSS의 inline-flex 표시가 hidden을 덮어쓰지 않도록 명시적으로 `[hidden]` 규칙을 둔다. 새 LC/NE 등급을 만들어 넣는 변경이 아니며 기존 평가 객체와 카드의 중립색은 그대로다. 실제 등급이 연결된 배지의 내용·색상은 유지한다. 평가가 연결되지 않은 이유는 기존 `답변 출처 보기` 안의 보전 출처 설명에 남는다.

기존 응답에 `source_scope_notes`가 들어오더라도 별도 토글 제목을 노출하지 않고 category에 맞는 외관/재미있는 사실 섹션에 합친다. 새 API는 이 섹션을 생성하지 않는다. `note_evidence`와 본문 항목에서 모은 source_note는 답변 출처 안에서 중복 제거해 보여주며, 지연 조회에서도 note_evidence를 전달한다. 사용자가 읽는 본문을 내부 검토 문구로 대체하지 않는다.

최종 통합 Python130개/프런트292개 모두 통과(실패·건너뛰기0). 신규 프런트 테스트가 기본 정보 섹션 없는 fixture에서 brief 배지를 찾던 오류가 있어 실제 brief 컴포넌트를 직접 검사하도록 바로잡았다. 잘못된 테스트가 남은 커밋은 배포하지 않았고 수정 후 전체 통과한 `5fce6eb6578639c29414a6849c759e07f76c0828`로 배포했다. source graph는 AST 갱신했다.

배포 패키지 SHA-256 `3dc8e79ca32f61a4c40a7f41ec869fbada13573875c69e987703adca99f895bf`. TEST/Production 컨테이너는 각각 `test-readable-5fce6eb`/`prod-readable-5fce6eb`이며 같은 이미지를 승격했다. 두 컨테이너 healthy를 확인했다. 이전 운영 `prod-species-only-48add3a`는 유지하며 DB 수정은 없다.


실제 HTTP20건씩 TEST/Production 모두 통과했고, 실제 Chrome 박새 질문 PC1280px/모바일390px도 각 환경2건 최종 통과했다. 화면에서 `평가 범위 확인 필요`와 `출처 범위별 설명`이 보이지 않으며 외관 특징 항목이 본문에 존재하고 아종군 수치·섹션은 없다. 운영 최초 검사는 appearance 항목이 비어 실패했으나 실제 재조회에서 경고 없이2개 항목이 생성된 후 최종 PC/모바일 검사를 통과했다. 최초 설명 생성 실패의 내부 원인은 확인되지 않았으며 외부 자료·생성 의존에 따른 설명 누락 가능성을 해결했다고 주장하지 않는다.

검사 도구 `assets/2026-10-09-readable-answer-browser.cjs`, 실제 결과 `assets/2026-10-09-readable-answer-runtime.json`. 현재 문서의 이 최종 절이 이전 토글/경고 배지 정책을 대체한다. 자료 범위·평가 연결에 대한 내부 정보는 출처에서 확인 가능하고, 확인되지 않은 등급을 LC로 바꾸지 않았다. TEST 모바일 및 운영 화면 캡처를 실제로 확인했다. 이 검증은 전체 종의 설명을 새로 생성한 전수 검증이 아니다.
