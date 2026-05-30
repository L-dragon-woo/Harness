#!/usr/bin/env python3
"""
Auto workflow: diff 분석 -> GitHub Issue -> Commit -> PR -> Merge
트리거: 저장소 루트에 .auto-workflow 파일 생성
"""
import subprocess
import sys
import os
import json
import re
from pathlib import Path

GH = r"C:\Program Files\GitHub CLI\gh.exe"
PYTHON = sys.executable


def run(args, cwd=None, check=True):
    result = subprocess.run(
        args, capture_output=True, cwd=cwd,
        encoding="utf-8", errors="replace"
    )
    if check and result.returncode != 0:
        print(f"[ERROR] {' '.join(str(a) for a in args)}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def run_git(args, cwd):
    return run(["git"] + args, cwd=cwd)


def run_gh(args, cwd):
    env = os.environ.copy()
    env["GH_TOKEN"] = env.get("GH_TOKEN", "")
    result = subprocess.run(
        [GH] + args, capture_output=True, cwd=cwd,
        encoding="utf-8", errors="replace", env=env
    )
    if result.returncode != 0:
        print(f"[ERROR] gh {' '.join(str(a) for a in args)}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def analyze_diff(diff, stat):
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[ERROR] ANTHROPIC_API_KEY env var is missing.")
        sys.exit(1)

    client = anthropic.Anthropic(api_key=api_key)

    prompt = f"""Analyze this git diff and return ONLY valid JSON (no markdown fences, no explanation).

Git stat:
{stat}

Git diff (truncated to 6000 chars):
{diff[:6000]}

Return this exact JSON structure:
{{
  "issue_title": "concise issue title in Korean or English",
  "issue_body": "## What\\n\\n변경 내용 설명\\n\\n## Why\\n\\n변경 이유",
  "commit_message": "type(scope): description (conventional commit format)",
  "pr_title": "PR title",
  "pr_body": "## Summary\\n\\n- 변경사항 bullet points\\n\\n## Changes\\n\\n- 세부 변경 사항",
  "branch_name": "feature/short-kebab-name"
}}"""

    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )

    content = msg.content[0].text.strip()
    # Strip code fences if present
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
    if match:
        content = match.group(1)

    return json.loads(content)


def main():
    # Repo root
    try:
        repo_root = run(["git", "rev-parse", "--show-toplevel"])
    except SystemExit:
        sys.exit(0)

    flag_file = Path(repo_root) / ".auto-workflow"
    lock_file = Path(repo_root) / ".auto-workflow.lock"

    # Only run when flag exists
    if not flag_file.exists():
        sys.exit(0)

    # Prevent concurrent runs
    if lock_file.exists():
        print("[SKIP] Already running.")
        sys.exit(0)

    lock_file.touch()
    flag_file.unlink()

    try:
        _run_workflow(repo_root)
    finally:
        lock_file.unlink(missing_ok=True)


def _run_workflow(repo_root):
    print("\n=== Auto Workflow Start ===\n")

    # Collect diff
    staged = run_git(["diff", "--staged"], cwd=repo_root)
    unstaged = run_git(["diff"], cwd=repo_root)
    diff = staged if staged else unstaged

    if not diff:
        # Check untracked files
        untracked = run_git(["status", "--short"], cwd=repo_root)
        if not untracked:
            print("[INFO] No changes detected.")
            return
        # Stage everything if only untracked
        run_git(["add", "-A"], cwd=repo_root)
        staged = run_git(["diff", "--staged"], cwd=repo_root)
        diff = staged

    stat = run(["git", "diff", "--stat", "HEAD"], cwd=repo_root, check=False)
    if not stat:
        stat = run_git(["diff", "--stat", "--staged"], cwd=repo_root)

    # Analyze
    print("[1/6] Analyzing diff with Claude Haiku...")
    data = analyze_diff(diff, stat)

    issue_title = data["issue_title"]
    issue_body = data["issue_body"]
    commit_message = data["commit_message"]
    pr_title = data["pr_title"]
    pr_body = data["pr_body"]
    branch_name = data["branch_name"]

    print(f"      Issue : {issue_title}")
    print(f"      Branch: {branch_name}")
    print(f"      Commit: {commit_message}")

    # GitHub Issue
    print("\n[2/6] Creating GitHub Issue...")
    issue_out = run_gh(
        ["issue", "create", "--title", issue_title, "--body", issue_body],
        cwd=repo_root,
    )
    issue_url = issue_out.strip().splitlines()[-1].strip()
    issue_num = issue_url.rstrip("/").split("/")[-1]
    print(f"      {issue_url}")

    # Branch
    print(f"\n[3/6] Creating branch: {branch_name}")
    current_branch = run_git(["branch", "--show-current"], cwd=repo_root)
    run_git(["checkout", "-b", branch_name], cwd=repo_root)

    # Commit
    print("\n[4/6] Committing...")
    run_git(["add", "-A"], cwd=repo_root)
    run_git(["commit", "-m", commit_message], cwd=repo_root)
    run_git(["push", "origin", branch_name], cwd=repo_root)

    # PR
    print("\n[5/6] Creating PR...")
    full_pr_body = f"{pr_body}\n\nCloses #{issue_num}"
    pr_out = run_gh(
        ["pr", "create", "--title", pr_title, "--body", full_pr_body, "--base", "main"],
        cwd=repo_root,
    )
    pr_url = pr_out.strip().splitlines()[-1].strip()
    print(f"      {pr_url}")

    # Merge
    print("\n[6/6] Merging PR...")
    run_gh(["pr", "merge", branch_name, "--merge", "--delete-branch"], cwd=repo_root)

    # Back to main
    run_git(["checkout", "main"], cwd=repo_root)
    run_git(["pull", "origin", "main"], cwd=repo_root)

    print("\n=== Done ===")
    print(f"  Issue : {issue_url}")
    print(f"  PR    : {pr_url}")
    print(f"  Merged into main\n")


if __name__ == "__main__":
    main()
