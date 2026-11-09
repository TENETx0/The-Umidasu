"""All HTTP routes for The Umidasu."""
from __future__ import annotations

import shutil
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import PlainTextResponse, StreamingResponse
from pydantic import BaseModel

from app.core.config import settings
from app.editors import metadata_editor
from app.models.schemas import (
    ApplyPresetResponse,
    CopyMetadataRequest,
    CopyMetadataResponse,
    CreatePresetRequest,
    CustomTimestamps,
    RemovalPresetRequest,
    SnapshotRequest,
)
from app.reports import builder as report_builder
from app.security.subprocess_exec import ExternalToolError, ExternalToolTimeout
from app.security.tool_check import check_tools
from app.services import copy_paste, domains, exiftool_service, hashing, preset_mapping, stream_integrity
from app.services.analysis import analyze_file
from app.services.diff import build_field_map, diff_field_maps
from app.storage import db, workspace

router = APIRouter()

MAX_UPLOAD = settings.MAX_UPLOAD_BYTES


# ---------------------------------------------------------------- system ---
@router.get("/system/status")
def system_status():
    tools = check_tools()
    return {
        "app_name": settings.APP_NAME,
        "app_version": settings.APP_VERSION,
        "app_author": settings.APP_AUTHOR,
        "host": settings.HOST,
        "port": settings.PORT,
        "max_upload_bytes": settings.MAX_UPLOAD_BYTES,
        "tools": [t.__dict__ for t in tools],
    }


# ---------------------------------------------------------------- upload ---
@router.post("/files/upload")
async def upload_file(file: UploadFile = File(...)):
    if not file.filename:
        raise HTTPException(400, "Filename is required")

    tmp_name = f"upload_{uuid.uuid4().hex}.part"
    tmp_path = settings.WORKING_DIR / tmp_name
    total = 0
    try:
        with tmp_path.open("wb") as out:
            while chunk := await file.read(settings.UPLOAD_CHUNK_SIZE):
                total += len(chunk)
                if total > MAX_UPLOAD:
                    out.close()
                    tmp_path.unlink(missing_ok=True)
                    raise HTTPException(413, f"File exceeds the {MAX_UPLOAD // (1024*1024)} MB upload limit")
                out.write(chunk)
    finally:
        await file.close()

    if total == 0:
        tmp_path.unlink(missing_ok=True)
        raise HTTPException(400, "Uploaded file is empty")

    sess = workspace.register_upload(file.filename, tmp_path)
    sess.original_sha256 = hashing.compute_hashes(sess.original_path).sha256

    try:
        analysis = analyze_file(sess.file_id, sess.working_path, sess.original_filename, sess.sanitized_filename)
    except Exception as exc:
        raise HTTPException(500, f"Analysis failed: {exc}") from exc

    sess.analysis = analysis
    db.record_file(sess.file_id, sess.original_filename, sess.sanitized_filename,
                    analysis.identity.detected_format, analysis.identity.mime_type,
                    analysis.identity.size_bytes, sess.original_sha256)

    # One-Click Metadata Snapshot (feature #2): capture the as-uploaded
    # state automatically so there is always a baseline to diff/restore
    # against, even if the user never explicitly takes one.
    workspace.take_snapshot(sess, "Original")

    return {"file_id": sess.file_id, "analysis": analysis.model_dump()}


@router.get("/files")
def list_files():
    return {"files": db.list_recent_files()}


@router.get("/files/{file_id}/analysis")
def get_analysis(file_id: str):
    sess = _require_session(file_id)
    return sess.analysis.model_dump() if sess.analysis else {}


@router.delete("/files/{file_id}")
def remove_file(file_id: str):
    _require_session(file_id)
    workspace.remove_session(file_id, delete_files=True)
    db.mark_removed(file_id)
    return {"removed": True}


# ------------------------------------------------------------- editing -----
class PendingEditIn(BaseModel):
    field_key: str
    group: str = ""
    action: str  # "set" | "remove"
    new_value: Any = None


class EditsBody(BaseModel):
    edits: list[PendingEditIn]


