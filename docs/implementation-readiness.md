# RobinGraph 구현 준비 체크리스트

- 상태: In progress
- 작성일: 2026-09-03
- 목적: 설계에서 코드 구현으로 넘어가기 전에 입력과 결정이 충분한지 확인한다.

## 바로 다음 작업

| 순서 | 작업 | 산출물 | 차단 여부 |
|---:|---|---|---|
| 1 | 데이터 후보·라이선스·품질 조사 결과를 시스템 요구사항으로 변환 | `data-source-decision-input.md` | 완료, Claude |
| 2 | MVP 범위와 정책 결정 | taxonomy 및 license ADR | Proposed, 사용자 확정 필요 |
| 3 | 출처별 staging 필드와 공통 데이터 계약 정의 | `data-contracts.md`, `config/schemas/source-registry.schema.json`, `src/robingraph/ingest/validation.py` | 공통 계약·registry/staging fixture 검증 완료, 원본 필드 매핑 대기 |
| 4 | 10종·관찰 100건·문서 2개 fixture와 15개 gold 질문 설계 | `docs/evaluation.md`, `data/eval/v1` | 완료, fixture 수직 슬라이스 검증됨 |
| 5 | 빈 환경부터 인용 답변까지의 수직 슬라이스 구현 | 첫 실행 가능한 MVP | 합성 fixture의 Neo4j·FastAPI 경로 검증됨, 운영 source·모델 연결 대기 |

## 결정 등록부

| ID | 결정 | 권장 기본값 | 필요한 입력 | 상태 |
|---|---|---|---|---|
| D-01 | 주 사용자·언어 | 한국어 일반 사용자, 학명과 영어 근거 지원 | 제품 목표 | 확인 필요 |
| D-02 | MVP 지역 | 한 광역 지역 | 관찰 데이터 밀도와 사용자 관심 | 확인 필요 |
| D-03 | 분류 기준판과 릴리스 | AviList v2025b + NIBR 별도 concept set | NIBR 정확한 이용 조건 | ADR-0002 Proposed |
| D-04 | 관찰 데이터 범위 | GBIF의 CC0/CC BY 레코드, 10만 건 이하 | MVP 지역과 GBIF 실제 건수 | 확인 필요 |
| D-05 | 민감종 좌표 | 원좌표 비공개, 공개 좌표 별도 파생 | 국내 기준과 격자 해상도 | 확인 필요 |
| D-06 | 라이선스 허용 행렬 | CC0·CC BY·공공누리 1유형만 | 서비스 상업성 | ADR-0003 Proposed |
| D-07 | 문헌 저장 | 허용 목록의 전문만 Chunk 생성, 나머지 서지 링크 | 개별 문서 조건 | 정책 초안 완료 |
| D-08 | 미디어 저장 | 허용 목록의 메타데이터와 딥링크 | 자산별 라이선스·API 조건 | 정책 초안 완료 |
| D-09 | 기본 DB | Neo4j Community | 규모·배포·라이선스 조건 | ADR-0001 Proposed |
| D-10 | LLM 실행 | HermesAgent → gpt-5.6-sol | endpoint·구조화 출력·reasoning·usage 계약 | 모델 확인, API 계약 대기 |
| D-11 | 임베딩 | Jina-embeddings-v3 API, 512차원 | 운영 모델 revision 고정·키 공급 방식 | 실제 문서/검색어 임베딩 인증·정규화 검증 완료 |
| D-12 | 관찰 저장소 분리 | 10만 건까지 Neo4j, 이후 TimescaleDB 검증 | 예상 관찰량과 질의 성능 | 측정 후 결정 |

## 데이터 계약에 필요한 최소 정보

각 외부 소스는 구현 전에 다음 항목이 채워져야 한다.

- 출처 ID, 제공자, 공식 landing URL, 데이터 릴리스/접근일
- 접근 방식, 인증, rate limit, 증분 수집 키
- 원본 포맷과 필수 필드, 안정적 외부 ID
- 분류 기준과 학명 필드, 기준 백본으로의 매핑 방법
- 시간·좌표 정밀도와 민감정보 처리 상태
- 라이선스 원문 URL과 판본, attribution 문구
- 검색·임베딩·청크 저장·원본 재배포·상업 이용의 허용 상태
- 품질 위험, 결측 의미, 중복 가능성, 격리 기준
- 원본 SHA-256와 수집 manifest 생성 가능 여부

## 실제 데이터 수직 슬라이스 시작 조건

다음 조건이 모두 충족되어야 구현을 시작한다.

- [ ] 분류 기준판과 릴리스가 하나로 정해졌다.
- [ ] 관찰·문헌 소스가 각각 하나 이상 정해졌다.
- [ ] 선택한 소스의 안정적 ID와 최소 필드가 확인됐다.
- [ ] 라이선스 정책이 검색·임베딩·표시·재배포별로 정해졌다.
- [ ] 민감종 좌표의 보관본과 공개본 처리 방식이 정해졌다.
- [x] 15개 gold 질문과 기대 evidence가 정의됐다. 합성 fixture로 `15/15` 평가를 통과했다.
- [ ] HermesAgent endpoint, 모델 ID, 구조화 출력과 token usage 응답이 확인됐다.
- [x] Jina API의 endpoint, 인증, 512차원 출력, 문서/검색어 task와 L2 정규화를 실제 요청으로 확인했다.

## 구현 환경 확인

- [x] Python 3.12.13과 `uv.lock`으로 개발환경을 고정했다. Windows의 `core.autocrlf=true` 새 체크아웃에서 fixture 검증, 15개 gold 평가, 재생성·손상 검사 포함 단위 테스트를 실행했다.
- [x] Windows·Ubuntu·macOS 검증과 별도 Neo4j 서비스 통합 테스트용 GitHub Actions workflow를 추가했다. 원격 실행 결과는 push 후 확인한다.
- [x] Neo4j Community `2026.07.1` 임시 인스턴스에서 전체 44개 테스트(실제 DB 통합 테스트 10개 포함), 반복 적재·정책 철회·인용 위치 검증을 통과했다. Neo4j 모드 HTTP 응답도 확인했다. 현재는 소규모 fixture의 이름 해소와 매개변수 기반 그래프 조회이며, 전문·벡터 검색은 후속 단계다.
- [x] Jina API의 연결 계약을 실제 endpoint로 확인했다. 문서 청크 4개와 검색어 1개의 임베딩을 검증했다.
- [ ] HermesAgent의 연결 계약을 실제 endpoint로 확인했다.
- [x] Jina 호환 HTTP 어댑터와 Neo4j 전문/벡터 검색 CLI를 추가했다. 모의 Jina와 실제 Neo4j를 연결해 전체 96개 테스트를 통과했다. 기본 DB 없는 실행은 76개 통과·20개 skip이며, 기존 15개 gold 질문도 유지된다. 세부 결과는 [현재 구현 상태 §12](current-implementation.md#12-하이브리드-검색-배치-완료)에 있다.

## 협업 결과 통합 규칙

Claude의 데이터 조사 결과는 사실 입력으로 사용하되, 불확실한 라이선스 해석은 `review_required`로 유지한다. Codex는 그 결과를 내부 staging 계약, provenance 필드, ingest 차단 규칙과 테스트 기준으로 변환한다. 두 문서가 충돌하면 공식 라이선스 원문과 고정된 데이터 릴리스를 기준으로 ADR에 쟁점을 기록한다.
