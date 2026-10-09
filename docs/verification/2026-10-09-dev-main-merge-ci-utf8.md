# dev → main 병합과 Windows CI UTF-8 보완

- 작업일: 2026-10-09
- 요청: 완료한 개발 작업을 main 브랜치에 병합한다.

## 대상·범위와 병합 전 상태

dev 작업 디렉터리는 `/Volumes/Dove-Nest-SSD/app-data/orca/kimdove/home/workspaces/RobinGraph/dev-3`, 기존 main worktree는 `/Volumes/Dove-Nest-SSD/projects/RobinGraph`다. 두 worktree 모두 미커밋 변경이 없었다. origin을 fetch한 후 main/origin/main은 `834ddd28c12bda819209be3cda715076d773ffce`, dev/origin/dev는 `b4049cb8cff8cb26622c3d834f9fe21dba2779ba`였다. main 전용 커밋0·dev 전용109로 main이 dev의 조상이었다.

병합은 지금까지의 dev 변경 전체를 대상으로 한다. 분류·국명/아종·계통/생태 관계 검색, Jev 질문 의도 분석, LangChain/MLflow 관측과 응답 결과 구분, PC/모바일 조류 카드 UI 및 검증 기록이 포함된다. 이전 TEST 배포 완료 기능을 main에 통합하는 작업이며 새 백로그 기능에 착수하는 요청으로 확대하지 않는다.

main은 보호 브랜치가 아니고 추가 PR/merge 의무 규칙은 없었다. 기존 main worktree를 그대로 사용해 fast-forward 병합했다. 브랜치 삭제·강제 푸시·기존 커밋 재작성은 하지 않는다. `.github/workflows/ci.yml`은 push/pull_request의 테스트와 Docker 빌드만 실행하며 NAS 자동 배포는 없다.

## 발견한 CI 실패·원인·보완

