from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Point the app at an isolated, temporary data directory before importing
# any app module (app.core.config reads the env var at import time).
_TMP_DATA = tempfile.mkdtemp(prefix="umidasu_test_")
os.environ["UMIDASU_DATA_DIR"] = _TMP_DATA

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session", autouse=True)
def build_fixtures():
    FIXTURES_DIR.mkdir(exist_ok=True)

    from PIL import Image
    jpg_path = FIXTURES_DIR / "sample.jpg"
    if not jpg_path.exists():
        img = Image.new("RGB", (120, 90), color=(10, 20, 30))
        img.save(jpg_path, "JPEG")
        import subprocess
        subprocess.run(["exiftool", "-overwrite_original", "-Artist=Jane Doe",
                         "-GPSLatitude=40.7128", "-GPSLatitudeRef=N",
                         "-GPSLongitude=-74.0060", "-GPSLongitudeRef=W",
                         "-Make=TestCam", str(jpg_path)], check=False, capture_output=True)

    docx_path = FIXTURES_DIR / "sample.docx"
    if not docx_path.exists():
        import docx
        d = docx.Document()
        d.core_properties.author = "Doc Author"
        d.add_paragraph("hello")
        d.save(str(docx_path))

    pdf_path = FIXTURES_DIR / "sample.pdf"
    if not pdf_path.exists():
        import pikepdf
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(200, 200))
        pdf.docinfo["/Title"] = "Sample PDF"
        pdf.save(str(pdf_path))

    zip_path = FIXTURES_DIR / "sample.zip"
    if not zip_path.exists():
        import zipfile
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("hello.txt", "hello world")

    malformed_path = FIXTURES_DIR / "malformed.jpg"
    if not malformed_path.exists():
        malformed_path.write_text("this is not a jpeg")

    traversal_zip = FIXTURES_DIR / "traversal.zip"
    if not traversal_zip.exists():
        import zipfile
        with zipfile.ZipFile(traversal_zip, "w") as z:
            z.writestr("../../etc/evil.txt", "pwned")

    # PNG with a tEXt metadata chunk, for size_analysis/duplicate-detector
    # tests (PNG metadata is measured via a direct chunk walk, not exiftool).
    png_path = FIXTURES_DIR / "sample.png"
    if not png_path.exists():
        from PIL import PngImagePlugin
        img2 = Image.new("RGB", (80, 60), color=(50, 100, 150))
        info = PngImagePlugin.PngInfo()
        info.add_text("Author", "PNGAuthor")
        info.add_text("Description", "A test PNG")
        img2.save(png_path, "PNG", pnginfo=info)

    # Small MP4 (ISO-BMFF) for mdat-box stream-preservation tests.
    mp4_path = FIXTURES_DIR / "sample.mp4"
    if not mp4_path.exists():
        import subprocess
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
             "-i", "testsrc=duration=1:size=64x64:rate=5", str(mp4_path)],
            check=False, capture_output=True,
        )

    # JPEG enriched with conflicting author/title/description tags across
    # EXIF/IPTC/XMP namespaces (Duplicate Metadata Detector), plus a rare,
    # non-standard EXIF tag (Unknown Tag Decoder) and full GPS (GPS
    # Coordinate Converter). Deliberately has no XMP/IPTC Keywords so
    # Missing Metadata Suggestions has something real to report.
    enriched_path = FIXTURES_DIR / "enriched.jpg"
    if not enriched_path.exists():
        img3 = Image.new("RGB", (100, 80), color=(80, 40, 20))
        img3.save(enriched_path, "JPEG")
        import subprocess
        subprocess.run([
            "exiftool", "-overwrite_original",
            "-EXIF:Artist=EXIFAuthor",
            "-IPTC:By-line=IPTCAuthor",
            "-XMP-dc:Creator=XMPAuthor",
            "-EXIF:Copyright=(c) 2024 EXIF",
            "-XMP-dc:Rights=(c) 2024 XMP",
            "-GPSLatitude=51.5074", "-GPSLatitudeRef=N",
            "-GPSLongitude=-0.1278", "-GPSLongitudeRef=W",
            "-EXIF:Gamma=2.2",  # a real but uncommon EXIF tag, deliberately absent from
                                 # known_tags.py's curated list, for Unknown Tag Decoder tests
            "-EXIF:DateTimeOriginal=2024:03:15 10:30:00",
            str(enriched_path),
        ], check=False, capture_output=True)

    yield
