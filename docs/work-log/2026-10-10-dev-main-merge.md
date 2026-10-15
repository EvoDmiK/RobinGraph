# dev → main 병합 — 2026-10-10

## 요청과 목표

사용자가 오늘 수정한 내용을 main 브랜치에 병합하도록 요청했다. 이미 TEST와 Production에서 검증한 카드 수정, 그 근거 및 배포 기록을 기본 브랜치에서도 확인할 수 있도록 한다. 새로운 기능 구현이나 서버 재배포 요청은 아니다.

## 병합 전 확인과 범위

현재 작업 공간은 dev이며 main은 `/Volumes/Dove-Nest-SSD/projects/RobinGraph`의 기존 worktree에서 체크아웃되어 있었다. 두 작업 공간의 git status가 깨끗함을 확인했다. `git fetch origin` 후 main과 origin/main은 동일했고, main에만 있는 커밋 0개·dev에만 있는 커밋 15개였다. 따라서 충돌 해결이나 커밋 재작성 없이 fast-forward가 가능한 상태였다.

병합 전 main은 `123c35c`, dev는 `5aee641ff1b64cc654ea02001fb94774a0e98747`이었다. dev 전체 병합에는 오늘 작업뿐 아니라 전날 운영 반영 후 아직 main에 들어가지 않은 변경도 포함된다. 이 범위를 사용자에게 알리고 요청한 브랜치 병합을 진행했다.

주요 포함 항목:

- 카드 뒷면 토글을 열어도 카드 배율·너비가 유지되도록 수정한 `05ebc61`.
- 토글에 따른 소재 빛 무늬 이동을 막는 `a7f5e63`, 소재 레이어를 카드 안으로 자르고 반복 경계를 없앤 `3ac07e2`.
- 운영 이미지 승격과 실제 PC/모바일·픽셀 검증 기록 `5aee641` 및 관련 상세 문서·검증 JSON.
- 이전 카드 사진 확대·모바일 비율 자료 박스 정렬 `a2c8bcc`, 보전 등급 출처 연결 및 전종 검토 변경과 운영 DB 이관 기록.

전체 범위는 69개 파일이며 대다수 추가 줄은 검증 JSON이다. 인증 정보·환경 파일은 이번 병합에 새로 추가하지 않았다.

## 실제 수행과 결과

main의 기존 worktree에서 `git merge --ff-only dev`를 실행했다. main이 `123c35c`에서 `5aee641`로 이동했고 충돌 0개, 새 merge commit 0개였다. 앱 코드를 다시 편집하거나 cherry-pick하지 않았으며 dev의 기존 커밋 이력을 그대로 유지했다.

`git push origin main` 성공 후 `git ls-remote origin refs/heads/main refs/heads/dev`로 원격 두 브랜치가 모두 `5aee641ff1b64cc654ea02001fb94774a0e98747`임을 확인했다. 병합 직후 두 브랜치 tree ID는 `08b76734af59f224cf7a5b22096140e21e9c6184`로 동일했다. `git diff --check HEAD`도 통과했다.

이 병합 작업 문서를 dev에 별도 커밋한 뒤 main도 같은 문서 커밋으로 fast-forward하고 두 원격 브랜치를 함께 push한다. 앱 변경 없이 기록만 추가하는 단계다. 최종 원격 두 브랜치와 작업 공간 상태는 채팅 완료 안내 전 다시 확인한다.

## 검증 범위와 구분

이번에는 앱 코드의 의미가 바뀌지 않는 fast-forward 병합이며 이미 검증된 dev와 main의 tree 일치를 실제 확인했다. 따라서 Node 298검사나 실제 DB/API 브라우저 부하를 불필요하게 다시 실행하지 않았다. 오늘 선행 작업에서 실행한 Node 298 통과, PC/모바일 토글 18사례·60개 검사, 소재 팔레트 18사례와 운영 서버 검증은 아래 원문을 근거로 유지하며 이번에 재실행한 것으로 표현하지 않는다.

- `docs/work-log/2026-10-10-card-toggle-stable-scale.md`
- `docs/work-log/2026-10-10-card-material-toggle-stability.md`
- 전날 데이터/보전 변경: `docs/work-log/2026-10-09-approved-production-pg-sync-and-deploy.md`와 관련 전종 감사 문서.

main 작업 공간에서 `graphify update .` 실행을 완료했다(exit 0). SQL parser dependency 부재 및 커뮤니티 이름 갱신 안내 경고는 있었으며 앱 병합 실패와 구분한다. 문서 변경만 추가한 뒤 앱 테스트를 중복 실행하지 않는다.

## 배포·한계·문서 보관

이번 브랜치 병합에서는 NAS 배포, DB 마이그레이션, 자료 수집을 실행하지 않았다. 운영에는 앞서 검증·배포한 `3ac07e2` 이미지가 이미 반영되어 있으며 브랜치 병합으로 앱을 재빌드하지 않았다. GitHub CI의 새 실행 완료 여부는 이번 작업에서 조회하지 않았으므로 CI 통과를 주장하지 않는다. 해결되지 않은 데이터 항목은 기존 감사 문서에 계속 남으며 병합 자체로 해결되는 것이 아니다.

Obsidian `Work/RobinGraph/작업기록/2026-10-10-dev-main-병합.md`에 같은 본문을 저장하고 프로젝트·작업기록 index에 연결한다. 저장 후 원문과 index를 다시 읽어 일치를 확인한다. dev 작업 공간은 dev 브랜치를 유지하고 기존 main 작업 공간을 이용한다.
