# RG-701 UI 호환 계약 기준선 및 재사용 검증기 — 2026-10-20

## 배경·목표·범위

FastAPI → Django/DRF 전환 시 기존 UI 소비 계약과 정적 자산 제공 동작을 보존하기 위한 독립 검증 자산이다. 사용자 승인 범위는 구현·TEST이며 이 담당자의 범위는 신규 검사 스크립트와 기록뿐이다. canonical 소스는 `/Users/kimdove/orca/workspaces/RobinGraph/dev-codex`이고, 본 담당자의 main/dev-agy 정적 UI와 기존 테스트에는 선행 미커밋 변경이 있어 수정하지 않았다. 다른 워크트리는 읽기만 했다.

루트 `docs/work-log/2026-10-20-django-drf-migration-backlog.md`와 현재 소비자 `src/robingraph/api/static/{chat,birds}.js`, `index.html`, 기존 서버의 정적 경로 구현을 확인했다. 백로그의 미착수 표시는 등록 당시 이력이며 본 작업 요청의 구현 승인을 취소하는 의미로 해석하지 않았다.

## 확인한 계약과 위험

| 소비 URL | 요청 | UI가 사용하는 응답·동작 |
|---|---|---|
| GET `/health` | credentials omit | JSON `mode`로 백엔드 모드 표시, 실패해도 질문 가능 |
| POST `/v1/chat` | JSON question, intent(auto/profile/taxonomy/observations/evidence), optional filters, optional species_scope, defer_discovery=true | disposition answer/abstain/clarify만 성공 표시, route별 result와 profile/relationships, 출처와 경고 보존 |
| GET `/v1/taxa/profile` | name, optional species_scope | 직접 profile 객체. taxon, traits 배열, warnings 배열, lineage.items, lineage.taxonomy_source/release; images와 photo_availability, vegetation_note 및 출처/보전/분포 메타데이터 |
| GET `/v1/taxa/related`, `/similar` | name, optional species_scope | 근연 후보 items 및 순위·관계 근거, 후보 profile 추가 조회 |
| GET `/v1/taxa/ecological-related` | 동일 | 생태 관계 목록과 근거; 근연 결과와 혼용 금지 |
| GET `/v1/taxa/subspecies` | 동일 | 아종 목록과 taxon 정보; 부모 profile 추가 조회 |
| GET `/v1/taxa/name-relations` | 동일 | relations 배열; 가축형 관계 경고와 종 범위 구별 |

scope는 all(기본 생략), korea, outside, unknown이다. filters는 profile의 name, taxonomy의 scientific_name 또는 name(둘 중 하나), observations의 limit(1~10)·taxon_key·scientific_name·place·observed_from·observed_to, evidence의 limit이다. 본 스크립트는 intent·scope 조합과 대표 필터를 검증하며 관찰 필터의 모든 조합을 전수 생성하지 않는다. `/v1/answers`, `/v1/search`, `/v1/observations`, `/v1/taxa/lineage` 직접 HTTP 호출은 현재 두 화면에서 하지 않으므로 전체 서버 계약 담당 범위에 남긴다.

주요 호환 위험은 POST 자동 slash 리다이렉트, CSRF/인증·Content-Type 변화, DRF 검증 오류와 기존 JSON 오류 형식 차이, null/생략/빈 배열 변화, 지연 enrichment 필드 손실이다. name-relations는 relations 배열 유무를 검사하고, chat은 알 수 없는 disposition을 거절한다. 오류 상태 404/429/503은 UI 고정 문구 선택에 사용하며 서버 detail을 신뢰해 출력하지 않는다. 이것은 소스에서 확인한 위험이며 실제 Django 결함 판정이 아니다.

`/`, `/chat`, `/birds`, `/static/index.html`, `/static/birds.html`, `/static/chat.js`, `/static/birds.js`, `/static/styles.css`를 유지한다. HTML/CSS/JS는 `Cache-Control: no-cache, must-revalidate`, JS `application/javascript`, CSS `text/css`, HTML `text/html`이며 HTML은 내용 해시 query로 JS/CSS URL을 버전 관리한다. 아이콘은 optional 404가 가능하고 TEST 전용 파란 아이콘 대체가 있으므로 아이콘 바이트 동등성은 강제하지 않는다. 정적 허용 목록 바깥 및 encoded traversal은 404로 차단해야 한다.

## 변경 내용·전후 동작

신규 `scripts/check_ui_migration_contract.py`는 Python 표준 라이브러리만 사용하고 두 fixture 서버를 외부 HTTP로 비교한다. 기존 앱/UI 동작 변경은 없다. 95개 사례에서 상태 코드·Content-Type·Cache-Control·Location, JSON 전체(값·중첩·null·빈 배열·오류 포함), UI 자산 바이트, encoded traversal을 검사한다. 리다이렉트는 따라가지 않으며 실패는 JSON problems와 종료 코드 1로 반환한다. 통신 실패도 사례 실패로 기록한다. 전송 전 양쪽 `/health`가 mode=fixture인지 검사해 live DB 모드에 chat 요청을 보내지 않는다.

