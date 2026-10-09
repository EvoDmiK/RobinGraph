# 종 설명과 아종군 참고 자료 분리 (2026-10-09)

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
