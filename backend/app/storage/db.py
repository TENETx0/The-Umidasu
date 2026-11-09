"""SQLite-backed session/history store.

Synchronous sqlite3 wrapped behind simple functions is sufficient here: all
calls are short, local, single-writer operations invoked from FastAPI path
functions. A lock serializes writes to avoid "database is locked" errors
under concurrent requests from the same local user.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import settings

_lock = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS files (
    file_id TEXT PRIMARY KEY,
    original_filename TEXT NOT NULL,
    sanitized_filename TEXT NOT NULL,
    detected_format TEXT,
    mime_type TEXT,
    size_bytes INTEGER,
    original_sha256 TEXT,
    created_at TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    removed INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS operations (
    op_id TEXT PRIMARY KEY,
    file_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    fields_changed TEXT,
    original_hash TEXT,
    output_hash TEXT,
    output_file_id TEXT,
    tool_versions TEXT,
    success INTEGER NOT NULL,
    verification TEXT,
    timestamp TEXT NOT NULL,
    FOREIGN KEY(file_id) REFERENCES files(file_id)
);

CREATE TABLE IF NOT EXISTS presets (
    preset_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    fields_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);
"""

# Columns added after the initial release. Added via ALTER TABLE for
# installs whose umidasu.db predates this column, guarded so re-running
# init_db() on an already-migrated database is a harmless no-op.
_MIGRATIONS: list[tuple[str, str]] = [
    ("operations", "ALTER TABLE operations ADD COLUMN field_diffs_json TEXT"),
]


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(settings.DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with _lock, _connect() as conn:
        conn.executescript(SCHEMA)
        for table, stmt in _MIGRATIONS:
            try:
                conn.execute(stmt)
            except sqlite3.OperationalError as exc:
                if "duplicate column" not in str(exc).lower():
                    raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_file(file_id: str, original_filename: str, sanitized_filename: str,
                 detected_format: str, mime_type: str, size_bytes: int, original_sha256: str) -> None:
    ts = now_iso()
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO files (file_id, original_filename, sanitized_filename, detected_format, "
            "mime_type, size_bytes, original_sha256, created_at, last_accessed_at, removed) "
            "VALUES (?,?,?,?,?,?,?,?,?,0)",
            (file_id, original_filename, sanitized_filename, detected_format, mime_type, size_bytes, original_sha256, ts, ts),
        )


def touch_file(file_id: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE files SET last_accessed_at=? WHERE file_id=?", (now_iso(), file_id))


def mark_removed(file_id: str) -> None:
    with _lock, _connect() as conn:
        conn.execute("UPDATE files SET removed=1 WHERE file_id=?", (file_id,))


def list_recent_files(limit: int = 50) -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM files WHERE removed=0 ORDER BY last_accessed_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]


def record_operation(op_id: str, file_id: str, operation: str, fields_changed: list[str],
                      original_hash: str | None, output_hash: str | None, output_file_id: str | None,
                      tool_versions: dict, success: bool, verification: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO operations (op_id, file_id, operation, fields_changed, original_hash, output_hash, "
            "output_file_id, tool_versions, success, verification, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (op_id, file_id, operation, json.dumps(fields_changed), original_hash, output_hash, output_file_id,
             json.dumps(tool_versions), int(success), json.dumps(verification), now_iso()),
        )


def list_operations(file_id: str | None = None, limit: int = 200) -> list[dict]:
    with _lock, _connect() as conn:
        if file_id:
            rows = conn.execute(
                "SELECT * FROM operations WHERE file_id=? ORDER BY timestamp DESC LIMIT ?", (file_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM operations ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["fields_changed"] = json.loads(d["fields_changed"] or "[]")
            d["tool_versions"] = json.loads(d["tool_versions"] or "{}")
            d["verification"] = json.loads(d["verification"] or "{}")
            # Metadata Change History (feature #13) — per-field old/new
            # values, present for save_as operations recorded after this
            # feature shipped; absent (empty list) for older rows.
            d["field_diffs"] = json.loads(d.pop("field_diffs_json", None) or "[]")
            out.append(d)
        return out


def clear_session_data() -> None:
    """Wipe all history rows (used by the 'Clear Session Data' action). Does
    not delete files on disk — callers handle that separately."""
    with _lock, _connect() as conn:
        conn.execute("DELETE FROM operations")
        conn.execute("DELETE FROM files")


def record_operation_field_diffs(op_id: str, field_diffs: list[dict]) -> None:
    """Attach old/new per-field values to an already-recorded operation
    (Metadata Change History, feature #13). Stored separately from the
    INSERT in record_operation() so callers that don't have per-field
    before/after values yet (older call sites) are unaffected."""
    with _lock, _connect() as conn:
        conn.execute(
            "UPDATE operations SET field_diffs_json=? WHERE op_id=?",
            (json.dumps(field_diffs), op_id),
        )


# ---------------------------------------------------------------------------
# Metadata Presets (feature #11) — reusable templates of logical fields
# (author/copyright/title/description/keywords) a user can apply to any
# compatible file. fields_json stores a PresetLogicalFields-shaped dict.
# ---------------------------------------------------------------------------

def create_preset(preset_id: str, name: str, fields: dict) -> None:
    with _lock, _connect() as conn:
        conn.execute(
            "INSERT INTO presets (preset_id, name, fields_json, created_at) VALUES (?,?,?,?)",
            (preset_id, name, json.dumps(fields), now_iso()),
        )


def list_presets() -> list[dict]:
    with _lock, _connect() as conn:
        rows = conn.execute("SELECT * FROM presets ORDER BY created_at DESC").fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["fields"] = json.loads(d.pop("fields_json") or "{}")
            out.append(d)
        return out


def get_preset(preset_id: str) -> dict | None:
    with _lock, _connect() as conn:
        row = conn.execute("SELECT * FROM presets WHERE preset_id=?", (preset_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["fields"] = json.loads(d.pop("fields_json") or "{}")
        return d


def delete_preset(preset_id: str) -> bool:
    with _lock, _connect() as conn:
        cur = conn.execute("DELETE FROM presets WHERE preset_id=?", (preset_id,))
        return cur.rowcount > 0
