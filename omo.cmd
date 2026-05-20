@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONLEGACYWINDOWSSTDIO=0"
set "NO_COLOR=1"
set "RICH_NO_COLOR=1"
set "RICH_FORCE_TERMINAL=0"
set "CLICOLOR=0"
cd /d "%~dp0"
python "%~dp0omx_ouro_pipeline.py" %*
if errorlevel 1 (
  echo.
  echo [omo] Failed. Check .omx_ouro_pipeline\logs.
)
endlocal
