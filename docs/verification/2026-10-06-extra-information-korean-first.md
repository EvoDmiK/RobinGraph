# 2026-10-06 추가 정보 한국어 우선 표시 · 구현 및 NAS TEST 배포

## 1. 요청 배경과 목표

사용자는 새 이름을 한국 도감과 확인 가능한 국명 자료에 따라 표시하고, 한국어 이름을 확인하지 못한 종은 영어로 남기기를 요청했다. 이어서 답변의 `추가 정보` 토글을 열었을 때 나오는 정보도 한국어를 우선하도록 요청했다.

이번 작업의 범위는 다음 세 항목이다.

1. 같은 서식 환경·먹이 생태의 새 살펴보기: 국명이 확인된 후보를 먼저 선택하고 한국어 이름으로 표시한다.
2. 이 종의 아종 살펴보기: 아종 자체의 국명이 없더라도 한국어로 소속 종을 안내한다.
3. 통칭·가축형 관계 알아보기: 관계 제목과 관련 종의 이름을 한국어 우선으로 표시하고 중복 영문명을 줄인다.

근연 관계 가중합 점수와 TOP3 정렬 규칙은 이번 변경 대상이 아니다. 검증되지 않은 번역을 추가하거나, 서로 다른 종을 같은 국명으로 합치는 작업도 포함하지 않는다.

## 2. 확인한 문제와 원인

### 2.1 생태 후보를 먼저 제한한 뒤 국명을 교정하던 순서

기존 `ecological_relations.py`의 `PEERS_QUERY`는 Neo4j의 한국어 이름을 기준으로 후보를 정렬하고 `LIMIT 4`를 적용했다. 반환된 후보에 Python의 `with_korean_display_name()`을 적용해 검증된 국명으로 다시 표시한 뒤 처음 3종을 노출했다.

그래프에 한국어 이름이 있더라도 별도 국명 표에서 확인하지 못하면 표시 단계에서 영어로 바뀐다. 반대로 국명 표에 한국어 이름이 있는 종이 처음 4개 후보에 포함되지 않으면 표시 단계에서 그 종을 다시 선택할 수 없다. 따라서 화면의 이름 선택은 한국어 우선이었지만 후보 선택은 검증된 국명 우선이 아니었다.

배포 전 실제 청둥오리 API 응답에서 확인한 사례는 다음과 같다.

| 항목 | 기존 후보 표시 |
| --- | --- |
| 같은 서식 환경 | Great Reed Warbler → 개구리매 → 검둥오리사촌 |
| 같은 먹이 생태 | Black-headed Duck → 고니 → 고방오리 |

첫 후보의 한국어 이름이 확인되지 않아 영어로 표시되면서, 한국어 이름이 있는 후보가 뒤로 밀렸다.

### 2.2 관계 목록의 중복 이름과 학명 제목

`chat.js`의 `nameRelationTaxonLabel()`은 한국어 이름·영어 이름·학명을 모두 이어 붙였다. 청둥오리의 경우 `청둥오리 · Mallard · Anas platyrhynchos`로 표시됐다.

또한 종의 학명으로 통칭·가축형 관계를 조회하면 제목에도 조회 학명이 그대로 쓰였다. 한국어 이름이 확인된 종에서도 학명이 제목의 주요 이름으로 보일 수 있었다.

### 2.3 국명이 없는 아종의 선택 안내

청둥오리의 아종 목록에서 확인한 두 항목은 자체 한국어 이름과 영어 이름이 모두 비어 있었다.

- `Anas platyrhynchos conboschas`
- `Anas platyrhynchos platyrhynchos`

학명은 식별에 필요하지만, 목록에 한국어 소속 종 안내를 붙이면 무엇의 아종인지 더 쉽게 이해할 수 있다. 부모 종의 국명을 아종 자체의 국명으로 옮겨 붙이는 방식은 사용하지 않았다.

## 3. 구현 변경

### 3.1 생태 관계: 국명 검증을 후보 제한보다 먼저 수행

변경 파일: `src/robingraph/retrieval/ecological_relations.py`.

