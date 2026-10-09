# Production 앱 배포 — f71b37b

## 요청과 목표

2026-10-09 TEST → Production DB 재이관을 완료한 뒤 사용자가 Production 앱도 배포하도록 요청했다. DB에 저장되지 않고 패키지 코드에 포함된 보전 등급 참고평가 인덱스·형질 연결·카드 표시까지 Production에 반영하는 작업이다.

대상은 당시 main `f71b37bee3a55e3c992b0a4727b57accd8db1b0c`이다. 이 배포를 기록하는 후속 문서 커밋과 실제 실행 코드 커밋을 구분한다.

## 배포 전후

| 항목 | 이전 | 이후 |
|---|---|---|
| Production 이미지 | robingraph-api:prod-e90ff85 | robingraph-api:prod-f71b37b |
| Production 코드 revision | e90ff85 | f71b37bee3a55e3c992b0a4727b57accd8db1b0c |
| Production 작업 디렉터리 | /home/kimdove/RobinGraph-e90ff85 | /home/kimdove/RobinGraph-prod-f71b37b |
| TEST 이미지 | robingraph-api:test-badge-017a273 | 동일 |
| DB | 직전 TEST → PROD 이관 완료 상태 | 이번 배포에서 추가 복원·변경 없음 |

배포 후 Production·TEST 컨테이너 모두 healthy를 직접 확인했다. Production health의 deployment_target도 prod로 확인했다.

## 준비와 수행

1. 요청 직후 SSH 99번 포트가 연결 거절 상태였다. 사용자에게 SSH 재개를 요청하고 기다리는 동안 main에서 배포 묶음과 검증 도구를 준비했다. 사용자가 열었다고 응답한 뒤 연결을 재확인했다.
2. `scripts/package_nas_release.sh --ref main --output-dir /tmp/rg-prod-f71b37b`로 패키지를 생성했다. 실행 당시 main은 위 전체 revision이다. 실제 비밀 환경파일이 포함되지 않았음을 확인했다.
3. 아카이브 SHA-256은 `6c180f1bbebcac2557d5aa7b4dea9b574e3290fa4c851d83275d8f14b506e2f3`. SSH 표준입력으로 NAS에 전송한 뒤 동일 해시를 검증했다. 포함 파일 125개에 대해 내장 MANIFEST.txt의 개별 해시도 확인했다.
4. 새 디렉터리에 압축을 풀고 기존 Production `.env.nas.prod`만 내부 복사했다. 권한 600을 설정하고 이미지 태그를 prod-f71b37b로 변경했다. TEST DB 주소나 TEST 비밀을 가져오지 않았다. 배포 대상 prod와 VCS revision을 명시했다.
5. 이전 이미지 prod-e90ff85가 NAS에 존재함을 확인했다. preflight가 통과한 뒤 `ROBINGRAPH_DEPLOY_TARGET=prod sh scripts/deploy_nas.sh deploy`로 빌드·컨테이너 교체·health 대기를 수행했다.
6. 배포 스크립트의 verify가 status ok, deployment_target prod를 반환했다. 별도 docker inspect로 실제 이미지·healthy·OCI revision을 재확인했다.

빌드 시작 로그는 2026-10-09 10:07:57 UTC / 19:07:57 KST다. verify 이후 같은 SSH 표준입력 스크립트의 종료 시각 출력이 남지 않아 정확한 종료 초나 사용자 관점 중단 시간을 추정하지 않았다. 별도 요청의 컨테이너 상태·공개 응답 검증으로 완료를 판정했다.

## 반영된 동작

- 전체 종의 보전 등급 연결 상태와 원본 NE를 구분하고, 출처가 확인된 참고평가 360건을 제공한다.
- 참고평가가 있으면 큰부리까마귀처럼 `관심대상 (LC) · 2024 평가 · 참고` 뱃지로 표시한다. 현재 분류 범위와 평가 범위 일치 미확인이라는 설명과 출처는 유지한다.
- 까치의 먹이 구성·먹이 활동 위치 대체 상자를 제목 아래 중앙 정렬한다. 생활 방식은 짧은 구절과 `비율 자료 없음`으로 표시한다.
- 앞선 DB 이관에 포함된 까마귀 → 큰부리까마귀 통칭 관계 제거가 새 앱에서도 유지된다. 패키지 manifest에도 삭제가 반영되어 있다.
- 기존 TEST에서 검증한 형질 연결 복구와 카드 표시 코드를 Production에 포함한다. 이번 배포가 새로운 생물학적 사실 검증을 수행한 것은 아니다.

