#!/usr/bin/env python3
"""
Personal OMX + Ouroboros pipeline launcher.

This is intentionally a small, dependency-free local tool:

    Ouroboros auto --skip-run  ->  configured OMX step

It is designed for private local use, not for publishing.  The default OMX step
is Codex handoff mode, which avoids launching a separate OMX CMD/tmux shell.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import shlex
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parent
APP_DIR = ROOT / ".omx_ouro_pipeline"
LOG_DIR = APP_DIR / "logs"
PROMPT_DIR = APP_DIR / "prompts"
STATE_PATH = APP_DIR / "state.json"
CONFIG_PATH = APP_DIR / "config.json"
DEFAULT_OMX_CMD = Path.home() / ".local" / "bin" / "omx.cmd"
DEFAULT_OUROBOROS_DIR = ROOT / "ouroboros"
DEFAULT_UV_CACHE = ROOT / ".uv-cache"
CODEX_HOME = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
CODEX_CONFIG_PATH = CODEX_HOME / "config.toml"
CODEX_TMP_DIR = CODEX_HOME / ".tmp"

try:
    # Windows Korean consoles often default to cp949; Seed previews may contain
    # punctuation outside that codepage. Prefer UTF-8 and replace if needed.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def now_id() -> str:
    return _dt.datetime.now().strftime("%Y%m%d-%H%M%S")


def ensure_dirs() -> None:
    APP_DIR.mkdir(exist_ok=True)
    LOG_DIR.mkdir(exist_ok=True)
    PROMPT_DIR.mkdir(exist_ok=True)
    DEFAULT_UV_CACHE.mkdir(exist_ok=True)


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def default_config() -> dict:
    omx = shutil.which("omx") or (str(DEFAULT_OMX_CMD) if DEFAULT_OMX_CMD.exists() else "omx")
    return {
        "workspace": str(ROOT),
        "target_cwd": str(ROOT),
        "ouroboros_dir": str(DEFAULT_OUROBOROS_DIR),
        "ouroboros_runtime": "codex",
        "max_interview_rounds": 8,
        "continue_on_ouroboros_blocked": True,
        "omx_command": omx,
        # Default to Codex handoff so the pipeline can be used from this native
        # Codex surface without opening or attaching to a separate CMD/tmux OMX
        # shell. Set this to "ralph" or "exec" to launch the OMX CLI directly.
        "omx_mode": "codex",
        "codex_app_safety_guard": True,
        "uv_cache_dir": str(DEFAULT_UV_CACHE),
        "seed_search_dirs": [
            ".ouroboros/seeds",
            str(DEFAULT_OUROBOROS_DIR / ".ouroboros" / "seeds"),
        ],
    }


def load_config() -> dict:
    ensure_dirs()
    cfg = default_config()
    existing = read_json(CONFIG_PATH, {})
    cfg.update(existing)
    # Older generated configs used 4 rounds, which often hits Ouroboros auto's
    # safe-default closure guard. Lift the private-launcher default unless the
    # user already chose a higher value.
    try:
        cfg["max_interview_rounds"] = max(int(cfg.get("max_interview_rounds", 8)), 8)
    except Exception:
        cfg["max_interview_rounds"] = 8
    cfg.setdefault("continue_on_ouroboros_blocked", True)
    cfg.setdefault("codex_app_safety_guard", True)
    if not CONFIG_PATH.exists() or cfg != existing:
        write_json(CONFIG_PATH, cfg)
    return cfg


def q(s: str | Path) -> str:
    """Windows-friendly command-line quoting for display/shell .cmd launch."""
    return subprocess.list2cmdline([str(s)])


def command_display(args: Sequence[str]) -> str:
    return " ".join(q(a) for a in args)


@dataclass
class CommandResult:
    code: int
    command: str


class Logger:
    def __init__(self, path: Path):
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = self.path.open("a", encoding="utf-8", newline="")

    def close(self) -> None:
        self._fh.close()

    def line(self, text: str = "") -> None:
        print(text)
        self._fh.write(text + "\n")
        self._fh.flush()

    def raw(self, text: str) -> None:
        print(text, end="")
        self._fh.write(text)
        self._fh.flush()


def merged_env(cfg: dict) -> dict:
    env = os.environ.copy()
    env["UV_CACHE_DIR"] = str(Path(cfg["uv_cache_dir"]).expanduser())
    # Windows Korean consoles often default to cp949. Ouroboros uses Rich panels
    # that may contain Unicode box/dash characters, so force UTF-8 all the way
    # down to child Python processes and reduce terminal styling.
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    env["NO_COLOR"] = "1"
    env["RICH_NO_COLOR"] = "1"
    env["RICH_FORCE_TERMINAL"] = "0"
    env["CLICOLOR"] = "0"
    env["LANG"] = env.get("LANG", "C.UTF-8")
    env["LC_ALL"] = env.get("LC_ALL", "C.UTF-8")
    # Helps local source checkouts work even when the package is not installed globally.
    ouro_src = Path(cfg["ouroboros_dir"]).expanduser() / "src"
    env["PYTHONPATH"] = str(ouro_src) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def _set_toml_feature_bool(text: str, name: str, value: bool) -> str:
    lines = text.splitlines()
    out: list[str] = []
    in_features = False
    seen_features = False
    seen_name = False
    desired = f"{name} = {'true' if value else 'false'}"

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            if in_features and not seen_name:
                out.append(desired)
                seen_name = True
            in_features = stripped == "[features]"
            seen_features = seen_features or in_features
            out.append(line)
            continue
        if in_features and stripped.split("=", 1)[0].strip() == name and "=" in stripped:
            if seen_name:
                continue
            out.append(desired)
            seen_name = True
            continue
        out.append(line)

    if in_features and not seen_name:
        out.append(desired)
        seen_name = True
    if not seen_features:
        if out and out[-1].strip():
            out.append("")
        out.extend(["[features]", desired])
    return "\n".join(out).rstrip() + "\n"


def ensure_codex_app_safety(log: Logger, *, dry_run: bool = False) -> None:
    """Keep the VS Code/Codex app from loading noisy plugin and hook surfaces."""
    CODEX_HOME.mkdir(parents=True, exist_ok=True)
    original = CODEX_CONFIG_PATH.read_text(encoding="utf-8") if CODEX_CONFIG_PATH.exists() else ""
    next_text = original
    for feature in ("plugins", "hooks"):
        next_text = _set_toml_feature_bool(next_text, feature, False)
    if next_text != original:
        if dry_run:
            log.line(f"[codex-safety] Would update {CODEX_CONFIG_PATH}: plugins=false, hooks=false")
        else:
            CODEX_CONFIG_PATH.write_text(next_text, encoding="utf-8")
            log.line(f"[codex-safety] Updated {CODEX_CONFIG_PATH}: plugins=false, hooks=false")
    else:
        log.line("[codex-safety] Codex plugins/hooks already disabled.")

    stamp = now_id()
    for name in ("plugins", "plugins.sha"):
        path = CODEX_TMP_DIR / name
        if not path.exists():
            continue
        disabled = CODEX_TMP_DIR / f".{name}.disabled-{stamp}"
        if dry_run:
            log.line(f"[codex-safety] Would move {path} -> {disabled}")
        else:
            shutil.move(str(path), str(disabled))
            log.line(f"[codex-safety] Moved {path} -> {disabled}")


def run_command(
    args: Sequence[str],
    *,
    cwd: Path,
    cfg: dict,
    log: Logger,
    dry_run: bool = False,
    interactive: bool = False,
) -> CommandResult:
    display = command_display(args)
    log.line(f"\n$ {display}")
    log.line(f"  cwd: {cwd}")
    if dry_run:
        log.line("  [dry-run] 실행하지 않음")
        return CommandResult(0, display)

    env = merged_env(cfg)

    if interactive:
        code = subprocess.call(list(args), cwd=str(cwd), env=env)
        return CommandResult(code, display)

    proc = subprocess.Popen(
        list(args),
        cwd=str(cwd),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
    )
    assert proc.stdout is not None
    for chunk in proc.stdout:
        log.raw(chunk)
    return CommandResult(proc.wait(), display)


def run_omx_cmd(
    omx_command: str,
    omx_args: Sequence[str],
    *,
    cwd: Path,
    cfg: dict,
    log: Logger,
    dry_run: bool = False,
) -> CommandResult:
    # .cmd/.bat files are most reliable through cmd.exe on Windows.
    full = [omx_command, *omx_args]
    display = command_display(full)
    log.line(f"\n$ {display}")
    log.line(f"  cwd: {cwd}")
    if dry_run:
        log.line("  [dry-run] 실행하지 않음")
        return CommandResult(0, display)

    suffix = Path(omx_command).suffix.lower()
    if os.name == "nt" and suffix in {".cmd", ".bat"}:
        cmdline = command_display(full)
        code = subprocess.call(cmdline, cwd=str(cwd), env=merged_env(cfg), shell=True)
    else:
        code = subprocess.call(full, cwd=str(cwd), env=merged_env(cfg))
    return CommandResult(code, display)


def ouroboros_base_cmd(cfg: dict) -> list[str]:
    project = Path(cfg["ouroboros_dir"]).expanduser()
    if project.exists() and shutil.which("uv"):
        return ["uv", "run", "--project", str(project), "ouroboros"]
    found = shutil.which("ouroboros")
    if found:
        return [found]
    return ["ouroboros"]


def newest_seed(cfg: dict, target_cwd: Path, after: float | None = None) -> Path | None:
    candidates: list[Path] = []
    for raw in cfg.get("seed_search_dirs", []):
        p = Path(raw).expanduser()
        if not p.is_absolute():
            p = target_cwd / p
        if not p.exists():
            continue
        for ext in ("*.yaml", "*.yml", "*.json"):
            candidates.extend(p.glob(ext))
    if after is not None:
        candidates = [p for p in candidates if p.stat().st_mtime >= after]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def compact_seed_preview(seed_path: Path, limit: int = 2500) -> str:
    try:
        text = seed_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return ""
    text = text.strip()
    return text[:limit] + ("\n..." if len(text) > limit else "")


def write_codex_handoff_prompt(
    *,
    run_id: str,
    prompt_path: Path,
    target_cwd: Path,
    seed_path: Path | None,
    goal: str,
) -> Path:
    """Create a Codex-native handoff prompt instead of launching an OMX CMD shell.

    The local CLI cannot control this already-running Codex conversation.  This
    handoff file is therefore the durable bridge: paste its contents into Codex,
    or ask Codex to read the file path.  The instructions explicitly avoid
    tmux-only OMX surfaces such as ``omx question``, ``omx hud``, and
    ``omx team``.
    """
    handoff_dir = APP_DIR / "codex_handoffs"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    handoff_path = handoff_dir / f"{run_id}-codex-handoff.md"
    seed_line = f"- Seed path: {seed_path}\n" if seed_path else ""
    handoff_path.write_text(
        "\n".join(
            [
                "# Codex-native OMX/Ouroboros handoff",
                "",
                "Read and execute the local OMX/Ouroboros pipeline prompt below from",
                "the current Codex/native surface. Do not require the user to open or",
                "attach to a separate CMD, PowerShell, tmux, OMX HUD, OMX team, or",
                "OMX question session.",
                "",
                f"- Run ID: {run_id}",
                f"- Target cwd: {target_cwd}",
                f"- Original goal: {goal}",
                seed_line.rstrip(),
                f"- Pipeline prompt path: {prompt_path}",
                "",
                "Execution instructions:",
                "1. Read the pipeline prompt file.",
                "2. Execute the requested work using native Codex tools where possible.",
                "3. If an OMX feature requires an attached tmux shell, replace it with",
                "   native structured/plain-text interaction or local file-state updates.",
                "4. Verify changes with targeted tests/lint and report concrete evidence.",
                "",
            ]
        ).replace("\n\n\n", "\n\n"),
        encoding="utf-8",
    )
    return handoff_path


def save_state(**kwargs: object) -> None:
    state = read_json(STATE_PATH, {})
    state.update(kwargs)
    state["updated_at"] = _dt.datetime.now().isoformat(timespec="seconds")
    write_json(STATE_PATH, state)


def doctor(cfg: dict, *, log: Logger, dry_run: bool = False) -> int:
    target = Path(cfg["target_cwd"]).expanduser()
    log.line("== 환경 점검 ==")
    log.line(f"작업 폴더: {target}")
    log.line(f"설정 파일: {CONFIG_PATH}")
    log.line(f"로그 폴더: {LOG_DIR}")
    log.line(f"UV_CACHE_DIR: {cfg['uv_cache_dir']}")
    log.line(f"OMX 명령: {cfg['omx_command']}")
    log.line(f"Ouroboros 폴더: {cfg['ouroboros_dir']}")

    if cfg.get("codex_app_safety_guard", True):
        ensure_codex_app_safety(log, dry_run=dry_run)

    problems = 0
    if not target.exists():
        log.line("!! target_cwd가 없습니다.")
        problems += 1
    if not Path(cfg["ouroboros_dir"]).expanduser().exists() and not shutil.which("ouroboros"):
        log.line("!! Ouroboros checkout 또는 전역 ouroboros 명령을 찾지 못했습니다.")
        problems += 1
    if not shutil.which("uv") and not shutil.which("ouroboros"):
        log.line("!! uv 또는 ouroboros 실행 파일이 PATH에 없습니다.")
        problems += 1
    omx_cmd = Path(str(cfg["omx_command"])).expanduser()
    if not omx_cmd.exists() and not shutil.which(str(cfg["omx_command"])):
        log.line("!! omx 명령을 찾지 못했습니다.")
        problems += 1

    if problems == 0:
        log.line("OK: 기본 실행 경로를 찾았습니다.")

    if not dry_run:
        # Ouroboros help is safe and confirms dependencies can load.
        result = run_command(
            [*ouroboros_base_cmd(cfg), "--help"],
            cwd=target if target.exists() else ROOT,
            cfg=cfg,
            log=log,
            dry_run=False,
            interactive=False,
        )
        if result.code != 0:
            problems += 1
            log.line("!! Ouroboros CLI 실행에 실패했습니다. 위 로그를 확인하세요.")
    return 0 if problems == 0 else 1


def run_pipeline(
    goal: str,
    *,
    cfg: dict,
    target_cwd: Path,
    skip_seed: bool = False,
    skip_omx: bool = False,
    dry_run: bool = False,
    log: Logger,
) -> int:
    started = _dt.datetime.now().timestamp()
    run_id = now_id()
    save_state(run_id=run_id, active=True, phase="start", goal=goal, target_cwd=str(target_cwd))

    log.line("== OMX + Ouroboros 개인 파이프라인 ==")
    log.line(f"목표: {goal}")
    log.line(f"실행 ID: {run_id}")

    if cfg.get("codex_app_safety_guard", True):
        ensure_codex_app_safety(log, dry_run=dry_run)

    seed_path: Path | None = None
    if not skip_seed:
        save_state(phase="ouroboros:auto_skip_run")
        cmd = [
            *ouroboros_base_cmd(cfg),
            "auto",
            goal,
            "--runtime",
            str(cfg.get("ouroboros_runtime", "codex")),
            "--max-interview-rounds",
            str(cfg.get("max_interview_rounds", 4)),
            "--skip-run",
        ]
        result = run_command(cmd, cwd=target_cwd, cfg=cfg, log=log, dry_run=dry_run)
        if result.code != 0:
            seed_path = newest_seed(cfg, target_cwd, after=started)
            if cfg.get("continue_on_ouroboros_blocked", True) and not skip_omx:
                log.line(
                    "\n[warn] Ouroboros auto did not create a closed Seed. "
                    "Continuing with OMX using the original goal and the latest available context."
                )
                save_state(
                    phase="warn:ouroboros_blocked_continuing_to_omx",
                    ouroboros_exit_code=result.code,
                    seed_path=str(seed_path) if seed_path else None,
                )
            else:
                save_state(active=False, phase="failed:ouroboros", exit_code=result.code)
                return result.code
        else:
            seed_path = newest_seed(cfg, target_cwd, after=started)
        if seed_path:
            log.line(f"\nSeed 감지: {seed_path}")
            save_state(seed_path=str(seed_path))
        else:
            log.line("\n새 Seed 파일을 자동 감지하지 못했습니다. 원본 목표만 OMX에 넘깁니다.")
    else:
        seed_path = newest_seed(cfg, target_cwd)
        if seed_path:
            log.line(f"기존 최신 Seed 사용: {seed_path}")

    if not skip_omx:
        save_state(phase="omx:prepare")
        omx_goal = goal
        if seed_path:
            preview = compact_seed_preview(seed_path)
            omx_goal = (
                "Ouroboros가 만든 Seed를 기준으로 작업을 실행하고 검증해줘.\n"
                f"- Seed path: {seed_path}\n"
                f"- Original goal: {goal}\n\n"
                "Seed preview:\n"
                f"{preview}"
            )
        prompt_path = PROMPT_DIR / f"{run_id}-omx-prompt.md"
        prompt_path.write_text(omx_goal, encoding="utf-8")
        save_state(omx_prompt_path=str(prompt_path))
        omx_cli_goal = f"Read and execute this local OMX/Ouroboros pipeline prompt: {prompt_path}"
        omx_mode = str(cfg.get("omx_mode", "ralph")).lower()
        if omx_mode in {"codex", "native", "handoff", "codex_handoff"}:
            handoff_path = write_codex_handoff_prompt(
                run_id=run_id,
                prompt_path=prompt_path,
                target_cwd=target_cwd,
                seed_path=seed_path,
                goal=goal,
            )
            save_state(
                active=False,
                phase="codex:handoff_ready",
                exit_code=0,
                codex_handoff_path=str(handoff_path),
            )
            log.line("\nCodex-native handoff ready.")
            log.line("No CMD/tmux OMX shell was launched.")
            log.line(f"Ask Codex to read and execute: {handoff_path}")
            return 0
        if omx_mode == "exec":
            omx_args = ["exec", omx_cli_goal]
        else:
            omx_args = ["ralph", omx_cli_goal]
        result = run_omx_cmd(
            str(cfg["omx_command"]),
            omx_args,
            cwd=target_cwd,
            cfg=cfg,
            log=log,
            dry_run=dry_run,
        )
        if result.code != 0:
            save_state(active=False, phase="failed:omx", exit_code=result.code)
            return result.code

    save_state(active=False, phase="complete", exit_code=0)
    log.line("\n완료: 파이프라인이 끝났습니다.")
    return 0


def status(cfg: dict, log: Logger, dry_run: bool = False) -> int:
    log.line("== 저장된 상태 ==")
    log.line(json.dumps(read_json(STATE_PATH, {}), ensure_ascii=False, indent=2))
    target = Path(cfg["target_cwd"]).expanduser()
    log.line("\n== OMX 상태 ==")
    run_omx_cmd(str(cfg["omx_command"]), ["status"], cwd=target, cfg=cfg, log=log, dry_run=dry_run)
    return 0


def prompt(default: str, label: str) -> str:
    value = input(f"{label} [{default}]: ").strip()
    return value or default


def menu() -> int:
    cfg = load_config()
    while True:
        print("\n=== OMX + Ouroboros 개인 런처 ===")
        print("1) 전체 파이프라인 실행 (Ouroboros Seed -> configured OMX step)")
        print("2) Ouroboros Seed만 생성")
        print("3) OMX 단계만 실행")
        print("4) 상태 확인")
        print("5) 환경 점검")
        print("6) 설정 파일 위치 보기")
        print("0) 종료")
        choice = input("> ").strip()
        log = Logger(LOG_DIR / f"{now_id()}-menu.log")
        try:
            if choice == "1":
                goal = input("목표를 입력하세요: ").strip()
                if not goal:
                    print("목표가 비어 있습니다.")
                    continue
                cwd = Path(prompt(str(cfg["target_cwd"]), "작업 폴더")).expanduser()
                return run_pipeline(goal, cfg=cfg, target_cwd=cwd, log=log)
            if choice == "2":
                goal = input("목표를 입력하세요: ").strip()
                cwd = Path(prompt(str(cfg["target_cwd"]), "작업 폴더")).expanduser()
                return run_pipeline(goal, cfg=cfg, target_cwd=cwd, skip_omx=True, log=log)
            if choice == "3":
                goal = input("OMX에 넘길 목표를 입력하세요: ").strip()
                cwd = Path(prompt(str(cfg["target_cwd"]), "작업 폴더")).expanduser()
                return run_pipeline(goal, cfg=cfg, target_cwd=cwd, skip_seed=True, log=log)
            if choice == "4":
                return status(cfg, log)
            if choice == "5":
                return doctor(cfg, log=log)
            if choice == "6":
                print(f"설정: {CONFIG_PATH}")
                print(f"로그: {LOG_DIR}")
                continue
            if choice == "0":
                return 0
            print("알 수 없는 선택입니다.")
        finally:
            log.close()



def short_help() -> str:
    return f"""\
