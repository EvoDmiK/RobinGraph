# n8n 한국어 이름 수집 파이프라인 작업 중단 기록

- 기록일: 2026-09-11
- 상태: **WIP / 사용자 요청으로 중단. 배포 준비 완료가 아님.**
- 저장 브랜치: `EvoDmiK/dev-2` (작업 시작 커밋: `b6625da`)
- 역할: Claude 구현, GPT-5.6 Sol 독립 평가, Codex 통합 확인.
- 이번 저장은 구현·테스트·문서의 중간 체크포인트이며 운영 배포, 데이터 적재, `product` 병합을 의미하지 않는다.

## 목적과 현재 구현

기존 한국어 lineage 조회는 코드가 있어도 Neo4j에 한국어 이름이 없으면 404를 반환한다. 이를 보완하기 위해 Wikidata의 CC0 조류 종 한국어 label을 수집하고, 활성 AviList 분류의 학명과 정확히 매칭하는 별도 n8n 워크플로우를 구현 중이다. 이름은 공식 국명이 아닌 `community-sourced`로 구분한다.

- 생성기: `scripts/generate_n8n_korean_vernacular_ingest.py`
- n8n import JSON: `n8n/robingraph-korean-vernacular-ingest.json`
- 배포 선택자: `scripts/deploy_n8n_reference_ingest.py --workflow korean-vernacular`
- 수집 포인트·소스 레지스트리, NAS 배포 설정, API의 `korean_name_status`, Neo4j 읽기 경로와 관련 테스트를 추가·수정했다.
- Claude는 Sol 1차 지적에 따라 동명 충돌 격리, 잘못된 입력 집계, 불변 스냅샷 식별자, 활성 스냅샷 읽기 제한, 적재 완료 시점의 분류 상태 재확인 등을 수정하다 중단했다. 수정 완료나 최종 검증 통과로 간주하지 않는다.

## 확인한 증거

- 실제 Wikidata 무제한 SPARQL 조회: HTTP 200, 당시 948 bindings. `Q25348 / Anas platyrhynchos / 청둥오리` 포함. 이는 원본 응답 수이며 AviList 매칭 수나 Neo4j 적재 수가 아니다.
- 초기 artifact 로컬 검증: `ready-local: nodes=30, active=False`. 이후 수정본에 대한 최종 결과가 아니다.
- n8n 읽기 전용 원격 사전 확인: 서버 및 Neo4j credential 조회는 가능했으나, 설정된 이름의 Discord credential이 없어 실패했다. 원격 변경은 하지 않았다.
- 중단 시점 실행: `.venv\Scripts\python.exe -m unittest discover -s tests`
- 결과: **219개 실행, 196개 통과, 22개 skip, 1개 error**.
- 오류 테스트: `test_korean_vernacular_normalize_computes_idempotent_content_addressed_dataset_id`. 내부 Node 실행이 0이 아닌 종료 코드를 반환했다. 서로 다른 본문 테스트가 동일한 hash를 전달하는 부분부터 확인할 것. 이번 중단 저장에서는 고치지 않았다.
- `git diff --check`는 통과했다(LF/CRLF 안내만 출력).
- 실제 n8n import/Manual Trigger 실행, 운영 Neo4j batch 적재, 실제 API `청둥오리` 200 응답은 **검증하지 않았다**.

## Sol 평가와 남은 작업

Sol 1차 평가는 완료했으며 다음 문제를 보고했다. Claude의 수정이 일부 들어갔지만 최종 재평가는 완료되지 않았다. 재평가 터미널은 ORCA 명령 PATH 문제로 멈췄고 사용자 요청으로 작업을 중단했다.

1. 서로 다른 종의 동일 한국어 이름을 임의로 한 종으로 선택하지 않는지 확인.
2. 스냅샷·출처 레코드 불변성, 재실행 멱등성, 새 스냅샷에서 삭제된 이름의 조회 제외 확인.
3. 잘못된 binding의 누락 없는 집계와 실패 정책 확인.
4. 매칭 후 활성 taxonomy가 바뀌거나 동시 실행이 경합할 때 활성화 차단 확인.
5. 모든 QID의 출처 연결과 후보 레코드 추적성 확인.
6. 위 오류 테스트 수정 후 전체 테스트와 Sol 최종 평가 재실행.
7. 수정 중인 생성기와 체크인 JSON을 재생성·비교해 동기화 확인. 중단 시점에는 생성기의 수정 시각이 JSON보다 늦었다.
8. 한국어 워크플로우에서 Discord를 선택 사항으로 만들고, NAS 한국어 워크플로우 단독 배포 경로를 마무리. 기존 다른 워크플로우는 보존.
9. 기존 런북의 `mutable-as-of`, 노드 수, 테스트 수, Discord 필수 조건 등은 초기본 설명이므로 최종 코드와 대조해 갱신. 이 작업 기록이 현재 상태의 기준이다.
10. 준비가 끝난 뒤 실제 환경에서 import → 수동 실행 → Neo4j count/활성 상태 → API 조회를 검증하고 그때 실행 증거를 기록.

## 소스 결정 및 재개 주의사항

Wikidata 채택과 NIBR 비활성 유지는 기존 라이선스 허용 목록에 따른 코디네이터의 구현 판단이다. 사용자가 NIBR 예외를 명시적으로 거부한 사실은 없다. 확인한 NIBR 데이터셋의 공공누리 제3유형은 현재 기본 허용 목록 밖이므로 예외를 임의로 만들지 않았다.

- Wikidata 정책: https://www.wikidata.org/wiki/Wikidata:Licensing
- 확인한 NIBR 데이터셋: https://www.data.go.kr/data/15048041/fileData.do
- 실행·배포 시 `.env` 등의 비밀정보를 저장소에 넣지 않는다.
- 기존 `graphify-out/`는 작업 시작 때부터 존재한 로컬 미추적 산출물이다. 이번 체크포인트 커밋에서는 제외하고 로컬에 보존한다.
- ORCA는 승인된 AppData 절대경로를 사용한다. `.venv/orca-bridge`와 이전 실패 Dispatch를 재사용하지 않는다.
- 중단된 작업을 자동 재시작하지 않는다. 재개 요청 시 이 문서와 실제 diff부터 확인한다.