기존 검증 국명 파일 `species_ko_names.json`을 읽는 `sourced_korean_names()`를 재사용한다. 종별 taxon ID를 키로 하고 국명·학명·영어 이름만 담은 참조 맵을 Cypher에 전달한다. 새로운 외부 데이터 수집이나 n8n 워크플로 생성은 하지 않았다.

Cypher에서 후보의 taxon ID로 참조 기록을 찾고, 다음 조건을 모두 확인한 경우에만 정렬용 한국어 이름을 부여한다.

- 후보의 학명이 국명 기록의 학명과 정확히 일치한다.
- 활성 그래프의 출처 우선 영어 이름이 국명 기록의 영어 이름과 정확히 일치한다.

그다음 검증된 한국어 이름이 있는 후보를 먼저 정렬한다. 한국어 후보끼리는 국명순, 그 밖의 후보는 영어 이름 또는 학명순으로 정렬하고 taxon ID로 동점을 해소한다. 이 정렬 이후 `LIMIT 4`를 적용한다.

Python에서도 `with_korean_display_name()`을 다시 적용하여 기존 표시 이름 검증을 유지하고, 한국어 이름 우선으로 정렬한 뒤 3종을 반환한다. 네 번째 후보는 `has_more` 판단에 사용한다.

기존 조회 보호 조건은 유지한다. 활성 개념집합·분류판, 종 수준 대상, 허용된 정책, 추론하지 않은 형질, 동일 자료·릴리스, 원본 및 후보 양쪽의 근거 기록, 안전한 출처 URL을 계속 확인한다. 국명 우선 정렬을 위해 생태 근거가 없는 후보를 추가하지 않는다.

### 3.2 통칭·가축형 관계: 한국어 이름과 학명 중심으로 표시

변경 파일: `src/robingraph/api/static/chat.js`.

`nameRelationTaxonLabel()`에서 기존 `speciesLabel()`을 재사용한다. 이름 우선순위는 확인된 한국어 이름 → 영어 이름 → 학명이다. 대표 이름이 학명과 다를 때만 학명을 뒤에 붙인다.

예시 변경:

- 이전: `청둥오리 · Mallard · Anas platyrhynchos`
- 이후: `청둥오리 · Anas platyrhynchos`

학명으로 조회한 종의 관계 제목은 반환된 대상 중 학명이 조회어와 일치하는 종을 찾아 대표 이름으로 표시한다. 통칭 자체를 검색한 경우에는 입력한 통칭을 유지한다.

예시 변경:

- 이전: `‘Anas platyrhynchos’ 이름 관계`
- 이후: `‘청둥오리’ 이름 관계`

관련 종 선택, 가축형과 야생종의 구분 안내, 출처와 분류판 검증은 유지한다.

### 3.3 아종 목록: 한국어 소속 종 안내 추가

한국어 이름이 있는 부모 종의 아종 선택 버튼에는 소속 종 안내를 앞에 붙인다.

예시:

- `청둥오리의 아종 · Anas platyrhynchos conboschas · 아종 자료 보기`
- `청둥오리의 아종 · Anas platyrhynchos platyrhynchos · 아종 자료 보기`

아종 자체의 이름이 있으면 기존 대표 이름 우선순위로 표시한다. 부모 종의 한국어 이름을 아종의 `korean_name` 필드에 저장하지 않는다. 아종 조회·선택은 계속 실제 학명과 taxon ID를 사용한다.

## 4. 한국어 이름 적용 기준과 종 구분

이번 작업은 기존에 검증된 국명을 더 먼저 보여주는 변경이며, 국명 표에 새로운 이름을 추가하지 않았다.

개개비와 Great Reed Warbler는 다음 구분을 유지했다.

| 영어 이름 | 현재 학명 | 한국어 표시 |
| --- | --- | --- |
| Oriental Reed Warbler | Acrocephalus orientalis | 개개비 |
| Great Reed Warbler | Acrocephalus arundinaceus | 영어 유지 |

가까운 계통에 속한다는 이유만으로 같은 국명을 붙이지 않는다. 옛 분류명과 현재 종 사이의 검색 연결 기능은 이번 작업에 추가하지 않았다.

기존 국명 표는 한국조류학회 목록을 우선하고 별도로 확인된 참고 자료의 이름을 사용한다. 이름 확인 기준과 출처는 `docs/korean-display-names.md`, 실제 기록은 `src/robingraph/retrieval/species_ko_names.json`에 있다.