OMX + Ouroboros personal launcher

Shortest usage:
  oo "your task goal"

Commands:
  oo go "goal"       Run full pipeline: Ouroboros Seed -> configured OMX step
  oo seed "goal"     Create Ouroboros Seed only
  oo omx "goal"      Prepare/execute the OMX step
  oo status             Show last saved state and OMX status
  oo doctor             Check local environment
  oo help               Show this help

Options:
  --cwd "folder"      Target project folder
  --dry-run             Print commands without executing

Examples:
  oo "clean README and run tests"
  oo go "add login feature" --cwd "C:\\my-project"
  oo seed "write requirements for payment feature"
  oo omx "implement from latest Seed"

Old long command still works:
  run_omx_ouro_pipeline.cmd run --goal "goal"

Config/logs:
  config: {CONFIG_PATH}
  logs:   {LOG_DIR}

No-CMD mode:
  Set config "omx_mode" to "codex" (the default for new configs). The launcher
  will write a Codex handoff file instead of opening/attaching to an OMX shell.
"""


def goal_from_parts(parts: Sequence[str], explicit_goal: str | None = None) -> str:
    if explicit_goal:
        return explicit_goal.strip()
    return " ".join(parts).strip()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Personal OMX + Ouroboros pipeline launcher")
    sub = p.add_subparsers(dest="cmd")

    run = sub.add_parser("run", help="Run full pipeline")
    run.add_argument("goal_parts", nargs="*", help="task goal")
    run.add_argument("--goal", "-g", required=False, help="task goal")
    run.add_argument("--cwd", default=None, help="target project folder")
    run.add_argument("--skip-seed", action="store_true", help="skip Ouroboros step")
    run.add_argument("--skip-omx", action="store_true", help="skip OMX step")
    run.add_argument("--dry-run", action="store_true", help="print commands only")

    go = sub.add_parser("go", help="Short full-run command")
    go.add_argument("goal_parts", nargs="*", help="task goal")
    go.add_argument("--cwd", default=None, help="target project folder")
    go.add_argument("--dry-run", action="store_true", help="print commands only")

    seed = sub.add_parser("seed", help="Create Ouroboros Seed only")
    seed.add_argument("goal_parts", nargs="*", help="task goal")
    seed.add_argument("--cwd", default=None, help="target project folder")
    seed.add_argument("--dry-run", action="store_true", help="print commands only")

    omx = sub.add_parser("omx", help="Run configured OMX step only")
    omx.add_argument("goal_parts", nargs="*", help="task goal")
    omx.add_argument("--cwd", default=None, help="target project folder")
    omx.add_argument("--dry-run", action="store_true", help="print commands only")

    sub.add_parser("doctor", help="Check environment")
    sub.add_parser("status", help="Show saved state and OMX status")
    sub.add_parser("config", help="Print config path")
    sub.add_parser("help", help="Show concise help")
    return p


def main(argv: Sequence[str] | None = None) -> int:
    ensure_dirs()
    argv = list(sys.argv[1:] if argv is None else argv)

    # ??? ??:
    #   oo "?? ??"
    # ? ??? ??/??? ??? ??? ?? ???? ?? ?? ????.
    known = {"run", "go", "seed", "omx", "doctor", "status", "config", "help", "-h", "--help"}
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        # Support: oo "goal" --cwd "C:\repo" --dry-run
        direct = argparse.ArgumentParser(add_help=False)
        direct.add_argument("goal_parts", nargs="*")
        direct.add_argument("--cwd", default=None)
        direct.add_argument("--dry-run", action="store_true")
        direct_args = direct.parse_args(argv)
        cfg = load_config()
        log = Logger(LOG_DIR / f"{now_id()}-go.log")
        try:
            goal = goal_from_parts(direct_args.goal_parts)
            if not goal:
                log.line(short_help())
                return 2
            return run_pipeline(
                goal,
                cfg=cfg,
                target_cwd=Path(direct_args.cwd or cfg["target_cwd"]).expanduser(),
                dry_run=direct_args.dry_run,
                log=log,
            )
        finally:
            log.close()

    parser = build_parser()
    args = parser.parse_args(argv)
    cfg = load_config()

    if not args.cmd:
        return menu()

    log = Logger(LOG_DIR / f"{now_id()}-{args.cmd}.log")
    try:
        if args.cmd == "run":
            goal = goal_from_parts(args.goal_parts, args.goal)
            if not goal:
                log.line(short_help())
                return 2
            cwd = Path(args.cwd or cfg["target_cwd"]).expanduser()
            return run_pipeline(
                goal,
                cfg=cfg,
                target_cwd=cwd,
                skip_seed=args.skip_seed,
                skip_omx=args.skip_omx,
                dry_run=args.dry_run,
                log=log,
            )
        if args.cmd == "go":
            goal = goal_from_parts(args.goal_parts)
            if not goal:
                log.line(short_help())
                return 2
            return run_pipeline(
                goal,
                cfg=cfg,
                target_cwd=Path(args.cwd or cfg["target_cwd"]).expanduser(),
                dry_run=args.dry_run,
                log=log,
            )
        if args.cmd == "seed":
            goal = goal_from_parts(args.goal_parts)
            if not goal:
                log.line(short_help())
                return 2
            return run_pipeline(
                goal,
                cfg=cfg,
                target_cwd=Path(args.cwd or cfg["target_cwd"]).expanduser(),
                skip_omx=True,
                dry_run=args.dry_run,
                log=log,
            )
        if args.cmd == "omx":
            goal = goal_from_parts(args.goal_parts)
            if not goal:
                log.line(short_help())
                return 2
            return run_pipeline(
                goal,
                cfg=cfg,
                target_cwd=Path(args.cwd or cfg["target_cwd"]).expanduser(),
                skip_seed=True,
                dry_run=args.dry_run,
                log=log,
            )
        if args.cmd == "doctor":
            return doctor(cfg, log=log)
        if args.cmd == "status":
            return status(cfg, log)
        if args.cmd == "config":
            log.line(str(CONFIG_PATH))
            return 0
        if args.cmd == "help":
            log.line(short_help())
            return 0
        parser.print_help()
        return 2
    finally:
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
