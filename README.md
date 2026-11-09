 <div align="center">

#  THE UMIDASU

### Universal Metadata Inspector, Editor and File Analyzer

**Reveal What Files Conceal.**

[![Platform](https://img.shields.io/badge/Platform-Local--First-00F0FF?style=for-the-badge&logo=linux&logoColor=white)](#)
[![Python](https://img.shields.io/badge/Python-3.9--3.13-3776AB?style=for-the-badge&logo=python&logoColor=white)](#)
[![React](https://img.shields.io/badge/React-TypeScript-61DAFB?style=for-the-badge&logo=react&logoColor=black)](#)
[![FastAPI](https://img.shields.io/badge/Backend-FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](#)
[![Privacy](https://img.shields.io/badge/Privacy-Local_Processing-success?style=for-the-badge&logo=shield&logoColor=white)](#)

---

**Inspect · Analyze · Compare · Edit · Sanitize · Export**

</div>

The Umidasu is a local-first web application for inspecting, analyzing, comparing, editing, sanitizing, and exporting metadata from images, video, audio, PDFs, Office documents, archives, and arbitrary binary files. It is built for people who need to know exactly what information a file is carrying, and exactly what changes when that information is edited or removed.

**Author:** TENETx0

> [!IMPORTANT]
> Everything runs on your own machine. There is no external API, no telemetry, and no third-party upload path. Files you analyze never leave the host running the application.

---

##  Table of Contents

- [Uses](#uses)
- [Use cases](#use-cases)
- [Areas of usage](#areas-of-usage)
- [Feature overview](#feature-overview)
- [Installation](#installation)
- [Architecture](#architecture)
- [Security model](#security-model)
- [Known limitations](#known-limitations)
- [Testing](#testing)
- [Fail-safe reset](#fail-safe-reset)

---

##  Uses

The Umidasu is used to:

- Extract and view every metadata field a file exposes (EXIF, IPTC, XMP, PDF document info, Office core properties, archive member listings, container-level audio/video tags, and raw binary structure).
- Identify a file by its actual content rather than its name or extension, and flag files whose extension does not match their real format.
- Compare the metadata of two files, or compare a file against a previously saved snapshot of itself, with field-level added/removed/modified highlighting.
- Edit, add, or remove individual metadata fields and verify after saving that the output file actually reflects the intended change.
- Apply metadata removal presets (GPS, device/camera, author/personal identifiers, timestamps, comments, XMP/IPTC blocks, or everything writable) before sharing or publishing a file.
- Normalize inconsistent timestamp formats across EXIF, XMP, and filesystem metadata into a single readable form, and convert embedded GPS coordinates between decimal degrees and DMS.
- Detect duplicate or redundant metadata fields carried in more than one tag group, and surface fields that are commonly present in similar files but missing from the current one.
- Decode unknown or vendor-specific tag identifiers into a best-effort human-readable description instead of a raw hex/numeric tag ID.
- Search across every extracted field, tag, and raw value in a file at once, rather than hunting through sections by hand.
- Maintain a local, auditable history of every operation performed on a file (hashes before and after, fields changed, tool versions, success/failure) and export that history as JSON, CSV, or HTML.
- Hash files (MD5, SHA-1, SHA-256, SHA-512) and quickly copy any digest for use elsewhere.
- Save edited files without forcing recompression of image or media payloads, and get an explicit report on whether the original encoding was preserved.

##  Use cases

- **Pre-publication sanitization** — stripping GPS coordinates, device identifiers, author names, and embedded timestamps from photos, documents, or PDFs before they are published, submitted, or shared externally.
- **OSINT and reconnaissance triage** — pulling every available metadata field from a target's publicly shared files (documents, images, PDFs) to assess what information they unintentionally expose, as part of an authorized engagement.
- **Bug bounty and client deliverable preparation** — confirming that report attachments, proof-of-concept files, and screenshots do not themselves leak information about the tester's environment, tooling, or internal network before submission.
- **Evidence and artifact review** — inspecting files received during an engagement (dropped payloads, attachments, documents of unknown origin) for embedded metadata that may indicate authorship, tooling, or originating environment, without executing the file.
- **File provenance and tamper checking** — hashing a file before and after it passes through a pipeline or third party, and diffing its metadata to confirm nothing was altered beyond what was expected.
- **Format verification** — catching files whose declared extension does not match their actual binary signature, a common indicator of disguised payloads or mislabeled attachments.
- **Metadata-standard research and tooling development** — using the parser and tag-decoding layer as a reference implementation when building or testing other tools that need to read or strip the same metadata.
- **Personal and organizational privacy hygiene** — routine cleanup of metadata in images and documents before they are stored, shared, or uploaded, without relying on a third-party online "metadata remover."

##  Areas of usage

- Penetration testing and red team engagements (reconnaissance, reporting hygiene, artifact review)
- Bug bounty research and submission preparation
- Digital forensics and incident response (non-destructive inspection of files of unknown origin)
- OSINT investigations
- Security awareness and training (demonstrating what metadata reveals)
- Journalism and research requiring source protection before publishing attachments
- General privacy-conscious personal and organizational file hygiene
- Software and tooling development that needs a local reference for metadata extraction/removal behavior

---

##  Feature overview

###  Inspection and analysis

- **File identification** independent of filename — magic-byte signatures plus libmagic, with extension-mismatch detection and warning.
- **Hashing** — MD5, SHA-1, SHA-256, SHA-512, each annotated with a note on its current cryptographic strength, plus entropy and byte-histogram analysis. One-click copy of any hash.
- **Image metadata** — EXIF/IPTC/XMP via exiftool, dimensions/color/animation via Pillow, GPS and camera/author fields grouped and flagged for sensitivity.
- **Video/audio** — container and per-stream analysis via ffprobe, container tags, chapter data. Frame-by-frame decoding is explicitly not performed and is reported as such, never silently skipped.
- **PDF** — document info, structure, encryption/permission flags, embedded file listing via PyMuPDF/pikepdf. Digital signature presence is flagged heuristically; cryptographic validation is explicitly not implemented and is reported as such.
- **Office (DOCX/XLSX/PPTX)** — core properties, structural summary (paragraphs/sheets/slides), raw ZIP package member listing. Macros are never executed.
- **Archives (ZIP/TAR/GZIP)** — member listing only, with path-traversal and nested-archive detection. Contents are never auto-extracted.
- **Binary/encoding analysis** — BOM detection, UTF-8 validity, printable-string extraction, hex/ASCII preview, ELF/PE header peek. Runs on every file regardless of recognized format.
- **Metadata Search Everywhere** — a single search box that matches against every extracted tag name and value across every section at once.
- **Unknown Tag Decoder** — best-effort human-readable description for vendor-specific or unrecognized tag identifiers instead of a bare numeric/hex ID.
- **File Extension Mismatch Warning** — flags files whose real binary signature does not match their extension.
- **Metadata Size Analyzer** — reports how many bytes of a file are consumed by metadata versus actual payload, broken down by section.
- **Duplicate Metadata Detector** — surfaces fields that carry the same value across multiple tag groups (for example, a title present in both EXIF and XMP).
- **Missing Metadata Suggestions** — flags fields that are commonly present in files of the same type but absent from the current file.

###  Editing and transformation

- **Metadata Editor** — per-field add/edit/remove, full undo/redo, Reset Pending Changes, Revert Working Copy, and Save As, which never overwrites the original file.
- **Custom timestamps** — set created/modified/accessed values at the filesystem level (`os.utime`) and, where the format supports it, in embedded date tags (EXIF/XMP/QuickTime). The Linux filesystem birth-time limitation is explicitly reported, never silently ignored.
- **Timestamp Normalizer** — reconciles inconsistent date/time representations across EXIF, XMP, and filesystem metadata into one consistent, human-readable value.
- **GPS Coordinate Converter** — converts embedded GPS coordinates between decimal degrees and degrees/minutes/seconds.
- **Metadata Copy and Paste** — copy a set of metadata fields from one analyzed file and stage them for application to another.
- **Metadata Presets** — save a reusable set of logical fields (author, copyright, title, description, keywords) and apply it to any compatible file; fields with no analog in a given file type are reported as skipped rather than silently dropped.
- **One-Click Metadata Snapshot** — capture the current metadata state of a file for later comparison or restore.
- **Metadata Difference Highlighting** — live field-level added/removed/modified comparison, driven by pending edits or a restored snapshot.
- **Save Without Recompression** — preserves the original image/media encoding on save where the toolchain supports it, with an explicit report on whether recompression was avoided.
- **Removal presets** — GPS, camera/device, author/personal, timestamps, comments, XMP/IPTC, or all writable metadata, applied to a working copy with original-file immutability guaranteed.

###  Verification and auditability

- **Verification** — every Save As re-extracts metadata from the output file and reports exactly which fields changed, plus recomputed hashes.
- **Metadata Change History** — a persistent, field-level before/after log of every save operation.
- **Session history** — SQLite-backed operation log (original/output hashes, fields changed, tool versions, success/failure) with JSON/CSV/HTML export and a Clear Session Data action.

---

##  Installation

### Requirements

| Component | Purpose |
|---|---|
| Python 3.9 - 3.13 | Backend runtime (FastAPI/Uvicorn). Newer interpreters may lack prebuilt wheels for pinned dependencies. |
| Node.js and npm | Frontend build (React/TypeScript/Vite). |
| exiftool | Image/document metadata read and write. |
| ffmpeg / ffprobe | Video and audio container analysis. |

### Setup

```bash
git clone <this-repository-url>
cd umidasu
chmod +x execute.sh
./execute.sh
```

`execute.sh` will, on every run:

1. Verify `python3`, `node`/`npm`, and the external tools `exiftool`/`ffmpeg`/`ffprobe` are present, printing install instructions for anything missing.
2. Select a compatible Python interpreter automatically (preferring 3.13 down to 3.9) and create a virtual environment at `.venv/` if one does not already exist, offering to rebuild it if an existing one was created with a different interpreter version.
3. Install pinned backend dependencies (skipped if `requirements.txt` is unchanged since the last run).
4. Install and build the frontend (skipped if the existing build is already current).
5. Start a single backend process that also serves the built frontend, bound to `127.0.0.1` by default.
6. Print the local URL to open.

Press `Ctrl+C` to stop. The script shuts down its child process cleanly.

### Installing external tools manually

| Distribution | Command |
|---|---|
| Debian / Ubuntu / Kali | `sudo apt-get install -y libimage-exiftool-perl ffmpeg` |
| Fedora / RHEL | `sudo dnf install -y perl-Image-ExifTool ffmpeg` |
| Arch | `sudo pacman -S perl-image-exiftool ffmpeg` |

### Configuration

All configuration is via environment variables, read by `backend/app/core/config.py`:

| Variable | Default | Purpose |
|---|---|---|
| `UMIDASU_HOST` | `127.0.0.1` | Bind address. Changing this exposes the app beyond localhost — only do so if you understand the risk, as The Umidasu processes untrusted files. |
| `UMIDASU_PORT` | `8420` | Bind port. |
| `UMIDASU_DATA_DIR` | `~/.umidasu` | Directory for the database and the originals/working/output file stores. |
| `UMIDASU_MAX_UPLOAD_MB` | `512` | Maximum upload size. |
| `UMIDASU_PARSER_TIMEOUT` | `30` | Per-parser timeout, in seconds. |
| `UMIDASU_RETENTION_HOURS` | `24` | Hours of inactivity before the cleanup sweep removes a file's original/working copies. |

---

##  Architecture

```text
umidasu/
  execute.sh              startup script
  flush                   fail-safe: wipes all stored data and history
  requirements.txt        pinned backend dependencies
  backend/
    app/
      main.py              FastAPI app, static frontend serving
      api/routes.py         all HTTP endpoints
      core/config.py        settings (host, port, limits, storage paths)
      models/schemas.py     Pydantic models shared across the backend
      parsers/              plugin-based format parsers (image, media, pdf, office, archive, binary)
      editors/              metadata edit/save/verify logic, custom timestamps
      services/             identification, hashing, exiftool wrapper, analysis orchestration, presets
      security/              path safety, safe subprocess execution, tool availability checks
      reports/                JSON/CSV/HTML report builders
      storage/                SQLite history, in-memory session/workspace management
    tests/                  pytest suite with real fixtures (no mocked parsers)
  frontend/
    src/
      components/            React components (upload, inspection, editor, hex viewer, diff, snapshots, presets, history, reports…)
      hooks/useFileSession.ts  edit/undo/redo/save state management
      services/api.ts         typed API client
      types/metadata.ts       TypeScript types mirroring the backend Pydantic models
```

### Parser plugin interface

Every format parser (`backend/app/parsers/*.py`) implements:

- `supports(detected_format, mime_type, extension) -> bool`
- `extract_metadata(path) -> list[MetadataSection]`
- `get_capabilities(path) -> list[Capability]`

New formats can be added by writing a new parser module and registering it in `backend/app/parsers/__init__.py` — no other code changes required.

---

##  Security model

- Binds to `127.0.0.1` by default; any other host must be opted into explicitly.
- Randomized server-side file identifiers — uploaded filenames are never trusted or used as storage paths.
- Path-traversal-safe joins and symlink-attack protection throughout file handling.
- No-overwrite guarantee — the original uploaded file is never modified; all edits are written to a separate working/output copy.
- Subprocess calls (exiftool, ffprobe) are executed with explicit argv arrays, never through a shell string.
- Upload size limits and per-parser timeouts prevent resource exhaustion from hostile or malformed input.
- Error responses are generic by default and never leak internal paths, stack traces, or tool output to the client.
- Archive and nested-archive contents are listed, never auto-extracted.
- Office document macros are never executed.

##  Known limitations

Reported honestly, not hidden from the user interface:

- Filesystem "created" (birth) time cannot be set on Linux via any public API. The editor sets `modified`/`accessed` via `os.utime` and writes the requested "created" value into embedded date tags where the format supports it, reporting exactly what was and was not changed after every save.
- Digital signature validation (cryptographic) is not implemented for PDFs — only presence is heuristically flagged.
- Video/audio analysis is container/stream-level only; no frame-by-frame decoding is performed.
- Metadata removal presets cannot guarantee complete sanitization. Residual data may remain in pixel content, document body text, embedded streams, thumbnails, or format-specific structures that are not exposed as writable tags. This is stated to the user before and after every removal operation.

##  Testing

```bash
source .venv/bin/activate
cd backend
pytest tests/ -v
```

The suite runs against real generated fixture files (JPEG with real EXIF/GPS, DOCX, PDF, ZIP) rather than mocked parsers, covering identification and MIME-mismatch detection, hashing, extraction, editing, removal presets, undo/redo/reset, save-as plus verification, original-file integrity, custom timestamps (including the documented Linux limitation), copy/paste, snapshots and diffing, presets, duplicate and missing-field detection, metadata size analysis, change history, save-without-recompression, path-traversal rejection, and report export.

##  Fail-safe reset

`./flush` deletes all locally stored progress: the history database (file records, operation log, saved presets) and every originals/working/output file on disk under the configured data directory. It is destructive and irreversible, and prompts for confirmation before acting. See the script itself for details.

```bash
chmod +x flush
./flush
```

---

##  Disclaimer

The Umidasu is a local inspection and editing tool. It does not guarantee complete metadata removal for every format and should not be treated as a substitute for understanding what a given file format can and cannot fully sanitize. Use it only on files you own or are explicitly authorized to inspect and modify.

---

<div align="center">

###  THE UMIDASU

**Reveal What Files Conceal.**

*Local-first. Privacy-focused. Metadata intelligence.*

</div>