병합 점검 중 dev의 [기존 CI 실행37877070049](https://github.com/EvoDmiK/RobinGraph/actions/runs/37877070049)가 실패한 사실을 확인했다. Windows fixture만633개 실행 중 errors3/skipped46이었고 Ubuntu·macOS·프런트·Neo4j·PostgreSQL·Docker의 나머지6개 작업은 통과했다.

세 테스트는 UTF-8로 저장된 한국어 JSON을 Path.read_text()의 기본 인코딩으로 읽었다. Windows Python3.12 CI의 기본 cp1252에서는 각각0x9d·0x81·0x90 바이트에서 UnicodeDecodeError가 발생했다. 다음 세 줄에만 encoding='utf-8'을 명시했다.

| 파일 | 기존 실패 테스트 |
|---|---|
|tests/test_korean_display_names.py|test_snapshot_sources_crosswalks_and_split_species|
|tests/test_subspecies_name_references.py|test_domesticated_form_names_do_not_become_wild_subspecies_names|
|tests/test_subspecies_ranges.py|test_build_rejects_changed_source|

검증 assertion·JSON 자료·해시·줄바꿈 규칙·제품 코드와 CI 실행 환경은 바꾸지 않았다. 인코딩 오류를 건너뛰거나 Windows의 기본 인코딩을 전역으로 강제하지 않는다. 보완 커밋은 `969f332e4a5c48cda9aecaac06360fbd54c7595c`이며 origin/dev에 push했다.

## 협업과 로컬 검증

pc_drag_popup_fix가 세 테스트 보완, 일반/기본 cp1252 모의 대상 검증, graphify를 담당했다. card_selection_review는 읽기 전용으로 workflow·병합 규칙·CI 실패와 최종3줄 diff를 검토했다. root는 원격 CI 확인·전체 로컬 테스트·main 병합/푸시·문서/Obsidian을 담당했다. 독립 검토에서 변경이 필요한 차단 문제는 없었다.

- 세 모듈 일반 실행:36개 중34통과·조건부 건너뜀2·실패/오류0.
- Path.read_text 기본값을 cp1252로 모의한 동일 세 모듈:36개 중34통과·조건부 건너뜀2·실패/오류0. 실제 Windows 실행과 구분한다.
- `PYTHONPATH=src /tmp/rg010-venv/bin/python -m unittest discover -s tests -v`:633개 중598통과·건너뜀35·실패/오류0. 로컬 Python3.14.5 환경이며 원격 locked Python3.12와 구분한다. 건너뜀35는 DB opt-in/전용 환경33과 pinned 원본 파일 부재2다. 로컬 실행을 실제 DB 검증으로 합산하지 않는다.
- git diff --check 통과.
- graphify update .를 dev와 병합한 main worktree에서 수행했다. AST 갱신 결과3854노드·8186간선·237커뮤니티이며, main은399/399개 코드 파일을 추출했다. 기존 SQL parser 미설치4/no-symbol2 안내가 있고 의미 추출 API는 호출하지 않았다.

[검증 증거](assets/2026-10-09-main-merge-verification.json)에 대상 커밋·원격 refs·각 CI 작업·실제 테스트 합계를 기록한다. 인증/환경파일 내용은 기록하지 않는다.

## 실제 GitHub CI 결과

보완 커밋의 [CI 실행37877644541](https://github.com/EvoDmiK/RobinGraph/actions/runs/37877644541)은 **7개 작업 모두 success**였다. 이 커밋이 main으로 들어가는 제품/테스트 내용이다.

| CI 작업 | 실제 결과 |
|---|---|
|Fixture Ubuntu|633실행,587통과·46건너뜀·실패/오류0|
|Fixture Windows|633실행,587통과·46건너뜀·실패/오류0|
|Fixture macOS|633실행,587통과·46건너뜀·실패/오류0|
|Frontend contract|chat_ui.test.js 245통과·실패0·건너뜀0|
|Neo4j integration|633실행,610통과·23건너뜀·실패/오류0; CI 일회용 Neo4j 포함|
|PostgreSQL ingest integration|실제 CI 일회용 PostgreSQL9통과·실패0·건너뜀0|
|NAS Docker image|Compose 검증·이미지 빌드 성공|

원격 fixture 환경의46건너뜀과 로컬35건너뜀을 혼동하지 않는다. optional tracing 의존성과 통합 DB opt-in 조건이 다른 환경이다. 실제 DB 검증은 위 CI의 Neo4j/PostgreSQL 작업이며 NAS 운영/TEST DB 전수 검증이라는 의미는 아니다. 이전 UI 작업의248개 프런트 검증과 달리 현재 CI workflow는 chat_ui 파일만 실행하므로245개다. 테스트를 삭제한 결과가 아니다.

## 병합·푸시 결과

CI7개 성공을 확인한 뒤 기존 main worktree에서 `git merge --ff-only origin/dev`를 실행했다. 충돌0·자동 내용 수정0의 fast-forward이며, main은834ddd2에서969f332로 이동했다. 처음 비교한109개와 인코딩 보완1개를 합한110개 커밋을 통합했다. `git push origin main`이 성공했고 main/origin/main/dev/origin/dev 네 ref가 전체 커밋969f332와 같은 것을 확인했다. 별도 merge commit이나 PR은 만들지 않았다.

이 기록을 추가하는 문서 커밋도 dev에 저장하고 main으로 fast-forward해 두 브랜치에 함께 남긴다. 작업 디렉터리는 dev 브랜치를 유지하고 기존 main worktree도 보존한다. 최종 원격 refs 일치와 두 worktree의 깨끗한 상태를 확인한다.

## 배포·남은 한계·백로그

이번 작업에서 NAS 배포·DB/환경파일 변경은 수행하지 않았다. 알려진 NAS TEST 제품 소스는 직전 `3e639ce51d9c247a244a2451adcb2a2e9da60a67`이며 이번 추가 소스 변경은 테스트 인코딩3줄뿐이다. main 푸시의 Docker CI 빌드를 실제 NAS 배포로 기록하지 않는다. PROD 배포도 하지 않았다.

Windows는 GitHub runner에서 실제 검증했으며 로컬 물리 Windows 장비는 사용하지 않았다. pinned 원본 자료 부재·선택 의존성/전용 DB가 필요한 조건부 검증의 건너뜀은 표에 그대로 남긴다. RG-405 최종 완료, 신규 대기 RG-202·RG-406, 최후순위 보류 RG-102·RG-503·RG-504·RG-505 상태는 유지한다.
