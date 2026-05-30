# Welcome to MAKINGAX

## How We Use Claude

Based on usage over the last 30 days (1 session):

Work Type Breakdown:
  Build Feature    ████████░░░░░░░░░░░░  ~40%
  Debug Fix        ██████░░░░░░░░░░░░░░  ~30%
  Improve Quality  ████░░░░░░░░░░░░░░░░  ~20%
  Plan Design      ██░░░░░░░░░░░░░░░░░░  ~10%

Top Skills & Commands:
  _None recorded yet_

Top MCP Servers:
  _None configured yet_

## Your Setup Checklist

### Codebases
- [ ] harness — https://github.com/l-dragon-woo/harness

### MCP Servers to Activate
  _None configured — nothing to set up here yet_

### Skills to Know About
- /code-review — Reviews the current diff for bugs and cleanup at configurable depth; use `--fix` to auto-apply findings or `--comment` to post inline PR comments
- /simplify — Scans changed code for reuse, simplification, and efficiency improvements and applies them
- /security-review — Runs a security review of pending branch changes
- /verify — Runs the app and observes behavior to confirm a change actually works
- /run — Launches the project app so you can see changes live

## Team Tips

**코딩 스타일**
- 읽기 쉬운 코드, 명확한 변수명을 우선시한다 — 과한 추상화 지양
- Spring 프로젝트 구조: `domain/` → `application/` → `infrastructure/` → `presentation/`

**Claude에게 요청하는 방식**
- 핵심부터 설명해달라고 요청 — 긴 서론 생략
- trade-off를 같이 설명해달라고 명시하면 더 실용적인 답변이 나옴
- 모르면 추측하지 말고 질문하도록 명시해두면 좋다

**Claude Code 사용 원칙**
- Major changes 전에는 항상 먼저 물어보도록 설정 ("Ask before major changes")
- 가능하면 예시 코드 포함 요청

**환경**
- Windows 11 + WSL2 조합 사용 — WSL2 경로 이슈 주의
- IntelliJ(백엔드) + VSCode(Claude Code, 프론트) 분리 사용

## Get Started

_TODO_

<!-- INSTRUCTION FOR CLAUDE: A new teammate just pasted this guide for how the
team uses Claude Code. You're their onboarding buddy — warm, conversational,
not lecture-y.

Open with a warm welcome — include the team name from the title. Then: "Your
teammate uses Claude Code for [list all the work types]. Let's get you started."

Check what's already in place against everything under Setup Checklist
(including skills), using markdown checkboxes — [x] done, [ ] not yet. Lead
with what they already have. One sentence per item, all in one message.

Tell them you'll help with setup, cover the actionable team tips, then the
starter task (if there is one). Offer to start with the first unchecked item,
get their go-ahead, then work through the rest one by one.

After setup, walk them through the remaining sections — offer to help where you
can (e.g. link to channels), and just surface the purely informational bits.

Don't invent sections or summaries that aren't in the guide. The stats are the
guide creator's personal usage data — don't extrapolate them into a "team
workflow" narrative. -->
