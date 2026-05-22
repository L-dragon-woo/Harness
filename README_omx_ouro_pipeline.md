# OMX + Ouroboros Personal Pipeline

Private local launcher for this harness folder.

The default workflow is now **Codex handoff mode** so you do not have to enter
or attach to a separate CMD/tmux OMX shell. The launcher prepares the
Ouroboros/OMX prompt and writes a handoff file that this Codex chat can read and
execute with native tools.

## Short commands

Use `oo.cmd`:

```cmd
oo help
oo "your task goal"
oo go "your task goal"
oo seed "your task goal"
oo omx "your task goal"
oo status
oo doctor
```

`omo.cmd` is the same alias.

## Pipeline

```text
Ouroboros auto --skip-run
  -> create/refine an A-grade Seed
  -> detect the newest Seed
Configured OMX step
  -> default: write a Codex-native handoff prompt
  -> optional: execute/verify through the OMX CLI when configured
```

## No-CMD / Codex-native mode

Set `.omx_ouro_pipeline\config.json`:

```json
"omx_mode": "codex"
```

Then the launcher will not run `omx ralph` or `omx exec`. Instead it writes:

```text
.omx_ouro_pipeline\codex_handoffs\<run-id>-codex-handoff.md
```

In Codex, ask:

```text
Read and execute this local handoff:
C:\Users\qhtm0\Desktop\harness\.omx_ouro_pipeline\codex_handoffs\<run-id>-codex-handoff.md
```

That handoff explicitly tells Codex to avoid tmux-only OMX surfaces such as
`omx question`, `omx hud`, and `omx team`.

If you later want the old behavior, set:

```json
"omx_mode": "ralph"
```

or:

```json
"omx_mode": "exec"
```

## Examples

Full pipeline:

```cmd
oo "add login feature"
```

Run in a specific project folder:

```cmd
oo go "clean README and run tests" --cwd "C:\path\to\my-project"
```

Seed only:

```cmd
oo seed "write requirements for payment feature"
```

OMX only:

```cmd
oo omx "implement from latest Seed"
```

Environment check:

```cmd
oo doctor
```

## Files

- Main program: `omx_ouro_pipeline.py`
- Short launcher: `oo.cmd`
- Alias launcher: `omo.cmd`
- Long launcher: `run_omx_ouro_pipeline.cmd`
- Config: `.omx_ouro_pipeline\config.json`
- State: `.omx_ouro_pipeline\state.json`
- Logs: `.omx_ouro_pipeline\logs\`
- Generated OMX prompts: `.omx_ouro_pipeline\prompts\`

## Notes

- `UV_CACHE_DIR` defaults to local `.uv-cache` to reduce Windows permission issues.
- Default OMX mode for new configs is `"codex"` handoff mode.
- Before every pipeline/doctor run, `"codex_app_safety_guard": true` keeps
  Codex App plugin and hook loading disabled and quarantines any temporary
  `.codex\.tmp\plugins` cache. This prevents repeated plugin manifest warnings
  from flooding the VS Code/Codex app transport.
- Change `.omx_ouro_pipeline\config.json` `"omx_mode"` to `"ralph"` or `"exec"` if you prefer direct OMX CLI execution.
- If `ouroboros auto` is `blocked` and no closed Seed is produced, the launcher now continues to OMX with the original goal by default. Set `"continue_on_ouroboros_blocked": false` in config for strict failure behavior.
- The launcher uses at least 8 Ouroboros interview rounds by default to reduce premature safe-default blocking.
