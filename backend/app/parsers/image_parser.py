"""Image metadata parser: EXIF/IPTC/XMP via exiftool, dimensions via Pillow."""
from __future__ import annotations

from pathlib import Path

from app.models.schemas import Capability, ExtractionStatus, MetadataField, MetadataSection
from app.parsers.base import BaseParser, register
from app.parsers.known_tags import is_known_tag
from app.services import exiftool_service, gps as gps_service
from app.services.exiftool_service import EXIFTOOL_AVAILABLE

IMAGE_EXTS = {"jpg", "jpeg", "png", "tif", "tiff", "webp", "heic", "heif", "avif", "gif", "bmp", "svg"}
IMAGE_FORMATS = {"JPEG", "PNG", "TIFF (little-endian)", "TIFF (big-endian)", "GIF", "BMP", "SVG"}

GPS_KEYS = {"GPSLatitude", "GPSLongitude", "GPSAltitude", "GPSDateStamp", "GPSTimeStamp", "GPSPosition", "GPSDirection", "GPSImgDirection"}
CAMERA_KEYS = {"Make", "Model", "LensModel", "LensMake", "SerialNumber", "LensSerialNumber", "LensInfo"}
AUTHOR_KEYS = {"Artist", "Creator", "Author", "OwnerName", "Copyright", "CameraOwnerName", "By-line"}


def _classify_group(tag_group: str, tag_name: str) -> tuple[str, bool]:
    """Return (ui_group, sensitive) for a raw exiftool group/tag."""
    if tag_name in GPS_KEYS or "GPS" in tag_name:
        return "GPS", True
    if tag_name in CAMERA_KEYS:
        return "Camera/Device", False
    if tag_name in AUTHOR_KEYS:
        return "Author/Personal", True
    if tag_group.upper().startswith("IPTC"):
        return "IPTC", False
    if tag_group.upper().startswith("XMP"):
        return "XMP", False
    if tag_group.upper().startswith("ICC") or tag_group.upper().startswith("ICC_PROFILE"):
        return "ICC Profile", False
    if tag_group.upper().startswith("EXIF") or tag_group.upper().startswith("IFD"):
        return "EXIF", False
    return tag_group or "Other", False


# Tags that exiftool can reliably write back for common image formats.
_WRITABLE_HINT_PREFIXES = ("EXIF", "IPTC", "XMP", "IFD0", "IFD1", "GPS")


