# Obsidian MCP 설정 복사와 하위 에이전트 재시작

## 요청 배경과 목표

세 에이전트의 Obsidian MCP 미연결을 확인한 뒤, 사용자가 원격 Mac mini의 Codex 설정을 현재 PC에 복사하도록 요청했다. 이어 Claude와 Antigravity에도 같은 설정을 추가하고 두 하위 세션을 재시작하도록 요청했다. 원격 접속·로컬 설정 변경·하위 세션 재시작과 실제 읽기 검증이 범위다. 인증 정보는 이 문서에 포함하지 않는다.

## 원인과 확인 근거

초기 Codex에는 Obsidian 도구가 없었고 로컬 MCP 등록도 없었다. Claude와 Antigravity도 각자 현재 도구와 설정을 확인하여 미연결을 보고했다. 원격 Mac mini는 SSH 접속에 성공했고 Apple M4·32GB, Obsidian 설치 및 보관함 1개 등록을 확인했다. 원격 Codex 설정에는 HTTPS 서버를 사용하는 obsidian_vault 항목과 인증 헤더가 있었다. 로컬 파일 경로나 SSH 터널에 의존하는 구성이 아니므로 기존 HTTPS 접속 방식을 복사했다.

## 변경 파일과 전후 동작

- ~/.codex/config.toml: 원격의 obsidian_vault 본 절과 http_headers 절만 추가했다. 시작 제한 30초·도구 제한 300초를 유지하고 다른 설정을 보존했다.
- ~/.claude.json: 사용자 범위 mcpServers.obsidian_vault에 HTTP 서버 URL과 동일한 헤더를 추가했다. 기존 사용자·프로젝트·로그인 설정은 유지했다.
- ~/.gemini/config/mcp_config.json: agy mcp add 명령으로 HTTP MCP를 등록했다. agy mcp enable로 활성화도 확인했다.
- ~/.gemini/antigravity-cli/settings.json: 변경 전 백업을 만들었다. 도구 실행의 영구 자동 승인을 추가하지 않았다.

Codex 설정은 config.toml.backup-obsidian-20261015-113058, Claude와 Antigravity 관련 기존 파일은 각 파일명의 .backup-obsidian-20261015-121450 사본으로 백업했다. 백업과 직접 수정한 민감 설정 파일은 소유자만 읽고 쓸 수 있게 했다. 원격 전체 설정을 잠시 받은 임시 파일은 필요한 절만 복사한 후 삭제했다. 인증 헤더는 Git이나 작업 문서에 넣지 않았다.

기존 두 에이전트 터미널이 대기 중임을 읽어 확인한 뒤 Orca terminal close로 해당 터미널만 종료했다. 일반 셸 터미널은 유지했다. 동일 워크트리에서 Claude는 --continue와 기존 권한 모드로, Antigravity는 agy --continue로 다시 실행했다. 두 새 터미널 모두 tui-idle 대기 결과 satisfied=true를 확인한 후 검증 지시를 전달했다. 이전 대화를 이어받은 화면도 확인했다.

## 검증 방법과 실제 결과

- codex mcp list: obsidian_vault가 enabled로 표시됐다.
- 복사한 설정으로 MCP initialize, tools/list 및 vault(action=list, pageSize=1)를 직접 호출했다. 인증 성공·도구 8개·보관함 읽기 성공을 확인했다. 이는 Python HTTP 클라이언트의 실제 서버 호출이며 현재 Codex 대화에 MCP 도구가 동적으로 노출됐다는 뜻은 아니다.
- 최초 Python 기본 User-Agent 호출은 HTTP 403이었다. 식별 가능한 Codex-MCP-Connection-Check/1.0 User-Agent로 다시 호출해 초기화·도구 목록·보관함 읽기에 성공했다. 첫 실패와 수정 후 성공을 구별한다.
- claude mcp list: obsidian_vault Connected를 확인했다. 재시작된 Claude 세션은 mcp__obsidian_vault__vault(action=list, pageSize=1)를 실제 호출하고 성공·session_connected=yes를 보고했다.
- Claude와 Antigravity 설정의 헤더 값은 로컬 Codex 원본과 메모리에서 비교해 동일함을 확인했다. 비교 시 값을 출력하지 않았다.
- 재시작된 Antigravity에서 obsidian_vault/vault 도구 노출과 호출 승인 화면을 확인했고, 요청 범위인 읽기 1회만 승인했다. 이후 call_mcp_tool 경유 vault(action=list, pageSize=1) 성공과 session_connected=yes 보고를 터미널 및 /tmp/robingraph-obsidian-restarted-antigravity.txt에서 확인했다.
- 저장소 git diff --check는 통과했다. 민감한 사용자 설정 파일은 저장소 밖에 유지했다.
- Antigravity가 제안한 사용자 설정 폴더 전체 grep은 인증 헤더를 출력할 수 있어 실행을 취소했다. 대신 현재 MCP 도구를 직접 사용하도록 지시했다. 추가 권한 요구를 사용자에게 넘기지 않고 이미 승인된 읽기 검증 범위에서 처리했다.

로컬 결과 증거는 /tmp/robingraph-obsidian-restarted-claude.txt 및 각 터미널의 실제 도구 호출 기록이다. 임시 파일은 영구 보관을 보장하지 않는다. 노트 본문·파일명은 이 문서에 기록하지 않았다. 노트 생성·편집·삭제는 하지 않았다.

## 배포·커밋·한계와 후속 사항

앱 코드 수정, 단위·통합·브라우저 테스트, TEST/Production 배포, 서비스 컨테이너 재시작, DB 변경, commit/push/병합은 수행하지 않았다. 변경은 에이전트 설정과 로컬 세션뿐이므로 앱 테스트와 Graphify AST 갱신은 해당하지 않는다. Obsidian 문서 작성은 요청되지 않아 하지 않았다.

현재 이 Codex 대화 자체는 재시작하지 않았다. 설정 파일과 직접 MCP 호출은 검증했지만 새 MCP 도구를 이 대화에서 쓰려면 Codex 세션 재시작이 필요하다. 사용자가 요청한 하위 Claude·Antigravity 세션은 재시작했다.

Claude가 서버 응답의 내부 HTTP 바인딩 경고를 보고했다. 클라이언트가 사용한 주소는 HTTPS이며 내부 프록시·TLS 종료 구성은 이번에 조사하지 않았으므로 종단 전체가 평문이라고 단정하지 않는다. 원격 서버 네트워크·플러그인 설정은 변경하지 않았다.
