"""Path safety helpers.

Every file the application touches on disk is addressed by a randomized
server-side identifier, never by the client-supplied filename. These helpers
make it structurally hard to escape the storage root, follow a symlink, or
collide with an existing file.
"""
from __future__ import annotations

import os
import re
import uuid
from pathlib import Path

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


def new_file_id() -> str:
    """A random, unguessable identifier used as the on-disk filename stem."""
    return uuid.uuid4().hex


def sanitize_display_name(name: str) -> str:
    """Sanitize a filename for *display and download* purposes only.

    This is never used to construct a filesystem path — it only strips
    path separators and control characters so the name can be shown in the
    UI and offered as a download filename safely.
    """
    name = os.path.basename(name or "file")
    name = name.replace("\x00", "")
    name = _SAFE_NAME_RE.sub("_", name).strip("._") or "file"
    return name[:200]


def safe_join(root: Path, *parts: str) -> Path:
    """Join path parts under root, raising if the result escapes root or
    traverses a symlink planted inside root.
    """
    root = root.resolve()
    candidate = root.joinpath(*parts)
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("path traversal detected")
    # Reject if any existing intermediate component is a symlink.
    probe = root
    for part in candidate.relative_to(root).parts:
        probe = probe / part
        if probe.exists() and probe.is_symlink():
            raise ValueError("symlink in path not permitted")
    return resolved


def ensure_no_overwrite(path: Path) -> None:
    """Refuse to write onto an existing file/symlink (unsafe overwrite guard)."""
    if path.exists() or path.is_symlink():
        raise FileExistsError(f"refusing to overwrite existing path: {path.name}")