## 5. 변경 파일

| 파일 | 변경 내용 |
| --- | --- |
| `src/robingraph/retrieval/ecological_relations.py` | 검증 국명 참조 맵 전달, 후보 제한 전 한국어 우선 Cypher 정렬, 반환 목록 정렬 |
| `src/robingraph/api/static/chat.js` | 대표 이름과 학명 표시, 한국어 관계 제목, 아종 소속 종 안내 |
| `tests/test_ecological_relations.py` | 검증 국명 우선 선택과 학명·영어 이름 불일치 처리 검증 추가 |
| `tests/frontend/chat_ui.test.js` | 중복 영어 이름 생략, 한국어 관계 제목, 아종 한국어 안내 검증 |
| `docs/verification/2026-10-06-extra-information-korean-first.md` | 구현 원인·변경·검증·배포 기록 |

## 6. 실행한 검증과 결과

### 6.1 Python 생태 관계 테스트

실행 명령:

```sh
uv run --locked --extra test --extra tracing \
  python -m unittest discover -s tests -p test_ecological_relations.py -v
```

결과: **6개 실행, 6개 통과, 실패 0, 오류 0, 건너뛰기 0**.

이번에 추가한 검증은 영어 이름의 후보 3개 뒤에 검증된 개개비 후보를 넣어도 개개비가 먼저 표시되는지 확인한다. 학명과 영어 이름이 바뀐 후보에는 기존 국명을 적용하지 않는 것도 확인한다. Cypher의 국명 정렬이 `LIMIT 4`보다 먼저 수행되는지, 참조 맵이 전달되는지 확인한다.

기존 테스트에서는 자료·릴리스 일치, 추론 형질 제외, 출처 URL 확인, 종 수준 대상 제한, 비활성 분류판 처리, 안전한 API 오류 응답을 계속 검증한다. 이 테스트 그룹은 모의 저장소를 사용한다.

이번 변경에 대해 전체 Python DB 통합 테스트를 다시 실행한 것은 아니다. 과거 작업의 전체 통과 수를 이번 변경의 재실행 결과로 표시하지 않는다. 변경한 실제 Cypher는 아래 NAS DB 읽기 검증으로 별도 확인했다.

### 6.2 프런트엔드 전체 검증

실행 명령:

```sh
node --test tests/frontend/*.test.js
```

결과: **127개 실행, 127개 통과, 실패 0, 건너뛰기 0**.

새로 추가하거나 보완한 검증:

- 학명 조회의 관계 제목이 `‘청둥오리’ 이름 관계`로 표시되는지 확인.
- 관련 종 이름에 한국어와 학명은 남고 중복 `Mallard`는 생략되는지 확인.
- 아종 버튼에 `청둥오리의 아종` 안내가 있는지 확인.
- 아종의 분류판이 바뀐 응답은 계속 거부되는지 확인.

프런트엔드 테스트는 Node와 가짜 DOM을 사용하는 계약 검증이다. 실제 브라우저에서 토글을 클릭한 시각적 검증으로 기록하지 않는다.

### 6.3 NAS 실제 TEST DB 읽기 검증

NAS TEST 환경의 기존 Neo4j와 PostgreSQL 설정을 사용해 수정한 `ecological_relations()`를 실행했다. 활성 PostgreSQL 분류 컨텍스트와 Neo4j 계통 조회를 사용했으며 서비스 데이터를 적재·삭제하지 않았다. 임시 로컬 인증 설정 파일은 검증 후 삭제했다.

청둥오리 기준 결과:

| 항목 | 수정 후 상위 3종 |
| --- | --- |
| 같은 서식 환경 | 가창오리 → 개개비 → 개구리매 |
| 같은 먹이 생태 | 가창오리 → 고니 → 고방오리 |

두 목록 모두 3종이 반환되고 각 후보의 한국어 이름이 확인됨을 검증했다.

### 6.4 저장소 확인

`git diff --check`를 통과했고 코드 변경 후 `graphify update .`를 실행했다. AST 그래프 갱신은 완료했다. graphify 실행 시 SQL 파서 의존성이 없어 SQL 파일 일부는 추출되지 않는 기존 안내가 있었으며 이번 변경 파일은 Python과 JavaScript다.

