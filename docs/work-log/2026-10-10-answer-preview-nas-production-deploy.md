# 국명·영문명 병기와 답변 사진 미리보기 NAS TEST·운영 배포

## 요청과 승인 범위

사용자가 구현 완료 안내 후 배포를 요청했다. 앞선 영문명 병기와 사진 미리보기 구현 커밋 `0df2b1b236252fa7b4b7083565440f5e6b220cdd`를 NAS TEST에서 먼저 검증한 다음 동일 이미지를 Production에 승격했다. 이번 배포 승인은 이전의 운영 보류 지시 이후 명시적으로 제공된 것이다. DB 이관이나 수집, main/dev 병합은 요청 범위에 포함하지 않았다.

## 배포 전 상태와 변경 동작

배포 전 TEST/PROD는 `3ac07e2` 카드 토글·소재 안정화 이미지였다. 새 앱은 답변 제목에서 국명 옆에 작은 영문명을 표시하고, 일반 종 소개 오른쪽 위의 작은 사진 버튼에서 기존 도감 카드를 연다. 사진이 없는 종과 이미지 실패는 자리표시자로 처리한다. 추가 사진은 기존 `더 알아보기` 흐름을 유지하고 받아온 사진으로 미리보기를 갱신한다. 처음부터 사진 조회를 자동 시작하지 않는다.

제품 코드 변경·원인·예외 처리·로컬 299개 회귀 및 20개 브라우저 사례는 `2026-10-10-answer-bilingual-heading.md`와 `2026-10-10-answer-photo-preview.md`를 따른다. 이번 단계는 그 변경의 실제 서버 반영이다.

## 패키징과 환경 보존

표준 `scripts/package_nas_release.sh --ref 0df2b1b --output-dir /tmp/rg-answer-preview-release`로 커밋의 런타임 허용 목록만 묶었다. 환경 파일·인증 정보는 패키지에 포함하지 않았다. 아카이브 SHA-256은 `312b0b3564786fd4bb631673a9c6af02e12b670030ef47b8ae7d2e82b8ba4106`이다. NAS에서 아카이브와 embedded MANIFEST의 파일별 해시를 모두 검증했다.

SCP의 기본 전송은 Connection closed로 실패해 실제 배포 작업은 시작되지 않았다. 이미 동작하는 SSH 세션으로 아카이브 바이트를 전송해 해결했다. 인증 정보는 출력하거나 문서에 기록하지 않았다.

기존 TEST/PROD 환경 파일을 NAS 안에서 복사해 보존하고 이미지 태그·VCS revision만 새 값으로 바꿨다. TEST PostgreSQL DB는 `robingraph_test`, PROD는 `robingraph`임을 검사했다. 새 릴리스 디렉터리는 `/home/kimdove/RobinGraph-answer-preview-0df2b1b`와 `/home/kimdove/RobinGraph-prod-answer-preview-0df2b1b`이다.

## TEST 배포와 운영 승격

TEST에서 표준 preflight → deploy(이미지 빌드 및 API 교체) → verify를 통과했다. Docker Compose의 buildx 미설치 경고가 있었으나 기존 classic builder로 이미지 빌드와 배포가 정상 완료됐다. uv는 기존 lockfile의 고정 버전을 설치했다.

- TEST 이미지: `robingraph-api:test-answer-preview-0df2b1b`.
- PROD 이미지: `robingraph-api:prod-answer-preview-0df2b1b`.
- 공통 이미지 ID: `sha256:0ce313b46e8c04aeda547fd52d6350028cf1e2e824a4106d1dff8589cb0d83df`.
- TEST 시작: `2026-10-10T04:45:53.838375138Z`.
- PROD 시작: `2026-10-10T04:47:15.110774265Z`.
- 검증 당시 양쪽 컨테이너 healthy, restart count 0.

TEST 공개 자산·실제 API와 브라우저 검증 후 이미지 ID를 재확인했다. 동일 ID에 운영 태그를 붙이고 `docker compose up -d --no-build api`로 운영 API만 교체했다. Production에서 preflight·health·표준 verify와 TEST 이미지 ID 일치를 확인했다. 운영에서 재빌드하거나 DB를 교체하지 않았다. 이전 `prod-material-3ac07e2` 이미지를 보존하고 실패 시 rollback 경로를 준비했으며 배포가 정상 완료돼 사용하지 않았다.

## 실제 검증 결과

1. TEST와 Production 공개 `/static/chat.js`·`/static/styles.css`가 로컬 커밋의 파일 바이트와 일치했다. 실제 `/health`의 대상은 각각 test/prod이며 neo4j 모드다. 양쪽 실제 POST `/v1/chat`의 청둥오리 질문에서 disposition answer, Anas platyrhynchos, 영문명 Mallard를 확인했다.
2. 각 서버의 배포 자산으로 320·390·768·1280px × 실제 프로필·사진 없음·위험 URL·이미지 실패·추가 자료 대기 5사례 = 20개씩, 총 40개 브라우저 검사 통과. 채팅 POST는 실제 서버에서 가져온 프로필을 재생했으므로 이 단계의 주 목적은 배포 UI 회귀다. 실제 프로필 설정에서는 이미지가 완전히 로드돼 naturalWidth > 0임을 확인했다. 예외 자료는 모의 상태다. 키보드 카드 진입·닫기 후 포커스 복원·가로 넘침 없음·사진과 요약 배치·페이지 오류 0을 확인했다.
3. 별도로 POST를 가로채지 않은 실제 채팅 UI를 TEST/PROD 각각 390·1280px에서 실행했다. 질문 전송 → Mallard 병기 → 더 알아보기 → 실제 이미지 로드 → 도감 카드 열기 → 닫기까지 **4개 실제 흐름 모두 통과**했다. 페이지 오류 0이며 서버 데이터·사진의 지연 갱신 callback까지 검증했다.

증거 파일은 `docs/verification/assets/2026-10-10-answer-photo-preview-test-deployed.json`, `2026-10-10-answer-photo-preview-production.json`, `2026-10-10-answer-preview-test-assets.json`, `2026-10-10-answer-preview-production-assets.json`, `2026-10-10-answer-preview-live-chat.json`이다. 실제 화면은 `/tmp/rg-answer-names-browser/live-{test,prod}-{390,1280}.png`에 남겼다.

배포 단계에서 코드가 추가 변경되지 않아 로컬 299개 회귀를 반복하지 않았다. 전체 종 HTTP·물리 모바일 기기·Safari·전체 백엔드 테스트·새 CI는 이번에 확인하지 않았다. 사진을 아직 조회하지 않은 첫 응답은 준비 전 표시일 수 있으며, `더 알아보기` 이후 작은 사진과 카드가 같이 갱신된다. 이를 모든 첫 응답에 사진이 즉시 제공되는 것으로 안내하지 않는다.

## 문서·Git·후속 사항

배포 앱의 revision은 `0df2b1b`이며 상세 작업 기록과 검증 JSON은 후속 문서 커밋으로 dev-codex에 push한다. 앱 코드와 배포 이미지는 문서 커밋 때문에 재빌드하지 않는다. main/dev 병합은 별도 지시를 따른다. 같은 상세 기록을 Obsidian 작업기록에도 저장하고 원문 일치 여부를 확인한다. 새 개인정보·자격 증명은 문서·검증 JSON에 포함하지 않는다.
