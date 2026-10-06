# 2026-10-06 아종 목록 카드와 출처 확인 표시명

## 1. 요청 배경과 작업 범위

사용자는 `추가 정보 → 이 종의 아종 살펴보기`를 연 화면을 제시했다. 화면에는 긴 학명 버튼과 `AviList global avian checklist` 링크가 한 줄에 붙어 있었으며, 아종 이름도 학명 위주였다. 요청은 목록을 보기 좋게 정리하고, 주요 이름에 한국어 이름 또는 영어 이름을 쓰는 것이다.

이번 작업에서는 아종 목록을 카드로 나누고 이름·분포·보기 버튼·접힌 학명 및 출처를 구분했다. 한국어 이름이 확인되지 않은 청둥오리 두 아종에는 기관 자료에서 확인한 영어 이름을 사용한다. 부모 종의 국명을 아종의 새 국명으로 만들지 않는다.

실제 분류 연결, 학명에 따른 자료 조회, 부모·아종 taxon ID와 활성 분류판 확인은 유지한다. 근연 관계의 가중치와 생태 후보 정렬은 변경 대상이 아니다.

## 2. 변경 전 문제와 원인

기존 목록은 각 아종을 일반 HTML 버튼 하나로 만들었다. 버튼 안에 `청둥오리의 아종 · Anas platyrhynchos conboschas · 아종 자료 보기`처럼 이름·학명·동작을 모두 이어 붙였다. 분류 출처 링크도 별도 문단 없이 버튼 목록 앞에 삽입했다.

`styles.css`에는 아종 버튼의 작은 margin만 정의돼 있었고, 다른 비교 후보에 적용하던 카드 배치·색상·테두리를 사용하지 않았다. 이 때문에 출처와 버튼이 붙어 보이고 긴 학명이 목록의 중심이 됐다.

실제 활성 아종 데이터의 한국어 이름과 영어 이름도 비어 있었다. 앞선 작업에서 소속 종을 한국어로 설명했지만, 아종 자체의 별도 표시 이름을 확인해 넣는 처리는 없었다.

## 3. 이름 조사와 적용 기준

### 3.1 출처에서 확인한 이름

| 활성 taxon ID | 학명 | 표시할 영어 이름 | 확인 자료 |
| --- | --- | --- | --- |
| `avilist-taxon:v2025b:546` | Anas platyrhynchos conboschas | Greenland Mallard | Dansk Ornitologisk Forening의 2019 세계 조류 이름 자료 |
| `avilist-taxon:v2025b:545` | Anas platyrhynchos platyrhynchos | Northern Mallard | NCBI Taxonomy ID 8840의 common name |

영어 이름 자료:

- [Dansk Ornitologisk Forening · Names of the birds of the World (2019)](https://www.dof.dk/images/organisationen/publikationer/Navne_pa_alverdens_fugle-til_DOF2019.pdf)
- [NCBI Taxonomy · Anas platyrhynchos platyrhynchos (8840)](https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id=8840)

NCBI 페이지에는 GenBank 이름으로 common mallard, 다른 common name으로 northern mallard가 기록돼 있다. 이 자료는 표시 이름 참고에 사용하고, 아종의 채택 여부나 부모 관계를 결정하는 분류 근거로 사용하지 않는다. 서비스의 분류 연결은 기존 AviList 그래프에서 확인한다.

### 3.2 이름을 적용하는 조건

`taxonomy_lineage.py`에 위 두 taxon ID의 학명·영어 이름·출처 제목·출처 URL을 보존했다. 공통 표시 함수에서 아종의 taxon ID와 학명이 모두 맞는 경우에만 이름을 보충한다.

이미 활성 데이터에 다른 영어 이름이 있으면 그 이름을 덮어쓰지 않는다. 한국어 이름이 있으면 기존 `speciesLabel()`의 한국어 우선 표시를 유지한다. 검증된 이름이 전혀 없는 다른 아종은 목록 제목을 `아종 1 · 이름 미등록`처럼 표시하고 실제 학명은 상세 정보에 남긴다. 이 번호는 목록 식별용이며 국명이나 영어 이름이 아니다.

추가 필드 `english_name_source_url`과 `english_name_source_title`을 통해 이름 참고 출처를 전달한다. 목록과 도감 프로필이 같은 표시 함수와 참고 기록을 사용해 동일한 이름을 보여주도록 했다.

## 4. 화면 변경 전후

### 4.1 아종 목록

기존:

- 출처 링크와 긴 학명 버튼이 같은 흐름에 배치.
- 학명이 버튼의 중심 이름.
- 이름·설명·학명·동작이 하나의 긴 문자열로 표시.

변경 후:

- `이 종의 아종 살펴보기`를 전체 폭의 둥근 토글 버튼으로 표시.
- `아종의 이름과 분포를 살펴보세요.`라는 짧은 안내.
- `분류 기준 · AviList` 링크를 별도 문단으로 표시.
- 아종마다 별도 카드에 대표 이름, 한국어 분포 설명, `아종 보기` 버튼 배치.
- 학명과 영어 이름 참고 출처는 기본적으로 접힌 `학명·출처` 안에 표시.
- 토글을 접으면 내용과 안내 문구도 함께 숨김.

청둥오리 목록 예시:

| 대표 이름 | 한국어 설명 | 동작 |
| --- | --- | --- |
| Greenland Mallard | 그린란드 남서부 해안에 분포하는 아종입니다. | 아종 보기 |
| Northern Mallard | 북반구의 넓은 지역에서 번식하고, 겨울에는 더 남쪽 지역으로 이동하는 아종입니다. | 아종 보기 |

위 분포 설명은 기존 AviList 원문과 검토된 한국어 요약을 재사용했다. 활성 concept set이 지정된 v2025b이고 실제 range 원문도 검토 당시 값과 일치하는 경우에만 목록에 요약을 추가한다. 원문이 바뀌면 기존 요약을 계속 보여주지 않는다.

### 4.2 데스크톱과 좁은 화면

기존 비교 후보 카드의 `buildComparisonPeer()`와 `.comparison-peer` 스타일을 재사용했다. 별도 디자인 시스템이나 의존성을 추가하지 않았다.

데스크톱에서는 이름과 분포 설명이 왼쪽, 보기 버튼이 오른쪽에 배치된다. 420px 이하에서는 버튼을 이름·설명 아래의 전체 폭으로 배치한다. 배경·글자·테두리는 기존 테마 변수를 사용하며 이름을 강제로 대문자로 바꾸지 않는다.

키보드 포커스, 최소 버튼 높이, `aria-expanded`, 종 이름을 포함한 버튼 `aria-label`을 유지·보완했다. 기존처럼 사용자 제공 문구를 HTML로 해석하지 않고 DOM의 `textContent`를 사용한다.

### 4.3 도감 카드

아종 자료를 열었을 때도 같은 영어 이름이 제목에 사용된다. 학명은 식별 정보로 유지한다. 카드의 `분류·아종 설명 출처`에는 분류 출처와 영어 이름 출처를 함께 제공한다.

아종 자체의 형질·사진·멸종위기 자료와 부모 종의 참고 자료를 분리하는 기존 동작을 유지했다. 부모 종의 이름이나 수치를 아종의 고유 자료로 복사하지 않는다.

## 5. 변경 파일

| 파일 | 변경 내용 |
| --- | --- |
| `src/robingraph/retrieval/taxonomy_lineage.py` | 출처 확인 영어 이름 2개와 정확한 아종 식별에 따른 표시 이름 보충 |
| `src/robingraph/retrieval/subspecies.py` | 목록에 영어 이름 출처와 검토된 한국어 분포 요약 전달, 대표 이름으로 아종 설명 작성 |
| `src/robingraph/retrieval/species_profile.py` | 아종 프로필의 이름·참고 출처를 목록과 동일하게 보충 |
| `src/robingraph/api/static/chat.js` | 아종 카드 목록, 접힌 학명·출처, 보기 버튼, 토글 상태와 카드 이름 출처 |
| `src/robingraph/api/static/styles.css` | 토글·안내·카드·버튼·좁은 화면 배치와 기존 테마 적용 |
| `tests/test_subspecies.py` | 이름 출처·식별 변경 거부·기존 이름 보존·목록/프로필 일치 검증 |
| `tests/frontend/chat_ui.test.js` | 카드 이름·분포·접힌 학명·접근성·토글·분류판 변경 거부 검증 |
| `docs/verification/assets/2026-10-06-subspecies-*.png` | 실제 브라우저 컴포넌트 렌더링 검증 이미지 |

## 6. 검증 범위와 실제 결과

### 6.1 Python 전체 실행

```sh
uv run --locked --extra test --extra tracing python -m unittest discover -s tests -v
```

실제 결과: **551개 검색, 519개 통과, 실패 0, 오류 0, 건너뛰기 32개**. 이 실행에서는 DB 통합 실행 스위치를 켜지 않았다. 이 결과를 551개 전체 통과로 기록하지 않는다. 이전 작업에서 실행한 모든 DB 통합 테스트의 결과도 이번 변경의 재실행 결과로 사용하지 않는다.

### 6.2 아종 관련 테스트

```sh
uv run --locked --extra test --extra tracing \
  python -m unittest discover -s tests -p test_subspecies.py -v
```

결과: **6개 실행, 6개 통과, 건너뛰기 0**.

확인 사항:

- 두 영어 이름이 정확한 taxon ID·학명에서만 적용됨.
- 학명이나 taxon ID가 다르면 이름을 보충하지 않음.
- 기존 출처 영어 이름을 덮어쓰지 않음.
- 목록과 프로필의 영어 이름·이름 출처가 일치함.
- 실제 아종 부모 연결·활성 분류판·출처 검증 유지.
- 부모 형질·사진·위험 등급을 아종 자체의 정보로 상속하지 않음.
- 사진 조회는 계속 정확한 아종 학명과 아종 rank를 사용함.

### 6.3 프런트엔드 전체

```sh
node --test tests/frontend/*.test.js
```

결과: **128개 실행, 128개 통과, 건너뛰기 0**.

카드의 대표 이름과 분포 설명, 기본적으로 접힌 학명, 보기 버튼의 이름별 접근성 라벨, 토글의 펼침·접힘 상태, 늦게 도착한 응답과 다른 분류판 응답의 거부를 확인했다.

### 6.4 실제 NAS DB 읽기 검증

기존 NAS TEST PostgreSQL의 활성 분류 컨텍스트와 Neo4j 그래프를 읽어 수정한 `subspecies_for()`를 실행했다. 청둥오리의 두 아종이 Greenland Mallard와 Northern Mallard로 반환되고, 각 항목에 영어 이름 출처와 검토된 한국어 분포 설명이 있는 것을 확인했다.

이 검증은 읽기 작업이다. 서비스 DB에 새 이름을 적재하거나 기존 자료를 삭제하지 않았다. 임시 로컬 인증 설정 파일은 검증 후 제거했다.

### 6.5 실제 브라우저 레이아웃 확인

수정된 실제 `chat.js`와 `styles.css`를 사용해 독립 아종 컴포넌트를 로컬 HTML에서 렌더링했다. 목록 데이터는 실제 확인한 두 아종과 동일한 이름·설명·식별 정보를 넣은 검증용 응답이다. 따라서 이 이미지는 실제 브라우저의 컴포넌트 렌더링 검증이며 공개 서비스 화면을 직접 클릭한 캡처는 아니다.

설치된 Chrome을 별도 임시 프로필로 실행했다. 900×650 데스크톱과 390×900 화면을 확인했다. 390px에서는 문서의 가로 스크롤 폭도 390px임을 확인하여 수평 넘침이 없는 것을 검증했다. 좁은 화면에서 버튼이 아래로 배치되는 것도 확인했다. 검증용 브라우저 프로세스는 종료했다.

- [데스크톱 렌더링](assets/2026-10-06-subspecies-desktop.png)
- [390px 화면 렌더링](assets/2026-10-06-subspecies-mobile.png)

### 6.6 저장소 확인

`git diff --check`를 통과했고 코드 변경 후 `graphify update .`로 AST 그래프를 갱신했다. SQL 파서 누락 안내는 기존 환경의 경고이며 이번 구현 변경 파일은 Python·JavaScript·CSS다.

## 7. 남은 한계와 적용 범위

- 이번에 기관 자료에서 확인해 보충한 아종 영어 이름은 청둥오리의 두 아종이다. 전 세계 모든 아종의 일반 이름 수집을 완료한 것은 아니다.
- 확인된 한국어 이름이 없으면 영어를 사용한다. 한국어 번역 이름을 임의로 만들어 표준 국명처럼 표시하지 않는다.
- 영어 이름도 확인하지 못한 다른 아종은 이름 미등록 표시와 접힌 학명으로 구분한다.
- 영어 이름 참고 자료는 분류판 자체를 교체하는 근거가 아니다. 아종의 채택·부모 연결은 계속 활성 AviList 그래프를 따른다.
- 검증된 분포 요약 외에 외형 차이를 추정해서 추가하지 않았다.
- 명칭 보충은 앱의 표시 자료이며 그래프의 새로운 검색 별칭으로 적재하지 않았다. 실제 선택과 사진 조회는 학명·taxon ID로 수행한다.

## 8. 배포 기록

### 8.1 커밋과 산출물

- Runtime commit: `5942bce546a485b868f255028bb85c5aa7d2afe9`.
- `origin/dev` push 완료.
- NAS 릴리스 디렉터리: `/home/kimdove/RobinGraph-subspecies-5942bce`.
- TEST image: `robingraph-api:test-subspecies-5942bce`.
- TEST 컨테이너: `robingraph-api-test`, 상태 healthy.
- Archive SHA-256: `589b9661ee7779ce9c5567d894bcd28802a7eef512ce33f08b301b5053f187dc`.

커밋된 파일에서 배포 archive를 생성하고 NAS에 전송했다. archive 해시와 내장 manifest를 검증한 뒤 기존 TEST 환경 설정을 복사하고 이미지 및 VCS revision을 새 릴리스로 설정했다. 인증 값은 문서와 git에 포함하지 않았다.

### 8.2 배포 명령과 상태

NAS 릴리스 디렉터리에서 다음 명령을 실행했다.

```sh
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh update
ROBINGRAPH_DEPLOY_TARGET=test sh scripts/deploy_nas.sh verify
```

배포 도구의 사전 확인을 거쳐 TEST 이미지를 빌드하고 컨테이너를 교체했다. 이미지 OCI revision이 runtime commit과 일치한다. PROD는 기존 `robingraph-api:prod-local` 이미지를 유지했고 healthy 상태를 확인했다. 서비스 DB 적재·삭제와 PROD 재배포는 하지 않았다.

### 8.3 공개 서비스 확인

대상: https://robingraph-test.dove-nest.com

- `/v1/taxa/subspecies`에서 청둥오리의 두 아종이 Greenland Mallard와 Northern Mallard로 반환된다.
- 각 목록 항목에 한국어 분포 설명과 영어 이름 출처 URL이 있다.
- 두 아종 각각의 `/v1/taxa/profile`에서 목록과 같은 taxon ID·영어 이름·이름 출처 URL을 확인했다.
- 공개 `/static/chat.js`와 `/static/styles.css`의 SHA-256이 커밋된 파일과 일치한다.

배포 계약 검증:

```sh
uv run --locked --extra test --extra tracing \
  python scripts/verify_api_deployment.py \
  --base-url https://robingraph-test.dove-nest.com --json
```

결과: **passed=true**. 브라우저의 컴포넌트 레이아웃 검증과 공개 API·정적 파일 검증을 구분해 기록했다.

## 9. 문서와 후속 관리

이 문서는 Obsidian `Work/RobinGraph/2026-10-06-아종목록-카드디자인-영어표시명-NAS배포.md`에도 상세 내용으로 기록한다. Obsidian에서는 렌더링 이미지 링크를 저장소의 이미지 경로로 연결한다. 향후 다른 아종의 이름을 추가할 때도 정확한 식별 정보와 확인 자료를 보존하고, 국명과 임의 번역을 구분한다.
