# Relay Orchestrator 배포 준비 계획

## Context and goal

현재 `relay-orchestrator` 스킬과 `relay-implementer-codex`, `relay-implementer-medium`
에이전트는 `~/.claude/` 개인 파일로만 존재한다. Codex 워커는 Haiku 전달 에이전트가
openai-codex 플러그인 캐시 안의 `codex-companion.mjs`를 `cygpath`로 호출한다.
그래서 macOS/Linux에서 실패하고, 플러그인 업데이트에 깨지며, `--resume-last` 때문에
디렉터리당 Codex 작업 1개로 제한된다. 모델 이름과 선택지는 하드코딩돼 있고,
매 실행마다 최대 4개 질문을 한다.

목표: relay 플러그인만 설치하면 모든 OS에서 오케스트레이터가 동작한다.
- 스킬과 medium 에이전트를 플러그인 안으로 옮긴다.
- Codex 워커는 `codex exec`를 직접 부르는 Node 스크립트로 실행한다 (전달 에이전트 제거).
- 재개는 thread id로 하고, 허용 파일 밖 수정은 스크립트가 자동 검사한다.
- 라우팅 기본값과 선택지는 JSON 설정에서 읽고, 설정이 있으면 질문을 건너뛴다.
- README와 매니페스트가 새 동작과 필수 조건을 설명한다.

Non-goals: Codex 호스트용 오케스트레이터, `/codex:status` 연동, 실시간 진행 표시,
새 의존성, 다른 스킬 동작 변경.

## Global constraints

- 저장소: `C:\Users\zxcvb\Desktop\claude\relay`, 브랜치 `feat/orchestrator-distribution`
  (main에서 메인 세션이 생성). 워커는 git commit/push/reset/checkout 금지. 커밋은
  리뷰 후 메인 세션이 한다.
- 의존성 추가 금지. 스크립트는 Node 18+ 표준 라이브러리(ESM `.mjs`), 테스트는
  Python 3 표준 라이브러리 `unittest` (기존 `tests/*.py` 스타일).
- Windows, macOS, Linux 모두 동작. `cygpath`, `sort -V`, bash 전용 문법 금지.
- Codex CLI 기준 버전 0.156.1. 검증된 사실:
  - `codex exec --json ... -` 는 stdin에서 프롬프트를 읽고 JSONL을 stdout에 쓴다.
  - 이벤트: `{"type":"thread.started","thread_id":"<id>"}`,
    `{"type":"item.completed","item":{"type":"agent_message","text":"..."}}`,
    `{"type":"turn.completed",...}`. 실패 시 `turn.failed` 또는 `error` 타입.
  - `codex exec resume <thread_id> ... -` 가 id로 재개된다. `resume`에는 `-s`, `-C`가
    없으므로 `-c sandbox_mode=workspace-write`와 spawn `cwd`를 쓴다.
  - Windows에서 Node `spawn('codex')`는 `shell` 없이 ENOENT. `.cmd` 셔임 때문이다.
- 코멘트: 자명하지 않은 이유만 1–2줄. 계획/작업 번호 인용 금지.
- 워커 리포트 40줄 이하, 수정 라운드 20줄 이하.

## Interfaces and dependencies

### `skills/relay-orchestrator/scripts/codex-worker.mjs` (Task 1 생산, Task 2 소비)

```text
node codex-worker.mjs --model <m> --effort <e> --cwd <dir> --brief <file>
                      --allowed <p1,p2,...> [--resume <thread_id>]
```

- 입력 검증 (실패 시 stderr 메시지, exit 2, codex 실행 안 함):
  `--model` `^[A-Za-z0-9._-]+$`, `--effort` ∈ {none, minimal, low, medium, high, xhigh, max},
  `--resume` `^[A-Za-z0-9-]+$`, `--cwd` 존재하는 디렉터리, `--brief` 존재하는 파일,
  `--allowed` 비어 있지 않음.
