"""PDF inspection via PyMuPDF (fitz) and pikepdf."""
from __future__ import annotations

from pathlib import Path

from app.models.schemas import Capability, ExtractionStatus, MetadataField, MetadataSection
from app.parsers.base import BaseParser, register

try:
    import fitz  # PyMuPDF
    _HAVE_FITZ = True
except Exception:
    _HAVE_FITZ = False

try:
    import pikepdf
    _HAVE_PIKEPDF = True
except Exception:
    _HAVE_PIKEPDF = False

PDF_EXTS = {"pdf"}


class PdfParser(BaseParser):
    name = "pdf"

    def supports(self, detected_format: str, mime_type: str, extension: str) -> bool:
        return detected_format == "PDF" or mime_type == "application/pdf" or extension in PDF_EXTS

    def get_capabilities(self, path: Path) -> list[Capability]:
        return [
            Capability(name="Document info/metadata extraction", available=_HAVE_FITZ or _HAVE_PIKEPDF,
                       reason=None if (_HAVE_FITZ or _HAVE_PIKEPDF) else "PyMuPDF/pikepdf not installed"),
            Capability(name="Metadata editing", available=_HAVE_PIKEPDF, reason=None if _HAVE_PIKEPDF else "pikepdf not installed"),
            Capability(name="Digital signature validation", available=False, reason="Signature cryptographic validation is not implemented; only presence is reported."),
        ]

    def extract_metadata(self, path: Path) -> list[MetadataSection]:
        doc_section = MetadataSection(section_id="pdf_document", title="Document Properties", status=ExtractionStatus.NOT_ANALYZED)
        struct_section = MetadataSection(section_id="pdf_structure", title="Structure & Security", status=ExtractionStatus.NOT_ANALYZED)
        embedded_section = MetadataSection(section_id="pdf_embedded", title="Embedded Files & XMP", status=ExtractionStatus.NOT_ANALYZED)

        if not _HAVE_FITZ and not _HAVE_PIKEPDF:
            for s in (doc_section, struct_section, embedded_section):
                s.status = ExtractionStatus.NOT_ANALYZED
                s.detail_message = "No PDF library (PyMuPDF/pikepdf) installed."
            return [doc_section, struct_section, embedded_section]

        if _HAVE_FITZ:
            try:
                with fitz.open(path) as doc:
                    meta = doc.metadata or {}
                    fields = []
                    for k, v in meta.items():
                        if v:
                            fields.append(MetadataField(key=f"pdf:{k}", group="Document Info", label=k, raw_value=v,
                                                          normalized_value=v, value_type="string", source_parser="PyMuPDF", writable=True))
                    doc_section.fields = fields
                    doc_section.status = ExtractionStatus.SUCCESS if fields else ExtractionStatus.NO_METADATA

                    struct_fields = [
                        MetadataField(key="pdf:page_count", group="Structure", label="Page Count", raw_value=doc.page_count,
                                      normalized_value=doc.page_count, value_type="number", source_parser="PyMuPDF"),
                        MetadataField(key="pdf:pdf_version", group="Structure", label="PDF Version", raw_value=doc.pdf_version() if hasattr(doc, "pdf_version") else None,
                                      normalized_value=None, value_type="string", source_parser="PyMuPDF"),
                        MetadataField(key="pdf:is_encrypted", group="Security", label="Encrypted", raw_value=doc.is_encrypted,
                                      normalized_value=doc.is_encrypted, value_type="boolean", source_parser="PyMuPDF"),
                        MetadataField(key="pdf:needs_pass", group="Security", label="Password Protected", raw_value=doc.needs_pass,
                                      normalized_value=doc.needs_pass, value_type="boolean", source_parser="PyMuPDF"),
                        MetadataField(key="pdf:permissions", group="Security", label="Permissions Bitmask", raw_value=doc.permissions,
                                      normalized_value=doc.permissions, value_type="number", source_parser="PyMuPDF"),
                    ]
                    if doc.page_count:
                        p0 = doc[0]
                        struct_fields.append(MetadataField(key="pdf:page0_size", group="Structure", label="Page 1 Size (pt)",
                                                             raw_value=[p0.rect.width, p0.rect.height], normalized_value=f"{p0.rect.width:.1f} x {p0.rect.height:.1f}",
                                                             value_type="string", source_parser="PyMuPDF"))
                    struct_fields.append(MetadataField(key="pdf:links_count", group="Structure", label="Total Links",
                                                         raw_value=sum(len(doc[i].get_links()) for i in range(doc.page_count)),
                                                         normalized_value=None, value_type="number", source_parser="PyMuPDF"))
                    toc = doc.get_toc()
                    struct_fields.append(MetadataField(key="pdf:bookmark_count", group="Structure", label="Bookmark/Outline Count",
                                                         raw_value=len(toc), normalized_value=len(toc), value_type="number", source_parser="PyMuPDF"))
                    struct_section.fields = struct_fields
                    struct_section.status = ExtractionStatus.SUCCESS

                    xmp = doc.xref_xml_metadata() if hasattr(doc, "xref_xml_metadata") else 0
                    embedded_names = doc.embfile_names() if hasattr(doc, "embfile_names") else []
                    emb_fields = [MetadataField(key=f"pdf:embedded_file:{n}", group="Embedded", label=f"Embedded File: {n}",
                                                 raw_value=n, normalized_value=n, value_type="string", source_parser="PyMuPDF")
                                  for n in embedded_names]
                    embedded_section.fields = emb_fields
                    embedded_section.status = ExtractionStatus.SUCCESS if emb_fields else ExtractionStatus.NO_METADATA

                    sig_present = b"/Sig" in path.read_bytes()[-200000:] if path.stat().st_size < 50_000_000 else False
                    struct_section.fields.append(MetadataField(key="pdf:has_signature_marker", group="Security",
                                                                 label="Digital Signature Marker Present", raw_value=sig_present,
                                                                 normalized_value=sig_present, value_type="boolean", source_parser="heuristic",
                                                                 notes="Heuristic marker only — not cryptographic validation."))
            except Exception as exc:
                doc_section.status = ExtractionStatus.FAILED
                doc_section.detail_message = str(exc)
                struct_section.status = ExtractionStatus.FAILED
                struct_section.detail_message = str(exc)
                embedded_section.status = ExtractionStatus.FAILED
                embedded_section.detail_message = str(exc)

        return [doc_section, struct_section, embedded_section]


register(PdfParser())
