"""JSON subprocess boundary between the Python API and TypeScript browser runner."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import queue
import threading
from typing import Any

from .config import settings
from .cli_transport import account_environment, stop_process


class BrowserRunnerError(RuntimeError):
    pass


class BrowserSession:
    """An owned TypeScript browser process, with one browser across agent turns."""

    def __init__(self, base_url: str, path: str):
        entry = settings.browser_runner_entry.with_name('session.js')
        if not entry.is_file():
            raise BrowserRunnerError('Build browser_runner before running browser automation')
        self.messages: queue.Queue = queue.Queue()
        self.proc = subprocess.Popen(
            [settings.node_binary, str(entry)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL, text=True, encoding='utf-8', env=account_environment(),
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )

        def read():
            try:
                for line in self.proc.stdout:
                    self.messages.put(line)
            finally:
                self.messages.put(None)

        threading.Thread(target=read, daemon=True).start()
        try:
            self.initial = self.request({'baseUrl': base_url, 'path': path}, timeout=50)
            if 'snapshot' not in self.initial:
                raise BrowserRunnerError(self.initial.get('error') or 'Browser returned no initial observation')
        except Exception:
            self.close()
            raise

    def request(self, payload: dict, *, timeout: int = 60) -> dict:
        if self.proc.poll() is not None:
            raise BrowserRunnerError('Browser session has closed')
        self.proc.stdin.write(json.dumps(payload, ensure_ascii=False) + '\n')
        self.proc.stdin.flush()
        try:
            line = self.messages.get(timeout=timeout)
        except queue.Empty as exc:
            self.close()
            raise TimeoutError('Browser session did not respond within the action timeout') from exc
        if line is None:
            raise BrowserRunnerError('Browser session ended before returning an observation')
        try:
            result = json.loads(line)
        except ValueError as exc:
            raise BrowserRunnerError('Browser session returned invalid JSON') from exc
        if not isinstance(result, dict):
            raise BrowserRunnerError('Browser session returned invalid data')
        return result

    def close(self):
        if self.proc.poll() is None:
            try:
                self.proc.stdin.write('{"command":"close"}\n')
                self.proc.stdin.flush()
                self.proc.wait(timeout=4)
            except (OSError, subprocess.TimeoutExpired):
                stop_process(self.proc)
        for stream in (self.proc.stdin, self.proc.stdout):
            if stream:
                stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


def browser_runner_available() -> bool:
    if not settings.browser_runner_entry.is_file() or shutil.which(settings.node_binary) is None:
        return False
    try:
        return invoke_browser("health", {}, timeout=10).get("browserInstalled") is True
    except (BrowserRunnerError, TimeoutError):
        return False


def invoke_browser(command: str, payload: dict[str, Any], *, timeout: int = 60) -> dict[str, Any]:
    entry = settings.browser_runner_entry
    if not entry.is_file():
        raise BrowserRunnerError("TypeScript browser runner is not built; run npm install and npm run build in browser_runner")
    request = json.dumps({"command": command, **payload}, ensure_ascii=False)
    try:
        completed = subprocess.run(
            [settings.node_binary, str(entry)],
            input=request,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise BrowserRunnerError("Node.js 20+ is required for the TypeScript browser runner") from exc
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"TypeScript browser runner exceeded {timeout} seconds") from exc
    try:
        result = json.loads(completed.stdout)
    except (ValueError, TypeError) as exc:
        detail = (completed.stderr or completed.stdout or "No output from TypeScript browser runner")[:1500]
        raise BrowserRunnerError(detail) from exc
    if not isinstance(result, dict):
        raise BrowserRunnerError("TypeScript browser runner returned an invalid response")
    if completed.returncode != 0 or "error" in result:
        raise BrowserRunnerError(str(result.get("error") or completed.stderr or "Browser runner failed")[:2000])
    return result
