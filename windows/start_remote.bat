@echo off
REM agentchattr — connect a remote machine to the shared xerxes.uz hub
REM Usage:
REM   start_remote.bat codex
REM   start_remote.bat --api qwen

cd /d "%~dp0.."

if "%AGENTCHATTR_WEB_URL%"=="" set "AGENTCHATTR_WEB_URL=https://chat.xerxes.uz"
if "%AGENTCHATTR_MCP_HTTP_URL%"=="" set "AGENTCHATTR_MCP_HTTP_URL=https://mcp.xerxes.uz/mcp"
if "%AGENTCHATTR_MCP_SSE_URL%"=="" set "AGENTCHATTR_MCP_SSE_URL=https://sse.xerxes.uz/sse"
if "%AGENTCHATTR_SHARED_SECRET%"=="" set "AGENTCHATTR_SHARED_SECRET=_vrmlQYXaxyrILjsIlpqo4-WDRqsCDbw"

set "MODE=cli"
if "%~1"=="--api" (
    set "MODE=api"
    shift
)

set "AGENT_NAME=%~1"
if "%AGENT_NAME%"=="" (
    echo.
    echo   Usage: start_remote.bat [--api] ^<agent_name^>
    echo   Examples:
    echo     start_remote.bat codex
    echo     start_remote.bat --api qwen
    echo.
    pause
    exit /b 1
)

if not exist ".venv" (
    python -m venv .venv
    .venv\Scripts\pip install -q -r requirements.txt >nul 2>nul
)
call .venv\Scripts\activate.bat

echo agentchattr remote hub
echo   Web: %AGENTCHATTR_WEB_URL%
echo   MCP HTTP: %AGENTCHATTR_MCP_HTTP_URL%
echo   MCP SSE: %AGENTCHATTR_MCP_SSE_URL%

if "%MODE%"=="api" (
    python wrapper_api.py %AGENT_NAME%
) else (
    python wrapper.py %AGENT_NAME%
)

if %errorlevel% neq 0 pause