이 검사는 차이 탐지기다. 동일한 잘못된 응답이나 양쪽 동일한 503을 성공 기능으로 인증하지 않는다. fixture의 종/핸들러 가용성이 같아야 하고 실제 종 데이터·DB·n8n 검증을 대체하지 않는다. JSON 값까지 엄격 비교하므로 시각 등 비결정 필드가 추가되면 두 런타임에서 시간을 고정하거나 명시적인 계약 결정을 내려야 한다. 자동으로 차이를 숨기지 않는다.

## 실행 명령·실제 결과

- `python3 scripts/check_ui_migration_contract.py --self-test`: 통과. 동일 JSON, 필드 삭제/null 손실, POST redirect, traversal 성공 응답 거절, intent 포함 여부를 assert로 확인했다. 실제 HTTP/DB 검증이 아닌 검증기 자체의 모의 입력 확인이다.
- `python3 -m py_compile scripts/check_ui_migration_contract.py`: 통과.
- `node --test ../dev-codex/tests/frontend/*.test.js`: canonical 루트 기존 검사 **317 통과, 0 실패, 0 건너뜀**. Node 가짜 DOM/fixture 검사이며 실제 브라우저 검증이 아니다. 실행 출력 `/tmp/rg701-ui-frontend.txt`는 임시 산출물이다.
- `graphify update .`: 성공, 5,218 nodes / 10,783 edges / 297 communities. 5,000 nodes 초과로 집계 HTML 생성. 경고: SQL parser 미설치로 SQL 4개 미추출, 심볼 없는 코드 7개, 분류 불가 파일 25개 제외. graphify 생성물은 ignored 상태이며 통합 대상은 아니다.
- 두 서버 실측 비교는 **미실행**: 이 dispatch에서 런타임 시작·설정은 총괄 소관이고 원본·후보 fixture origin을 전달받지 않았다. 서비스 시작/재시작을 하지 않았다.

총괄이 동일 fixture 두 런타임을 준비한 뒤 다음 명령을 실행한다. 포트는 실제 준비한 값으로 지정하고 JSON 증거를 저장한다.

```sh
python3 scripts/check_ui_migration_contract.py http://127.0.0.1:18001 http://127.0.0.1:18002 > /tmp/rg701-ui-http-contract.json
```

## 기존 브라우저 실행 경로와 남은 검증

canonical 루트의 `docs/verification/assets/2026-10-14-local-test/full-browser.cjs`는 Playwright Chromium 기반이며 `QA_BASE_URL`, `QA_OUTPUT`을 지원한다. 현재 `/tmp/robingraph-browser-qa/node_modules/playwright/package.json` 존재를 확인했다. 예시 실행은 다음과 같다(본 dispatch에서는 실행하지 않음).

```sh
QA_BASE_URL=http://127.0.0.1:18002 QA_OUTPUT=/tmp/rg701-ui-browser NODE_PATH=/tmp/robingraph-browser-qa/node_modules node docs/verification/assets/2026-10-14-local-test/full-browser.cjs
```

이 워크플로는 1280/390/320 폭, 카드 탐색·비교·생태·아종·통칭, chat 경로, birds 페이지, JS/HTTP 오류를 검사한다. 과거 데이터에 종속된 기대값은 현재 fixture와 맞는지 먼저 확인한다. `docs/verification/assets/2026-10-19-rg406-outside/browser.cjs`는 최신 scope·외국 조류 후보 확인용이나 TEST URL이 하드코딩되어 있어 fixture 재사용 시 총괄이 복사본에서 URL을 바꿔야 한다. `2026-10-18-scope-layout/browser-layout.cjs`도 분포 범위 UI 배치의 기존 검증 자산이다. 이 파일들을 이번에 수정하거나 실행하지 않았다.

새 Django 런타임에 실제 브라우저로 Enter 전송·Shift+Enter 줄바꿈·한국어 IME 확정키 미전송·focus 복귀, dialog Escape/Tab/focus 복원, scope 변경 중 요청 취소·초안 보존·오래된 카드 무시, PC 드래그·터치 스와이프, 320/390 폭 넘침, prefers-reduced-motion을 재확인해야 한다. Node 검사 통과를 물리 기기·Safari·Firefox 통과로 표현하지 않는다. 이 dispatch에서는 브라우저·물리 모바일·Safari·Firefox·실제 DB/API·TEST 배포 검증을 모두 미실행했다. 독립 API adapter 검토는 후속 별도 dispatch 대상이다.

## 배포·커밋·후속

DB 쓰기, 서비스 시작/재시작, 배포, commit/push/병합, Obsidian 쓰기 없음. 신규 스크립트와 이 기록만 총괄이 검토·통합한다. 기존 미커밋 변경은 보존했다. Production 승인은 요청하지 않았고 운영 작업도 하지 않았다. 이번 완료 범위는 소비 계약 기준선·재사용 검증기·기존 워크플로 확인이며 RG-701 전체 완료를 뜻하지 않는다.