@router.put("/files/{file_id}/edits")
def set_pending_edits(file_id: str, body: EditsBody):
    """Replace the full set of pending (unsaved) edits for a file, pushing
    an undo command for each newly-added/changed edit."""
    sess = _require_session(file_id)
    before = dict(sess.pending_values)

    new_pending: dict[str, Any] = {}
    for e in body.edits:
        new_pending[e.field_key] = workspace.DELETED if e.action == "remove" else e.new_value

    for key, new_val in new_pending.items():
        old_val = before.get(key, "__unset__")
        if old_val == new_val:
            continue
        cmd = _make_cmd(sess, key, old_val if old_val != "__unset__" else None, new_val)
        sess.undo_stack.append(cmd)
        sess.redo_stack.clear()

    sess.pending_values = new_pending
    return {"pending_count": len(sess.pending_values)}


def _make_cmd(sess, field_key: str, old_value: Any, new_value: Any):
    from app.storage.workspace import EditCommand
    return EditCommand(
        op_id=uuid.uuid4().hex, field_key=field_key, group="", action="set" if new_value is not workspace.DELETED else "remove",
        old_value=old_value, new_value=new_value, timestamp=db.now_iso(),
    )


@router.post("/files/{file_id}/edits/undo")
def undo_edit(file_id: str):
    sess = _require_session(file_id)
    if not sess.undo_stack:
        raise HTTPException(400, "Nothing to undo")
    cmd = sess.undo_stack.pop()
    if cmd.old_value is None:
        sess.pending_values.pop(cmd.field_key, None)
    else:
        sess.pending_values[cmd.field_key] = cmd.old_value
    sess.redo_stack.append(cmd)
    return {"pending_count": len(sess.pending_values)}


@router.post("/files/{file_id}/edits/redo")
def redo_edit(file_id: str):
    sess = _require_session(file_id)
    if not sess.redo_stack:
        raise HTTPException(400, "Nothing to redo")
    cmd = sess.redo_stack.pop()
    sess.pending_values[cmd.field_key] = cmd.new_value
    sess.undo_stack.append(cmd)
    return {"pending_count": len(sess.pending_values)}


@router.post("/files/{file_id}/edits/reset")
def reset_pending_edits(file_id: str):
    """Reset Pending Changes: clears in-memory pending edits + undo/redo,
    restoring the editor to the initial extracted state. Does NOT touch the
    working copy on disk (that's Revert Working Copy, below)."""
    sess = _require_session(file_id)
    sess.pending_values.clear()
    sess.undo_stack.clear()
    sess.redo_stack.clear()
    return {"reset": True}


@router.post("/files/{file_id}/revert-working-copy")
def revert_working_copy(file_id: str):
    sess = _require_session(file_id)
    workspace.revert_working_copy(sess)
    sess.pending_values.clear()
    sess.undo_stack.clear()
    sess.redo_stack.clear()
    sess.analysis = analyze_file(sess.file_id, sess.working_path, sess.original_filename, sess.sanitized_filename)
    return {"reverted": True, "analysis": sess.analysis.model_dump()}


@router.put("/files/{file_id}/custom-timestamps")
def set_custom_timestamps(file_id: str, body: CustomTimestamps):
    sess = _require_session(file_id)
    sess.custom_timestamps = {k: v for k, v in body.model_dump().items() if v}
    return {"custom_timestamps": sess.custom_timestamps}


@router.post("/files/{file_id}/remove-preset")
def apply_removal_preset(file_id: str, body: RemovalPresetRequest):
    sess = _require_session(file_id)
    result = metadata_editor.strip_metadata_preset(sess.working_path, body.presets, sess.extension)
    sess.analysis = analyze_file(sess.file_id, sess.working_path, sess.original_filename, sess.sanitized_filename)
    return {"result": result, "analysis": sess.analysis.model_dump()}