- 실행 인자 (경로를 인자로 넘기지 않아 Windows `shell: true` 인용 문제가 없다):
  - 신규: `exec --json -m <m> -c model_reasoning_effort=<e> -s workspace-write --skip-git-repo-check -`
  - 재개: `exec resume <id> --json -m <m> -c model_reasoning_effort=<e> -c sandbox_mode=workspace-write --skip-git-repo-check -`
  - brief 파일 내용을 stdin으로 쓴다. `cwd` 는 spawn 옵션.
  - 실행 파일: 환경변수 `RELAY_CODEX_BIN` 이 있으면 `process.execPath` 로 그 JS 파일을
    실행(테스트 seam), 없으면 `codex` 를 `shell: process.platform === 'win32'` 로 실행.
- 범위 검사: 실행 전후 `git -C <cwd> status --porcelain=v1 -z -uall` 로 경로 집합을
  얻고 각 파일 내용의 sha1(없으면 `deleted`)을 기록한다. 이름 변경 항목(`R`/`C`)은
  다음 NUL 필드(원래 경로)를 건너뛴다. 전후 해시가 다르거나 한쪽에만 있는 경로가
  "변경됨"이다. 변경됨 − allowed(역슬래시를 `/` 로 정규화, cwd 기준 상대경로) = outside.
  git 저장소가 아니면 검사 생략.
- stdout 출력 (항상 이 순서):

  ```text
  <마지막 agent_message 텍스트 그대로>
  Codex thread: <thread_id 또는 unknown>
  Scope: ok | outside allowed: <p1>, <p2> | unchecked (not a git repo)
  ```

- 실패 처리: codex 종료 코드 ≠ 0, `turn.failed`/`error` 이벤트, 또는 agent_message 없음
  → 첫 부분을 `Status: BLOCKED` 와 `Unresolved: <error 메시지 또는 stderr 마지막 20줄>`
  로 바꾸고, thread/Scope 줄은 그대로 출력, exit 1. 성공 시 exit 0.
  Scope가 outside면 exit 0 유지 (판단은 메인 세션 몫).

### 라우팅 설정 (Task 2 정의, 스크립트 없음, 메인 세션이 Read로 읽음)

- 사용자: `~/.claude/relay.json`, 프로젝트: `<project>/.relay.json`. 프로젝트 값이
  키 단위로 우선한다. 둘 다 없으면 기본 선택지로 질문한다.

```json
{
  "routing": {
    "easy": "codex gpt-6-luna/medium",
    "medium": "claude sonnet/high",
    "hard": "claude opus/high",
    "ui": "claude opus/high"
  },
  "options": ["codex gpt-6-luna/medium", "codex gpt-6-luna/high",
              "claude sonnet/high", "claude opus/high"]
}
```

- 값 형식: `<codex|claude> <model>/<effort>`. Claude effort는 `high`(→`relay:implementer`)
  또는 `medium`(→`relay:implementer-medium`)만 가능.

## Tasks

### Task 1: codex-worker.mjs 와 테스트

Tier: Hard. 소비: 없음. 생산: 위 스크립트 인터페이스.

Files:
- 생성 `skills/relay-orchestrator/scripts/codex-worker.mjs`
- 생성 `tests/test_codex_worker.py`
- 생성 `tests/fake_codex.mjs` (테스트용 가짜 codex)

`fake_codex.mjs` 동작: 받은 argv를 `argv.json` 으로 cwd에 쓰고, stdin 전체를
`stdin.txt` 로 쓴다. 환경변수 `FAKE_MODE`:
- `ok` (기본): `thread.started`(thread_id `t-123`), `item.completed` agent_message
  `Status: DONE\nChanged files: a.txt`, `turn.completed` 출력, exit 0.
- `touch`: `ok` 와 같고 추가로 cwd에 `a.txt`, `b.txt` 를 쓴다.
- `fail`: stderr에 `boom` 출력, exit 3.

