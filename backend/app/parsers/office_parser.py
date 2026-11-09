"""OOXML (docx/xlsx/pptx) inspection via python-docx/openpyxl/python-pptx
plus raw ZIP package inspection for structure-level detail."""
from __future__ import annotations

import zipfile
from pathlib import Path

from app.models.schemas import Capability, ExtractionStatus, MetadataField, MetadataSection
from app.parsers.base import BaseParser, register

OFFICE_EXTS = {"docx", "xlsx", "pptx", "dotx", "xltx", "potx"}

CORE_PROP_FIELDS = [
    "author", "category", "comments", "content_status", "created", "identifier", "keywords",
    "language", "last_modified_by", "last_printed", "modified", "revision", "subject", "title", "version",
]


def _detect_kind(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as z:
            names = z.namelist()
            if "word/document.xml" in names:
                return "docx"
            if "xl/workbook.xml" in names:
                return "xlsx"
            if "ppt/presentation.xml" in names:
                return "pptx"
    except Exception:
        return None
    return None


class OfficeParser(BaseParser):
    name = "office"

    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        if extension in OFFICE_EXTS:
            return True
        if detected_format == "ZIP/OOXML":
            return True
        return False

    def get_capabilities(self, path: Path) -> list[Capability]:
        kind = _detect_kind(path)
        return [
            Capability(name="Core/extended properties extraction", available=kind is not None,
                       reason=None if kind else "Not a recognized OOXML package"),
            Capability(name="Core properties editing", available=kind is not None,
                       reason=None if kind else "Not a recognized OOXML package"),
            Capability(name="Macro/active content execution", available=False, reason="Intentionally never executed."),
        ]

    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        core_section = MetadataSection(section_id="office_core", title="Core Document Properties", status=ExtractionStatus.NOT_ANALYZED)
        struct_section = MetadataSection(section_id="office_structure", title="Document Structure", status=ExtractionStatus.NOT_ANALYZED)
        package_section = MetadataSection(section_id="office_package", title="ZIP Package Members", status=ExtractionStatus.NOT_ANALYZED)

        kind = _detect_kind(path)
        if not kind:
            for s in (core_section, struct_section, package_section):
                s.status = ExtractionStatus.NOT_SUPPORTED
                s.detail_message = "File is not a recognized DOCX/XLSX/PPTX package."
            return [core_section, struct_section, package_section]

        try:
            if kind == "docx":
                import docx
                d = docx.Document(str(path))
                cp = d.core_properties
                fields = []
                for attr in CORE_PROP_FIELDS:
                    val = getattr(cp, attr, None)
                    if val not in (None, ""):
                        fields.append(MetadataField(key=f"core:{attr}", group="Core Properties", label=attr.replace("_", " ").title(),
                                                      raw_value=str(val), normalized_value=str(val), value_type="string",
                                                      source_parser="python-docx", writable=True))
                core_section.fields = fields
                core_section.status = ExtractionStatus.SUCCESS if fields else ExtractionStatus.NO_METADATA

                struct_section.fields = [
                    MetadataField(key="struct:paragraph_count", group="Structure", label="Paragraph Count",
                                  raw_value=len(d.paragraphs), normalized_value=len(d.paragraphs), value_type="number", source_parser="python-docx"),
                    MetadataField(key="struct:table_count", group="Structure", label="Table Count",
                                  raw_value=len(d.tables), normalized_value=len(d.tables), value_type="number", source_parser="python-docx"),
                    MetadataField(key="struct:section_count", group="Structure", label="Section Count",
                                  raw_value=len(d.sections), normalized_value=len(d.sections), value_type="number", source_parser="python-docx"),
                    MetadataField(key="struct:inline_shapes", group="Structure", label="Inline Shapes / Embedded Media",
                                  raw_value=len(d.inline_shapes), normalized_value=len(d.inline_shapes), value_type="number", source_parser="python-docx"),
                ]
                struct_section.status = ExtractionStatus.SUCCESS

            elif kind == "xlsx":
                import openpyxl
                wb = openpyxl.load_workbook(str(path), read_only=True, data_only=True)
                cp = wb.properties
                fields = []
                for attr in ("creator", "title", "subject", "description", "keywords", "category",
                             "lastModifiedBy", "created", "modified", "company", "manager", "identifier"):
                    val = getattr(cp, attr, None)
                    if val not in (None, ""):
                        fields.append(MetadataField(key=f"core:{attr}", group="Core Properties", label=attr,
                                                      raw_value=str(val), normalized_value=str(val), value_type="string",
                                                      source_parser="openpyxl", writable=True))
                core_section.fields = fields
                core_section.status = ExtractionStatus.SUCCESS if fields else ExtractionStatus.NO_METADATA

                struct_section.fields = [
                    MetadataField(key="struct:sheet_names", group="Structure", label="Sheet Names",
                                  raw_value=wb.sheetnames, normalized_value=", ".join(wb.sheetnames), value_type="array", source_parser="openpyxl"),
                    MetadataField(key="struct:sheet_count", group="Structure", label="Sheet Count",
                                  raw_value=len(wb.sheetnames), normalized_value=len(wb.sheetnames), value_type="number", source_parser="openpyxl"),
                ]
                struct_section.status = ExtractionStatus.SUCCESS
                wb.close()

            elif kind == "pptx":
                from pptx import Presentation
                prs = Presentation(str(path))
                cp = prs.core_properties
                fields = []
                for attr in CORE_PROP_FIELDS:
                    val = getattr(cp, attr, None)
                    if val not in (None, ""):
                        fields.append(MetadataField(key=f"core:{attr}", group="Core Properties", label=attr.replace("_", " ").title(),
                                                      raw_value=str(val), normalized_value=str(val), value_type="string",
                                                      source_parser="python-pptx", writable=True))
                core_section.fields = fields
                core_section.status = ExtractionStatus.SUCCESS if fields else ExtractionStatus.NO_METADATA

                struct_section.fields = [
                    MetadataField(key="struct:slide_count", group="Structure", label="Slide Count",
                                  raw_value=len(prs.slides), normalized_value=len(prs.slides), value_type="number", source_parser="python-pptx"),
                    MetadataField(key="struct:slide_width", group="Structure", label="Slide Width (EMU)",
                                  raw_value=prs.slide_width, normalized_value=prs.slide_width, value_type="number", source_parser="python-pptx"),
                    MetadataField(key="struct:slide_height", group="Structure", label="Slide Height (EMU)",
                                  raw_value=prs.slide_height, normalized_value=prs.slide_height, value_type="number", source_parser="python-pptx"),
                ]
                struct_section.status = ExtractionStatus.SUCCESS
        except Exception as exc:
            core_section.status = ExtractionStatus.FAILED
            core_section.detail_message = str(exc)
            struct_section.status = ExtractionStatus.FAILED
            struct_section.detail_message = str(exc)

        # --- Raw ZIP package members (always attempted independently) ---
        try:
            with zipfile.ZipFile(path) as z:
                infos = z.infolist()
                fields = [
                    MetadataField(key=f"zip:{i}", group="Package", label=info.filename,
                                  raw_value={"size": info.file_size, "compressed": info.compress_size,
                                             "date": "%04d-%02d-%02d %02d:%02d:%02d" % info.date_time},
                                  normalized_value=f"{info.file_size} bytes", value_type="object", source_parser="zipfile")
                    for i, info in enumerate(infos[:500])
                ]
                package_section.fields = fields
                package_section.status = ExtractionStatus.SUCCESS
                if len(infos) > 500:
                    package_section.warnings.append(f"Package has {len(infos)} members; showing first 500.")
        except Exception as exc:
            package_section.status = ExtractionStatus.FAILED
            package_section.detail_message = str(exc)

        return [core_section, struct_section, package_section]


register(OfficeParser())