# ---------------------------------------------------------------- save-as --
@router.post("/files/{file_id}/save-as")
def save_as(file_id: str):
    sess = _require_session(file_id)
    before_hash = hashing.compute_hashes(sess.working_path).sha256

    output_path = workspace.new_output_path(sess)

    # Old values for Metadata Change History (feature #13), captured from
    # the last analysis of the working copy before this save overwrites it.
    old_value_map: dict[str, Any] = {}
    if sess.analysis is not None:
        old_value_map = {f.key: f.normalized_value for s in sess.analysis.sections for f in s.fields}

    edits = []
    for key, val in sess.pending_values.items():
        edits.append({
            "field_key": key,
            "group": "",
            "action": "remove" if val is workspace.DELETED else "set",
            "new_value": None if val is workspace.DELETED else val,
        })

    try:
        outcome = metadata_editor.apply_edits_and_save(sess.working_path, output_path, sess.extension, edits)
    except Exception as exc:
        raise HTTPException(500, f"Save failed: {exc}") from exc

    if sess.custom_timestamps:
        ts_report = metadata_editor.apply_custom_timestamps(
            output_path, sess.custom_timestamps.get("created"),
            sess.custom_timestamps.get("modified"), sess.custom_timestamps.get("accessed"),
        )
    else:
        ts_report = None

    expected_keys = [e["field_key"] for e in outcome.applied]
    verification = metadata_editor.verify_output(sess.original_path, output_path, expected_keys)
    verification["timestamp_report"] = ts_report
    output_hashes = hashing.compute_hashes(output_path)
    verification["hash_changed_from_working_copy"] = output_hashes.sha256 != before_hash

    # Save Without Recompression (feature #15): structurally verify the
    # actual image/video/audio stream was left byte-for-byte identical.
    # Honestly reports measured=False for formats with no implemented
    # verifier rather than assuming success.
    verification["stream_preservation"] = stream_integrity.stream_preservation_report(
        sess.working_path, output_path, sess.extension,
    )

    # Metadata Change History (feature #13): old -> new value per field
    # actually applied, stored alongside the operation row.
    field_diffs = [
        {
            "key": e["field_key"],
            "old_value": old_value_map.get(e["field_key"]),
            "new_value": None if e["action"] == "remove" else e.get("new_value"),
            "action": e["action"],
        }
        for e in outcome.applied
    ]

    op_id = uuid.uuid4().hex
    db.record_operation(
        op_id=op_id, file_id=file_id, operation="save_as",
        fields_changed=expected_keys, original_hash=sess.original_sha256,
        output_hash=output_hashes.sha256, output_file_id=output_path.name,
        tool_versions=outcome.tool_versions, success=len(outcome.failed) == 0,
        verification=verification,
    )
    if field_diffs:
        db.record_operation_field_diffs(op_id, field_diffs)

    return {
        "output_file_id": output_path.name,
        "output_filename": f"{Path(sess.sanitized_filename).stem}_edited.{sess.extension}",
        "output_hashes": output_hashes.model_dump(),
        "applied_edits": outcome.applied,
        "unsupported_edits": outcome.unsupported,
        "failed_edits": outcome.failed,
        "verification": verification,
        "field_diffs": field_diffs,
    }


@router.get("/files/{file_id}/download/{output_name}")
def download_output(file_id: str, output_name: str):
    _require_session(file_id)
    from app.security.paths import safe_join
    try:
        path = safe_join(settings.OUTPUT_DIR, output_name)
    except ValueError:
        raise HTTPException(400, "Invalid output reference")
    if not path.exists():
        raise HTTPException(404, "Output not found")

    def stream():
        with path.open("rb") as f:
            while chunk := f.read(1024 * 1024):
                yield chunk

    return StreamingResponse(stream(), media_type="application/octet-stream",
                              headers={"Content-Disposition": f'attachment; filename="{output_name}"'})


# ------------------------------------------------------------- snapshots --
@router.get("/files/{file_id}/snapshots")
def list_snapshots(file_id: str):
    sess = _require_session(file_id)
    return {"snapshots": [s.model_dump() for s in sess.snapshots]}


@router.post("/files/{file_id}/snapshots")
def create_snapshot(file_id: str, body: SnapshotRequest):
    sess = _require_session(file_id)
    snap = workspace.take_snapshot(sess, body.label or f"Snapshot {len(sess.snapshots) + 1}")
    return {"snapshot": snap.model_dump()}


