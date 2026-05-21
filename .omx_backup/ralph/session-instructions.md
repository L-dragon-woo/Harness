<ralph_native_subagents>
You are in OMX Ralph persistence mode.
Primary task: Read and execute this local OMX/Ouroboros pipeline prompt: C:\Users\qhtm0\Desktop\harness\.omx_ouro_pipeline\prompts\20260520-140012-omx-prompt.md
Parallelism guidance:
- Prefer Codex native subagents for independent parallel subtasks.
- Treat `.omx/state/subagent-tracking.json` as the native subagent activity ledger for this session.
- Do not declare the task complete, and do not transition into final verification/completion, while active native subagent threads are still running.
- Before closing a verification wave, confirm that active native subagent threads have drained.
Goal mode guidance:
- If Codex goal tools are available, call `get_goal` during Ralph intake or before final verification to discover the active thread goal.
- Treat any active goal objective as the top-level completion contract for this Ralph run; Ralph mode state is not proof of goal completion by itself.
- Call `create_goal` only when the user/system explicitly requested a new goal and `get_goal` reports no active goal; otherwise do not invent a goal.
- Before completion, build a prompt-to-artifact checklist, inspect real evidence for every requirement, and continue working if any item is missing, incomplete, weakly verified, or uncovered.
- Record Ralph completion evidence in state before final Stop/cleanup: `completion_audit.passed=true`, a non-empty `completion_audit.prompt_to_artifact_checklist`, and non-empty `completion_audit.verification_evidence` (or point `completion_audit_path`/`completion_audit_evidence_path` at a repo-relative JSON artifact with those fields).
- Call `update_goal({status: "complete"})` only after that audit proves the active objective is fully achieved; then report final elapsed time and token-budget usage when provided.
Final deslop guidance:
- Step 7.5 must run oh-my-codex:ai-slop-cleaner in standard mode on changed files only, using the repo-relative paths listed in `.omx/ralph/changed-files.txt`.
- Keep the cleaner scope bounded to that file list; do not widen the pass to the full codebase or unrelated files.
- Step 7.6 must rerun the current tests/build/lint verification after ai-slop-cleaner; if regression fails, roll back cleaner changes or fix and retry before completion.
</ralph_native_subagents>
