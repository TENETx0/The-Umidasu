from __future__ import annotations

from pathlib import Path

from tests.conftest import FIXTURES_DIR


def _upload(client, name: str):
    path = FIXTURES_DIR / name
    with path.open("rb") as f:
        resp = client.post("/api/files/upload", files={"file": (name, f, "application/octet-stream")})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_system_status_reports_tools(client):
    resp = client.get("/api/system/status")
    assert resp.status_code == 200
    data = resp.json()
    names = {t["name"] for t in data["tools"]}
    assert {"exiftool", "ffmpeg", "ffprobe"} <= names


def test_upload_jpeg_identification_and_hashes(client):
    data = _upload(client, "sample.jpg")
    identity = data["analysis"]["identity"]
    assert identity["detected_format"] == "JPEG"
    assert identity["extension_matches_format"] is True
    hashes = data["analysis"]["hashes"]
    assert len(hashes["sha256"]) == 64
    assert len(hashes["md5"]) == 32


def test_upload_jpeg_extracts_gps_and_camera(client):
    data = _upload(client, "sample.jpg")
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    assert sections["gps"]["status"] == "extracted_successfully"
    assert sections["camera"]["status"] == "extracted_successfully"
    assert sections["author"]["status"] == "extracted_successfully"


def test_mime_extension_mismatch_detection(client):
    """A text file renamed to .jpg should be flagged as unidentifiable by
    signature, not silently trusted as a real JPEG."""
    data = _upload(client, "malformed.jpg")
    identity = data["analysis"]["identity"]
    assert identity["detected_format"] != "JPEG"


def test_edit_undo_redo_reset(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]

    r = client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "EXIF:Artist", "group": "Author/Personal", "action": "remove"}
    ]})
    assert r.status_code == 200
    assert r.json()["pending_count"] == 1

    r = client.post(f"/api/files/{fid}/edits/undo")
    assert r.status_code == 200
    assert r.json()["pending_count"] == 0

    r = client.post(f"/api/files/{fid}/edits/redo")
    assert r.status_code == 200
    assert r.json()["pending_count"] == 1

    r = client.post(f"/api/files/{fid}/edits/reset")
    assert r.status_code == 200

    r = client.post(f"/api/files/{fid}/edits/undo")
    assert r.status_code == 400  # nothing left to undo after reset


def test_save_as_removes_field_and_verifies(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]

    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "EXIF:Artist", "group": "Author/Personal", "action": "remove"}
    ]})
    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    body = r.json()
    assert any(e["field_key"] == "EXIF:Artist" for e in body["applied_edits"])
    assert body["verification"]["re_extracted"] is True
    assert body["verification"]["fields_present_after_edit"]["EXIF:Artist"] is None


def test_custom_timestamps_applied_to_output(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    client.put(f"/api/files/{fid}/custom-timestamps", json={
        "created": "2019-03-01T10:00:00Z", "modified": "2020-04-02T11:00:00Z",
    })
    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    ts_report = r.json()["verification"]["timestamp_report"]
    assert ts_report["filesystem"]["modified"] is True
    assert ts_report["filesystem"]["created"] is False  # documented Linux limitation
    assert "cannot be modified on Linux" in " ".join(ts_report["notes"])


def test_original_file_untouched_after_edits(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    original_sha = data["analysis"]["hashes"]["sha256"]

    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "EXIF:Artist", "group": "Author/Personal", "action": "remove"}
    ]})
    client.post(f"/api/files/{fid}/save-as")

    # Re-fetch analysis fresh from the (untouched) working copy's original twin
    from app.storage import workspace
    sess = workspace.get_session(fid)
    from app.services.hashing import compute_hashes
    assert compute_hashes(sess.original_path).sha256 == original_sha


def test_revert_working_copy_restores_removed_metadata(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]

    r = client.post(f"/api/files/{fid}/remove-preset", json={"presets": ["gps"]})
    assert r.status_code == 200
    sections = {s["section_id"]: s for s in r.json()["analysis"]["sections"]}
    assert sections["gps"]["status"] == "no_relevant_metadata_found"

    r = client.post(f"/api/files/{fid}/revert-working-copy")
    assert r.status_code == 200
    sections = {s["section_id"]: s for s in r.json()["analysis"]["sections"]}
    assert sections["gps"]["status"] == "extracted_successfully"


def test_remove_file_clears_session(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    r = client.delete(f"/api/files/{fid}")
    assert r.status_code == 200
    r = client.get(f"/api/files/{fid}/analysis")
    assert r.status_code == 404


def test_pdf_document_properties(client):
    data = _upload(client, "sample.pdf")
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    assert sections["pdf_document"]["status"] == "extracted_successfully"
    titles = [f for f in sections["pdf_document"]["fields"] if f["label"] == "title"]
    assert titles and titles[0]["raw_value"] == "Sample PDF"


def test_docx_core_properties_and_edit(client):
    data = _upload(client, "sample.docx")
    fid = data["file_id"]
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    assert sections["office_core"]["status"] == "extracted_successfully"

    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "core:author", "group": "Core Properties", "action": "set", "new_value": "Redacted"}
    ]})
    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    assert any(e["field_key"] == "core:author" for e in r.json()["applied_edits"])


def test_archive_listing_detects_path_traversal(client):
    data = _upload(client, "traversal.zip")
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    archive = sections["archive_members"]
    assert archive["status"] == "extracted_successfully"
    assert any("traversal" in w.lower() for w in archive["warnings"])


def test_reports_export_json_csv_html(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    for fmt in ("json", "csv", "html"):
        r = client.get(f"/api/files/{fid}/report.{fmt}")
        assert r.status_code == 200
        assert len(r.text) > 50


def test_download_rejects_path_traversal(client):
    """A traversal attempt must never return real file content. Depending
    on ASGI path normalization, the request either hits the download route
    (which must reject it with 400/404) or falls through to the SPA
    fallback (which safely serves index.html, never a filesystem path
    outside the frontend build) — either way, /etc/passwd must never leak."""
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    r = client.get(f"/api/files/{fid}/download/..%2f..%2f..%2fetc%2fpasswd")
    assert "root:" not in r.text
    assert r.headers.get("content-type", "").startswith("application/octet-stream") is False or r.status_code != 200


def test_empty_upload_rejected(client):
    r = client.post("/api/files/upload", files={"file": ("empty.bin", b"", "application/octet-stream")})
    assert r.status_code == 400


def test_history_recorded_after_save(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "EXIF:Artist", "group": "Author/Personal", "action": "remove"}
    ]})
    client.post(f"/api/files/{fid}/save-as")
    r = client.get("/api/history", params={"file_id": fid})
    assert r.status_code == 200
    ops = r.json()["operations"]
    assert len(ops) >= 1
    assert ops[0]["operation"] == "save_as"