@router.delete("/files/{file_id}/snapshots/{snapshot_id}")
def delete_snapshot(file_id: str, snapshot_id: str):
    sess = _require_session(file_id)
    before = len(sess.snapshots)
    sess.snapshots = [s for s in sess.snapshots if s.snapshot_id != snapshot_id]
    if len(sess.snapshots) == before:
        raise HTTPException(404, "Snapshot not found")
    return {"deleted": True}


@router.post("/files/{file_id}/snapshots/{snapshot_id}/restore")
def restore_snapshot(file_id: str, snapshot_id: str):
    """Stage pending edits that bring every writable field back to its
    value at snapshot time (fields added since the snapshot are staged for
    removal). Nothing is written to disk until the usual Save As."""
    sess = _require_session(file_id)
    snap = next((s for s in sess.snapshots if s.snapshot_id == snapshot_id), None)
    if snap is None:
        raise HTTPException(404, "Snapshot not found")

    current_map: dict[str, Any] = {}
    if sess.analysis is not None:
        current_map, _ = build_field_map(sess.analysis.sections, writable_only=True)

    new_pending: dict[str, Any] = {}
    for key, snap_val in snap.field_map.items():
        if current_map.get(key) != snap_val:
            new_pending[key] = snap_val
    for key in current_map:
        if key not in snap.field_map:
            new_pending[key] = workspace.DELETED

    sess.pending_values = new_pending
    sess.undo_stack.clear()
    sess.redo_stack.clear()
    return {
        "restored": True,
        "snapshot_id": snapshot_id,
        "pending_count": len(sess.pending_values),
        # Explicit staged entries so the client can mirror server-side
        # pending state exactly (it was replaced wholesale, not merged).
        "pending": [
            {"key": k, "action": "remove"} if v is workspace.DELETED else {"key": k, "action": "set", "value": v}
            for k, v in sess.pending_values.items()
        ],
    }


# ------------------------------------------------- difference highlighting -
@router.get("/files/{file_id}/diff")
def get_diff(file_id: str, snapshot_id: str | None = None):
    """Metadata Difference Highlighting (feature #3): diff a snapshot's
    field map against the CURRENT state, which includes any unsaved pending
    edits layered on top of the last analysis — so the highlight updates
    live as the user edits, not just after a save."""
    sess = _require_session(file_id)
    if not sess.snapshots:
        raise HTTPException(400, "No snapshot exists yet for this file to diff against.")

    baseline = sess.snapshots[0] if snapshot_id is None else next(
        (s for s in sess.snapshots if s.snapshot_id == snapshot_id), None)
    if baseline is None:
        raise HTTPException(404, "Snapshot not found")

    current_map, label_map = ({}, {})
    if sess.analysis is not None:
        current_map, label_map = build_field_map(sess.analysis.sections, writable_only=True)
    for key, val in sess.pending_values.items():
        if val is workspace.DELETED:
            current_map.pop(key, None)
        else:
            current_map[key] = val
            label_map.setdefault(key, key)

    result = diff_field_maps(baseline.field_map, current_map, labels=label_map)
    result.baseline_label = baseline.label
    return result.model_dump()


# ----------------------------------------------------------- copy & paste --
@router.post("/files/{file_id}/copy-metadata", response_model=CopyMetadataResponse)
def copy_metadata(file_id: str, body: CopyMetadataRequest):
    """Metadata Copy & Paste (feature #1): compute which writable fields on
    `source_file_id` are compatible with `file_id`'s format domain and stage
    the compatible ones as pending edits (never written directly)."""
    sess = _require_session(file_id)
    source_sess = _require_session(body.source_file_id)
    if sess.analysis is None or source_sess.analysis is None:
        raise HTTPException(400, "Both the source and target files must be analyzed first.")

    candidates = copy_paste.compute_copy_candidates(source_sess.analysis, sess.analysis, body.field_keys)

    staged_count = 0
    for c in candidates:
        if not c.compatible:
            continue
        old_val = sess.pending_values.get(c.key, "__unset__")
        if old_val != c.value:
            cmd = _make_cmd(sess, c.key, old_val if old_val != "__unset__" else None, c.value)
            sess.undo_stack.append(cmd)
            sess.redo_stack.clear()
        sess.pending_values[c.key] = c.value
        c.staged = True
        staged_count += 1

    return CopyMetadataResponse(results=candidates, staged_count=staged_count)


