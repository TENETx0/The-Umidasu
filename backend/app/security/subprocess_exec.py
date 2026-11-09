"""Safe wrappers for invoking external tools (exiftool, ffprobe, ffmpeg).

All external tool calls MUST go through here. Never build a command via
string concatenation / shell=True; always pass an argv list so untrusted
filenames or values cannot be interpreted as shell syntax.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


class ExternalToolError(RuntimeError):
    pass


class ExternalToolTimeout(ExternalToolError):
    pass


@dataclass
class ToolResult:
    returncode: int
    stdout: bytes
    stderr: bytes

    @property
    def stdout_text(self) -> str:
        return self.stdout.decode("utf-8", errors="replace")

    @property
    def stderr_text(self) -> str:
        return self.stderr.decode("utf-8", errors="replace")


def run_tool(argv: list[str], timeout: int | None = None, cwd: Path | None = None) -> ToolResult:
    """Run an external tool with a hard timeout and no shell interpretation.

    argv[0] must be an absolute-resolvable executable name; arguments are
    passed as a list so no value is ever shell-interpreted. Output is
    captured (not streamed to a shared shell), and a timeout always
    terminates the process to bound resource usage on hostile input.
    """
    if not argv or not isinstance(argv, list):
        raise ValueError("argv must be a non-empty list")
    timeout = timeout or settings.PARSER_TIMEOUT_SECONDS
    try:
        proc = subprocess.run(
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            shell=False,
            cwd=str(cwd) if cwd else None,
        )
    except subprocess.TimeoutExpired as exc:
        raise ExternalToolTimeout(f"{argv[0]} timed out after {timeout}s") from exc
    except FileNotFoundError as exc:
        raise ExternalToolError(f"tool not found: {argv[0]}") from exc
    return ToolResult(proc.returncode, proc.stdout, proc.stderr)