TDD: 아래 테스트를 먼저 쓰고 RED 확인 후 구현. 각 테스트는 임시 git 저장소
(`git init`, 초기 커밋 1개)를 cwd로 쓴다.
1. `test_success_prints_message_thread_scope`: `ok` → stdout에 `Status: DONE`,
   `Codex thread: t-123`, `Scope: ok`, exit 0. `stdin.txt` == brief 내용.
   argv에 `exec`, `--json`, `-s`, `workspace-write`, `model_reasoning_effort=high` 포함.
2. `test_scope_flags_outside_file`: `touch`, `--allowed a.txt` → `Scope: outside allowed: b.txt`, exit 0.
3. `test_preexisting_dirty_file_unchanged_is_not_flagged`: 실행 전 `c.txt` 를 만들어 둠,
   `touch` → outside 목록에 `c.txt` 없음.
4. `test_resume_uses_thread_id`: `--resume t-123` → argv가 `exec resume t-123` 로 시작,
   `sandbox_mode=workspace-write` 포함, `-s` 없음.
5. `test_codex_failure_reports_blocked`: `fail` → stdout에 `Status: BLOCKED`, `boom`, exit 1.
6. `test_rejects_bad_model`: `--model "x; rm"` → exit 2, `argv.json` 생성 안 됨.
7. `test_non_git_dir_scope_unchecked`: git 아닌 임시 디렉터리 → `Scope: unchecked (not a git repo)`.

Test command (저장소 루트): `python tests/test_codex_worker.py` → 7 tests OK.
기존 테스트 회귀 없음: `python tests/test_task_brief.py`, `python tests/test_sdd_safety.py`.

### Task 2: 오케스트레이터 스킬과 medium 에이전트를 플러그인으로 이동

Tier: Medium. 소비: Task 1 인터페이스. 생산: 스킬 문서.

Files:
- 생성 `skills/relay-orchestrator/SKILL.md`
- 생성 `agents/implementer-medium.md`
- 수정 `skills/subagent-driven-development/SKILL.md` (Invariants에 한 줄만 추가:
  "`relay:relay-orchestrator`가 로드되면 워커 선택과 수정 루프는 그 스킬을 따른다.")

원본: `C:\Users\zxcvb\.claude\skills\relay-orchestrator\SKILL.md`,
`C:\Users\zxcvb\.claude\agents\relay-implementer-medium.md`. 원본 파일은 수정/삭제 금지.

`agents/implementer-medium.md`: 원본 본문 그대로, frontmatter `name: implementer-medium`
(플러그인에서 `relay:implementer-medium` 이 된다), `model: claude-sonnet-5`, `effort: medium`,
`disallowedTools: Agent`.

`SKILL.md` 변경점 (원본 구조 1–4절과 User controls 유지):
- frontmatter `name: relay-orchestrator`, description은 "Claude Code 전용. 난이도별
  Claude/Codex 워커 라우팅" 취지 영문 한 문장.
- 2절: 먼저 `~/.claude/relay.json` 과 `<project>/.relay.json` 을 Read(없으면 무시)하고
  위 스키마로 병합. 표에 나온 모든 tier에 routing 값이 있으면 질문 생략하고 매핑을
  한 줄로 보여준다. 없는 tier만 `AskUserQuestion` 으로 묻는다. 선택지는 설정 `options`,
  없으면 기존 4개. 사용자 저장 선호 언급 삭제. 설정 예시 JSON 포함.
- 3절 Claude 워커: `relay:implementer`(high) / `relay:implementer-medium`(medium).
- 3절 Codex 워커: 전달 에이전트 대신 메인 세션이 `Bash` 를 `run_in_background: true`,
  `timeout` 없이(백그라운드) 호출한다. description 은 `[Codex <model>/<effort>] Task N: <title>`.
  명령: `node "<이 스킬의 base directory>/scripts/codex-worker.mjs" --model .. --effort ..
  --cwd "<project>" --brief "<ledger>/task-N-codex-prompt.md" --allowed "<files>"`.
  완료 알림 후 출력의 `Codex thread:` 를 ledger에 기록.
