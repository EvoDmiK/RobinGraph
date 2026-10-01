# ADR-0005: 한국어 일반명(Korean vernacular name) 소스 — Wikidata를 커뮤니티 제공 보충 소스로 채택, NIBR은 계속 비활성

- 상태: Accepted
- 작성일: 2026-09-11
- 근거 입력: `docs/decisions/0002-taxonomy-backbone.md`, `docs/decisions/0003-license-policy.md`, `docs/data-source-decision-input.md`

## 맥락

b6625da가 `GET /v1/taxa/lineage?name=`(한국어 일반명 조회)를 구현했지만, 실제
AviList 적재는 영명만 보장하므로 `청둥오리` 같은 실제 종명은 항상 404였다.
ADR-0002는 국립생물자원관(NIBR) 국가생물종목록을 한국어 국명의 원 출처로
지정했지만 "정확한 공공누리 유형을 확인한 뒤"라는 조건을 걸었고, 그 조건은
당시 확인되지 않은 채로 남아 있었다.

## 이번에 확인한 사실

1. **NIBR 라이선스가 이제 확정됐다 — 하지만 허용 목록 밖이다.** 2026-09-11에
   data.go.kr의 실제 데이터셋 페이지(`https://www.data.go.kr/data/15048041/fileData.do`,
   "국가생물종목록", 국립생물자원관, XLSX, 61,230종/26개 분류군, 조류의 국명·학명
   포함, 최종 수정 2025-07-24)를 직접 조회해 이용허락범위가
   **"공공저작물 : 출처표시, 변경금지 (제 3유형)"**(공공누리 제3유형, KOGL
   Type 3)임을 확인했다. ADR-0003의 기본 허용 목록은 CC0, CC BY 3.0/4.0,
   공공누리 **제1유형**뿐이며 제3유형은 명시적으로 제외돼 있다(2차적 저작물
   작성 금지 조건 때문에 임베딩·그래프 적재 전 별도 예외 ADR이 필요하다고
   못박아 뒀다).
2. **Wikidata 구조화 데이터는 CC0로 확정돼 있다.** 2026-09-11에
   `https://www.wikidata.org/wiki/Wikidata:Licensing`를 직접 조회해 "All
   structured data in the main, property and lexeme namespaces is made
   available under the Creative Commons CC0 License" 문구를 확인했다. 같은 날
   `https://query.wikidata.org/sparql`에 아래 질의를 실행해 실제 매칭 사례를
   확인했다: `Q25348 → taxonName "Anas platyrhynchos" → itemLabel(ko)
   "청둥오리"`.

   ```sparql
   SELECT ?item ?taxonName ?itemLabel WHERE {
     ?item wdt:P105 wd:Q7432 .
     ?item wdt:P171* wd:Q5113 .
     ?item wdt:P225 ?taxonName .
     ?item rdfs:label ?itemLabel .
     FILTER(LANG(?itemLabel) = "ko")
   }
   ```

## 결정

- **NIBR은 계속 비활성 상태로 둔다.** `config/collection-points.json`의
  `korea-nibr-species`와 `config/source-registry.json`의 `nibr-species`는
  `enabled: false`, `license_policy_status: "review_required"`를 유지한다.
  공공누리 제3유형에 대한 예외를 만들지 않는다(기존 허용 목록에 따른 코디네이터 구현 판단, 2026-09-11).
  국명·학명이 포함된 실제 데이터셋(15048041)의 존재와 정확한 라이선스 유형은
  이 ADR에 기록해 다음 검토의 시작점으로 삼는다.
- **Wikidata를 별도의, 승인된 "커뮤니티 제공" 보충 소스로 채택한다.**
  `korean-vernacular-wikidata-species-labels` collection point(CC0,
  `license_policy_status: "allowed"`)를 통해 활성 AviList `Taxon`에 학명
  완전 일치로만 한국어 `VernacularName`을 붙인다. 자세한 실행 계약은
  [n8n 한국어 일반명 수집 런북](../n8n/korean-vernacular-ingest.md).