class ImageParser(BaseParser):
    name = "image"

    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        return detected_format in IMAGE_FORMATS or mime_type.startswith("image/") or extension in IMAGE_EXTS

    def get_capabilities(self, path: Path) -> list[Capability]:
        caps = [
            Capability(name="EXIF/IPTC/XMP extraction", available=EXIFTOOL_AVAILABLE,
                       reason=None if EXIFTOOL_AVAILABLE else "exiftool not installed"),
            Capability(name="Dimension/colorspace extraction", available=True),
            Capability(name="Metadata editing", available=EXIFTOOL_AVAILABLE,
                       reason=None if EXIFTOOL_AVAILABLE else "exiftool not installed"),
        ]
        return caps

    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        sections: dict[str, MetadataSection] = {}

        def section(section_id: str, title: str) -> MetadataSection:
            if section_id not in sections:
                sections[section_id] = MetadataSection(section_id=section_id, title=title, status=ExtractionStatus.NOT_ANALYZED, fields=[])
            return sections[section_id]

        # --- Dimensions / color via Pillow (independent of exiftool) ---
        dims_section = section("image_technical", "Image Technical Properties")
        try:
            from PIL import Image
            with Image.open(path) as img:
                fields = [
                    MetadataField(key="Pillow:Width", group="Technical", label="Width (px)", raw_value=img.width, normalized_value=img.width, value_type="number", source_parser="Pillow"),
                    MetadataField(key="Pillow:Height", group="Technical", label="Height (px)", raw_value=img.height, normalized_value=img.height, value_type="number", source_parser="Pillow"),
                    MetadataField(key="Pillow:Mode", group="Technical", label="Color Mode", raw_value=img.mode, normalized_value=img.mode, value_type="string", source_parser="Pillow"),
                    MetadataField(key="Pillow:Format", group="Technical", label="Pillow-detected Format", raw_value=img.format, normalized_value=img.format, value_type="string", source_parser="Pillow"),
                ]
                if img.width and img.height:
                    from math import gcd
                    g = gcd(img.width, img.height)
                    fields.append(MetadataField(key="Pillow:AspectRatio", group="Technical", label="Aspect Ratio",
                                                 raw_value=f"{img.width//g}:{img.height//g}", normalized_value=f"{img.width//g}:{img.height//g}",
                                                 value_type="string", source_parser="Pillow"))
                n_frames = getattr(img, "n_frames", 1)
                if n_frames and n_frames > 1:
                    fields.append(MetadataField(key="Pillow:FrameCount", group="Technical", label="Animation Frame Count",
                                                 raw_value=n_frames, normalized_value=n_frames, value_type="number", source_parser="Pillow"))
                dims_section.fields.extend(fields)
                dims_section.status = ExtractionStatus.SUCCESS
        except Exception as exc:
            dims_section.status = ExtractionStatus.FAILED
            dims_section.detail_message = f"Pillow could not decode image: {exc}"

        # --- EXIF/IPTC/XMP via exiftool ---
        exif_section = section("exif", "EXIF")
        iptc_section = section("iptc", "IPTC")
        xmp_section = section("xmp", "XMP")
        gps_section = section("gps", "GPS / Location")
        camera_section = section("camera", "Camera / Device")
        author_section = section("author", "Author / Personal")
        icc_section = section("icc", "ICC Profile")
        other_section = section("other_image_tags", "Other Embedded Tags")
        unknown_section = section("unknown_tags", "Unknown / Uncommon Tags")

        if not EXIFTOOL_AVAILABLE:
            for s in (exif_section, iptc_section, xmp_section, gps_section, camera_section, author_section, icc_section, unknown_section):
                s.status = ExtractionStatus.NOT_ANALYZED
                s.detail_message = "exiftool is not installed; install it to extract EXIF/IPTC/XMP metadata."
            return list(sections.values())

        try:
            tags = exiftool_service.read_all_tags_with_ids(path)
        except Exception as exc:
            for s in (exif_section, iptc_section, xmp_section, gps_section, camera_section, author_section, icc_section, unknown_section):
                s.status = ExtractionStatus.FAILED
                s.detail_message = str(exc)
            return list(sections.values())

        if not tags:
            for s in (exif_section, iptc_section, xmp_section, gps_section, camera_section, author_section, icc_section, unknown_section):
                s.status = ExtractionStatus.NO_METADATA
            return list(sections.values())

        any_exif = any_iptc = any_xmp = any_gps = any_camera = any_author = any_icc = any_other = any_unknown = False
        gps_lat_fields: list[MetadataField] = []
        gps_lon_fields: list[MetadataField] = []

        for full_key, entry in tags.items():
            if ":" not in full_key:
                continue
            group, tag_name = full_key.split(":", 1)
            if tag_name in ("SourceFile", "ExifToolVersion", "FileName", "Directory", "FileSize",
                             "FileModifyDate", "FileAccessDate", "FileInodeChangeDate", "FilePermissions",
                             "FileType", "FileTypeExtension", "MIMEType"):
                continue  # filesystem/tool bookkeeping, not embedded metadata

            value = entry["val"]
            raw_tag_id = entry.get("id")
            ui_group, sensitive = _classify_group(group, tag_name)
            writable = group.upper().startswith(_WRITABLE_HINT_PREFIXES)
            value_type = "number" if isinstance(value, (int, float)) and not isinstance(value, bool) else (
                "boolean" if isinstance(value, bool) else ("array" if isinstance(value, list) else
                ("object" if isinstance(value, dict) else "string")))

            # A hex-formatted ID (e.g. "0x010f") is a real numeric tag ID;
            # anything else (a bare tag name) means exiftool had no numeric
            # ID to report for this tag (XMP/composite/derived tags).
            tag_id = raw_tag_id if isinstance(raw_tag_id, str) and raw_tag_id.startswith("0x") else None

            # The Unknown Tag Decoder only makes sense within the metadata
            # namespaces users actually care about (EXIF/IFD/GPS/IPTC/XMP).
            # Structural/derived groups (JFIF, Composite, File, ICC_Profile's
            # internal table) are excluded so routine structural fields
            # don't get flagged as "unknown" noise.
            _interesting_group = group.upper().startswith(("EXIF", "IFD", "GPS", "IPTC", "XMP", "PNG", "QUICKTIME"))
            unknown = _interesting_group and not is_known_tag(tag_name) and not tag_name.startswith("Unknown")

            field = MetadataField(
                key=full_key,
                group=ui_group,
                label=tag_name,
                raw_value=value,
                normalized_value=value,
                value_type=value_type,
                source_parser="exiftool",
                writable=writable,
                sensitive=sensitive,
                tag_id=tag_id,
                namespace=group,
                is_unknown_tag=unknown,
                # is_timestamp/timestamp_utc/timestamp_has_tz are filled in
                # centrally by services.analysis for every parser's fields.
            )

            if ui_group == "GPS":
                gps_section.fields.append(field); any_gps = True
                if tag_name == "GPSLatitude":
                    gps_lat_fields.append(field)
                elif tag_name == "GPSLongitude":
                    gps_lon_fields.append(field)
            elif ui_group == "Camera/Device":
                camera_section.fields.append(field); any_camera = True
            elif ui_group == "Author/Personal":
                author_section.fields.append(field); any_author = True
            elif ui_group == "IPTC":
                iptc_section.fields.append(field); any_iptc = True
            elif ui_group == "XMP":
                xmp_section.fields.append(field); any_xmp = True
            elif ui_group == "ICC Profile":
                icc_section.fields.append(field); any_icc = True
            elif ui_group == "EXIF":
                exif_section.fields.append(field); any_exif = True
            else:
                other_section.fields.append(field); any_other = True

            if unknown:
                unknown_section.fields.append(field.model_copy())
                any_unknown = True

        # Attach decimal/DMS/DDM/grid-locator representations to the GPS
        # lat/long fields using a clean numeric pass (not fragile string
        # parsing of exiftool's own DMS-formatted display string).
        if gps_lat_fields or gps_lon_fields:
            try:
                decimals = exiftool_service.read_gps_decimal(path)
                reprs = gps_service.build_representations(decimals.get("GPSLatitude"), decimals.get("GPSLongitude"))
                locator = {"grid_locator": reprs["grid_locator"]["maidenhead"]} if "grid_locator" in reprs else {}
                if "latitude" in reprs:
                    for f in gps_lat_fields:
                        f.representations = reprs["latitude"] | locator
                if "longitude" in reprs:
                    for f in gps_lon_fields:
                        f.representations = reprs["longitude"] | locator
            except Exception:
                pass  # representations are a bonus display feature; never fail extraction over this

        exif_section.status = ExtractionStatus.SUCCESS if any_exif else ExtractionStatus.NO_METADATA
        iptc_section.status = ExtractionStatus.SUCCESS if any_iptc else ExtractionStatus.NO_METADATA
        xmp_section.status = ExtractionStatus.SUCCESS if any_xmp else ExtractionStatus.NO_METADATA
        gps_section.status = ExtractionStatus.SUCCESS if any_gps else ExtractionStatus.NO_METADATA
        camera_section.status = ExtractionStatus.SUCCESS if any_camera else ExtractionStatus.NO_METADATA
        author_section.status = ExtractionStatus.SUCCESS if any_author else ExtractionStatus.NO_METADATA
        icc_section.status = ExtractionStatus.SUCCESS if any_icc else ExtractionStatus.NO_METADATA
        other_section.status = ExtractionStatus.SUCCESS if any_other else ExtractionStatus.NO_METADATA
        unknown_section.status = ExtractionStatus.SUCCESS if any_unknown else ExtractionStatus.NO_METADATA
        if any_unknown:
            unknown_section.warnings.append(
                "These tags are not in this tool's curated list of common EXIF/GPS/IPTC/XMP tags. They may be "
                "vendor-specific (MakerNotes), non-standard, or simply uncommon — worth a closer look."
            )

        if any_gps:
            gps_section.warnings.append("GPS location data reveals where this file/photo was captured. Handle and share with care.")

        return list(sections.values())


register(ImageParser())