- 병렬: Codex 워커도 파일이 겹치지 않으면 병렬 허용 (`--resume-last` 제약 문장 삭제).
- 4절 수정 라운드: `--resume <thread>` 와 `task-N-codex-fix-K.md` brief로 재실행.
  `Scope: outside allowed` 이면 리뷰 finding으로 처리.
- 필수 조건 절 추가: Codex CLI 설치와 `codex login`, Node 18+. `codex --version`
  실패 시 Codex tier는 Claude로 대체할지 사용자에게 묻는다.
- User controls: 작업 목록에서 확인, 취소는 `TaskStop <task id>` (워커 BLOCKED 처리),
  "switch Task N to <model>".
- `/codex:status`, `/codex:cancel`, `relay-implementer-codex`, `cygpath`, `codex-companion`
  언급이 남아 있으면 안 된다.

Check: `grep -rnE "cygpath|codex-companion|relay-implementer-codex|--resume-last" skills/relay-orchestrator agents`
→ 출력 없음. `claude plugin validate .` → 성공.

### Task 3: README와 매니페스트

Tier: Easy. 소비: Task 1, 2. 생산: 문서.

Files: `README.md`, `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`

- `plugin.json`: version `6.4.1+claude.20260927`, description
  "Superpowers 6.4.1 fork: the main session plans and reviews; tiered workers run on Claude subagents or the Codex CLI."
  keywords에 `codex`, `orchestration` 추가.
- `marketplace.json`: plugin description을 같은 취지로.
- README Claude Code 섹션에 "Relay Orchestrator (Claude + Codex)" 소절 추가 (한국어):
  필수 조건(Codex CLI, `codex login`, Node 18+), 설정 파일 위치와 예시 JSON,
  사용 예 3줄, 작업 목록 라벨/TaskStop 취소, 범위 검사 설명.
  구성 수치(스킬 개수 15→16, 에이전트 1→2)와 디렉터리 트리, 검증 절의 테스트 목록에
  `python3 tests/test_codex_worker.py` 추가.
- 과장 금지: 사용량 절감 수치 주장 추가하지 않는다.

Check: `python -c "import json;json.load(open('.claude-plugin/plugin.json'));json.load(open('.claude-plugin/marketplace.json'))"` → exit 0.
`claude plugin validate .` → 성공.

## Verification

- Task별 위 명령. 전체: `python tests/test_codex_worker.py && python tests/test_task_brief.py && python tests/test_sdd_safety.py && python tests/test_worktree_cleanup.py && python tests/test_worktree_instructions.py`.
- 실제 스모크 (메인 세션): 임시 git 저장소에서 `codex-worker.mjs` 를 `gpt-6-luna/low`,
  "hello.txt 에 hi 쓰기" brief, `--allowed hello.txt` 로 실행 → `Scope: ok`, thread id 출력.
  이어 `--resume <id>` 로 한 번 더 실행 → 같은 thread id.
- 리뷰: 스테이징/미스테이징 diff와 새 파일 전부 확인.

## Review focus and recovery

- Windows `shell: true` 에서 인자 인젝션: 검증 정규식이 모든 사용자 값에 적용되는지.
- `-z` 파싱의 rename 처리, 경로 구분자 정규화.
- 스킬 문서가 base directory 경로를 따옴표로 감싸는지 (공백 경로).
- 통합 후 메인 세션 인라인 작업 (사용자 확인 후): 플러그인 재설치, 동작 확인,
  `~/.claude/skills/relay-orchestrator`, `~/.claude/agents/relay-implementer-codex.md`,
  `relay-implementer-medium.md` 삭제, 메모리 갱신. 삭제 전 반드시 사용자 확인.
- 막히는 결정: Codex CLI 이벤트 형식이 위와 다르면 Task 1은 BLOCKED 보고.
