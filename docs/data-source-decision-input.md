# RobinGraph 외부 데이터 소스 조사 결과

- 상태: Draft (구현 전 검토 대기)
- 작성일: 2026-09-03
- 대상 문서: `docs/system-design.md` 14절("구현 전에 결정할 항목")의 2, 3, 5, 6, 7번 입력값
- 조사 범위: 조류 분류, 관찰, 지역/서식지, 이미지, 음성, 문헌 6개 도메인의 공식 출처 후보
- 조사 방법: 각 후보 기관의 공식 사이트·이용약관·API 문서를 직접 확인. 검색 결과만으로 확정하지 않고 가능한 경우 원문 문구를 대조했다. 봇 차단 등으로 원문에 직접 접근하지 못한 항목은 표에 "접근 실패, 검색 결과 기반"으로 표시하고 별도 재확인 대상으로 남겼다.
- 원칙: 라이선스 문구가 모호하거나 원문을 확인하지 못한 경우 특정 SPDX/허용 범위를 단정하지 않고 **"검토 필요"**로 표시한다. 이 문서는 법률 자문이 아니며, 실제 계약·법적 판단은 별도로 받아야 한다.

## 1. 도메인별 후보 조사

각 표의 "재배포·임베딩" 열은 system-design.md의 `License` 노드 속성(`commercial_use`, `derivatives`, `redistribution`, `embedding_allowed`)에 대응하도록 작성했다.

### 1.1 분류 (Taxon / ScientificName / TaxonConceptSet)