- **Wikidata 한국어 이름은 공식 한국어 표준명이 아니다.** 모든
  `VernacularName {language: 'ko'}` (Wikidata 적재분)에 `status:
  'community-sourced'`를 명시적으로 표기하고, `/v1/taxa/lineage` 응답의
  `lineage[].korean_name_status` 필드로 그대로 노출한다(참고:
  `docs/taxonomy-lineage-api.md`). 이는 Wikidata가 누구나 계속 편집하는
  데이터베이스이고, 국립생물자원관처럼 국가가 관리하는 표준명 목록이
  아니기 때문이다. AviList 자체 영명은 `status: 'source-preferred'`로 이미
  구분돼 있었다 — 이번 결정은 같은 구분을 한국어 이름에도 적용하고 API로
  노출한 것이다.
- 이 ADR은 ADR-0002의 NIBR 관련 결과("NIBR 조건 확인 전에는 해당 데이터를
  운영 그래프에 넣지 않는다")를 바꾸지 않는다. NIBR이 나중에 승인되면(예:
  제3유형 예외 ADR을 통해, 또는 다른 공공누리 유형이 적용되는 하위
  데이터셋을 찾아서) 국내 법적 지위(멸종위기종 등)와 공식 국명을 원 출처로
  병행 적재하는 계획은 그대로 유효하며, 그때는 `status`에 별도 값(예:
  `'source-preferred'` 또는 `'official'`)을 부여해 Wikidata 커뮤니티 이름과
  구분한다.

## 이유

- ADR-0003이 이미 정한 라이선스 허용 목록을 유지하려면, 방금 확인한 제3유형
  조건에서 NIBR을 자동 승인할 수 없다. "변경금지" 조건 하에서 이름-학명
  쌍만 구조화 데이터로 추출하는 것이 "2차적 저작물 작성"에 해당하는지는
  법률 판단이 필요한 영역이며(ADR-0003의 검토한 대안 참고), 이 프로젝트의
  1인 MVP 범위에서 임의로 판단하지 않는다.
- Wikidata는 이미 라이선스가 명확하고(CC0), 실제 매칭 사례를 라이브로
  확인했으며, AviList 학명에 대해서만 결정론적으로 매칭하고 충돌·미매칭은
  `VernacularNameCandidate`로 격리하는 파이프라인을 이미 구현·테스트했다.
  "동작하는 한국어 n8n 파이프라인"이라는 목표를 지금 달성할 수 있는
  현재 선택한 허용 목록 내 보충 수집 경로다. 구현은 진행 중이며 최종 검증은 완료되지 않았다.
- `status` 구분과 API 노출을 통해, 이 이름들이 "공식" 표준명이라는 오해를
  만들지 않는다 — 이는 "라이선스·권리·결과를 임의로 지어내지 않는다"는
  프로젝트 원칙을 지키는 데 필수적이다.

## 검토한 대안

- **NIBR 제3유형에 대한 즉시 예외 승인**: 실제 국가 공식 국명을 얻을 수
  있으나, 임베딩·그래프 적재 전 법률 판단이 필요하다는 ADR-0003의 기존
  경계를 우회하게 되므로 코디네이터가 예외를 만들지 않았다. 사용자의 명시적 거부 결정은 없었다.
- **NIBR을 위한 비활성 스캐폴딩(다운로더만) 선구현**: 예외가 나중에
  승인됐을 때 빨리 착수할 수 있지만, 지금은 필요하지 않다고 판단했다
  (코디네이터 구현 판단, 2026-09-11) — 실제로 쓰지 못하는 코드를 미리 만들어 두는
  대신, 이 ADR에 위 데이터셋 정보를 기록해 두는 것으로 충분하다.
- **Wikidata를 아예 사용하지 않고 한국어 조회를 계속 404로 둠**: 라이선스
  위험은 없지만 사용자가 요청한 "동작하는" 파이프라인을 전혀 만족하지
  못한다.

## 확정 전 조건

- 다음에 NIBR을 재검토할 때는 이 ADR에 기록한 정확한 데이터셋
  (`https://www.data.go.kr/data/15048041/fileData.do`, XLSX, 61,230종)과
  라이선스(공공누리 제3유형)에서 시작한다 — "확인 필요" 상태가 아니다.
- Wikidata 적재분이 실제 NAS/Neo4j에서 한 번도 실행된 적이 없다는 점은
  [n8n 한국어 일반명 수집 런북](../n8n/korean-vernacular-ingest.md)의
  "현재 검증 상태" 절에 정직하게 기록한다.
