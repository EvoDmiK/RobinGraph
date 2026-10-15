# 서비스 도메인 참조 정리

## 요청 배경과 목표

사용자가 현재 서비스 주소를 robingraph.dove-nest.com으로 확인하고 이전 도메인 관련 내용을 제거하도록 요청했다. 저장소의 현재 설정 안내와 검증기 기본 주소를 현재 서비스에 맞추고 과거 문서에서 혼동을 일으키는 호스트 표기를 제거했다.

## 원인과 변경 전후

배포 런북과 API 검증기의 기본 URL, 기본 인자 테스트에 이전 주소가 남아 있어 상태 점검 시 잘못된 호스트를 확인했다. 현재 주소가 필요한 곳은 https://robingraph.dove-nest.com으로 교체했다. 과거 검증 기록은 당시 결과를 새 도메인에서 확인한 것으로 바꾸지 않고 공개 API라는 표현으로 수정했다. 과거 이관 문서의 폐기된 호스트 TLS 오류 설명은 제거했다. 채팅 주소의 테스트 UI 표기는 채팅 UI로 수정했다.

## 변경 파일과 구현

- scripts/verify_api_deployment.py: 기본 URL 변경, 과거 User-Agent 검증 주석에서 호스트 표기 제거.
- tests/test_api_deployment.py: 기본 URL 기대값 수정.
- docs/nas-deployment.md: 프록시 설정, 확인 URL, curl 예제, 기본 검증 대상 수정.
- docs/current-implementation.md, docs/n8n/WORK_STATUS_2026-09-11.md, docs/n8n/korean-vernacular-ingest.md: 과거 검증의 도메인 표기 제거.
- docs/work-log/2026-09-07.md, 2026-09-12.md, 2026-10-09-test-to-prod-migration-r2.md: 과거 호스트 참조 정리.

## 검증 방법과 실제 결과

전체 저장소의 숨김 파일을 포함하고 .git을 제외한 텍스트 검색에서 이전 호스트 관련 문자열은 0건이었다. git diff --check 통과. 변경 Python 파일 2개 AST 문법 검사 통과. uv run --locked 단위 테스트는 uv 명령이 없어 실행하지 못했다. 시스템 Python unittest 실행은 robingraph 모듈 의존성 부재로 import 단계에서 실패했다. 따라서 테스트 통과 건수는 기록하지 않는다. 새 실제 DB/API 검증은 이번 수정에서 수행하지 않았다. 직전 상태 점검에서는 현재 운영 주소의 /health와 /chat HTTP 200을 확인했다.

규정에 따라 graphify update .을 실행해 AST 그래프를 갱신했다. 5141 노드와 10668 엣지가 생성됐다. SQL 추출 의존성 tree_sitter_sql 부재로 SQL 파일 4개가 그래프 추출에서 제외됐으며, 문서 의미 추출은 수행하지 않았다.

## 배포·커밋·한계와 후속 사항

커밋, push, TEST 또는 Production 배포, 컨테이너 재시작, DB 변경은 수행하지 않았다. Obsidian 기록은 요청되지 않아 작성하지 않았다. Git 과거 이력은 재작성하지 않았으며 현재 작업 트리의 참조를 정리했다. 프로젝트 Python 환경이 준비되면 tests.test_api_deployment를 다시 실행해야 한다. NAS 프록시나 DNS 설정은 변경 범위에 포함하지 않았다.
