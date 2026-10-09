# 까마귀 → 큰부리까마귀 통칭 관계 제거

## 요청·목표

2026-10-09 사용자는 `까마귀`가 `큰부리까마귀`의 통칭으로 등록된 관계를 제거하도록 요청했다. 변경 범위는 해당 편집 관계 1건이다. 큰부리까마귀의 정식 국명·학명·프로필과 까마귀의 다른 연결은 유지한다.

## 원인과 변경 전 상태

패키지 `src/robingraph/retrieval/name_relations.json`에 `crow-large-billed` 레코드가 `crow-common` 이름 엔티티의 `common_usage` 관계로 존재했다. 검색어 `까마귀`에 `Corvus macrorhynchos`를 후보로 추가하는 구조였다. 설명에는 두 종을 동의어로 합치지 않는다고 적혀 있었지만, 사용자가 보기에 큰부리까마귀의 통칭으로 제공되는 동작이었다.

실제 TEST 이름 관계 API를 확인한 결과 `까마귀`의 대상은 `Corvus corone`, `Corvus macrorhynchos` 두 종이었다.

## 변경 파일과 구현

- `src/robingraph/retrieval/name_relations.json`: `crow-large-billed` 레코드 1개 삭제. 검토일을 2026-10-09로 갱신. `crow-corone` 레코드 유지.
- `docs/name-relations-coverage.md`: 제거된 관계 표 행 삭제, 현재 총계와 변경 이유 반영. 과거 적재 검증 기록은 과거 사실로 유지.
- 나머지 종·관계 레코드와 표준 한국어 이름 자료는 변경하지 않았다.

현재 목록은 이름 엔티티 33개, 검색어 70개, 관계 46개, 대상 종 36개다. 이전 47개 관계·37개 대상에서 각각 1개 감소했다.

## TEST 실제 자료 적용

이름 관계 조회는 실행 이미지의 JSON을 직접 읽는 대신 PostgreSQL 활성 manifest와 Neo4j 관계를 사용한다. 따라서 파일 수정만으로 완료 처리하지 않고 기존 `scripts/load_name_relations.py`의 버전 적재 절차를 사용했다.

1. 수정 manifest를 TEST 컨테이너 임시 경로로 전달했다.
2. `--manifest`로 dry-run을 실행해 46개 관계·36개 대상이 활성 AviList v2025b에 각각 유일하게 연결되는지 확인했다.
3. 같은 입력에 `--apply`를 실행했다. PostgreSQL에 새 불변 릴리스·원장을 기록하고 Neo4j에 새 버전 관계를 투영한 다음 활성 릴리스를 전환했다.
4. 과거 릴리스나 다른 종의 노드를 임의 삭제하지 않았다. 제거 관계는 새 활성 릴리스에 포함되지 않는다.

활성 manifest SHA-256: `d799f0f023086039f8811827d4b21871dc77f5b5ea26368194bbba57a283d154`.
개념집합: `rg:concept-set:avilist-v2025b`.

TEST API 이미지 자체는 `robingraph-api:test-badge-017a273`을 유지했다. 별도 코드 변경이나 이미지 재빌드 없이 활성 자료 릴리스를 갱신했다. 저장소 manifest도 수정했으므로 이후 패키지에 변경 내용이 포함된다. PROD 대상 명령은 실행하지 않았다. 인증 정보는 기록하지 않았다.

## 검증과 결과

- `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests -p 'test_name_relations.py'`: 17개 통과, 실패·건너뜀 0. 모의 저장소를 포함하는 단위 테스트이며 실제 DB 검증과 구분한다.
- 실제 TEST 적재 dry-run 및 apply 성공. `Reviewed name relationships activated` 확인.
- 실제 공개 `name-relations?name=까마귀`: `Corvus corone`만 반환.
- 실제 공개 `name-relations?name=Corvus macrorhynchos`: 관계 목록 빈 배열. 큰부리까마귀의 까마귀 통칭 연결 제거 확인.
- 실제 공개 프로필 `Corvus corone` 및 `큰부리까마귀`: 각각 해당 종 반환, 프로필 유지 확인.
- 직접 프로필 API의 `name=까마귀`는 404를 반환했다. 이 엔드포인트와 통칭 관계 API의 이름 처리 계약은 다르므로 직접 프로필 조회까지 성공했다고 기록하지 않는다. 최초 `curl -f` 검사와 재시도는 오류로 종료되어 HTTP 상태를 별도로 확인했다.
- 실제 채팅 `까마귀에 대해 알려줘`: answer, name_relations 결과로 Corvus corone 1종만 안내함을 확인했다.
- `git diff --check` 통과. 변경 후 `graphify update .` 실행.

## 한계·후속

이번 요청은 특정 통칭 관계 삭제이며 까마귀의 분류·표준 국명 전체를 재검토하는 작업은 아니다. 새 이름 자료 적재에는 수정한 manifest를 사용해야 한다. 과거 이미지에 들어 있는 이전 manifest로 별도 재적재하면 이전 관계가 다시 활성화될 수 있으므로 최신 저장소 자료를 기준으로 운영한다.

[실제 API 확인 결과](../verification/assets/2026-10-09-crow-alias-removal.json)
