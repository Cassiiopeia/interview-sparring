# interview-sparring

**이 레포를 fork 하지 마세요 — 공개 레포의 fork 는 공개이고, 면접 기록도 함께 공개됩니다.**
**「Use this template」** 으로 자기 **비공개** 레포를 만들거나, clone 한 뒤 자기 비공개 레포로 push 하세요.

Claude Code(그리고 `AGENTS.md` 를 읽는 에이전트)에서 도는 면접 준비 스파링 상대입니다.
사용자는 말만 합니다. 조수가 면접관이 실제로 물을 질문을 던지고, 가장 큰 문제를 짚고, **사용자가 한 말로** 다듬은 답을
보여 준 뒤 다시 답하게 합니다. 파일 편집이나 명령 입력은 하지 않습니다.

[English README](README.md)

## 시작

1. **Use this template** > **비공개** 레포 생성 > clone
2. 폴더를 Claude Code 로 연다
3. `/spar init` 을 입력하고 질문에 답한다

그다음부터는 `/spar` 만 입력하면 지난번 멈춘 곳에서 이어집니다.

## 하는 일

「어디에 낼까」 부터 「무엇을 물었나」 까지. 면접마다 폴더 하나, 재료는 다음 면접으로 이어집니다.

| 단계 | 명령 | 하는 일 |
|---|---|---|
| 탐색 | `/spar explore` | 목표 · 공식 출처의 후보 · 마감 달력 · 문의 메일 초안 |
| 지원 | `/spar new`, `/spar apply` | 면접 폴더 · 공고에서 체크리스트 · 접수 화면 칸별 확인 (제출은 사용자가 누름) |
| 작성 | `/spar writing` | 사용자 말로 쓴 초안 · 문체를 지키는 첨삭 · 최종본은 `submitted/` 로 |
| 연습 | `/spar`, `/spar research` | 낸 서류에서 질문 하나씩. 말하면 다듬어 주고 다시 묻는다 |
| 실전 | `/spar mock` | 중간 교정 없는 모의 면접 + 총평. 친구가 면접관을 하면 「기록만」 |
| 사후 기록 | `/spar debrief` | 실제로 받은 질문 · 반응 · 새로 안 사실 > 다음 단계 재료 |
| 결과 | `/spar result` | 결과 · 다음 단계 · 다음 면접으로 넘길 것 |

연습 한 턴: 편하게 말한다(두서없어도 됨) > 조수가 그 말을 답변 칸(`[결론] [판단] [한 일] [배운 점]`)에 배치 >
무엇을 왜 바꿨는지 짧게 > 같은 질문을 다시. 없는 경험·감정·숫자를 지어내지 않고, 모든 답을 사실 원장과 대조합니다.

몇 번 쓴 뒤의 기록 모습은 `example/en-job/`(가상의 취업 지원자, 영어)와 `example/ko-oral-exam/`(가상의 대학원 지원자,
한국어)에서 볼 수 있습니다.

## 기록을 어디에 두나 — 보관 방식

`/spar init` 의 첫 질문입니다. 기록은 `prep/` 에 쌓입니다.

| 방식 | 처리 | 백업 |
|---|---|---|
| **비공개 레포** (권장) | `prep/` 를 자기 비공개 레포에 커밋. `secret/` 암호화도 선택 가능 | 있음 |
| **이 컴퓨터만** | `prep/` 는 git 에 들어가지 않음 | **없음** |
| **공개 레포 + 암호화** | `secret/` 는 암호화해 커밋. **`prep/` 의 나머지는 공개** | 있음 |

`prep/` 안에서는 폴더 이름이 민감도입니다. `local/` 은 컴퓨터 밖으로 나가지 않고(녹음 · 증명서 · 전화번호),
`secret/` 은 암호화한 `.enc` 로만 커밋되며(밖에 말하면 안 되는 숫자 · 낸 서류 전문), 나머지는 일반 파일입니다.

## 음성으로 연습하기

말로 하는 연습이 실제 면접에 더 가깝습니다. 조수는 받아쓰기 결과로 읽습니다(이름의 오변환은 채점하지 않고, 고친 것을
기억합니다).

- **휴대폰 키보드 마이크**는 여러 언어(한국어 포함)에서 정확합니다. 밖에서 연습할 때 좋습니다.
- Claude Code 마이크는 책상에서 편합니다. 언어 설정을 확인하세요.
- 일부 데스크톱 · 원격 에이전트 앱은 기본 음성 모델이 **영어 전용**입니다. 다른 언어로 연습하기 전에 다국어 모델로
  바꾸세요.

## 기록 보호: 보장하는 것과 못 하는 것

스크립트가 보장하는 것 (테스트 있음):
- pre-commit 훅이 전화번호 · 이메일 · 주민등록번호 · `.env` 파일 · `secret/` · `local/` 원문을 막고, 커밋 전에
  `secret/` 를 암호화합니다 (AES-256-CBC, PBKDF2, `openssl`).
- pre-push 훅이 기록을 공개 템플릿으로 보내는 push 를 막고, 비공개 방식에서는 공개로 응답하는 GitHub 레포로의 push 를
  막습니다.

조수의 규칙으로 지키는 것 (훅이 강제하지 않음):
- 커밋 메시지에 내용을 쓰지 않습니다 (`practice: 1 session`).
- 훅을 우회하지 않습니다 (`--no-verify`).

한계:
- **암호화된 파일의 이름과 폴더 구조는 보입니다.** 내용만 암호화됩니다.
- **암호화 열쇠를 잃으면 복구할 수 없습니다.** 비밀번호 관리자에 백업하세요.
- GitHub 이 아닌 원격, 또는 GitHub 을 가리키는 SSH 호스트 별칭은 공개 여부를 확인할 수 없습니다. 조수가 「비공개
  레포입니까?」 라고 물을 때의 답에 기댑니다.
- 패턴 검사는 흔한 형식을 잡을 뿐 전부는 아닙니다. 이름은 `secret/` 에 두세요.

## 엔진 업데이트

`/spar update` 가 바뀔 파일을 보여 주고, 확인하면 엔진 파일만 교체합니다 (`tutor/`, `example/`, `tests/`,
`CLAUDE.md`, `AGENTS.md`, `.claude/commands/`, `.agents/skills/`, README 둘, `.gitignore`, `.gitattributes`,
`.githooks/`, `.github/`, `pyproject.toml`). `prep/` 와 `.env` 는 건드리지 않습니다.

## 필요한 것

- Claude Code (또는 `AGENTS.md` 를 읽는 에이전트)
- Python 3.10+ (표준 라이브러리만) — macOS · Windows
- git, 암호화에는 `openssl` (macOS · Git for Windows 에 포함)

## 기여

- **엔진 개발용 clone 에서는 `/spar init` 이나 `init.py setup` 을 실행하지 마세요.** setup 은 개인 사본용
  `prep/` · 설정 · 훅 · 열쇠를 만듭니다. 임시 사본에서 시험하세요.
- 규칙은 `tutor/rules/`(영어)에 있습니다. 원본은 `CLAUDE.md` 와 `.claude/commands/spar.md` 이고, 고친 뒤에는
  `python3 tutor/scripts/sync_agents.py write` 를 실행합니다 (AGENTS.md · `.agents/skills/` 는 생성본).
- PR 전에: `python3 -m pytest`, `python3 tutor/scripts/privacy_check.py scan-all`.
- 새 언어: `tutor/rules/language/<code>.md` 와 `<code>.patterns.txt`. 새 면접 종류: `tutor/rules/interview-types/<kind>.md`.

## 라이선스

Apache License 2.0 — [LICENSE](LICENSE) 참고.
