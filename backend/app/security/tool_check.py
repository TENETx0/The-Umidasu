"""Detect availability of required external tools at startup."""
from __future__ import annotations

import shutil
from dataclasses import dataclass

from app.security.subprocess_exec import run_tool


@dataclass
class ToolStatus:
    name: str
    available: bool
    path: str | None
    version: str | None


def _version(argv: list[str]) -> str | None:
    try:
        result = run_tool(argv, timeout=5)
        text = (result.stdout_text or result.stderr_text).strip().splitlines()
        return text[0] if text else None
    except Exception:
        return None


def check_tools() -> list[ToolStatus]:
    statuses = []
    for name, version_argv in (
        ("exiftool", ["exiftool", "-ver"]),
        ("ffmpeg", ["ffmpeg", "-version"]),
        ("ffprobe", ["ffprobe", "-version"]),
    ):
        path = shutil.which(name)
        version = _version([path] + version_argv[1:]) if path else None
        statuses.append(ToolStatus(name=name, available=path is not None, path=path, version=version))
    return statuses