## 7. NAS TEST 배포와 공개 서비스 확인

### 7.1 커밋과 배포 산출물

- Runtime commit: `5906c10440af87f17e809b9dd66befb95678cbef`.
- 배포 검증 기록 commit: `34b2f0b`.
- 위 커밋들은 `origin/dev`에 push했다.
- NAS 릴리스 디렉터리: `/home/kimdove/RobinGraph-ko-extra-5906c10`.
- TEST 이미지: `robingraph-api:test-ko-extra-5906c10`.
- TEST 컨테이너: `robingraph-api-test`.
- Archive SHA-256: `65fc69d905306110c6025a2b1b4000d6a83aea9b897b79d0e2cdee1b96f628e6`.

커밋된 파일을 대상으로 `scripts/package_nas_release.sh`를 사용해 배포 archive를 만들었다. NAS에 전송한 뒤 archive 해시와 내장 manifest의 파일 해시를 확인했다. 기존 TEST 환경 파일을 복사하고 이미지 이름과 VCS revision만 이번 릴리스로 설정했다. 인증 값은 문서와 커밋에 포함하지 않았다.

### 7.2 배포 명령과 상태

NAS 릴리스 디렉터리에서 TEST 대상으로 다음 명령을 실행했다.

```sh
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh update
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh verify
```

배포 도구의 사전 확인을 거쳐 이미지를 빌드하고 TEST 컨테이너를 교체했다. TEST 컨테이너 상태는 healthy이고 이미지의 OCI revision은 runtime commit과 일치했다.

PROD 컨테이너는 기존 `robingraph-api:prod-local` 이미지를 유지했고 healthy 상태를 확인했다. PROD 재배포와 DB 변경은 하지 않았다.

### 7.3 공개 API와 프런트엔드 확인

대상 서비스: https://robingraph-test.dove-nest.com

배포 후 다음을 실제 HTTP 요청으로 확인했다.

- `/v1/taxa/ecological-related`의 청둥오리 응답에서 위의 국명 우선 후보 두 목록이 반환된다.
- `/v1/taxa/profile`에서 `Acrocephalus orientalis`는 개개비로, `Acrocephalus arundinaceus`는 한국어 이름 없이 영어로 유지된다.
- 공개 `/static/chat.js`의 SHA-256이 커밋된 프런트엔드 파일과 일치한다.

배포 계약 검증 명령:

```sh
uv run --locked --extra test --extra tracing \
  python scripts/verify_api_deployment.py \
  --base-url https://robingraph-test.dove-nest.com --json
```

결과: **passed=true**.

## 8. 남은 한계와 후속 사항

- 한국어 이름이 없는 종은 계속 영어로 표시한다. 이 작업을 전체 해외 종의 국명 수집 완료로 해석하지 않는다.
- 아종 자체의 국명을 새로 검증하거나 생성하지 않았다. 소속 종 안내와 학명으로 구분한다.
- 생태 목록의 한국어 우선 정렬은 가까운 계통의 순위가 아니다. 해당 자료에서 같은 생태 범주를 공유하는 후보의 표시 순서다.
- 근연 관계 가중합 TOP3에서는 점수순 정렬을 유지한다. 한국어 이름 유무로 점수나 순위를 바꾸지 않는다.
- 옛 이름 검색, 종 분할·통합 안내는 별도 검증과 구현이 필요한 후속 범위다.

## 9. 작업 문서 작성 기준 보강

이 문서는 사용자의 ‘작업 문서는 무조건 상세하게’ 요청에 따라 기존 짧은 기록을 확장했다. 동일한 상세 내용은 Obsidian의 `Work/RobinGraph/2026-10-06-추가정보-한국어우선-NAS배포.md`에 반영한다.

향후 문서에도 요청 배경, 원인과 근거, 변경 전후, 변경 파일, 실제 검증 범위와 결과, 배포·커밋 정보, 한계와 후속 사항을 기록하도록 프로젝트 `AGENTS.md`에 기준을 추가했다. 이번 문서 보강은 런타임 코드를 변경하지 않으므로 추가 서비스 배포가 필요하지 않다.
