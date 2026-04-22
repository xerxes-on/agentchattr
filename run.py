"""Entry point — starts MCP server (port 8200) + web UI (port 8300)."""

import argparse
import asyncio
import secrets
import sys
import threading
import time
import logging
from pathlib import Path

# Ensure the project directory is on the import path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))


def _parse_args():
    parser = argparse.ArgumentParser(
        description="Start agentchattr (web UI + MCP server).",
        epilog="Flags override config.toml for this invocation. The same flags "
               "are also accepted by wrapper.py and wrapper_api.py so a launcher "
               "can isolate per-project instances by passing matching values to "
               "each process.",
    )
    parser.add_argument("--data-dir",      default=None, help="Override server.data_dir (path)")
    parser.add_argument("--port",          default=None, help="Override server.port (int)")
    parser.add_argument("--mcp-http-port", default=None, help="Override mcp.http_port (int)")
    parser.add_argument("--mcp-sse-port",  default=None, help="Override mcp.sse_port (int)")
    parser.add_argument("--upload-dir",    default=None, help="Override images.upload_dir (path)")
    parser.add_argument("--allow-network", action="store_true",
                        help="Allow binding to non-localhost hosts (with confirmation).")
    return parser.parse_args()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    # Parse flags for --help support; the actual env propagation happens via
    # the shared config_loader.apply_cli_overrides helper so run.py and the
    # wrappers use identical extraction logic.
    _parse_args()

    from config_loader import apply_cli_overrides, load_config
    apply_cli_overrides()

    config_path = ROOT / "config.toml"
    if not config_path.exists():
        print(f"Error: {config_path} not found")
        sys.exit(1)

    config = load_config(ROOT)

    # --- Security: generate a random session token (in-memory only) ---
    session_token = secrets.token_hex(32)

    # Configure the FastAPI app (creates shared store)
    from app import (
        app,
        configure,
        set_event_loop,
        store as _store_ref,
        _browser_has_access,
        _is_local_client,
        _remote_access_enabled,
        _set_browser_session_cookies,
    )
    configure(config, session_token=session_token)

    # Share stores with the MCP bridge
    from app import store, rules, summaries, jobs, room_settings, registry, router as app_router, agents as app_agents, session_engine, session_store
    import mcp_bridge
    mcp_bridge.store = store
    mcp_bridge.rules = rules
    mcp_bridge.summaries = summaries
    mcp_bridge.jobs = jobs
    mcp_bridge.room_settings = room_settings
    mcp_bridge.registry = registry
    mcp_bridge.config = config
    mcp_bridge.router = app_router
    mcp_bridge.agents = app_agents

    # Enable cursor and role persistence across restarts
    data_dir = ROOT / config.get("server", {}).get("data_dir", "./data")
    mcp_bridge._CURSORS_FILE = data_dir / "mcp_cursors.json"
    mcp_bridge._load_cursors()
    mcp_bridge._ROLES_FILE = data_dir / "roles.json"
    mcp_bridge._load_roles()

    # Start MCP servers in background threads
    http_port = config.get("mcp", {}).get("http_port", 8200)
    sse_port = config.get("mcp", {}).get("sse_port", 8201)
    mcp_bridge.mcp_http.settings.port = http_port
    mcp_bridge.mcp_sse.settings.port = sse_port

    threading.Thread(target=mcp_bridge.run_http_server, daemon=True).start()
    threading.Thread(target=mcp_bridge.run_sse_server, daemon=True).start()
    time.sleep(0.5)
    logging.getLogger(__name__).info("MCP streamable-http on port %d, SSE on port %d", http_port, sse_port)

    # Mount static files
    from fastapi.staticfiles import StaticFiles
    from fastapi.requests import Request
    from fastapi.responses import HTMLResponse

    static_dir = ROOT / "static"

    @app.get("/")
    async def index(request: Request):
        # Read index.html fresh each request so changes take effect without restart.
        # Remote browsers need an access secret before they receive a session.
        if not _is_local_client(request):
            if not _remote_access_enabled():
                return HTMLResponse(
                    """
                    <!DOCTYPE html>
                    <html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
                    <title>agentchattr</title>
                    <style>
                    body{font-family:ui-sans-serif,system-ui,sans-serif;background:#0d1117;color:#e6edf3;display:grid;place-items:center;min-height:100vh;margin:0}
                    main{max-width:520px;padding:32px;border:1px solid #30363d;border-radius:16px;background:#161b22}
                    code{background:#0d1117;padding:2px 6px;border-radius:6px}
                    </style></head><body><main><h1>Remote access disabled</h1>
                    <p>Set <code>network.shared_secret</code> before using agentchattr from another device.</p>
                    </main></body></html>
                    """,
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
            if not _browser_has_access(request):
                return HTMLResponse(
                    """
                    <!DOCTYPE html>
                    <html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
                    <title>agentchattr login</title>
                    <style>
                    body{font-family:ui-sans-serif,system-ui,sans-serif;background:#0d1117;color:#e6edf3;display:grid;place-items:center;min-height:100vh;margin:0}
                    form{display:grid;gap:12px;min-width:320px;max-width:360px;padding:28px;border:1px solid #30363d;border-radius:16px;background:#161b22}
                    input,button{font:inherit;padding:12px 14px;border-radius:10px;border:1px solid #30363d}
                    input{background:#0d1117;color:#e6edf3}
                    button{background:#238636;color:#fff;cursor:pointer}
                    p{margin:0;color:#8b949e;font-size:14px}
                    </style></head><body>
                    <form method="post" action="/auth/login" autocomplete="off">
                        <h1 style="margin:0">agentchattr</h1>
                        <p>Enter the shared access secret for this room.</p>
                        <input type="password" name="secret" placeholder="Shared secret" required autofocus>
                        <button type="submit">Enter room</button>
                    </form>
                    </body></html>
                    """,
                    headers={"Cache-Control": "no-store"},
                )
        html = (static_dir / "index.html").read_text("utf-8")
        response = HTMLResponse(html, headers={"Cache-Control": "no-store"})
        _set_browser_session_cookies(response, request)
        return response

    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Capture the event loop for the store→WebSocket bridge
    @app.on_event("startup")
    async def on_startup():
        set_event_loop(asyncio.get_running_loop())
        # Resume any sessions that were active before restart
        if session_engine:
            session_engine.resume_active_sessions()

    # Run web server
    import uvicorn
    host = config.get("server", {}).get("host", "127.0.0.1")
    port = config.get("server", {}).get("port", 8300)

    # --- Security: warn if binding to a non-localhost address ---
    if host not in ("127.0.0.1", "localhost", "::1"):
        print(f"\n  !! SECURITY WARNING — binding to {host} !!")
        print("  This exposes agentchattr to your local network.")
        print()
        print("  Risks:")
        print("  - No TLS: traffic (including session token) is plaintext")
        print("  - Anyone on your network can sniff the token and gain full access")
        print("  - With the token, anyone can @mention agents and trigger tool execution")
        print("  - If agents run with auto-approve, this means remote code execution")
        print()
        print("  Only use this on a trusted home network. Never on public/shared WiFi.")
        if "--allow-network" not in sys.argv:
            print("  Pass --allow-network to start anyway, or set host to 127.0.0.1.\n")
            sys.exit(1)
        else:
            print()
            try:
                confirm = input("  Type YES to accept these risks and start: ").strip()
            except (EOFError, KeyboardInterrupt):
                confirm = ""
            if confirm != "YES":
                print("  Aborted.\n")
                sys.exit(1)

    print(f"\n  agentchattr")
    print(f"  Web UI:  http://{host}:{port}")
    print(f"  MCP HTTP: http://{host}:{http_port}/mcp  (Claude, Codex)")
    print(f"  MCP SSE:  http://{host}:{sse_port}/sse   (Gemini)")
    print(f"  Data:    {data_dir}")
    print(f"  Agents auto-trigger on @mention")
    if config.get("network", {}).get("shared_secret"):
        print("  Remote access: enabled (shared secret required)")
    else:
        print("  Remote access: disabled until network.shared_secret is set")
    print()

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
