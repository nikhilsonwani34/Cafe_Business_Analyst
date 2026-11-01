"""Run the FastAPI backend and Vite frontend together for local development."""

from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
from types import FrameType
from typing import Sequence


ROOT = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
REQUIRED_PYTHON_MODULES = ("fastapi", "pydantic", "requests", "uvicorn")
SHUTDOWN_TIMEOUT_SECONDS = 8


def _python_executable() -> Path:
    if os.name == "nt":
        venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = ROOT / ".venv" / "bin" / "python"
    return venv_python if venv_python.is_file() else Path(sys.executable)


def _check_python_dependencies(python: Path) -> bool:
    check_script = (
        "import importlib.util, sys; "
        "missing = [name for name in sys.argv[1:] "
        "if importlib.util.find_spec(name) is None]; "
        "print(', '.join(missing)); sys.exit(bool(missing))"
    )
    result = subprocess.run(
        [str(python), "-c", check_script, *REQUIRED_PYTHON_MODULES],
        capture_output=True,
        check=False,
        text=True,
    )
    if result.returncode == 0:
        print(f"Python dependencies are available: {python}")
        return True

    missing = result.stdout.strip() or result.stderr.strip()
    print(f"Python dependency check failed: {missing}", file=sys.stderr)
    print(
        "Install project dependencies with "
        "`python -m pip install -r requirements.txt` "
        "(preferably inside a .venv).",
        file=sys.stderr,
    )
    return False


def _check_frontend() -> bool:
    if not (FRONTEND / "package.json").is_file():
        print("Frontend package.json is missing.", file=sys.stderr)
        return False
    if not (FRONTEND / "node_modules").is_dir():
        print(
            "Frontend dependencies are missing. Run `npm install` from "
            "the frontend directory.",
            file=sys.stderr,
        )
        return False
    if shutil.which("npm") is None:
        print("npm was not found on PATH; install Node.js and npm.", file=sys.stderr)
        return False
    print("Frontend dependencies are available.")
    return True


def _commands(python: Path) -> list[tuple[str, Sequence[str]]]:
    backend = [
        str(python),
        "-m",
        "uvicorn",
        "app.main:app",
        "--port",
        "8000",
    ]
    frontend = [
        "npm",
        "run",
        "dev",
        "--prefix",
        str(FRONTEND),
        "--",
        "--host",
        "127.0.0.1",
    ]
    if os.name == "nt":
        frontend = [
            os.environ.get("COMSPEC", "cmd.exe"),
            "/c",
            subprocess.list2cmdline(frontend),
        ]
    return [("Backend", backend), ("Frontend", frontend)]


def _start_process(command: Sequence[str]) -> subprocess.Popen[bytes]:
    options: dict[str, object] = {"cwd": ROOT}
    if os.name == "nt":
        options["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        options["start_new_session"] = True
    return subprocess.Popen(command, **options)


def _signal_process(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (OSError, ValueError):
        process.terminate()


def _stop_processes(processes: list[subprocess.Popen[bytes]]) -> None:
    active = [process for process in processes if process.poll() is None]
    for process in active:
        _signal_process(process)

    deadline = time.monotonic() + SHUTDOWN_TIMEOUT_SECONDS
    for process in active:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except OSError:
                    process.kill()
    for process in active:
        process.wait()


def _handle_interrupt(_: int, __: FrameType | None) -> None:
    raise KeyboardInterrupt


def main() -> int:
    if os.name == "nt" and hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, _handle_interrupt)

    python = _python_executable()
    if not _check_python_dependencies(python) or not _check_frontend():
        return 1

    processes: list[subprocess.Popen[bytes]] = []
    try:
        for name, command in _commands(python):
            process = _start_process(command)
            processes.append(process)
            print(f"{name} started (PID {process.pid}).")

        print("Open http://localhost:5173. Press Ctrl+C to stop both servers.")
        while True:
            for name, process in zip(("Backend", "Frontend"), processes):
                exit_code = process.poll()
                if exit_code is not None:
                    print(
                        f"{name} exited with status {exit_code}; "
                        "stopping the other server.",
                        file=sys.stderr,
                    )
                    return exit_code or 1
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping backend and frontend...")
        return 0
    except OSError as exc:
        print(f"Could not start project services: {exc}", file=sys.stderr)
        return 1
    finally:
        _stop_processes(processes)


if __name__ == "__main__":
    raise SystemExit(main())