# --------------------------------------------------------------- presets --
@router.get("/presets")
def list_presets():
    return {"presets": db.list_presets()}


@router.post("/presets")
def create_preset(body: CreatePresetRequest):
    preset_id = uuid.uuid4().hex
    db.create_preset(preset_id, body.name, body.fields.model_dump())
    return {"preset": db.get_preset(preset_id)}


@router.delete("/presets/{preset_id}")
def delete_preset(preset_id: str):
    if not db.delete_preset(preset_id):
        raise HTTPException(404, "Preset not found")
    return {"deleted": True}


@router.post("/files/{file_id}/apply-preset/{preset_id}", response_model=ApplyPresetResponse)
def apply_preset(file_id: str, preset_id: str):
    """Metadata Presets (feature #11): map the preset's logical fields onto
    concrete keys for this file's metadata domain and stage them as pending
    edits. Logical fields with no sensible analog in this domain (e.g.
    'copyright' on a PDF) are reported as skipped, not force-mapped."""
    sess = _require_session(file_id)
    preset = db.get_preset(preset_id)
    if preset is None:
        raise HTTPException(404, "Preset not found")
    if sess.analysis is None:
        raise HTTPException(400, "File has not been analyzed yet.")

    target_section_ids = {s.section_id for s in sess.analysis.sections}
    domain = domains.domain_for_analysis(target_section_ids)

    staged: list[dict] = []
    skipped: list[dict] = []

    if domain is None:
        for logical_name, value in preset["fields"].items():
            if value:
                skipped.append({"logical_name": logical_name, "reason": "This file format exposes no writable metadata domain."})
        return ApplyPresetResponse(staged=staged, skipped=skipped)

    for logical_name, value in preset["fields"].items():
        if not value:
            continue
        keys = preset_mapping.concrete_keys_for(logical_name, domain)
        if not keys:
            skipped.append({"logical_name": logical_name, "reason": f"No equivalent field for this file's format ({domain})."})
            continue
        for key in keys:
            old_val = sess.pending_values.get(key, "__unset__")
            if old_val != value:
                cmd = _make_cmd(sess, key, old_val if old_val != "__unset__" else None, value)
                sess.undo_stack.append(cmd)
                sess.redo_stack.clear()
            sess.pending_values[key] = value
            staged.append({"logical_name": logical_name, "key": key, "value": value})

    return ApplyPresetResponse(staged=staged, skipped=skipped)


# ----------------------------------------------------------------- history -
@router.get("/history")
def get_history(file_id: str | None = None):
    return {"operations": db.list_operations(file_id=file_id)}


@router.post("/history/clear")
def clear_history():
    db.clear_session_data()
    return {"cleared": True}


# ----------------------------------------------------------------- reports -
@router.get("/files/{file_id}/report.{fmt}")
def export_report(file_id: str, fmt: str):
    sess = _require_session(file_id)
    if not sess.analysis:
        raise HTTPException(400, "No analysis available")
    if fmt == "json":
        return PlainTextResponse(report_builder.build_json_report(sess.analysis), media_type="application/json")
    if fmt == "csv":
        return PlainTextResponse(report_builder.build_csv_report(sess.analysis), media_type="text/csv")
    if fmt == "html":
        return PlainTextResponse(report_builder.build_html_report(sess.analysis), media_type="text/html")
    raise HTTPException(400, "Unsupported report format. Use json, csv, or html.")


def _require_session(file_id: str):
    try:
        return workspace.get_session(file_id)
    except KeyError:
        raise HTTPException(404, "File not found in this session. It may have expired or been removed.")
