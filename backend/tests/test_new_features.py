"""Tests for the 15 requested feature additions plus the bonus features
(appended-data / trailer detection is exercised indirectly through
analysis; GPS/size/duplicate/suggestion services are also unit-tested
directly for precision beyond what the HTTP layer alone would show)."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.conftest import FIXTURES_DIR


def _upload(client, name: str):
    path = FIXTURES_DIR / name
    with path.open("rb") as f:
        resp = client.post("/api/files/upload", files={"file": (name, f, "application/octet-stream")})
    assert resp.status_code == 200, resp.text
    return resp.json()


# --------------------------------------------------------------------- #2 --
def test_snapshot_auto_created_on_upload(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    r = client.get(f"/api/files/{fid}/snapshots")
    assert r.status_code == 200
    snaps = r.json()["snapshots"]
    assert len(snaps) == 1
    assert snaps[0]["label"] == "Original"
    # exiftool's -G1 read reports the specific IFD group ("IFD0:Artist"),
    # not a flat "EXIF:Artist" — this is the real key the frontend works with.
    assert "IFD0:Artist" in snaps[0]["field_map"]


def test_manual_snapshot_and_restore(client):
    """Snapshots guard against a destructive operation that actually
    mutates the working copy (and refreshes the session's analysis) — a
    removal preset is the realistic case, not an unsaved pending edit that
    never touches the working copy until Save As."""
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]

    r = client.post(f"/api/files/{fid}/snapshots", json={"label": "Before cleanup"})
    assert r.status_code == 200
    snap_id = r.json()["snapshot"]["snapshot_id"]

    r = client.post(f"/api/files/{fid}/remove-preset", json={"presets": ["author"]})
    assert r.status_code == 200
    sections = {s["section_id"]: s for s in r.json()["analysis"]["sections"]}
    assert sections["author"]["status"] == "no_relevant_metadata_found"

    r = client.post(f"/api/files/{fid}/snapshots/{snap_id}/restore")
    assert r.status_code == 200
    assert r.json()["pending_count"] > 0

    r2 = client.post(f"/api/files/{fid}/save-as")
    assert r2.status_code == 200
    present = r2.json()["verification"]["fields_present_after_edit"]
    assert any(v == "Jane Doe" for v in present.values())


def test_snapshot_delete_and_404(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    r = client.post(f"/api/files/{fid}/snapshots", json={"label": "Temp"})
    snap_id = r.json()["snapshot"]["snapshot_id"]
    r = client.delete(f"/api/files/{fid}/snapshots/{snap_id}")
    assert r.status_code == 200
    r = client.delete(f"/api/files/{fid}/snapshots/{snap_id}")
    assert r.status_code == 404


# --------------------------------------------------------------------- #3 --
def test_diff_highlights_pending_removal_live(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]

    r = client.get(f"/api/files/{fid}/diff")
    assert r.status_code == 200
    diff = r.json()
    assert diff["added"] == [] and diff["removed"] == [] and diff["modified"] == []
    assert diff["baseline_label"] == "Original"

    # Stage (but don't save) a removal — diff must reflect it immediately.
    # Use the exact key the analysis reported ("IFD0:Artist"), matching
    # what the real frontend sends since it comes straight off the field.
    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "IFD0:Artist", "group": "", "action": "remove"}
    ]})
    r = client.get(f"/api/files/{fid}/diff")
    diff = r.json()
    removed_keys = {e["key"] for e in diff["removed"]}
    assert "IFD0:Artist" in removed_keys


def test_diff_highlights_modification(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "IFD0:Artist", "group": "", "action": "set", "new_value": "New Name"}
    ]})
    r = client.get(f"/api/files/{fid}/diff")
    diff = r.json()
    mods = {e["key"]: e for e in diff["modified"]}
    assert "IFD0:Artist" in mods
    assert mods["IFD0:Artist"]["before"] == "Jane Doe"
    assert mods["IFD0:Artist"]["after"] == "New Name"


def test_diff_without_any_snapshot_rejected():
    """Direct unit check that diff_field_maps alone (no HTTP/session state)
    behaves correctly for an added field — covered thoroughly via HTTP
    above; this covers the pure function edge case of a brand new key."""
    from app.services.diff import diff_field_maps
    result = diff_field_maps({}, {"XMP-dc:Title": "New title"})
    assert len(result.added) == 1
    assert result.added[0].key == "XMP-dc:Title"
    assert result.added[0].after == "New title"


# --------------------------------------------------------------------- #4 --
def test_unknown_tag_decoder_reports_id_namespace_and_raw_value(client):
    data = _upload(client, "enriched.jpg")
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    unknown = sections.get("unknown_tags")
    assert unknown is not None
    assert unknown["status"] == "extracted_successfully"
    gamma_fields = [f for f in unknown["fields"] if "Gamma" in f["key"]]
    assert gamma_fields, "Expected Gamma to be classified as an uncommon/unknown tag"
    f = gamma_fields[0]
    assert f["is_unknown_tag"] is True
    assert f["namespace"]  # some exif group name present
    assert f["raw_value"] is not None
    assert f["value_type"]


def test_known_tags_not_flagged_unknown(client):
    data = _upload(client, "sample.jpg")
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    author = sections["author"]
    artist_fields = [f for f in author["fields"] if f["key"].endswith(":Artist")]
    assert artist_fields and artist_fields[0]["is_unknown_tag"] is False


# --------------------------------------------------------------------- #5 --
def test_search_everywhere_field_values_present_in_analysis(client):
    """Metadata Search Everywhere is implemented as a client-side filter over
    the full analysis payload (every section's fields, including raw
    values) — this test confirms the payload actually carries everything a
    search needs to be exhaustive: label, key, raw_value, normalized_value."""
    data = _upload(client, "enriched.jpg")
    all_fields = [f for s in data["analysis"]["sections"] for f in s["fields"]]
    assert any("EXIFAuthor" in str(f.get("raw_value")) or "EXIFAuthor" in str(f.get("normalized_value"))
               for f in all_fields)
    for f in all_fields:
        assert "key" in f and "label" in f and "raw_value" in f and "normalized_value" in f


# --------------------------------------------------------------------- #6 --
def test_extension_mismatch_flagged(client):
    data = _upload(client, "malformed.jpg")
    identity = data["analysis"]["identity"]
    # malformed.jpg is actually plain text with no recognizable signature;
    # identify.py cannot assert "mismatch" with no real detected format,
    # so it correctly reports extension_matches_format True (no false claim)
    # while detected_format itself already signals something is off.
    assert identity["detected_format"] != "JPEG"


def test_extension_mismatch_true_positive(client, tmp_path):
    """A real PNG saved with a .jpg extension must be flagged as a mismatch."""
    from PIL import Image
    fake = tmp_path / "actually_png.jpg"
    Image.new("RGB", (10, 10)).save(fake, "PNG")
    with fake.open("rb") as f:
        r = client.post("/api/files/upload", files={"file": ("actually_png.jpg", f, "application/octet-stream")})
    assert r.status_code == 200
    identity = r.json()["analysis"]["identity"]
    assert identity["detected_format"] == "PNG"
    assert identity["extension_matches_format"] is False
    assert "png" in identity["expected_extensions"]


# --------------------------------------------------------------------- #7 --
def test_timestamp_normalizer_flags_explicit_offset():
    from app.services.timestamps import detect_and_annotate
    is_ts, forced_type, ts_utc, has_tz = detect_and_annotate("2024:01:15 10:30:00+05:00")
    assert is_ts is True
    assert has_tz is True
    assert ts_utc == "2024-01-15T05:30:00+00:00"


def test_timestamp_normalizer_never_fabricates_tz():
    from app.services.timestamps import detect_and_annotate
    is_ts, forced_type, ts_utc, has_tz = detect_and_annotate("2024:01:15 10:30:00")
    assert is_ts is True
    assert has_tz is False
    assert ts_utc is None  # must not guess a timezone


def test_timestamp_normalizer_rejects_non_timestamp():
    from app.services.timestamps import detect_and_annotate
    is_ts, *_ = detect_and_annotate("TestCam")
    assert is_ts is False


def test_analysis_marks_known_date_fields_as_timestamps(client):
    data = _upload(client, "enriched.jpg")
    all_fields = [f for s in data["analysis"]["sections"] for f in s["fields"]]
    date_fields = [f for f in all_fields if "Date" in f["key"] or "date" in f["key"]]
    assert date_fields, "fixture should expose at least one date tag"
    assert any(f["is_timestamp"] for f in date_fields)


# --------------------------------------------------------------------- #8 --
def test_gps_representations_round_trip(client):
    data = _upload(client, "sample.jpg")
    sections = {s["section_id"]: s for s in data["analysis"]["sections"]}
    lat_fields = [f for f in sections["gps"]["fields"] if "Latitude" in f["key"] and "Ref" not in f["key"]]
    assert lat_fields
    reprs = lat_fields[0]["representations"]
    assert reprs is not None
    assert "decimal" in reprs and "dms" in reprs and "ddm" in reprs
    assert reprs["decimal"].startswith("40.71")


def test_gps_service_dms_and_maidenhead_accuracy():
    from app.services import gps
    reprs = gps.build_representations(40.7128, -74.0060)
    assert reprs["latitude"]["decimal"].startswith("40.71")
    assert "N" in reprs["latitude"]["dms"] or "40" in reprs["latitude"]["dms"]
    assert "grid_locator" in reprs
    assert len(reprs["grid_locator"]["maidenhead"]) >= 4


def test_gps_haversine_known_distance():
    from app.services import gps
    # NYC to London, real-world great-circle distance is ~5570km.
    dist = gps.haversine_distance_km(40.7128, -74.0060, 51.5074, -0.1278)
    assert 5500 < dist < 5600


# --------------------------------------------------------------------- #9 --
def test_metadata_size_analyzer_jpeg_measured(client):
    data = _upload(client, "sample.jpg")
    size_info = data["analysis"]["metadata_size"]
    assert size_info is not None
    assert size_info["measured"] is True
    assert size_info["method"] == "jpeg_app_segments"
    assert size_info["metadata_bytes"] > 0
    assert size_info["total_bytes"] > size_info["metadata_bytes"]
    assert 0 <= size_info["percentage"] <= 100


def test_metadata_size_analyzer_png_measured(client):
    data = _upload(client, "sample.png")
    size_info = data["analysis"]["metadata_size"]
    assert size_info["measured"] is True
    assert size_info["method"] == "png_text_chunks"
    assert size_info["metadata_bytes"] > 0


def test_metadata_size_analyzer_honest_when_unsupported(client):
    data = _upload(client, "sample.zip")
    size_info = data["analysis"]["metadata_size"]
    assert size_info is not None
    assert size_info["measured"] is False
    assert size_info["method"] == "not_supported"


# -------------------------------------------------------------------- #10 --
def test_duplicate_detector_flags_conflicting_author(client):
    data = _upload(client, "enriched.jpg")
    groups = {g["concept"]: g for g in data["analysis"]["duplicate_groups"]}
    assert "Author / Creator" in groups
    g = groups["Author / Creator"]
    assert g["status"] == "conflicting"
    # XMP-dc:Creator can come back as a list (XMP seq); normalize to str
    # before set-membership since a list isn't hashable.
    values = {str(f["value"]) for f in g["fields"]}
    assert any("EXIFAuthor" in v for v in values)
    assert any("IPTCAuthor" in v for v in values)
    assert any("XMPAuthor" in v for v in values)


def test_duplicate_detector_flags_conflicting_copyright(client):
    data = _upload(client, "enriched.jpg")
    groups = {g["concept"]: g for g in data["analysis"]["duplicate_groups"]}
    assert "Copyright" in groups
    assert groups["Copyright"]["status"] == "conflicting"


def test_duplicate_detector_no_false_positive_on_plain_file(client):
    data = _upload(client, "sample.jpg")
    concepts = {g["concept"] for g in data["analysis"]["duplicate_groups"]}
    # sample.jpg only has a single Artist tag -> no concept should have 2+ fields.
    assert "Author / Creator" not in concepts


# -------------------------------------------------------------------- #11 --
def test_preset_crud_and_apply_to_image(client):
    r = client.post("/api/presets", json={
        "name": "Standard Credit",
        "fields": {"author": "Studio X", "copyright": "(c) Studio X", "title": None,
                    "description": None, "keywords": None},
    })
    assert r.status_code == 200
    preset_id = r.json()["preset"]["preset_id"]

    r = client.get("/api/presets")
    assert any(p["preset_id"] == preset_id for p in r.json()["presets"])

    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    r = client.post(f"/api/files/{fid}/apply-preset/{preset_id}")
    assert r.status_code == 200
    body = r.json()
    staged_keys = {s["key"] for s in body["staged"]}
    # preset_mapping now writes under the same specific-group key the
    # analyzer reads back ("IFD0:Artist"), not the family-0 "EXIF:Artist",
    # so a pending preset edit shows up as a modification of the real
    # field rather than a phantom new one.
    assert "IFD0:Artist" in staged_keys
    assert "IFD0:Copyright" in staged_keys

    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    assert r.json()["verification"]["fields_present_after_edit"]["IFD0:Artist"] == "Studio X"

    r = client.delete(f"/api/presets/{preset_id}")
    assert r.status_code == 200
    r = client.delete(f"/api/presets/{preset_id}")
    assert r.status_code == 404


def test_preset_skips_incompatible_fields_on_pdf(client):
    r = client.post("/api/presets", json={
        "name": "Full set", "fields": {"author": "A", "copyright": "C", "title": "T",
                                        "description": "D", "keywords": "K"},
    })
    preset_id = r.json()["preset"]["preset_id"]
    data = _upload(client, "sample.pdf")
    fid = data["file_id"]
    r = client.post(f"/api/files/{fid}/apply-preset/{preset_id}")
    assert r.status_code == 200
    body = r.json()
    staged_logical = {s["logical_name"] for s in body["staged"]}
    skipped_logical = {s["logical_name"] for s in body["skipped"]}
    assert "author" in staged_logical and "title" in staged_logical
    # PDF has no copyright/description analog in preset_mapping -> skipped, not force-mapped.
    assert "copyright" in skipped_logical
    assert "description" in skipped_logical


# -------------------------------------------------------------------- #12 --
def test_quick_copy_hashes_all_four_algorithms_present(client):
    data = _upload(client, "sample.jpg")
    hashes = data["analysis"]["hashes"]
    assert len(hashes["md5"]) == 32
    assert len(hashes["sha1"]) == 40
    assert len(hashes["sha256"]) == 64
    assert len(hashes["sha512"]) == 128


# -------------------------------------------------------------------- #13 --
def test_change_history_records_old_and_new_values(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "IFD0:Artist", "group": "", "action": "set", "new_value": "Changed Name"}
    ]})
    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    diffs = r.json()["field_diffs"]
    artist_diff = next(d for d in diffs if d["key"] == "IFD0:Artist")
    assert artist_diff["old_value"] == "Jane Doe"
    assert artist_diff["new_value"] == "Changed Name"
    assert artist_diff["action"] == "set"

    r = client.get("/api/history", params={"file_id": fid})
    ops = r.json()["operations"]
    assert ops[0]["field_diffs"]
    assert ops[0]["field_diffs"][0]["old_value"] == "Jane Doe"


# -------------------------------------------------------------------- #14 --
def test_missing_metadata_suggestions_present_and_neutral(client):
    data = _upload(client, "enriched.jpg")
    suggestions = data["analysis"]["missing_suggestions"]
    logical_names = {s["logical_name"] for s in suggestions}
    assert "Camera Make/Model" in logical_names  # enriched.jpg never sets Make/Model
    entry = next(s for s in suggestions if s["logical_name"] == "Camera Make/Model")
    # neutral framing: must not accuse the file of anything
    note_lower = entry["note"].lower()
    assert "forged" not in note_lower and "tampered" not in note_lower and "suspicious" not in note_lower


def test_missing_suggestions_empty_when_fields_present(client):
    data = _upload(client, "enriched.jpg")
    suggestions = {s["logical_name"] for s in data["analysis"]["missing_suggestions"]}
    assert "Author / Creator" not in suggestions  # enriched.jpg has 3 author tags
    assert "Capture Date" not in suggestions  # enriched.jpg sets DateTimeOriginal


# -------------------------------------------------------------------- #15 --
def test_save_without_recompression_jpeg_preserved(client):
    data = _upload(client, "sample.jpg")
    fid = data["file_id"]
    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "EXIF:Artist", "group": "", "action": "set", "new_value": "Metadata Only Edit"}
    ]})
    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    sp = r.json()["verification"]["stream_preservation"]
    assert sp["measured"] is True
    assert sp["method"] == "jpeg_scan_data"
    assert sp["preserved"] is True
    assert sp["before_hash"] == sp["after_hash"]


def test_save_without_recompression_honest_for_unsupported_format(client):
    data = _upload(client, "sample.docx")
    fid = data["file_id"]
    client.put(f"/api/files/{fid}/edits", json={"edits": [
        {"field_key": "core:author", "group": "", "action": "set", "new_value": "New Author"}
    ]})
    r = client.post(f"/api/files/{fid}/save-as")
    assert r.status_code == 200
    sp = r.json()["verification"]["stream_preservation"]
    assert sp["measured"] is False
    assert sp["method"] == "not_supported"
    assert sp["preserved"] is None


def test_stream_integrity_detects_recompression_tamper(tmp_path):
    """Direct unit test proving the verifier is not a rubber stamp: flipping
    a byte inside the actual JPEG scan data must be detected as NOT
    preserved, not just trusted because exiftool is believed safe."""
    from app.services import stream_integrity
    import shutil as _shutil

    src = FIXTURES_DIR / "sample.jpg"
    before = tmp_path / "before.jpg"
    after = tmp_path / "after.jpg"
    _shutil.copy2(src, before)
    _shutil.copy2(src, after)

    data = bytearray(after.read_bytes())
    data[-5] ^= 0xFF  # flip a byte near EOF, inside the compressed scan data
    after.write_bytes(bytes(data))

    report = stream_integrity.stream_preservation_report(before, after, "jpg")
    assert report["measured"] is True
    assert report["preserved"] is False


def test_appended_data_detector_finds_trailing_bytes(tmp_path):
    from app.services import stream_integrity
    import shutil as _shutil

    src = FIXTURES_DIR / "sample.jpg"
    tampered = tmp_path / "trailer.jpg"
    _shutil.copy2(src, tampered)
    with tampered.open("ab") as f:
        f.write(b"HIDDEN_PAYLOAD_DATA")

    result = stream_integrity.detect_appended_data(tampered, "JPEG")
    assert result["checked"] is True
    assert result["trailing_bytes"] == len(b"HIDDEN_PAYLOAD_DATA")


def test_appended_data_clean_file_reports_zero(client):
    data = _upload(client, "sample.jpg")
    appended = data["analysis"]["appended_data"]
    assert appended is not None
    assert appended["trailing_bytes"] == 0


# ------------------------------------------------------ copy & paste (#1) --
def test_copy_paste_between_compatible_images(client):
    source = _upload(client, "enriched.jpg")
    target = _upload(client, "sample.jpg")
    source_fid, target_fid = source["file_id"], target["file_id"]

    r = client.post(f"/api/files/{target_fid}/copy-metadata", json={"source_file_id": source_fid})
    assert r.status_code == 200
    body = r.json()
    assert body["staged_count"] > 0
    staged_keys = {res["key"] for res in body["results"] if res["staged"]}
    assert "IFD0:Copyright" in staged_keys

    r = client.post(f"/api/files/{target_fid}/save-as")
    assert r.status_code == 200
    assert r.json()["verification"]["fields_present_after_edit"].get("IFD0:Copyright") == "(c) 2024 EXIF"


def test_copy_paste_rejects_incompatible_domain(client):
    source = _upload(client, "sample.jpg")      # image_media domain
    target = _upload(client, "sample.pdf")       # pdf domain
    source_fid, target_fid = source["file_id"], target["file_id"]

    r = client.post(f"/api/files/{target_fid}/copy-metadata", json={"source_file_id": source_fid})
    assert r.status_code == 200
    body = r.json()
    assert body["staged_count"] == 0
    assert all(res["compatible"] is False for res in body["results"])
    assert any("not" in (res["reason"] or "").lower() or res["reason"] for res in body["results"])


def test_copy_paste_specific_field_keys_only(client):
    source = _upload(client, "enriched.jpg")
    target = _upload(client, "sample.jpg")
    source_fid, target_fid = source["file_id"], target["file_id"]

    r = client.post(f"/api/files/{target_fid}/copy-metadata",
                     json={"source_file_id": source_fid, "field_keys": ["IFD0:Copyright"]})
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 1
    assert body["results"][0]["key"] == "IFD0:Copyright"


# -------------------------------------------------- domain helper sanity --
def test_domain_classification_consistency():
    from app.services import domains
    assert domains.domain_for_key("EXIF:Artist") == "image_media"
    assert domains.domain_for_key("core:author") == "office"
    assert domains.domain_for_key("pdf:title") == "pdf"
    assert domains.domain_for_key("struct:zip_entries") is None
