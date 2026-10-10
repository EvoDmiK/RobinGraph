# dev-codex → main UI 변경 병합

## 요청·배경·목표

사용자가 브랜치에 커밋된 파일 46개 목록을 확인하고, push 여부 설명 이후 “응 main에도 merge 시켜줘”라고 요청했다. dev-codex의 최근 답변·비교·출처·탐색 UI와 검증 문서를 main에 반영하고 원격 main까지 올리는 작업이다. 운영은 직전 승인 배포로 이미 해당 UI가 적용되어 있으며 이번 요청은 Git 병합이다.

## 사전 확인과 방식

origin을 fetch했다. dev-codex와 origin/dev-codex는 90e9b00, main과 origin/main은 8db363b였으며 양쪽 작업 트리가 깨끗했다. origin/main...dev-codex의 좌우 커밋 수는 0·17로 main이 dev-codex의 조상임을 확인했다. 따라서 충돌 해결이나 별도 merge commit 없이 --ff-only로 17개 커밋을 반영했다.

main은 `/Volumes/Dove-Nest-SSD/projects/RobinGraph`의 기존 작업 트리에서 사용 중이라 해당 경로의 main을 갱신했다. 현재 작업 공간은 dev-codex를 유지한다. 새 브랜치·작업 트리를 만들거나 기존 브랜치를 삭제하지 않았다.

## 반영 내용과 변경 전후

첫 fast-forward에서 main이 8db363b → 90e9b00으로 이동했다. 46개 파일, 5859줄 추가·51줄 삭제이며 JS/CSS 구현과 frontend 회귀, 검증 JSON·상세 작업 문서가 포함된다. 국명 옆 작은 영문명·사진 미리보기, 먹이 답변 타일과 profile 탐색 통일, 비교 도감 버튼 가로 배치, 비교값 중복 제거·출처 통합·kg 단위, 비교 하단 정리와 출처 카드, 네 탐색 버튼 크기 통일, 근연 관계 화살표 제거가 포함된다. 개별 원인·구현·실제 TEST/운영 검증은 각 작업 문서에 보존되어 있다.

이번 병합에서는 추가 런타임 구현이나 데이터 변환을 수행하지 않았다. 이 기록 문서를 후속 dev-codex 커밋에 저장한 뒤 main에도 fast-forward하여 두 브랜치가 같은 최종 내용을 갖도록 한다.

## 검증과 실제 결과

병합 후 `git -C /Volumes/Dove-Nest-SSD/projects/RobinGraph diff --exit-code dev-codex`가 종료 코드 0으로 main과 dev-codex의 파일 내용 일치를 확인했다. 동일한 dev-codex 파일 트리에서 `node --test tests/frontend/*.test.js`를 실행해 303개 통과, 실패·취소·건너뛰기 0이었다. 이는 fake DOM·단위 회귀이며 새 실제 DB/API 검증으로 계산하지 않는다. main의 동일 코드에 중복 테스트를 추가 실행하지 않았다.

첫 병합 결과 origin/main push 성공을 확인했다. 문서 후속 반영 후 양쪽 원격 브랜치의 HEAD·ahead/behind·작업 트리 상태를 다시 확인한다. 충돌이나 건너뛴 커밋은 없었다. 코드 자체는 이전 작업에서 graphify update를 완료했으며 이번에는 Git 참조와 문서만 갱신했다.

## 배포·문서·한계

이번 작업에서 NAS 배포·운영 재시작·DB 마이그레이션은 하지 않았다. 직전 사용자 승인 배포의 운영 이미지 prod-approved-ui-0681747 상태에 새 변경 작업을 실행하지 않았다. 상세 작업 기록은 저장소와 Obsidian 작업기록에 동일 본문으로 기록한다. 기존 dev·dev-claude 브랜치 내용은 변경하지 않는다.

전체 backend 테스트·새 브라우저 실행·물리 모바일 검증·GitHub CI 결과 확인은 이번 병합 검증 범위에 포함하지 않았다. 최근 UI의 실제 TEST/운영 검증은 이전 기록에서 확인할 수 있다. main에 추가 개발이 생기면 이후 병합에서는 fast-forward가 가능하지 않을 수 있어 다시 최신 원격과 충돌 여부를 확인해야 한다.
