#!/usr/bin/env python3
"""
Launcher — starts all 7 servers (MCP + 5 agents + web) as subprocesses.

Usage:
    python start.py

Press Ctrl+C to stop all servers.
"""
import os
import sys
import time
import signal
import subprocess

# Ensure we're running from the project root
ROOT = os.path.dirname(os.path.abspath(__file__))
os.chdir(ROOT)

PYTHON = sys.executable

SERVERS = [
    ("MCP Server",      [PYTHON, "mcp_server/http_app.py"]),
    ("Reviewer Agent",  [PYTHON, "agents/run_reviewer.py"]),
    ("Planner Agent",   [PYTHON, "agents/run_planner.py"]),
    ("Writer Agent",    [PYTHON, "agents/run_writer.py"]),
    ("Gatekeeper Agent",[PYTHON, "agents/run_gatekeeper.py"]),
    ("Orchestrator",    [PYTHON, "agents/run_orchestrator.py"]),
    ("Web Server",      [PYTHON, "-m", "uvicorn", "web.app:app",
                         "--host", "0.0.0.0", "--port", "8000"]),
]

processes: list[subprocess.Popen] = []


def start_all():
    print("=" * 60)
    print("  GitHub Repository Agent — Starting all servers")
    print("=" * 60)

    for name, cmd in SERVERS:
        print(f"  Starting {name}...")
        proc = subprocess.Popen(
            cmd,
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        processes.append(proc)
        time.sleep(0.5)  # stagger startup

    print()
    print("  All servers started!")
    print("  Web UI: http://localhost:8000")
    print("  Press Ctrl+C to stop all servers.")
    print("=" * 60)


def stop_all():
    print("\n  Stopping all servers...")
    for proc in processes:
        try:
            proc.terminate()
        except Exception:
            pass
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
    print("  All servers stopped.")


def main():
    def handler(sig, frame):
        stop_all()
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)

    start_all()

    # Keep running until interrupted
    try:
        while True:
            # Check if any process has died
            for i, (name, _) in enumerate(SERVERS):
                if processes[i].poll() is not None:
                    print(f"  WARNING: {name} exited with code {processes[i].returncode}")
            time.sleep(5)
    except KeyboardInterrupt:
        stop_all()


if __name__ == "__main__":
    main()
