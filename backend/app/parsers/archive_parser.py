"""Archive inspection (ZIP/TAR/GZIP) with path-traversal-safe listing only —
members are never extracted to disk by this parser."""
from __future__ import annotations

import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from app.models.schemas import Capability, ExtractionStatus, MetadataField, MetadataSection
from app.parsers.base import BaseParser, register

ARCHIVE_EXTS = {"zip", "tar", "gz", "tgz", "bz2", "xz"}
ARCHIVE_FORMATS = {"GZIP", "TAR"}  # ZIP/OOXML is claimed by office_parser when it's actually OOXML
MAX_MEMBERS_LISTED = 2000


def _looks_traversal(name: str) -> bool:
    p = PurePosixPath(name)
    return p.is_absolute() or ".." in p.parts


class ArchiveParser(BaseParser):
    name = "archive"

    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        if extension in ARCHIVE_EXTS:
            return True
        if detected_format in ARCHIVE_FORMATS:
            return True
        return False

    def get_capabilities(self, path: Path) -> list[Capability]:
        return [
            Capability(name="Member listing (no extraction)", available=True),
            Capability(name="Automatic extraction", available=False, reason="Disabled by design to avoid path-traversal / zip-bomb risk on untrusted archives."),
        ]

    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        section = MetadataSection(section_id="archive_members", title="Archive Contents", status=ExtractionStatus.NOT_ANALYZED)
        nested_warns: list[str] = []

        try:
            if zipfile.is_zipfile(path):
                with zipfile.ZipFile(path) as z:
                    infos = z.infolist()
                    for i, info in enumerate(infos[:MAX_MEMBERS_LISTED]):
                        if _looks_traversal(info.filename):
                            nested_warns.append(f"Suspicious path-traversal member name: {info.filename}")
                        if info.filename.lower().endswith((".zip", ".tar", ".gz", ".tgz", ".7z", ".rar")):
                            nested_warns.append(f"Nested archive detected: {info.filename}")
                        section.fields.append(MetadataField(
                            key=f"zip:{i}", group="ZIP", label=info.filename,
                            raw_value={"size": info.file_size, "compressed_size": info.compress_size,
                                       "crc": info.CRC, "date": "%04d-%02d-%02d %02d:%02d:%02d" % info.date_time,
                                       "is_dir": info.is_dir()},
                            normalized_value=f"{info.file_size} bytes", value_type="object", source_parser="zipfile"))
                    section.status = ExtractionStatus.SUCCESS
                    if len(infos) > MAX_MEMBERS_LISTED:
                        section.warnings.append(f"Archive has {len(infos)} members; showing first {MAX_MEMBERS_LISTED}.")
            elif tarfile.is_tarfile(path):
                with tarfile.open(path, mode="r:*") as t:
                    members = t.getmembers()
                    for i, m in enumerate(members[:MAX_MEMBERS_LISTED]):
                        if _looks_traversal(m.name):
                            nested_warns.append(f"Suspicious path-traversal member name: {m.name}")
                        if m.name.lower().endswith((".zip", ".tar", ".gz", ".tgz", ".7z", ".rar")):
                            nested_warns.append(f"Nested archive detected: {m.name}")
                        section.fields.append(MetadataField(
                            key=f"tar:{i}", group="TAR", label=m.name,
                            raw_value={"size": m.size, "mode": oct(m.mode), "uid": m.uid, "gid": m.gid,
                                       "mtime": m.mtime, "type": m.type.decode() if isinstance(m.type, bytes) else str(m.type)},
                            normalized_value=f"{m.size} bytes", value_type="object", source_parser="tarfile"))
                    section.status = ExtractionStatus.SUCCESS
                    if len(members) > MAX_MEMBERS_LISTED:
                        section.warnings.append(f"Archive has {len(members)} members; showing first {MAX_MEMBERS_LISTED}.")
            else:
                section.status = ExtractionStatus.NOT_SUPPORTED
                section.detail_message = "Not a recognized ZIP or TAR archive (gzip-only streams have no member listing)."
        except Exception as exc:
            section.status = ExtractionStatus.FAILED
            section.detail_message = str(exc)

        section.warnings.extend(nested_warns)
        section.warnings.append("Members are listed only — never auto-extracted. Treat archive contents as untrusted.")
        return [section]


register(ArchiveParser())