| 후보 | 범위 | 접근 방식 | 갱신 주기 | 식별자 | 라이선스 / 저작자 표시 | 재배포·임베딩 | 품질 위험 |
|---|---|---|---|---|---|---|---|
| **AviList — The Global Avian Checklist** ([avilist.org](https://www.avilist.org/), [checklist v2025](https://www.avilist.org/checklist/v2025/)) | 전세계 조류 11,131종. IOC World Bird List, Clements/eBird Taxonomy, Howard & Moore를 단일판으로 통합한 신규 국제 표준(2025-06 최초 발표) | 공식 사이트에서 XLSX 일괄 다운로드(AviList 탭, 결정 요약, 인용 포함). 공개 API는 확인 안 됨 | 연 1회 예상(공식 갱신 주기 명문화는 확인 못함, 검토 필요) | 학명 + 계통순서(sequence), 안정적 국제 판 하나로 통합되어 후속 crosswalk 부담이 낮음 | **CC BY 4.0**("AviList: The Global Avian Checklist © 2025 by AviList Core Team is licensed under CC BY 4.0") | 저작자 표시 하에 재배포·그래프 임베딩 가능 | 2025년 최초 발표로 장기 유지보수·개정 이력이 짧음. 기존 IOC/Clements 사용자 커뮤니티의 완전한 전환 여부 확인 필요 |
| IOC World Bird List ([worldbirdnames.org](https://www.worldbirdnames.org/new/)) | 전세계 조류, v15.2(2026-04-13)가 마지막 독자 갱신으로 안내됨 | 웹사이트에서 XLSX/CSV 다운로드 | 과거 분기별. **v15.2 이후 편집팀이 AviList로 이관 예정이라고 공식 명시** | 학명 + IOC sequence | **CC BY 3.0 Unported**. 인용: "Gill F, D Donsker & P Rasmussen (Eds). 2026. IOC World Bird List (v15.2)." | 저작자 표시 하에 재배포·임베딩 가능 | **유지보수 종료 위험** — 신규 분류 반영이 AviList로 이전되므로 장기 기준판으로 신규 채택하기에 부적합 |
| Clements Checklist / eBird Taxonomy (Cornell Lab, [birds.cornell.edu/clementschecklist](https://www.birds.cornell.edu/clementschecklist/)) | 전세계 조류(species, subspecies, group). 최신판 Excel/CSV 제공 | 웹사이트에서 Excel(5MB)/CSV(10MB) 무료 다운로드 | 연 1회(매년 8월경 공지, 최근 2023b 등) | 학명 + sequence number, eBird 코드(species code)와 연동 | **검토 필요** — 공식 다운로드 페이지에서 재배포·상업적 이용 조건을 명시한 라이선스 문구를 직접 확인하지 못했다. eBird 자체 이용약관(재배포 제한)과 연계될 가능성이 있어 별도 확인 필요 | 확인 전까지 재배포·임베딩 불가로 간주(잠정) | 최신판은 이제 AviList와 병행 유지되는 상태로 보이며, 향후 유지보수 방향이 불확실 |
| GBIF Backbone Taxonomy ([gbif.org/dataset/d7dddbf4...](https://www.gbif.org/dataset/d7dddbf4-2cf0-4f39-9b2a-bb099caae36c)) | 전 생물군을 아우르는 GBIF 자체 종합 분류 체계(조류 포함) | [hosted-datasets.gbif.org](https://hosted-datasets.gbif.org/datasets/backbone/) 에서 Darwin Core Archive 다운로드, GBIF Species API | 비정기(릴리스 아카이브 존재) | `taxonKey`(usageKey) — 릴리스마다 변경 가능 | **CC BY 4.0** | 저작자 표시 하에 재배포·임베딩 가능 | GBIF는 향후 자체 Backbone을 폐기하고 **Catalogue of Life를 주 분류 기준으로 전환할 계획**이라고 공지함 — 신규 채택 시 장기 지속가능성 위험 |
| 국립생물자원관(NIBR) 국가생물종목록 ([species.nibr.go.kr](https://species.nibr.go.kr/)) | 한반도 서식 생물종 전체(2026년 기준 약 56,248종, 조류 포함, 국명 포함) | 사이트에서 Excel 다운로드, Open API 신청 페이지 존재([species.nibr.go.kr/api-list](https://species.nibr.go.kr/api-list)) — 정확한 API 약관은 미확인 | 비정기(신종 등재 시 갱신) | 국명/학명, 종목록 고유 코드 | **검토 필요** — 공공누리(KOGL) 표시가 확인되나 정확한 유형(0~4)을 원문에서 확정하지 못함 | 확인 전까지 상업적 이용·2차 저작물 생성 여부는 보수적으로 가정(출처표시만 확정) | 국제 표준 분류판과 국명·분류 범위가 다를 수 있어 crosswalk 시 동의어/이명 처리 필요. 이 소스는 **한국어 국명(VernacularName)과 국내 멸종위기종 지정 여부**를 얻는 데 필수적 |

**분류 구조상 위험**: IOC, Clements/eBird, GBIF Backbone, NIBR 목록은 서로 다른 분류 개정 주기를 가지며 특히 조류는 최근 대규모 계통 재배치가 잦다. AviList가 IOC·Clements·H&M을 통합했지만 국내 목록(NIBR)과는 별도 crosswalk가 필요하다.

### 1.2 관찰 (Observation)

| 후보 | 범위 | 접근 방식 | 갱신 주기 | 식별자 | 라이선스 / 저작자 표시 | 재배포·임베딩 | 품질 위험 |
|---|---|---|---|---|---|---|---|
| GBIF Occurrence (일반) ([gbif.org](https://www.gbif.org/)) | 여러 발행기관(publisher)이 올린 한국 조류 occurrence 레코드 합. 예: KIEE-BI(한국환경생태연구소), NSMK-BI(국립중앙과학관) 등 개별 데이터셋 | GBIF API/occurrence download(DOI 발급), 필터로 국가·분류군 지정 가능 | 발행기관마다 상이(비정기) | `gbifID`, 원본 `occurrenceID` 보존 | 레코드(데이터셋)별로 **CC0 / CC BY / CC BY-NC 중 하나**. 다운로드 시 GBIF가 DOI와 함께 라이선스 혼합 목록을 제공 | 라이선스별로 상이 — CC0/CC BY는 재배포·임베딩 가능(저작자표시 필요시 병기), **CC BY-NC는 상업적 재배포 불가** | 여러 발행기관의 레코드가 섞여 있어 데이터셋 단위 라이선스 태깅을 빠짐없이 보존해야 함(license 필드 유실 시 quarantine 필요) |
| EOD — eBird Observation Dataset (GBIF 경유, [gbif.org/dataset/4fa7b334...](https://www.gbif.org/dataset/4fa7b334-ce0d-4e88-aaae-2e0c138d049e)) | Cornell Lab이 GBIF에 발행한 eBird 관찰 스냅샷. 한국 포함 전세계 | GBIF occurrence download API, DOI 인용 | GBIF 릴리스 주기(수개월~1년) | `occurrenceID`(eBird checklist/observation 기반), `gbifID` | GBIF의 3종 라이선스 체계 중 하나로 게시됨(CC BY-NC 계열로 알려짐) — **정확한 SPDX는 실제 다운로드 시 데이터셋 페이지에서 재확인 필요(검토 필요)** | CC BY-NC 계열이면 비상업적 이용 및 출처표시 하에 재배포 가능, 상업 서비스 전환 시 재협의 필요 | eBird 원본의 민감종 좌표는 GBIF 배포본에서도 계속 마스킹됨(아래 EBD 항목 참고) |
| eBird Basic Dataset (EBD, 원본 직접 다운로드, [science.ebird.org/en/use-ebird-data](https://science.ebird.org/en/use-ebird-data), [support.ebird.org](https://support.ebird.org/en/support/solutions/articles/48000838205-download-ebird-data)) | 전세계 eBird 체크리스트 원본(참여 관찰자 수, 개수, 노력량 포함) | Cornell 계정으로 목적 기재 후 다운로드 신청, 텍스트 파일(TSV) | 월 1회 갱신본 제공 | `GLOBAL UNIQUE IDENTIFIER`, checklist/observation ID | Cornell Lab 자체 이용약관 — **원본 형식 그대로의 재배포 금지**가 명시됨("cannot redistribute eBird data in its original format"). 파생 결과물은 인용 요구, 상업적 재배포는 사전 서면 허가 필요 | **원본 재배포 불가**. 자체 파이프라인에서 파생 집계·요약만 만들어 내부 그래프에 반영하는 용도로 제한 | **민감종(Sensitive Species) 좌표는 원천적으로 EBD에서 마스킹**되어 배포됨(전세계 325개 taxa, 20×20km 격자 수준). 국내 조류 다수(맹금류 등)가 해당될 수 있음 |
| iNaturalist Observations ([inaturalist.org](https://www.inaturalist.org/), API 문서) | 시민과학 관찰, research-grade는 전문가 동정 합의 레코드 | 공개 REST API(무료, rate limit 있음), AWS Open Data(iNaturalist Open Data, 대량 스냅샷) | 상시(API), 스냅샷은 월 단위 | 관찰 ID(안정적), 사용자 계정 연동 | **관찰마다 사용자가 개별 지정** — GBIF에 넘어가려면 CC0/CC BY/CC BY-NC 중 하나여야 함(CC BY-SA/ND는 GBIF에서 제외). 사진은 관찰과 별도로 라이선스 지정 가능(기본값 CC BY-NC) | 라이선스가 레코드마다 다르므로 **적재 시 레코드 단위 라이선스 필터링 필수** | 동정 신뢰도는 research-grade 기준(2인 이상 동의)이 있으나 여전히 오동정 가능. 좌표는 사용자가 자체적으로 흐리게(geoprivacy) 설정 가능 |
| 환경부·국립생물자원관 겨울철 조류 동시총조사(센서스) / 철새지리정보 ([species.nibr.go.kr/bird](https://species.nibr.go.kr/bird/home/main/intro.do)) | 국내 주요 철새도래지 200곳, 매년 10월~익년 3월 매월 실시. 가락지 부착·위치추적 이동 정보 포함 | 보도자료·웹 조회 서비스로 요약 통계 공개. 원본 레코드 단위 벌크 다운로드/API 여부는 **검토 필요**(확인 못함) | 월 단위(조사), 연간 요약 발표 | 조사구역 코드, 종/개체수 집계 단위(개체 단위 occurrence ID는 불명) | 정부 공공저작물 — 공공누리 적용 가능성 높으나 **정확한 유형 미확인, 검토 필요** | 확인 전까지 보수적으로 링크·요약 통계만 활용 가능한 것으로 가정 | 개체 단위가 아닌 집계 단위일 가능성이 높아 Observation 노드보다 지역·시기 집계 근거(EvidenceUnit)로 더 적합할 수 있음 |
| 공공데이터포털(data.go.kr) 내 환경부/국립생태원 조류 관련 데이터셋 | 기관별로 산발적 게시(정확한 데이터셋 목록은 이번 조사에서 특정하지 못함) | Open API 또는 파일 다운로드, 포털 공통 이용약관 | 데이터셋마다 상이 | 데이터셋마다 상이 | 공공데이터포털의 기본 라이선스는 공공누리이나 **데이터셋별 유형이 다를 수 있어 개별 확인 필요(검토 필요)** | 데이터셋별 확인 후 결정 | 목록화되지 않은 다수 데이터셋 존재 — Source registry 등록 전 개별 실사가 필요 |

### 1.3 지역(Place) / 서식지(Habitat)

| 후보 | 범위 | 접근 방식 | 갱신 주기 | 식별자 | 라이선스 / 저작자 표시 | 재배포·임베딩 | 품질 위험 |
|---|---|---|---|---|---|---|---|
| 국가공간정보포털(NSDI)/국토지리정보원 행정구역 경계 API ([nsdi.go.kr](http://www.nsdi.go.kr/lxportal/), data.go.kr 경유) | 광역시도·시군구·읍면동·리 등 행정구역 경계(공간정보) | Open API(OGC 표준, REST, JSON/XML), API 키 발급 필요 | 행정구역 개편 시 갱신(비정기) | 법정동/행정동 코드(행정표준코드) | 공공데이터포털 게시물로 공공누리 적용 가능성이 높으나 **정확한 유형은 데이터셋별 확인 필요(검토 필요)** | 확인 전까지 출처표시 조건으로 사용 가능하다고 잠정 가정, 상업적 이용/변형 여부는 재확인 | MVP는 좌표 속성 기반 접근을 우선하므로(설계 4.4절) 이 소스는 Place 계층 구성 시 보조적으로만 필요 |
| 국립생태원 EcoBank(국제생태정보종합은행, [nie-ecobank.kr](https://www.nie-ecobank.kr/), [ecobank.nie.re.kr](https://ecobank.nie.re.kr/)) | 전국자연환경조사, 멸종위기종 조사, 외래종 모니터링 등에서 나온 종 분포·서식지 환경 특성·생태계 구조 데이터 | 포털 조회/다운로드, 공공데이터포털에도 일부 파일 게시(예: "국립생태원_EcoBank 생태 정보") | 조사 주기에 따름(전국자연환경조사는 다년 주기, 최근 5차 완료) | 조사구역/격자 코드, 표준화된 종 목록 코드 | 공공누리 표시 확인됨(사이트 내 "공공누리" 안내 페이지 존재) — **정확한 유형은 항목별 확인 필요(검토 필요)** | 유형 확인 후 결정 | 서식지 관련 통제 어휘가 국내 관행 기준이라 국제 표준(IUCN)과 매핑 작업 필요 |
| 환경부 생태자연도 / 환경공간정보서비스(EGIS) | 전국 생태자연도 1~3등급, 별도관리지역, 보호구역 경계 | 웹 지도 서비스 및 공간정보 다운로드(**이번 조사에서 API/라이선스 원문 직접 확인 못함, 검토 필요**) | 수년 주기 개정 | 등급도 폴리곤 코드 | 공공누리 추정, **확인 필요** | 확인 필요 | 갱신 지연 시 실제 서식지 상태와 괴리 가능 |
| IUCN Habitats Classification Scheme ([iucnredlist.org/resources/classification-schemes](https://www.iucnredlist.org/resources/classification-schemes)) | 국제 표준 서식지 통제 어휘(계층형 코드 체계) — 공간 데이터가 아니라 **어휘 자체** | PDF/웹 문서로 코드·레이블 공개 | 비정기 개정 | 계층형 코드(예: 1.x, 4.x 등) | IUCN Red List 전체 이용약관은 **개인/가구 단위 이용으로 한정하고 제3자 이전을 금지하는 조항**이 있어("rights ... are personal to you or to members of your household and are not transferable") 자사 서비스 그래프에 통제 어휘로 편입하는 것이 이 약관 범위에 해당하는지 **명확하지 않음 — 검토 필요(법률 검토 권장)** | **재배포·임베딩 여부 확정 불가.** 어휘 코드·레이블 자체가 저작물로 보호되는 범위인지도 별도 판단 필요 | 국내 서식지 분류 관행과 1:1 대응이 되지 않아 매핑 규칙이 필요 |

**메모**: Protected Planet(WDPA) 등 국제 보호구역 DB, 통계청 SGIS 등은 후보로 거론될 수 있으나 이번 조사에서 공식 약관을 직접 확인하지 못해 표에서 제외했다. 후속 조사 대상으로 남긴다.

### 1.4 이미지 (MediaAsset — Image)

| 후보 | 범위 | 접근 방식 | 갱신 주기 | 식별자 | 라이선스 / 저작자 표시 | 재배포·임베딩 | 품질 위험 |
|---|---|---|---|---|---|---|---|
| iNaturalist 사진 | 한국 조류 관찰에 첨부된 사진(제출자별로 편차 큼) | REST API, iNaturalist Open Data(AWS) | 상시 | 사진 ID(안정적), 관찰 ID와 연동 | **사진 기본 라이선스는 CC BY-NC**이나 업로더가 CC0/CC BY/CC BY-SA/CC BY-ND 등으로 개별 변경 가능. 관찰의 라이선스와 사진의 라이선스가 다를 수 있음 | 라이선스별 상이. MVP 설계상(3.1, 8.1절) **원본 파일 저장이 아니라 URL·메타데이터만 저장**하므로 CC BY-NC 포함 대부분 라이선스에서 딥링크+메타데이터 표시는 가능하나, 상업적 재배포·자체 호스팅은 라이선스별 확인 필요 | hotlink 안정성(원본 삭제/비공개 전환 위험), 라이선스 메타데이터 누락 가능성 |
| Wikimedia Commons ([commons.wikimedia.org/wiki/Commons:Licensing](https://commons.wikimedia.org/wiki/Commons:Licensing)) | 조류 카테고리 이미지, 다수가 CC BY-SA 2.0~4.0, 일부 CC0/Public Domain | 웹/미디어위키 API, 카테고리별 크롤링 | 상시 | 파일명/File 페이지 URL | 파일별로 상이하나 **대부분 CC BY-SA**(저작자 표시 + 동일조건변경허락) 또는 CC BY. 파일 설명 페이지의 저작권 태그가 원본(authoritative) | CC BY-SA는 재배포 가능하나 **파생물도 동일 라이선스로 공개해야 함** — 자사 서비스 내 메타데이터/썸네일 활용이 "파생물"에 해당하는지는 통상적으로 허용되는 인용 범위로 보이나, 그래프 서비스 전체 저작물성 판단은 **검토 필요** | 오동정 이미지 혼입 가능(위키 특성상 검증 수준 상이), 라이선스 태그 오류 사례 존재 |
| Macaulay Library 이미지 ([macaulaylibrary.org](https://www.macaulaylibrary.org/), [support.ebird.org 크레딧 안내](https://support.ebird.org/en/support/solutions/articles/48001064570-crediting-media)) | eBird에 업로드된 이미지 아카이브, 한국 조류 포함 | 연구/일부 교육 목적은 무료 요청, **상업적 이용은 별도 라이선스 계약 필요** | 상시 업로드 | Macaulay 자산 ID(ML#) | 기고자가 원저작권 보유, Cornell에 비독점 사용권만 부여. 최근 기고자가 자신의 미디어에 Creative Commons 라이선스를 선택할 수 있는 기능이 추가됨(라이선스는 자산별로 상이) | **원칙적으로 상업적 재배포는 Cornell/기고자 허가 필요.** CC 라이선스가 명시된 자산만 그 조건 하에 재사용 가능 | 자산별 라이선스 상태 편차가 커서 일괄 적재 전 자산 단위 필터링 필요 |
| GBIF Multimedia Extension(occurrence에 포함된 이미지 링크) | GBIF occurrence 레코드에 첨부된 이미지 URL(제공처는 iNaturalist 등 원 출처) | occurrence download에 포함 | 원본 갱신 주기에 따름 | 이미지 URL + occurrence ID | **원 제공자(예: iNaturalist)의 라이선스를 그대로 따름** — GBIF 자체가 별도 라이선스를 부여하지 않음 | 원 출처 라이선스 기준으로 개별 판단 | 딥링크 방식이라 원본 삭제 시 deadlink 발생 |

### 1.5 음성 (MediaAsset — Audio)

| 후보 | 범위 | 접근 방식 | 갱신 주기 | 식별자 | 라이선스 / 저작자 표시 | 재배포·임베딩 | 품질 위험 |
|---|---|---|---|---|---|---|---|
| Xeno-canto ([xeno-canto.org](https://xeno-canto.org/)) | 전세계 조류 울음소리, 한국 조류도 다수 등록됨 | REST API v3(API 키 필요, 등록 회원 대상), 개별/대량 다운로드는 "무분별한 자동 대량 다운로드는 자제" 요청, 대량 필요 시 별도 문의 안내 | 상시 업데이트(사용자 업로드) | 녹음번호(XC#, 안정적, 영구 URL 부여) | **녹음마다 개별 CC 라이선스**(CC BY-4.0, CC0, 일부 더 제한적인 CC 조합 존재 — 접근 실패로 전체 유형 분포는 원문 재확인 필요, 검토 필요) | 라이선스가 CC0/CC BY 계열이면 저작자 표시 하에 재배포·링크 가능. 자동 대량 수집은 약관상 제한되므로 **rate limit 준수 및 API 키 사용 필수** | 커뮤니티 기반 동정이라 동정 신뢰도 편차, 배경 잡음·다종 혼입 가능 |
| Macaulay Library 오디오(eBird 녹음, [macaulaylibrary.org](https://www.macaulaylibrary.org/)) | eBird 체크리스트에 첨부된 녹음, 전문 녹음가 자료 포함 | 이미지와 동일한 요청/라이선스 체계(연구용 무료, 상업용 별도 계약) | 상시 | ML# | 이미지와 동일 — 기고자 CC 선택 가능, 미선택 시 Cornell 비독점 사용권만 | 이미지 항목과 동일한 제약 | 이미지 항목과 동일 |

**MVP 결론(음성)**: 설계 문서가 이미지·음성을 "메타데이터와 URL만" 저장하기로 정했으므로(1절 원칙 6, 8.1절), Xeno-canto의 CC0/CC BY 표시 레코딩을 우선 후보로 삼고 Macaulay Library는 라이선스가 명시적으로 CC로 공개된 자산만 보조적으로 링크한다.

### 1.6 문헌 (Publication / Document / Chunk)

| 후보 | 범위 | 접근 방식 | 갱신 주기 | 식별자 | 라이선스 / 저작자 표시 | 재배포·임베딩(원문) | 품질 위험 |
|---|---|---|---|---|---|---|---|
| Crossref ([crossref.org](https://www.crossref.org/), [REST API 라이선스 안내](https://www.crossref.org/documentation/retrieve-metadata/rest-api/rest-api-metadata-license-information/)) | 전세계 학술 논문 **서지 메타데이터**(원문 아님), DOI 기반 | 공개 REST API, 등록 불필요, 익명 요청 가능 | 상시(발행 즉시 반영) | DOI(영구 식별자) | **메타데이터는 CC0**("Crossref metadata is CC0"), 단 일부 회원이 등록한 초록(abstract)은 저작권이 있을 수 있음 | 메타데이터(제목/저자/발행처/인용관계)는 자유 재배포·임베딩 가능. **원문(전문) 자체는 Crossref가 제공하지 않음** | 초록이 섞여 들어올 경우 라이선스 구분 필요 |
| 한국학술지인용색인 KCI ([kci.go.kr](https://www.kci.go.kr/)) | 국내 학술지 서지정보, 인용관계, 일부 원문 링크 | 웹 검색/API(포털 자체 이용약관 적용) | 상시 | KCI 논문 고유번호 | 서지 메타데이터의 재이용 조건은 확인했으나, **원문의 저작권 귀속(저자/학회/출판사)은 논문별로 다르며 KCI가 일괄 공표하지 않음 — 검토 필요.** 학회지 저작권 정책은 별도 시스템(KJCI, copyright.oak.go.kr)에서 안내 | **원문 전체 저장은 논문/학회별 저작권 이관 여부 확인 전까지 보류.** 서지 메타데이터만 우선 사용 | 오픈액세스 여부가 학회지마다 상이해 일괄 정책 적용 불가 |
| RISS ([riss.kr](http://www.riss.kr/)) | 국내 학위논문·학술지 논문 검색, 학위논문 원문 대다수는 비로그인으로 무료 열람 가능 | 웹 검색/원문보기(사이트 자체 이용약관, 벌크 크롤링 여부는 확인 못함) | 상시 | 논문 제어번호 | 학위논문 제출 시 저작자가 **CCL(Creative Commons License) 동의 여부를 개별 선택** — 일괄 라이선스가 아니므로 **논문 단위로 CCL 표시 확인 필요(검토 필요)** | CCL이 명시적으로 부여된 논문만 그 조건 하에 재사용. 그 외는 링크·서지 정보만 사용 | 지도교수 협의로 공개가 유예된 논문 존재, 일괄 벌크 수집 시 이용약관 위반 소지 — **자동 수집 전 약관 재확인 필수** |
| 한국조류학회(OSK) 학회지(한국조류학회지, [osk.jams.or.kr](https://osk.jams.or.kr/co/locale.kci?lang=en_US)) | 국내 조류학 전문 학술지(1994~) | 학회/JAMS 플랫폼, KISS·DBpia 등 상업 DB에도 유통 | 정기 간행(연 2회 등, 확인 필요) | ISSN 1225-9179(print) / 2586-6893(online), 논문별 DOI 여부는 확인 못함 | **오픈액세스 여부와 저작권 정책을 원문에서 확인하지 못함 — 검토 필요.** 상업 DB(KISS/DBpia) 유통 사실은 완전 오픈액세스가 아닐 가능성을 시사 | 확인 전까지 서지 정보(제목/저자/연도)만 Publication 메타데이터로 사용, 원문 저장 보류 | 국내 조류 생태 근거의 핵심 출처이므로 저작권 정책 확인이 최우선 후속 과제 |
| 국립생물자원관/국립생태원 발간 도감·보고서(PDF) | 국가생물종목록 해설, 생태조사 보고서 등 정부 발간물 | 각 기관 웹사이트에서 PDF 다운로드 | 발간 시 | 보고서 고유번호 | 공공누리 표시(정확한 유형은 문서별 확인 필요) | 유형 확인 후 원문 저장 가능성 있음(공공누리 1유형이면 전문 저장·재배포 가능) | 발간물마다 표시 유형이 다를 수 있어 문서 단위 확인 필요 |

## 2. MVP 최소 조합 추천

| 도메인 | MVP 1순위 소스 | 근거 |
|---|---|---|
| 분류 기준판 | **AviList v2025**(국제) + **국립생물자원관 국가생물종목록**(한국어 국명·국내 crosswalk) | AviList는 명시적 CC BY 4.0으로 재배포·임베딩 제약이 가장 적고, IOC/Clements 분절 문제를 해소한 최신 통합판이다. NIBR 목록은 한국어 국명과 국내 법적 지위(멸종위기종 등)를 얻는 유일한 공식 출처이므로 원 출처로 병행 보존한다(system-design.md 5.2절의 crosswalk 원칙 적용) |
| 관찰 | **GBIF Occurrence(CC0/CC BY 레코드만 필터링)** + 필요 시 **iNaturalist API(CC0/CC BY 레코드만)** | 둘 다 레코드 단위 라이선스가 명확히 태깅되어 있어 "라이선스 정책을 검색 전에 적용"(설계 원칙 5)을 코드로 구현하기 쉽다. eBird EBD 원본은 재배포 금지 조항이 있어 MVP 1순위에서 제외하고, 필요해지면 목적 기재 후 별도 신청 경로로 다룬다 |
| 지역 | 좌표 속성 우선 + **국가공간정보포털 행정구역 경계**(라이선스 확정 후) | 설계 4.4절이 이미 "좌표 속성 + 사전 계산한 Place 관계"를 MVP 기본값으로 정했으므로, 행정구역 폴리곤은 라이선스 확인 후 보조적으로만 도입 |
| 서식지 | **국립생태원 EcoBank**(공간 실측) — 단, 공공누리 유형 확정 전까지 요약·링크만 사용. 통제 어휘는 국내 관행 라벨을 우선하고 IUCN 매핑은 라이선스 확정 후 보류 | IUCN Habitats Classification Scheme는 이용약관상 재배포 허용 범위가 불명확해(개인/가구 한정 조항) MVP에 바로 편입하기 어렵다 |
| 이미지 | **iNaturalist(CC0/CC BY 레코드만) 딥링크 + 메타데이터** | 설계 문서가 "메타데이터/URL만 저장"을 MVP 범위로 명시했고, iNaturalist는 레코드 단위 라이선스 필드를 API로 명확히 제공해 필터링이 쉽다 |
| 음성 | **Xeno-canto(CC0/CC BY 레코딩만) 딥링크 + 메타데이터** | 동일한 이유로 라이선스 필터링이 API 수준에서 가능하다. Macaulay는 자산별 라이선스 편차가 커서 2순위로 둔다 |
| 문헌 | **Crossref 서지 메타데이터(CC0)** + 오픈액세스가 확인된 개별 논문·정부 발간물만 원문 색인 | 메타데이터는 무조건 CC0로 안전하다. 원문은 KCI/RISS/OSK 저작권 확인 전까지 링크와 서지 정보만 사용하고, 확인된 공공누리 1유형 보고서만 전문 저장한다 |

## 3. 시스템 구현에 필요한 확정값

### 3.1 분류 기준판 (system-design.md 14절 항목 3)

- **1차 기준판**: AviList v2025 (CC BY 4.0, avilist.org 배포 XLSX 스냅샷을 SourceDataset으로 등록)
- **원 출처 보존**: 국립생물자원관 국가생물종목록을 별도 TaxonConceptSet으로 함께 적재하고, 국명(`VernacularName`, language=ko)과 국내 법적 지위(멸종위기종 등)는 이 목록에서만 채운다
- **재확인 필요**: 구현 착수 시점에 AviList/NIBR 최신 버전과 라이선스 문구를 다시 확인한다(둘 다 개정 이력이 짧거나 빠르게 바뀔 수 있음)

### 3.2 좌표 민감도 정책 (system-design.md 14절 항목 5)

원좌표 공개 여부를 자동 결정하는 규칙은 아래와 같이 잠정 제안한다(**국내법 저촉 여부는 법률 검토 필요**):

| 조건 | 공개 좌표 정책 |
|---|---|
| 비민감종 + 출처 라이선스가 좌표 공개를 허용 | 원본 정밀도 그대로 공개 |
| eBird Sensitive Species 목록에 해당하거나, 국내 멸종위기 야생생물 I급/천연기념물 번식지처럼 도래·채집 위험이 있는 종 | **원좌표 비공개**. eBird 관행을 참고해 20km×20km 격자 중심점 등 저해상도 대체값만 `Observation`의 공개용 파생 속성으로 저장하고, 원좌표는 별도 접근제어 하의 raw 계층에만 보관 |
| 사유지·개인 관찰자 위치가 특정될 수 있는 경우 | Place 계층 중 시군구 이하로는 노출하지 않음 |
| 위 어느 것도 명확하지 않은 경우 | 보수적으로 비공개 처리(설계 원칙과 동일하게 "판단이 불확실하면 제외") |

원좌표는 검색 결과·근거(EvidenceUnit)·로그·API 응답 어디에도 그대로 노출하지 않는다(system-design.md 7.2절 규칙 유지). 국내 야생생물법·문화재보호법상 민감정보 공개 제한 여부는 이 조사의 범위를 벗어나며 별도 법률 검토가 필요하다.

### 3.3 라이선스 허용 행렬 (system-design.md 14절 항목 6)

| 라이선스 유형 | 검색 인덱싱(비공개 내부 처리) | 임베딩(벡터화) | 그래프 적재(메타데이터) | 원문/원본파일 재배포 | 상업적 이용 |
|---|---|---|---|---|---|
| CC0 | 허용 | 허용 | 허용 | 허용(저작자 표시 불필요, 권장은 가능) | 허용 |
| CC BY(-3.0/4.0) | 허용 | 허용 | 허용 | 허용(저작자 표시 필수) | 허용(표시 유지) |
| CC BY-SA | 허용 | 허용 | 허용 | 허용하되 **파생 결과물도 동일 라이선스 표시 필요** — 서비스 전체 저작물성 판단은 검토 필요 | 허용(표시·동일조건 유지 시) |
| CC BY-NC | 허용(내부 검색·근거 생성 목적) | 허용(내부 목적) | 허용 | 허용(비상업적 이용 한정) | **금지**. 서비스가 유료화되는 시점에 전면 재검토 |
| CC BY-ND | 허용 | 허용 | 허용(메타데이터만) | **원문/원본 자체의 변경·재가공 금지** — 요약·청크 분할이 "변경"에 해당하는지 검토 필요, 잠정적으로 링크만 제공 | 조건부(표시, 무변경 시) |
| 공공누리 제1유형 | 허용 | 허용 | 허용 | 허용(출처표시) | 허용 |
| 공공누리 제2유형 | 허용 | 허용 | 허용 | 허용(출처표시) | **금지** |
| 공공누리 제3유형 | 허용 | 허용(원문 변경 없는 임베딩 여부는 검토 필요) | 허용 | 허용하되 **2차적 저작물 작성(변형) 금지** — 청크 분할·요약 생성이 여기 해당하는지 검토 필요, 잠정적으로 원문 링크 + 짧은 인용만 | 허용(무변경 시) |
| 공공누리 제4유형 | 허용(내부 목적) | 보수적으로 보류(검토 필요) | 허용(메타데이터만) | **금지**(2차적 저작물 작성 금지 + 비상업). 링크만 제공 | 금지 |
| 계정 기반 제한적 접근(예: eBird EBD 원본) | 허용(내부 파생 집계 목적) | 파생 집계 결과만 허용, 원본 텍스트 임베딩 금지 | 파생 결과만 적재 | **원본 형식 재배포 금지**(약관 명시) | 사전 서면 허가 필요 |
| 사용자별 혼합(예: iNaturalist, Macaulay, Wikimedia) | 레코드 단위 라이선스 확인 후 허용 | 레코드 단위 확인 후 허용 | 레코드 단위 라이선스 필드와 함께 적재 | 레코드에 태깅된 라이선스 조건을 그대로 적용 | 레코드 단위 확인 필요 |
| `unknown`(라이선스 미확인) | **금지** — system-design.md 3.2절 규칙대로 `policy_status = unknown`으로만 표시 | 금지 | 원본 레코드는 SourceRecord로 보관하되 답변 생성 컨텍스트에서 제외 | 금지 | 금지 |

이 표에서 "검토 필요"로 남긴 칸(CC BY-SA/ND, 공공누리 3유형의 임베딩·청크화 관련)은 저작권법상 "2차적 저작물 작성"과 "정보 검색을 위한 색인·요약"의 경계에 대한 법률 판단이 필요하므로, 확정 전까지는 보수적 옵션(링크·짧은 인용만)을 기본값으로 적용할 것을 권장한다.

### 3.4 원문(전문) 보관 정책 (system-design.md 14절 항목 7)

권리 유형별로 분리해 적용한다(`Document.document_type`/`License.policy_status`에 반영):

1. **CC0 / CC BY / 공공누리 1유형**: 전문 저장, 청크 분할, 임베딩, 재배포 모두 가능. 저작자 표시를 `licenses` 응답 필드에 항상 병기한다.
2. **CC BY-SA**: 전문 저장·임베딩은 가능하나, 파생 결과물(답변에 포함된 인용 청크)에도 동일 라이선스 조건이 적용될 수 있음을 출처 카드에 표시한다(검토 필요 항목).
3. **CC BY-NC / 공공누리 2유형**: MVP(개인용 데모, 비상업)에서는 전문 저장·임베딩을 허용하되, 상업 서비스로 전환하는 즉시 재평가 게이트를 둔다.
4. **CC BY-ND / 공공누리 3유형**: 원문 변경(요약·재가공) 없이 그대로 인용하는 범위로 제한한다. 청크는 원문 문장을 그대로 발췌하는 형태로만 만들고, 자동 요약은 생성하지 않는다.
5. **공공누리 4유형 / 저작권 정책 미확인 학술지(KCI/OSK 등) / eBird EBD 원본**: **전문 저장 금지**. `Document`는 서지 메타데이터와 원문 링크만 보관하고, `Chunk`는 생성하지 않는다. 근거가 필요하면 `EvidenceUnit.locator`로 원문 위치(페이지/절)만 가리키고 텍스트는 인용 최소 범위로 제한한다.
6. **`unknown`**: 저장은 SourceRecord 수준까지만 하고 검색·생성 파이프라인에서 완전히 제외한다(설계 3.2절, 7.1절과 동일).

## 4. 확인하지 못해 후속 조사가 필요한 항목

- Clements Checklist / eBird Taxonomy 공식 재배포 라이선스 문구(현재 라이선스 텍스트를 원문에서 확인하지 못함)
- 국립생물자원관 국가생물종목록의 정확한 공공누리 유형과 Open API 이용약관 전문
- 한국조류학회지(OSK)의 오픈액세스 정책과 저작권 귀속 주체(저자/학회/유통 DB)
- KCI/RISS에 등록된 개별 논문·학위논문의 저작권 상태를 대량으로 사전 확인하는 절차(수작업 대량 확인은 비현실적이므로 자동 필터링 규칙 필요)
- data.go.kr에 게시된 환경부·국립생태원 산하 조류 관련 개별 데이터셋 목록과 각각의 공공누리 유형
- 환경부 생태자연도/환경공간정보서비스(EGIS)의 정확한 이용약관과 API 제공 여부
- eBird Observation Dataset(EOD, GBIF 경유)의 정확한 SPDX 라이선스(다운로드 시점에 데이터셋 페이지에서 재확인)
- Xeno-canto 전체 녹음의 라이선스 유형 분포(CC0/CC BY 비중, 봇 차단으로 약관 원문 직접 확인 실패)
- Macaulay Library 이미지·오디오 API의 정확한 요청 한도와 대량 접근 조건
- CC BY-SA/ND 및 공공누리 3유형 자료에 대한 "청크 분할·임베딩이 2차적 저작물 작성에 해당하는지"에 대한 법률 자문
- 좌표 민감도 정책의 국내 법적 근거(야생생물법, 문화재보호법 등)와 이 문서가 제안한 격자 마스킹 방식의 적법성

이 목록은 구현 착수 전 ADR(`docs/decisions/0002-taxonomy-backbone.md`, `docs/decisions/0003-license-policy.md`)에서 하나씩 답변 확정 상태로 전환해야 한다.
