# PMC 실제 문헌 1편 적재 파일럿

TEST Neo4j에서 실제 문헌 검색과 Gemini 근거 답변을 확인하는 일회성 경로다.
대상은 [PMC9946348](https://pmc.ncbi.nlm.nih.gov/articles/PMC9946348/) 한 편이다.
원문은 PMC의 [OAI-PMH API](https://pmc.ncbi.nlm.nih.gov/tools/oai/)로 받고,
매 실행마다 논문 원문 XML의 CC BY 4.0 표기와 PMCID를 확인한다.
`config/source-registry.json`에도 이 논문만 허용된 소스로 등록했다.

## 범위

- 초록과 본문 문단만 적재한다. 그림·표·참고문헌·보충자료는 제외한다.
- 제목, DOI, 원문 URL, 라이선스, 원문 XML의 SHA-256, 절과 문단 위치를 출처 체인에 남긴다.
- 청크를 `HybridSearchChunk`로 전문 검색한다. 임베딩·벡터 검색은 하지 않는다.
- 노드는 `:PmcPilot:Fixture`로 표시된다. API의 `fixture_only: true`는 이 TEST 코퍼스를 가리킨다. 운영 문헌 로더로 사용하지 않는다.
- `load-neo4j-fixture`를 다시 실행하면 fixture reconciliation이 파일럿 문서·청크·출처 노드를 제거한다.

## 실행

로컬 `.env`의 Neo4j 값이 **TEST DB**를 가리키는지 확인한 후 실행한다.
다운로드·권한·파싱 확인은 DB 쓰기 없이 먼저 할 수 있다.

```sh
uv run --locked python scripts/load_pmc_pilot.py
uv run --locked python scripts/load_pmc_pilot.py --apply
uv run --locked robingraph search-neo4j --question "climate land use Los Angeles birds" --limit 5
```

적재는 같은 `:PmcPilot` 노드를 한 트랜잭션 안에서 교체한다. 재실행 시 청크가
누적되지 않는다. 원문 해시는 요청 시각이 들어 있는 OAI 응답 봉투를 제외하고
논문 XML 자체에서 계산한다.

`GEMINI_API_KEY`가 있으면 `serve-neo4j`의 `POST /v1/chat`에서 다음 질문을
시험할 수 있다.

```json
{
  "question": "How did climate and land use change affect birds in Los Angeles?",
  "intent": "evidence",
  "filters": {"kind": "evidence", "limit": 3}
}
```

TEST DB에서 논문 1개·본문 청크 55개, 전문 검색 상위 5개 모두 파일럿 청크,
`/v1/chat` HTTP 200과 검색된 청크 ID 인용을 확인했다. 이 확인은 FastAPI
`TestClient`에 실제 TEST Neo4j 검색 핸들러와 실제 Gemini 생성기를 연결해
수행했다. 배포 서버와 운영 DB는 시험하지 않았다.

## 운영 전환 시 필요한 것

실제 문헌 서비스에는 `:Fixture`와 별도의 운영 적재·검색 경로가 필요하다.
소스별 라이선스 결정, 고정 원본 보관, 업데이트·철회 처리, 검색 대상의
`fixture_only` 표시를 운영 계약에 맞게 구현해야 한다. PMC 전체가 같은
라이선스인 것은 아니므로 이 파일럿의 허용 판정을 다른 논문에 복사하지 않는다.
