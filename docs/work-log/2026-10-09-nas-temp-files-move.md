# NAS 임시 파일 `/volume3`로 이동 — 2026-10-09

## 요청 배경과 목표

오늘 배포·이관 작업으로 NAS 홈(`/home/kimdove`, `/volume1`)에 릴리스 묶음과 체크아웃이 쌓였다. 사용자가 이 임시 파일들을 NAS의 `/volume3/` 아래에 적절히 폴더를 만들어 옮겨 달라고 요청했다.
삭제는 요청 범위가 아니어서 **아무것도 지우지 않고 옮기기만** 했다(비어 버린 임시 폴더 2개만 `rmdir`).

## 확인한 사실 (이동 전, 읽기 전용)

- `/volume3` 루트는 root 소유(`drwxr-xr-x`)라 `kimdove`가 폴더를 만들 수 없다(`touch` 시 `Permission denied`).
- `/volume3/RobinGraph`는 앱 저장소의 작업 트리(`.git` 포함, 10월 2일 생성)다. 임시 파일을 섞으면 git 상태가 지저분해져서 대상에서 제외했다.
- `/volume3/Birds-Nest/backups/`는 `kimdove` 소유(`drwx------`)이고 이미 다른 백업이 모여 있다. Birds-Nest 저장소에서 `backups/`는 untracked 폴더다. 여기에 새 폴더를 만들었다.
- 홈 사용량: 릴리스 tarball 51개, 체크아웃 60개, 이전 세션의 배포 백업 13개, 합계 약 549MB. 디스크 여유는 `/volume3` 390G, `/home` 2.2T.
- 실행 중 컨테이너 2개(`robingraph-api`, `robingraph-api-test`)에는 바인드 마운트가 없고 이미지에서 실행된다. compose 작업 디렉터리 라벨은 둘 다 `/home/kimdove/RobinGraph-e90ff85`, 프로젝트 이름은 `robingraph`, `robingraph-test`로 고정이다.
- 저장소 스크립트와 `compose.nas.yml`, `docs/nas-deployment.md`는 `~/RobinGraph-*` 같은 홈 경로를 참조하지 않는다(검색 결과 없음).

## 이동한 것

대상 폴더 `/volume3/Birds-Nest/backups/robingraph-deploy/`(권한 `700`)

| 하위 폴더 | 내용 | 개수 |
|---|---|---:|
| `releases/` | `~/robingraph-*.tar.gz` 릴리스 묶음(오늘 것과 이전 세션 것 모두) | 51 |
| `checkouts/` | `~/RobinGraph-<태그>` 체크아웃 | 57 |
| `deploy-backups/` | `~/robingraph-deploy-backups/` 안의 이전 배포 백업(2026-10-01) | 13 |
| `neo4j-migration-20261009/` | `prod-pre-migration-20261009.dump`(PROD 이관 전 백업, 92,939,227바이트)와 `test-dump-20261009.dump`(PROD에 로드한 TEST 덤프, 104,719,306바이트) | 2 |

- 이동 합계는 약 706MB. 비어 버린 `~/robingraph-deploy-backups/`와 `…/neo4j/backups/incoming`, `…/neo4j/backups/`는 제거했다(둘 다 이번 작업에서 만든 폴더였다).
- 폴더에 `README.txt`(무엇이 어디서 왔는지, 남긴 체크아웃 설명)를 넣었다.

## 홈에 남긴 것과 이유

| 남긴 체크아웃 | 이유 |
|---|---|
| `~/RobinGraph-e90ff85` | 실행 중인 PROD·TEST 스택의 compose 작업 디렉터리이고 현재 배포의 `.env.nas.prod`·`.env.nas.test`가 있다 |
| `~/RobinGraph-5fb401e` | PROD를 `robingraph-api:prod-5fb401e`로 롤백할 때 쓰는 `.env.nas.prod` |
| `~/RobinGraph-51cecd1` | TEST를 `robingraph-api:test-framefav-51cecd1`로 롤백할 때 쓰는 `.env.nas.test` |

이 세 개는 롤백 명령과 문서가 가리키는 경로(`~/RobinGraph-<태그>`)를 바꾸지 않으려고 홈에 뒀다. 사용자가 원하면 같은 폴더로 옮길 수 있고, 그때는 문서의 롤백 경로도 바꿔야 한다.

## 검증 (실제 실행 결과)

| 항목 | 결과 |
|---|---|
| 이동 후 홈 | tarball 0개, 체크아웃 3개(`51cecd1`, `5fb401e`, `e90ff85`), `robingraph-deploy-backups` 없음 |
| 이동 후 대상 | `releases` 51, `checkouts` 57, `deploy-backups` 13, `neo4j-migration-20261009` 2, 합계 706MB. 이동 전 개수와 일치(체크아웃 60 = 57 + 남긴 3) |
| 권한 | 대상 폴더 5개와 `README.txt`는 소유자 전용(`700`/`600`) |
| 서비스 영향 | 컨테이너 설정·이미지를 건드리지 않았다. 이동 작업은 파일 이동만 수행했고 컨테이너 재시작은 하지 않았다 |

`mv`는 `/volume1`에서 `/volume3`로(다른 파일시스템) 복사 후 삭제하는 방식이다. 모든 개수가 일치함을 확인했지만 파일별 해시 비교는 하지 않았다.

## 발견한 점

- 옮긴 체크아웃의 비밀 값이 있는 `.env.nas.*` 파일 62개 중 22개는 이전부터 `-rwxrwxrwx+`(Synology ACL, 모두 읽기 가능)였다. 새 위치는 폴더가 `700`이라 소유자만 접근할 수 있어 노출이 줄었지만, 파일 자체의 권한과 ACL은 바꾸지 않았다. 홈의 남은 3개 체크아웃의 `.env.nas.*`도 확인하지 않았다.
- PROD 이관 전 백업 덤프는 컨테이너 사용자(uid 7474) 소유라 `kimdove`가 `-rw-r--r--` 파일을 읽을 수 있지만 지우려면 폴더 권한에 의존한다.

## 문서에 반영한 경로 변경

- `test-to-prod-migration`: PROD 이관 전 백업의 새 경로, "정리 필요" 항목을 "정리 완료"로.
- `prod-deploy-3e639ce`: 릴리스·체크아웃의 새 위치와 롤백 경로 주석.
- `favicon`: 롤백에 쓰는 `~/RobinGraph-336d987`의 새 위치 주석.
- 다른 작업 문서의 `~/RobinGraph-<옛 태그>` 언급은 이제 `checkouts/RobinGraph-<태그>`에 있다(오늘의 `5fb401e`·`e90ff85`·`51cecd1` 롤백 명령은 그대로 유효).

## 남은 한계

- NAS의 Docker에는 오늘 만든 `robingraph-api:test-*`·`prod-*` 이미지가 아직 많이 남아 있다. 롤백 대상 태그(`prod-5fb401e`, `test-framefav-51cecd1`)는 필요하므로 지우지 않았고, 정리 여부는 별도로 정해야 한다.
- 이번 이동은 파일 이동뿐이라 TEST·PROD 서비스의 동작과 배포 상태는 확인할 필요가 없었고 확인하지 않았다.
- `/volume3` 루트에 직접 폴더를 만들 수 없어 `Birds-Nest/backups/` 아래에 두었다. 이 폴더는 Birds-Nest 저장소에서는 untracked라 git에 올라가지 않는다.
