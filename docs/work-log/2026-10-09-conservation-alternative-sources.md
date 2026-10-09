# 보전 등급 대체 출처 조사: GBIF 공개 IUCN 목록

## 배경과 목표

사용자는 IUCN API 사용 신청 거절과 실제 토큰의 HTTP 401 응답을 확인한 뒤 다른 출처를 찾아보자고 요청했다. 이번 작업은 API 토큰 없이 이용 가능한 보전 등급 출처의 실제 제공 범위, 라이선스, 종 연결 가능성을 확인하는 조사다. 앱 구현이나 데이터 활성화 작업은 포함하지 않는다.

## 결과와 권장 방향

가장 적합한 후보는 **IUCN이 GBIF에 공개한 CC BY 4.0 적색목록 체크리스트**다. 원 평가 기관은 IUCN으로 동일하지만, 제한된 API와 구분되는 별도 공개 배포본이다. 공식 등록 정보와 다운로드 파일 내부의 라이선스가 일치한다. 원 IUCN API의 승인 여부와 관계없이 이 공개 배포본의 명시적 라이선스와 제공 범위를 기준으로 검토할 수 있다.

| 항목 | 확인 결과 |
| --- | --- |
| 데이터셋 | The IUCN Red List of Threatened Species |
| 제공 기관 | International Union for Conservation of Nature |
| 공개 경로 | GBIF Hosted Datasets |
| datasetKey | 19491596-35ae-4a91-9a98-85cf505f1bd3 |
| 자료 버전 | 2026-1 |
| 배포일 | 2026-07-28 |
| DOI | 10.15468/0qnb58 |
| 라이선스 | CC BY 4.0 |
| 접근 | 인증 없는 메타데이터 조회와 ZIP 다운로드 성공 |
| 조류 종 | 11,185종 |
| 보전 등급 | 실제 파일의 Distribution.threatStatus에 포함 |

공식 출처:

- [GBIF 데이터셋 페이지](https://www.gbif.org/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3)
- [GBIF 등록 메타데이터](https://api.gbif.org/v1/dataset/19491596-35ae-4a91-9a98-85cf505f1bd3)
- [공개 Darwin Core Archive](https://hosted-datasets.gbif.org/datasets/iucn/iucn-latest.zip)
- [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)

등록 메타데이터의 변경 기록에는 2023년 IUCN 담당자와 협의해 CC BY-NC에서 CC BY로 변경했다는 근거도 있다. 협업 검토 에이전트가 이를 독립 확인했다. 공개 라이선스는 해당 배포본에 포함된 자료의 이용 근거다. IUCN 웹 본문, 원문 전체, 지도, 제한된 API 등 다른 자산의 이용 허락으로 확대하지 않는다.

## 실제 파일과 검증 방법

인증 없는 HEAD 요청은 HTTP 200과 파일 크기 21,140,648바이트를 반환했다. 부모 에이전트와 독립 검토 에이전트가 각각 실제 ZIP을 내려받아 파일 구조, 라이선스와 등급 값을 확인했다. 두 다운로드의 SHA-256이 일치했다.

SHA-256:
`2ed2c5f75667fa2dee9dc718406b5ba094fa9312e548934916b16c0c509ccb7d`

포함 파일:

- `taxon.txt`: SIS ID, 학명·속명·종소명·명명자, 분류 rank, accepted/synonym 상태, 인용문과 평가 URL.
- `distribution.txt`: 연결 SIS ID, 지역 범위, 인용 출처, 보전 등급과 출현 상태.
- `vernacularname.txt`: 제공된 언어별 이름.
- `meta.xml`: 각 컬럼의 의미와 파일 연결 정의.
- `eml.xml`: 라이선스, 발행일과 인용 메타데이터.

meta.xml의 Distribution extension index 5가 `http://iucn.org/terms/threatStatus`로 정의되어 있다. 등급은 taxon core의 직접 컬럼이 아니다. Global 행을 SIS ID로 연결해야 한다. scientificName에는 명명자가 포함되므로 단순 문자열을 AviList 학명과 비교하지 않고 genus와 specificEpithet를 사용했다.

전체 taxon.txt 행은 310,544개이며, `class=AVES`, `rank=species`, `status=accepted`로 제한한 조류 종이 11,185개였다. 각 종에 Global 등급이 정확히 하나 있었다. 중복 SIS ID, 등급 결측, 복수 Global 등급은 모두 0이었다.

| 등급 | 조류 종 수 |
| --- | ---: |
| LC | 8,757 |
| NT | 967 |
| VU | 668 |
| EN | 372 |
| CR | 216 |
| EW | 5 |
| EX | 164 |
| DD | 36 |

이는 공개 배포본의 값이다. 이번 조사로 각 종의 생물학적 위험을 재평가한 것은 아니다. 전체 생물 자료에는 과거 분류 체계의 등급 표현도 있으므로 범용 파서는 이를 자동으로 LC나 NT로 바꾸면 안 된다. 확인한 조류 범위에는 현대 8등급만 있었다.

## AviList 연결 후보 전수 확인

공식 AviList v2025b JSON 11,131종과 비교했다. 사용한 AviList 스냅샷 SHA-256은 `3b08845b54b8ab53908aee84d05b0fd8df765e9e01dc655599ca304d9f132411`이다. DB 조회 결과가 아니라 내려받은 공식 파일 간 비교다.

| 연결 검사 | 종 수 |
| --- | ---: |
| 기존 BirdLife 링크의 SIS ID와 학명이 모두 일치 | 9,849 |
| AviList에 기존 BirdLife 링크가 없음 | 808 |
| SIS ID는 있으나 속명·종소명 기준 학명이 다름 | 474 |
| 연결 SIS ID가 공개 조류 목록에 없음 | 0 |
| 연결 Global 등급이 하나가 아님 | 0 |

9,849종의 기본 등급은 AviList 기록과 차이가 없었다. CR의 PE/PEW 보조 표시는 이 배포본에 없으므로 기본 CR 코드만 비교했다. 이는 기본 코드 일치 결과이며 보조 표시까지 독립 검증했다는 뜻이 아니다.

9,849종도 자동 활성화 완료 상태가 아니다. 종 범위와 명명자, 출처 버전, 연결 정책을 검증하고 불일치·동의어 처리를 명시한 뒤 연결해야 한다. 474종의 학명 차이를 오타로 단정하거나 808종에 다른 종의 등급을 상속하지 않는다.

## 까치 사례와 남은 제약

공개 파일에 Pica pica의 LC와 평가 URL은 있다. Pica serica는 전체 taxon.txt와 GBIF의 이 데이터셋 검색에서 발견되지 않았다.

- Pica pica SIS ID: 103727048.
- 평가 URL: `https://www.iucnredlist.org/species/103727048/264575751`.
- 원자료 인용: BirdLife의 2024년 평가.

Pica pica의 등급을 Pica serica에 자동으로 적용할 수 없다. 같은 까치라는 한국어 이름이나 비슷한 학명만으로 평가 대상의 종 범위를 확정하지 않는다. 이 공개 배포본은 API 접근 문제를 해결할 후보지만 까치의 종 분리 문제까지 자동 해결하는 자료는 아니다.

공개 ZIP에는 Avibase 개념 ID, 정확한 평가 날짜, latest boolean, CR(PE/PEW) flags가 없다. 배포일 2026-07-28과 자료 버전 2026-1을 모든 종의 평가일이나 평가 연도로 표시하면 안 된다. 확인 가능한 개별 평가 ID와 인용문은 출처 그대로 보존한다. mutable `iucn-latest.zip`을 사용할 때는 버전과 SHA-256을 고정해야 한다.

## 국내 보호 상태를 보완하는 후보

협업 에이전트가 [국립생태원 「멸종위기 야생생물 개정 목록 공표」](https://www.nie.re.kr/nie/bbs/BMSR00028/view.do?boardId=695962914)의 공공누리 제1유형 표시와 첨부 HWP의 실제 GET HTTP 200, OLE 파일 시그니처를 확인했다.

이는 **2022년 개정 당시 국내 법정 I·II급 목록**이다. HWP 전체 내용 파싱이나 현재 시행 중인 목록과의 대조는 하지 않았다. IUCN 세계 등급과 다른 항목으로 저장해야 하며, 현행성 확인 전에는 현재 국내 보호 상태로 단정하지 않는다.

[국립생물자원관 조류 적색자료집 2019년 개정판](https://www.nibr.go.kr/aiibook/ecatalog5.jsp?Dir=1100&catimage=&callmode=admin)은 개별 공식 도서 목록에서 공공누리 제4유형으로 확인됐다. 현재 MVP의 허용 정책 밖이므로 자동 적재 대상에 넣지 않았다. PDF의 실제 다운로드·내용 검증도 하지 않았다.

## 변경·테스트·배포·후속 사항

변경 파일은 이 문서와 `docs/verification/assets/2026-10-09-gbif-iucn-source-inspection.json`이다. ZIP과 토큰은 Git에 넣지 않았다. 조사 스크립트는 임시 디렉터리에서 실행했다.

실제 검증은 공식 메타데이터 HTTP 조회, 공개 ZIP 다운로드와 내부 파일 파싱, AviList 공식 JSON과의 전수 비교, 협업 에이전트의 독립 파일·라이선스 검토다. 모의 API 검증, 새 단위 테스트, 전체 회귀 테스트는 실행하지 않았다. 실제 DB/API의 앱 연결 검증도 하지 않았다. 앱 코드를 변경하지 않았으므로 이 조사에서 graphify AST 갱신은 해당하지 않는다.

NAS 배포와 DB 수정은 없다. 기존 앱 출처는 그대로 유지된다. 권장 후속 작업은 이 공개 배포본을 릴리스와 해시로 고정한 뒤, 확실히 연결되는 종부터 보전 등급·평가 링크·인용·라이선스를 공급하는 어댑터를 만드는 것이다. 종 범위가 불확실한 값은 연결 확인 필요 상태를 유지해야 한다.

사용자의 후속 요청에 따라 이 조사 기록은 Obsidian `Work/RobinGraph/검토자료/2026-10-09-보전등급-대체출처-GBIF-IUCN-공개목록.md`에도 동일 내용으로 보존한다. 구현 승인을 받은 후속 작업은 별도 작업기록에 실제 검증·배포 결과를 기록한다. 이 문서의 전수 비교 수치는 조사 당시 학명·SIS 일치 기준이며, 명명자까지 검증하는 최종 구현 연결 수와 구분한다. 문서 커밋은 Git 이력에서 확인할 수 있다.
