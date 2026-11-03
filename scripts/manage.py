"""Local setup/start helper. No provider calls, MCP startup or global configuration changes."""

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"


def run(args, **kwargs):
    subprocess.run([str(arg) for arg in args], check=True, **kwargs)


def executable(name):
    path = shutil.which(name)
    if not path:
        raise ValueError(f"Missing {name}. Install it and reopen your terminal.")
    return path


def prerequisites():
    if sys.version_info[:2] != (3, 12):
        raise ValueError("Use Python 3.12 for the pinned dependency set.")
    node = executable("node")
    npm = executable("npm.cmd" if os.name == "nt" else "npm")
    executable("git")
    npm_version = subprocess.check_output([npm, "--version"], text=True).strip()
    if int(npm_version.split(".")[0]) < 9:
        raise ValueError("npm 9 or later is required for the lockfile.")
    version = subprocess.check_output([node, "--version"], text=True).strip().lstrip("v")
    major, minor, *_ = map(int, version.split("."))
    if not ((major == 22 and minor >= 12) or major == 24 or major >= 26):
        raise ValueError("Use Node.js 22.12+ within v22, v24, or v26+ (Vitest engine constraint).")
    return npm


def python_path():
    return BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def setup(npm):
    python = python_path()
    if not python.exists():
        run([sys.executable, "-m", "venv", BACKEND / ".venv"])
    run(
        [
            python,
            "-c",
            "import sys; assert sys.version_info[:2] == (3, 12), 'Recreate venv with Python 3.12'",
        ]
    )
    run([python, "-m", "pip", "install", "-r", BACKEND / "requirements-lock.txt"])
    run([npm, "ci"], cwd=ROOT / "frontend")
    env = BACKEND / ".env"
    if not env.exists():
        # Exclusive creation: never overwrite an operator's credentials/configuration.
        with env.open("x", encoding="utf-8") as target:
            target.write((BACKEND / ".env.example").read_text(encoding="utf-8"))
    print("Setup complete. Edit backend/.env, then run scripts/start.ps1 or bash scripts/start.sh.")
    print("No API key is needed for local diff parsing. No audits were started.")


def address(value):
    url = urlsplit(value)
    if (
        url.scheme != "http"
        or url.hostname != "127.0.0.1"
        or not url.port
        or url.username
        or url.password
        or url.path not in ("", "/")
        or url.query
        or url.fragment
    ):
        raise ValueError("Start supports http://127.0.0.1:PORT URLs only.")
    return url.port


def available(port):
    with socket.socket() as sock:
        if os.name == "nt":
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError as exc:
            raise ValueError(
                f"Port {port} is occupied. Keep the existing service or stop it yourself."
            ) from exc


def start(npm):
    python = python_path()
    if not python.is_file() or not (ROOT / "frontend/node_modules").is_dir():
        raise ValueError("Run setup first.")
    # Load dotenv using the installed backend interpreter; do not print its values.
    code = (
        "from dotenv import dotenv_values; import json; "
        "print(json.dumps(dotenv_values('.env', interpolate=False)))"
    )

    config = json.loads(subprocess.check_output([str(python), "-c", code], cwd=BACKEND, text=True))
    env = {**{k: v for k, v in config.items() if v is not None}, **os.environ}
    api = env.get("INSPECTOR_API_URL", "http://127.0.0.1:8000")
    web = env.get("INSPECTOR_WEB_URL", "http://127.0.0.1:5173")
    ports = address(api), address(web)
    if ports[0] == ports[1]:
        raise ValueError("API and frontend ports must be different.")
    for port in ports:
        available(port)
    children = []
    try:
        children.append(
            subprocess.Popen(
                [
                    str(python),
                    "-m",
                    "uvicorn",
                    "app.main:app",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(ports[0]),
                    "--workers",
                    "1",
                ],
                cwd=BACKEND,
                env=env,
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        )
        # Launch Node directly: shutdown owns the Vite process, not an npm shell wrapper.
        children.append(
            subprocess.Popen(
                [
                    executable("node"),
                    "node_modules/vite/bin/vite.js",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(ports[1]),
                    "--strictPort",
                ],
                cwd=ROOT / "frontend",
                env={**os.environ, "INSPECTOR_API_URL": api},
                creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
            )
        )
        print(
            f"Frontend: {web}\nAPI: {api}/docs\nPress Ctrl+C to stop these two services.",
            flush=True,
        )
        while all(child.poll() is None for child in children):
            time.sleep(0.25)
        raise ValueError("A service stopped. Check its output above.")
    except KeyboardInterrupt:
        print("Stopping services started by this script.")
    finally:
        # Ignore additional Ctrl+C while waiting only for our own children.
        previous = signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            for child in children:
                if child.poll() is None:
                    if os.name == "nt":
                        child.send_signal(signal.CTRL_BREAK_EVENT)
                    else:
                        child.terminate()
            for child in children:
                try:
                    child.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()
        finally:
            signal.signal(signal.SIGINT, previous)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["setup", "start", "check"])
    args = parser.parse_args()
    try:
        npm = prerequisites()
        if args.action == "setup":
            setup(npm)
        elif args.action == "start":
            start(npm)
        else:
            print("Python 3.12, compatible Node.js, npm >=9 and Git are available.")
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        # Never print dotenv or inherited environment contents.
        print(f"Unable to {args.action}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