## 실제 검증

| 검증 | 범위 | 결과 |
|---|---|---|
| 배포 health | 실제 PROD 컨테이너 | healthy, deployment_target prod |
| 배포 canary | 컨테이너 내부 health·openapi·대륙검은지빠귀 계통 | passed·backend_reachable·contract_parity_ok 모두 true |
| 공개 프로필 | 서로 다른 상태·등급을 포함한 11개 요청 | 모두 통과 |
| 정적 파일 | 공개 chat.js·styles.css와 저장소 바이트 해시 대조 | 둘 다 일치 |
| 실제 브라우저 | 까치·큰부리까마귀 × PC/모바일 | 4개 모두 HTTP 200, JS 오류 0 |
| 까마귀 관계 | 실제 Production 공개 API | Corvus corone만 안내 |
| 큰부리까마귀 관계 | 학명으로 역방향 조회 | 빈 관계 목록 |
| Production 파비콘 | 실제 공개 경로 | 응답 수신·해시 기록 |

공개 검증 주소는 `https://robingraph.dove-nest.com`이다. 프로필 11건은 큰부리까마귀(국명·학명), Pica pica, Pyrrhura subandina(CR 참고), Premnoplex tatei(EN), Pionites leucogaster(VU), Pteroglossus bitorquatus(NT), Pica serica, Anser serrirostris, Anas platyrhynchos, Hypsipetes amaurotis를 포함한다. 출처·등급 상태·기존 형질 차트·참고평가 없는 사례를 검사했다.

Chrome 1280×900과 390×844에서 실제 채팅 API를 사용했다. 응답 가로채기·모의 API는 사용하지 않았다. 까치 상자 중심 오차는 PC 0px, 모바일 최대 약 0.000004px이며 내부 text-align·align-items·justify-content가 모두 center였다. 큰부리까마귀 뱃지는 양쪽 화면에서 LC·2024·참고로 확인됐다. PC 큰부리까마귀 스크린샷을 열어 배치와 뱃지를 육안 검토했다.

공개 정적 파일 해시:

- chat.js: `09e6aa9af6fb03b9ebc107de8f07618b4efe9ec63025d1b29161f5a5fa955eb8`
- styles.css: `2139999e09f3f4f9d832250332ccd154a43deb167a29a2705aa0a3fbbc1f8bf1`

이번에는 단위 테스트를 반복 실행하지 않았다. 배포 대상의 관련 변경은 앞선 작업에서 프런트엔드 279개 및 이름 관계 17개 테스트를 통과했고, 이번에는 실제 Production 배포 검증을 수행했다. 모바일은 브라우저 에뮬레이션이며 실기기 검증으로 기록하지 않는다.

## 롤백과 한계

이전 이미지 prod-e90ff85와 이전 Production 설정·디렉터리를 유지했다. 문제가 생기면 새 디렉터리에서 `ROBINGRAPH_DEPLOY_TARGET=prod sh scripts/deploy_nas.sh rollback robingraph-api:prod-e90ff85`로 이전 이미지로 되돌릴 수 있다. 실제 롤백은 실행하지 않았다. 이 명령은 DB를 이전 데이터로 되돌리는 명령이 아니다.

DB 백업과 양쪽 DB 복구 절차는 [직전 DB 재이관 기록](2026-10-09-test-to-prod-migration-r2.md)을 따른다. 보전 등급의 종 범위 미확인과 고정 자료 버전의 한계는 그대로다. 모든 종의 평가 원문을 독립 검증하거나 최신 평가를 실시간 수집했다고 주장하지 않는다.

## 보존한 증거

- [공개 프로필 11건](../verification/assets/2026-10-09-prod-f71b37b-profiles.json)
- [브라우저 4개 시나리오](../verification/assets/2026-10-09-prod-f71b37b-browser.json)
- [공개 health·통칭 관계](../verification/assets/2026-10-09-prod-f71b37b-smoke.json)
- [Production 배포 canary](../verification/assets/2026-10-09-prod-f71b37b-api-verify.json)
- [까치 모바일 화면](../verification/assets/2026-10-09-prod-f71b37b-magpie-mobile.png)
- [큰부리까마귀 PC 화면](../verification/assets/2026-10-09-prod-f71b37b-crow-desktop.png)

인증 정보는 문서·증거에 포함하지 않았다. 이번 저장소 변경은 배포 기록과 검증 증거이며 실행 코드는 f71b37b다.
