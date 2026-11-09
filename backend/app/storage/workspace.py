"""In-memory + on-disk session workspace.

Each uploaded file gets a `file_id`. Three on-disk artifacts exist for it:
  originals/<file_id>__<ext>   - immutable, never written to after upload
  working/<file_id>__<ext>     - disposable copy the editor mutates
  output/<file_id>__<n>__<ext> - Save-As outputs, one per save

In-memory state (edit history, undo/redo stack, cached analysis) lives in
`SESSIONS`, a process-local dict. This is a local-first, single-user tool;
state does not need to survive a process restart, matching the documented
retention policy (originals/working data is also swept after
RETENTION_HOURS — see cleanup_expired()).
"""
from __future__ import annotations

import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from app.core.config import settings
from app.models.schemas import AnalysisResult, MetadataSnapshot
from app.security.paths import ensure_no_overwrite, new_file_id, safe_join, sanitize_display_name

_lock = threading.RLock()


@dataclass
class EditCommand:
    op_id: str
    field_key: str
    group: str
    action: str  # "set" | "remove"
    old_value: Any
    new_value: Any
    timestamp: str


@dataclass
class FileSession:
    file_id: str
    original_filename: str
    sanitized_filename: str
    extension: str
    original_path: Path
    working_path: Path
    original_sha256: str = ""
    analysis: Optional[AnalysisResult] = None
    undo_stack: list[EditCommand] = field(default_factory=list)
    redo_stack: list[EditCommand] = field(default_factory=list)
    pending_values: dict[str, Any] = field(default_factory=dict)  # field_key -> new value (or _DELETED sentinel)
    custom_timestamps: dict[str, str] = field(default_factory=dict)  # created/modified/accessed ISO strings
    output_counter: int = 0
    created_at: float = field(default_factory=time.time)
    last_touched: float = field(default_factory=time.time)
    snapshots: list[MetadataSnapshot] = field(default_factory=list)  # One-Click Metadata Snapshot


DELETED = object()
SESSIONS: dict[str, FileSession] = {}


def register_upload(original_filename: str, tmp_source: Path) -> FileSession:
    """Move a freshly-streamed upload into the originals dir under a random
    id, and create the disposable working copy."""
    file_id = new_file_id()
    sanitized = sanitize_display_name(original_filename)
    ext = Path(sanitized).suffix.lstrip(".")[:32] or "bin"

    original_dir = settings.ORIGINALS_DIR
    original_path = safe_join(original_dir, f"{file_id}.{ext}")
    ensure_no_overwrite(original_path)
    shutil.move(str(tmp_source), str(original_path))
    original_path.chmod(0o600)

    working_path = safe_join(settings.WORKING_DIR, f"{file_id}.{ext}")
    ensure_no_overwrite(working_path)
    shutil.copy2(original_path, working_path)
    working_path.chmod(0o600)

    sess = FileSession(
        file_id=file_id,
        original_filename=original_filename,
        sanitized_filename=sanitized,
        extension=ext,
        original_path=original_path,
        working_path=working_path,
    )
    with _lock:
        SESSIONS[file_id] = sess
    return sess


def take_snapshot(sess: FileSession, label: str) -> MetadataSnapshot:
    """One-Click Metadata Snapshot — capture the CURRENT writable field
    state (from sess.analysis, which reflects the working copy as last
    analyzed) so it can be restored later even after further edits or a
    removal preset has been applied."""
    from app.services.diff import build_field_map

    field_map: dict[str, Any] = {}
    if sess.analysis is not None:
        field_map, _labels = build_field_map(sess.analysis.sections, writable_only=True)

    snap = MetadataSnapshot(
        snapshot_id=uuid.uuid4().hex,
        label=label,
        created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        field_map=field_map,
    )
    sess.snapshots.append(snap)
    return snap


def get_session(file_id: str) -> FileSession:
    with _lock:
        sess = SESSIONS.get(file_id)
    if not sess:
        raise KeyError("unknown file_id")
    sess.last_touched = time.time()
    return sess


def revert_working_copy(sess: FileSession) -> None:
    """Restore the working copy from the immutable original, discarding any
    in-progress edits already written to disk."""
    shutil.copy2(sess.original_path, sess.working_path)
    sess.working_path.chmod(0o600)


def new_output_path(sess: FileSession) -> Path:
    sess.output_counter += 1
    name = f"{sess.file_id}__v{sess.output_counter}.{sess.extension}"
    path = safe_join(settings.OUTPUT_DIR, name)
    ensure_no_overwrite(path)
    return path


def remove_session(file_id: str, delete_files: bool = True) -> None:
    with _lock:
        sess = SESSIONS.pop(file_id, None)
    if sess and delete_files:
        for p in (sess.original_path, sess.working_path):
            try:
                if p.exists():
                    p.unlink()
            except OSError:
                pass


def cleanup_expired() -> int:
    """Delete sessions untouched for longer than RETENTION_HOURS. Returns
    the number of sessions removed. Intended to be called periodically."""
    cutoff = time.time() - settings.RETENTION_HOURS * 3600
    expired = []
    with _lock:
        for fid, sess in list(SESSIONS.items()):
            if sess.last_touched < cutoff:
                expired.append(fid)
    for fid in expired:
        remove_session(fid, delete_files=True)
    return len(expired)


def list_sessions() -> list[FileSession]:
    with _lock:
        return list(SESSIONS.values())
