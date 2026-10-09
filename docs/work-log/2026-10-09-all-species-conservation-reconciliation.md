# 전 11,131종 보전 등급 재검토·NE 표시 교정·출처 참고평가·TEST 배포

- 날짜: 2026-10-09
- 구현 커밋: `d4204bf5929459bce86dd07239a73f61037d31af`
- 감사 기준선: `0689001`
- 범위: 현재 AviList v2025b 활성 종 전체의 보전 등급 연결·응답·표시. 생물학적 위험도 재평가나 모든 형질의 사실 검증을 완료했다는 의미는 아니다.
- 결과: 전 종 감사 완료, 공통 처리 수정, 360개 참고평가 연결, NAS TEST 배포 및 공개 API·PC·모바일 검증 완료. PROD와 DB 원자료는 변경하지 않았다.

## 목차

1. [요청과 재현](#요청과-재현)
2. [원본과 실제 DB 대조](#원본과-실제-db-대조)
3. [전 종 감사 결과](#전-종-감사-결과)
4. [공통 구현과 변경 전후](#공통-구현과-변경-전후)
5. [변경 파일](#변경-파일)
6. [검증과 실제 결과](#검증과-실제-결과)
7. [배포와 복구](#배포와-복구)
8. [협업 검토](#협업-검토)
9. [증거와 재현](#증거와-재현)
10. [남은 한계와 후속 검토](#남은-한계와-후속-검토)

## 요청과 재현

사용자는 큰부리까마귀가 계속 NE로 나오는 문제를 제보하고 특정 종에 국한하지 말고 모든 종을 검토하라고 요청했다. 기존 형질 복구 작업과 별개로 보전 등급 연결 문제를 다시 조사했다.

배포 전 공개 `/v1/taxa/profile?name=큰부리까마귀` 응답은 `Corvus macrorhynchos`, taxon ID `avilist-taxon:v2025b:20296`, 원본 NE, `assessment_status=needs_review`, `evidence_kind=taxonomy_snapshot`, `independently_verified=false`였다. 연결 검토가 필요한 분류 스냅샷 값을 API 주 등급 NE 및 화면의 미평가처럼 읽히게 제공한 것이 문제였다.

고정 IUCN 공개 목록에는 같은 학명과 명명자의 2024년 LC 평가가 존재했다. SIS `103727590`, 평가 `264280673`, [공식 평가 링크](https://www.iucnredlist.org/species/103727590/264280673). 그러나 이름과 명명자가 같다는 사실만으로 현재 AviList 종 범위와 평가 범위가 같다고 확정할 수 없다.

따라서 큰부리까마귀만 LC로 덮어쓰지 않고, 전 종에 같은 식별·출처 검증 규칙을 적용했다. 평가 연결 실패, 실제 미평가, 자료부족 DD를 서로 구분한다.

## 원본과 실제 DB 대조

| 입력 | 고정 버전·범위 | SHA-256 |
|---|---|---|
| AviList JSON | v2025b, 활성 종 11,131 | `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411` |
| IUCN 공개 DwC-A | 2026-1, accepted AVES species 11,185 | `2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d` |
| 실제 TEST Neo4j 조회 행 | 활성 종 11,131, 읽기 전용 | `ee60f23871259d4cf2b8bb6d4be10475fa45b294f453018271180b1ad2abc982` |

- [AviList 원본](https://explore.avilist.org/data/avilist-2025b.json), [버전 안내](https://www.avilist.org/checklist/v2025b/).
- [GBIF 호스팅 IUCN 목록](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3), DOI `10.15468/0qnb58`, 발행기관 IUCN. 이번 고정 아카이브 EML의 CC BY 4.0을 확인했다. 라이선스 판정을 다른 API나 다른 버전에 일반화하지 않는다.
- 원본 ZIP URL은 갱신될 수 있는 `https://hosted-datasets.gbif.org/datasets/iucn/iucn-latest.zip`이므로 재현 시 해시 확인이 필요하다.
- 실제 TEST DB의 식별자·학명·명명자·보전 등급·자료 참조를 원본과 전수 대조했다. 누락·중복·불일치 0건. `Pericrocotus albifrons` 원본의 `LC `가 적재 시 `LC`로 정리된 공백 정규화 1건은 정상으로 구분했다.
- DB의 808개 원본 NE는 적재 누락으로 발생한 값이 아니다. 이 사실이 808종 모두 실제 미평가라는 뜻도 아니다.

## 전 종 감사 결과

### 기존 연결 상태를 기준으로 한 11,131종

| 기존 처리·검토 사유 | 종 수 | 해석 |
|---|---:|---|
| 공개 체크리스트 연결 | 7,507 | 기존 인덱스와 연결 범위 유지 |
| 명명자 불일치 | 2,286 | 자동 연결하지 않은 후보 |
| 학명 불일치 | 474 | 같은 식별자를 이유로 등급 상속하지 않음 |
| 평가 ID·인용 불일치 | 56 | 서지 정합성 추가 검토 필요 |
| 분류 원본 NE | 808 | 별도 세부 감사 |
| 합계 | 11,131 | 전 종 |

7,507건은 공개 체크리스트의 키와 인용 연결을 검증한 값이다. 평가 원문 전체 또는 종 개념의 독립 검토 7,507건을 뜻하지 않는다.

### 원본 NE 808종

| 대조 단계 | 종 수 |
|---|---:|
| 동일 학명 후보 있음 | 478 |
| 그중 평가·인용 정합성 유효 | 471 |
| 명명자까지 보수적으로 일치해 참고평가 수록 | 360 |
| 동일 학명은 있으나 엄격 연결 제외 | 118 |
| 동일 학명 후보 없음 | 330 |

118건은 명명자 격차 111건과 정합성 탈락 7건이다. 330건을 모두 신규 분할종 또는 실제 미평가종이라고 단정할 근거는 없다.

참고평가 360건의 출처 등급은 LC 332, NT 15, VU 9, EN 3, CR 1이다. 이 등급은 출처 평가의 등급이며 현재 AviList 개념에 확정 배정한 등급이 아니다. 모든 NE를 LC로 바꾸면 비-LC 평가 28건도 왜곡한다.

### 최종 실제 DB 행 리플레이

| 최종 API 상태 | 종 수 |
|---|---:|
| linked_checklist | 7,507 |
| needs_review | 807 |
| snapshot_only | 2,816 |
| manual_override | 1 |
| 합계 | 11,131 |

기존 사용자 요청으로 지정한 `Pica serica` 보정 1건을 유지했다. 남은 needs_review 807건은 참고평가 있는 360건과 없는 447건이다. 원본 NE 전체에서 참고평가 없는 수는 보정 1건을 포함해 448건이다. 이 분모들을 혼용하지 않는다.

## 공통 구현과 변경 전후

기존 동작은 미연결 분류 원본 NE가 API 주 등급과 미평가 라벨로 노출될 수 있었다. 새 동작은 원본과 현재 유효 등급을 분리한다.

```json
{
  "category": null,
  "category_raw": "NE",
  "taxonomy_category_raw": "NE",
  "assessment_status": "needs_review",
  "label": "평가 연결 확인 필요",
  "reference_assessment": {
    "category": "LC",
    "assessment_year": 2024,
    "taxonomy_alignment": "unverified",
    "independently_verified": false
  }
}
```

위 예시는 핵심 필드만 발췌한 큰부리까마귀 계약이다. API 클라이언트는 `category`의 null을 처리해야 하며 원본값이 필요하면 `category_raw`를 사용한다.

- 기존 확정 연결 및 기존 사용자 보정을 먼저 적용한다. 이후 미연결 원본 NE를 null로 처리한다.
- 참고평가는 별도 객체로 제공한다. 실제 주 등급이나 카드 위험도 색상을 바꾸지 않는다.
- UI 주 배지는 `평가 범위 확인 필요`, 별도 줄은 `참고 평가: 관심대상 (LC) · 2024 · 현재 분류 범위와 일치 여부 확인 필요`로 표시한다.
- 답변 출처에서 평가 URL·연도·학명·명명자·전체 인용과 자료 버전을 확인할 수 있다. 명명자는 종 이름을 명명한 사람이며 평가기관이라는 의미가 아니다.
- 참고평가 후보는 단일 accepted AVES 종, 정확한 학명, 보수적 명명자 일치, 단일 Global 평가, 지원 등급, SIS·평가 ID·공식 URL·DOI 인용 일치를 요구한다.
- 명명자 매칭은 기존 보수적 규칙을 사용하고 연도·괄호를 보존한다. 임의 퍼지 매칭이나 분할 전 종 등급 상속은 하지 않는다.
- 런타임에서 입력 종·원본 해시·자료 버전·출처·라이선스·URL과 식별자를 재검증한다. 불완전하거나 변조된 참고평가는 사용하지 않는다.
- 기존 DD 및 분류 스냅샷과 무관한 실제 NE 의미를 유지한다. 모든 NE 문자열을 무차별 치환하지 않는다.

## 변경 파일

| 파일 | 구현 내용 |
|---|---|
| `scripts/audit_conservation_reconciliation.py` | 11,131종 전체 대조 원장·집계·보고서 생성 |
| `scripts/build_conservation_index.py` | 기존 taxa와 별도로 references 및 reference_coverage 생성 |
| `src/robingraph/retrieval/conservation_index.json` | 기존 7,507 연결 유지, 참고평가 360개 추가 |
| `src/robingraph/retrieval/conservation.py` | 출처·종 식별·서지 검증을 수행하는 reference_checklist |
| `src/robingraph/retrieval/species_profile.py` | 참조 연결·우선순위·원본 NE와 주 등급 분리 |
| `src/robingraph/api/static/chat.js` | 답변·카드·출처 토글에 구분된 평가 표시 |
| `src/robingraph/api/static/styles.css` | 작은 참고평가 문구의 줄바꿈·간격 |
| `tests/test_conservation_reference.py` | 참고평가 정합성·변조·상태 검증 |
| `tests/test_conservation_reconciliation.py` | 전 종 대조 분모·분류 검증 |
| `tests/test_conservation.py`, `tests/test_species_profile.py` | 기존 동작 및 새 null 계약 회귀 검증 |
| `tests/frontend/chat_ui.test.js` | 참고 등급·출처·중립색·레거시 입력 표시 검증 |

## 검증과 실제 결과

| 검증 | 실제 실행 범위 | 결과 |
|---|---|---|
| Python 전체 | unittest discover, 로컬 단위·고정 원본 검사 | 763개 중 728 통과, 35 건너뜀, 실패 0 |
| 프런트엔드 전체 | Node test | 279 통과, 실패·건너뜀 0 |
| 보전 관련 집중 검사 | 협업자 실행, 전체와 중복되는 부분집합 | 45 통과, 실패·건너뜀 0 |
| 인덱스 재생성 확인 | 실제 고정 AviList·IUCN 원본, --check | 일치 |
| 실제 TEST DB 전수 대조 | 읽기 전용 11,131개 행 | 누락·중복·불일치 0 |
| 최종 reader 리플레이 | 위 실제 DB 행 11,131개 | 잘못된 유효 NE·미평가 표시 0, issues 비어 있음 |
| 공개 프로필 HTTP | 실제 TEST 11개 요청 | 모두 200, 예상 상태·출처 일치 |
| 실제 채팅 브라우저 | 2종 × PC/모바일 4개 시나리오 | 모두 통과, JS 오류 0 |
| 배포 정적 파일 | 공개 chat.js·styles.css와 로컬 SHA 비교 | 둘 다 동일 |
| graphify | 코드 변경 후 AST update | 갱신 성공; SQL parser 부재 4개 SQL 파일 제외 |

35개 건너뜀은 별도 DB·명시 opt-in 조건 33개와 이번 보전 등급과 무관한 아종 원본 자료 부재 2개다. 건너뛴 테스트를 통과로 계산하지 않았다. 단위 테스트의 모의 API·DB 호출과 아래 실제 연결 검증은 별개다. n8n 실제 수집은 실행하지 않았다.

중간 전체 실행은 협업 수정 도중 계약 차이 5개 실패와 로컬 원본 경로 오타 2개 오류가 있었다. 변경 완료 후 테스트 기대값과 경로를 바로잡아 위 최종 결과로 재실행했다. 최종 코드에서 미해결 테스트 실패는 없다.

공개 HTTP 표본은 큰부리까마귀의 한국어·학명 요청, Pica pica, Pyrrhura subandina(CR 참고), Premnoplex tatei(EN), Pionites leucogaster(VU), Pteroglossus bitorquatus(NT), 기존 Pica serica 보정, 참고평가 없는 Anser serrirostris, 기존 연결 Anas platyrhynchos, 기존 형질 차트가 있는 Hypsipetes amaurotis다.

브라우저는 API를 가로채지 않고 실제 채팅으로 큰부리까마귀·Pyrrhura subandina를 조회했다. Chrome 1280×900과 390×844에서 null 주 등급, LC/CR 참고평가, 중립 카드색, 출처 인용, 화면 안 카드 배치, 기본 상태 wheel 이동 0을 확인했다. PC 마우스 드래그와 모바일 CDP 터치 스와이프로 카드 전환을 확인했다. 모바일은 브라우저 에뮬레이션이며 실제 휴대전화 하드웨어 검증은 아니다.

사진 로딩 전에 캡처된 첫 증거를 개선하기 위해 이미지 로딩 대기 후 브라우저 검증을 한 번 더 실행했다. 보전 등급 검증 4개는 두 실행 모두 통과했다.

## 배포와 복구

- NAS TEST 이미지: `robingraph-api:test-conservation-d4204bf`.
- 배포 OCI revision: `d4204bf5929459bce86dd07239a73f61037d31af`.
- TEST 컨테이너 ID: `2b6df9285895bd913dc300a180c266513ac6a3da90bb2ff15b9bc49f21c79acd`, 상태 healthy.
- 패키지: `robingraph-nas-release-d4204bf5929459bce86dd07239a73f61037d31af.tar.gz`, 125개 허용 파일의 manifest 검증 성공.
- 패키지 SHA-256: `55774e9ddacdae7515b2b9a5afabb0b4c9238c70f73cd8723af24573bcfb8f8e`.
- NAS 작업 디렉터리: `/home/kimdove/RobinGraph-conservation-d4204bf`.
- 기존 TEST 설정을 권한 600으로 복사하고 이미지 태그를 지정했다. 자격 증명은 문서·로그에 기록하지 않았다.
- SCP 전송이 닫혀 SSH 표준입력으로 패키지를 전송했고 양쪽 해시를 검증했다. buildx 부재 경고 뒤 기존 Docker 빌드가 성공했다.
- PROD `robingraph-api:prod-e90ff85`, revision `e90ff8535ba677cb52ea67f6e06e30af8d9d5ed3`, healthy 유지. 이번 배포 대상이 아니다.
- DB 마이그레이션·원자료 갱신 없음. 문제가 발생하면 이전 TEST 릴리스 디렉터리 `/home/kimdove/RobinGraph-traits-663ef4f`의 기존 배포 설정으로 되돌릴 수 있다. 실제 롤백은 실행하지 않았다.
- 확인 주소: <https://robingraph-test.dove-nest.com/chat>.

## 협업 검토

Orca run `run_bb6779434843`에서 GPT-6.1-sol은 전 종 감사·인덱스·서버 참고평가 검증, Claude는 NE 표시·프런트엔드·통합 회귀 검증, Antigravity는 신뢰 출처·분류 범위 조사와 보고서 검토를 담당했다. 코디네이터는 실제 DB 전수 조회·테스트·출처 대조·배포·공개 API·브라우저 검증을 수행했다.

Antigravity 초기 초안의 평가 범위·국내 지위 관련 근거 없는 단정은 반려하고 개정했다. 최종 기록도 실제 원장·API와 대조해 라벨·입력 경로·기준선 표현을 교정했다. 협업 보고서가 있다는 이유만으로 주장을 자동 채택하지 않았다. 작업자 터미널은 결과 수락 후 정리했고 reclaimable 작업자는 0개다.

## 증거와 재현

- [출처·종 개념 검토](../verification/2026-10-09-conservation-concept-review.md)
- [전 종 감사 요약](../verification/assets/2026-10-09-conservation-reconciliation-summary.json)
- [11,131종 감사 원장 gzip](../verification/assets/2026-10-09-conservation-reconciliation.json.gz)
- [실제 DB 입력 행 gzip](../verification/assets/2026-10-09-conservation-live-rows.json.gz)
- [DB-원본 대조](../verification/assets/2026-10-09-conservation-live-source-check.json)
- [최종 reader 리플레이 요약](../verification/assets/2026-10-09-conservation-runtime-replay-summary.json)
- [최종 reader 전 종 결과 gzip](../verification/assets/2026-10-09-conservation-runtime-replay.json.gz)
- [공개 HTTP 결과](../verification/assets/2026-10-09-conservation-public-http.json)
- [실제 브라우저 결과](../verification/assets/2026-10-09-conservation-reconciliation-browser.json)
- [재현 노트북](../verification/assets/2026-10-09-conservation-reconciliation.ipynb)
- [큰부리까마귀 모바일](../verification/assets/2026-10-09-conservation-crow-front-390.png)
- [CR 참고평가 PC](../verification/assets/2026-10-09-conservation-parakeet-front-1280.png)

같은 assets 폴더의 `verify-conservation-runtime.py`, `verify-conservation-http.py`, `verify-conservation-browser.cjs`에 날짜 접두어가 붙은 실행 스크립트를 보존했다. HTTP·브라우저 재실행은 실제 서비스 요청을 발생시킨다. 노트북은 보존된 원장만 읽어 해시·합계·분모·표본을 재검증하며 네트워크나 DB에 접속하지 않는다.

노트북의 코드 셀 3개는 별도 Python 프로세스에서 순서대로 실제 실행해 assertion과 출력을 저장했고 JSON 구조를 검증했다. Jupyter kernel·nbclient 실행은 하지 않았다. 원본 다운로드와 노트북 검증을 혼동하지 않는다. 전체 DB reader 리플레이는 11,131개 HTTP 요청을 실행했다는 뜻이 아니다.

## 남은 한계와 후속 검토

1. 참고평가 360개의 현재 분류 범위 일치는 미확인이다. 원문에서 포함·제외 종, 지역·평가 시점의 개념을 확인하기 전에는 주 등급으로 승격하지 않는다.
2. 참고평가 없는 needs_review 447종과 기존 보정 1종은 별도로 남는다. 자료 부재를 위험도 또는 실제 미평가로 해석하지 않는다.
3. 비-NE snapshot_only 2,816종도 명명자·학명·서지 차이를 추가 검토해야 한다. 이번에 신뢰 가능한 새 연결로 승인하지 않았다.
4. Pica serica 기존 사용자 지정 LC는 이전 보정의 출처 정책을 유지한 예외다. 이번 자동 연결에서 독립 검증된 것으로 주장하지 않는다.
5. 국내 적색목록·법정 보호·지역 위험도는 전 지구 IUCN 평가와 별도 축이며 이번에 전수 검증하지 않았다.
6. 데이터는 해시로 고정한 2026-1 평가 목록이다. 웹의 이후 갱신을 실시간 반영한다고 주장하지 않는다.
7. 향후 자료 갱신 시 같은 감사 스크립트로 원장 차이와 연결 변경을 검토한다. n8n 수집 허용은 받았지만 이번에는 기존 공개 고정 원본으로 충분해 새 수집 플로를 만들지 않았다.
