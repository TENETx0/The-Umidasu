import { useState } from "react";
import { api, ApiError } from "../services/api";
import type { AnalysisResult, SaveAsResponse } from "../types/metadata";
import type { PendingEditState } from "../hooks/useFileSession";

// Mirrors backend/app/services/domains.py — which broad category of
// writable metadata a file format exposes. Kept in sync by hand since this
// panel only needs it to pick a tag list, not to validate a transfer.
type Domain = "image_media" | "office" | "pdf";

const IMAGE_MEDIA_SECTION_IDS = new Set([
  "exif", "gps", "camera", "author", "iptc", "xmp", "icc", "image_technical", "unknown_tags",
  "media_container", "media_video_streams", "media_audio_streams", "media_tags", "media_other_streams",
]);
const OFFICE_SECTION_IDS = new Set(["office_core", "office_structure"]);
const PDF_SECTION_IDS = new Set(["pdf_document", "pdf_structure"]);

function domainForSections(sectionIds: string[]): Domain | null {
  if (sectionIds.some((id) => OFFICE_SECTION_IDS.has(id))) return "office";
  if (sectionIds.some((id) => PDF_SECTION_IDS.has(id))) return "pdf";
  if (sectionIds.some((id) => IMAGE_MEDIA_SECTION_IDS.has(id))) return "image_media";
  return null;
}

interface QuickTag {
  key: string;
  group: string;
  label: string;
  placeholder: string;
}

// Every key below was verified against a real fixture (exiftool -G1 for
// image/media; python-docx core_properties for office; the pdf: key_map in
// editors/metadata_editor.py for PDF) so what's written is read back under
// the exact same key the diff/verification machinery expects — see
// preset_mapping.py for why that match matters.
const CATALOG: Record<Domain, QuickTag[]> = {
  image_media: [
    { key: "IFD0:Artist", group: "EXIF", label: "Author", placeholder: "e.g. Jane Doe" },
    { key: "IFD0:Copyright", group: "EXIF", label: "Copyright", placeholder: "e.g. (c) 2026 Jane Doe" },
    { key: "IFD0:ImageDescription", group: "EXIF", label: "Description", placeholder: "Short description" },
    { key: "IFD0:Software", group: "EXIF", label: "Software / Creator Tool", placeholder: "e.g. The Umidasu" },
    { key: "XMP-dc:Title", group: "XMP", label: "Title", placeholder: "Title" },
    { key: "XMP-dc:Subject", group: "XMP", label: "Subject / Tags", placeholder: "comma, separated, tags" },
    { key: "XMP-dc:Rights", group: "XMP", label: "Rights / Usage Terms", placeholder: "e.g. All rights reserved" },
    { key: "IPTC:Keywords", group: "IPTC", label: "Keywords", placeholder: "comma, separated, keywords" },
    { key: "IPTC:City", group: "IPTC", label: "Location — City", placeholder: "e.g. Chennai" },
    { key: "IPTC:Credit", group: "IPTC", label: "Credit Line", placeholder: "e.g. Staff" },
    { key: "IPTC:Source", group: "IPTC", label: "Source", placeholder: "e.g. Agency name" },
  ],
  office: [
    { key: "core:author", group: "Core Properties", label: "Author", placeholder: "e.g. Jane Doe" },
    { key: "core:title", group: "Core Properties", label: "Title", placeholder: "Document title" },
    { key: "core:subject", group: "Core Properties", label: "Subject", placeholder: "Document subject" },
    { key: "core:comments", group: "Core Properties", label: "Comments", placeholder: "Short note" },
    { key: "core:keywords", group: "Core Properties", label: "Keywords", placeholder: "comma, separated, keywords" },
    { key: "core:category", group: "Core Properties", label: "Category", placeholder: "e.g. Report" },
  ],
  pdf: [
    { key: "pdf:title", group: "Document Info", label: "Title", placeholder: "Document title" },
    { key: "pdf:author", group: "Document Info", label: "Author", placeholder: "e.g. Jane Doe" },
    { key: "pdf:subject", group: "Document Info", label: "Subject", placeholder: "Document subject" },
    { key: "pdf:keywords", group: "Document Info", label: "Keywords", placeholder: "comma, separated, keywords" },
    { key: "pdf:creator", group: "Document Info", label: "Creator Application", placeholder: "e.g. Microsoft Word" },
    { key: "pdf:producer", group: "Document Info", label: "Producer", placeholder: "e.g. The Umidasu" },
  ],
};

const DOMAIN_LABEL: Record<Domain, string> = {
  image_media: "images, video, and audio files",
  office: "Office documents",
  pdf: "PDFs",
};

// A larger catalog of classic tags, offered through the dropdown below the
// quick-add rows rather than as more always-visible inputs. Every key here
// was verified against a real fixture the same way as CATALOG above
// (exiftool -G1 round-trip for image/media; python-docx core_properties
// for office — see the note on hasattr validation in
// editors/metadata_editor.py for why these specific attribute names, and
// not e.g. openpyxl's differently-named equivalents, were chosen). PDF has
// no extended list: pikepdf's /Info dictionary mapping in
// editors/metadata_editor.py supports exactly the 6 keys already shown
// above as quick rows, so there is nothing further to offer.
const EXTENDED_CATALOG: Partial<Record<Domain, QuickTag[]>> = {
  image_media: [
    { key: "IFD0:HostComputer", group: "EXIF", label: "Host Computer", placeholder: "e.g. DESKTOP-TEST" },
    { key: "XMP-dc:Creator", group: "XMP", label: "Creator (XMP)", placeholder: "e.g. Jane Doe" },
    { key: "XMP-dc:Description", group: "XMP", label: "Description (XMP)", placeholder: "Short description" },
    { key: "XMP-dc:Publisher", group: "XMP", label: "Publisher", placeholder: "e.g. Acme Media" },
    { key: "XMP-xmp:Label", group: "XMP", label: "Label", placeholder: "e.g. Red, Approved" },
    { key: "XMP-xmp:Rating", group: "XMP", label: "Rating (0-5)", placeholder: "e.g. 4" },
    { key: "IPTC:By-line", group: "IPTC", label: "Byline", placeholder: "e.g. Jane Doe" },
    { key: "IPTC:By-lineTitle", group: "IPTC", label: "Byline Title", placeholder: "e.g. Staff Photographer" },
    { key: "IPTC:Caption-Abstract", group: "IPTC", label: "Caption / Abstract", placeholder: "Caption text" },
    { key: "IPTC:Headline", group: "IPTC", label: "Headline", placeholder: "Headline text" },
    { key: "IPTC:Province-State", group: "IPTC", label: "Province / State", placeholder: "e.g. Tamil Nadu" },
    { key: "IPTC:Country-PrimaryLocationName", group: "IPTC", label: "Country", placeholder: "e.g. India" },
    { key: "IPTC:SupplementalCategories", group: "IPTC", label: "Supplemental Categories", placeholder: "comma, separated" },
    { key: "IPTC:SpecialInstructions", group: "IPTC", label: "Special Instructions", placeholder: "Handling instructions" },
    { key: "IPTC:Writer-Editor", group: "IPTC", label: "Writer / Editor", placeholder: "e.g. Jane Doe" },
    { key: "IPTC:OriginalTransmissionReference", group: "IPTC", label: "Transmission Reference", placeholder: "e.g. Job #1234" },
    { key: "IPTC:Urgency", group: "IPTC", label: "Urgency (1-8)", placeholder: "e.g. 5" },
  ],
  office: [
    { key: "core:language", group: "Core Properties", label: "Language", placeholder: "e.g. en-US" },
    { key: "core:last_modified_by", group: "Core Properties", label: "Last Modified By", placeholder: "e.g. Jane Doe" },
    { key: "core:content_status", group: "Core Properties", label: "Content Status", placeholder: "e.g. Draft" },
    { key: "core:identifier", group: "Core Properties", label: "Identifier", placeholder: "e.g. DOC-001" },
    { key: "core:version", group: "Core Properties", label: "Version", placeholder: "e.g. 1.0" },
  ],
};

const CUSTOM_KEY_HELP: Record<Domain, string> = {
  image_media:
    'Format: Group:TagName — e.g. "IFD0:MyField" or "XMP-dc:MyField". Must be a tag your installed exiftool recognizes; unrecognized tags are reported as failed after saving, not silently dropped.',
  office:
    'A python-docx/pptx core-property name — e.g. "author", "category". Note: on .xlsx specifically, the real names differ ("creator" not "author", "description" not "comments", "contentStatus" not "content_status"). An unsupported name is reported as failed after saving, not silently applied.',
  pdf: 'PDF /Info only supports: title, author, subject, creator, keywords, producer (prefix with "pdf:", e.g. "pdf:subject"). Anything else will be reported as unsupported after saving.',
};

export function InsertMetadataPanel({
  analysis,
  fileId,
  pending,
  onApplyEdit,
  onClearEdit,
  onSaved,
}: {
  analysis: AnalysisResult;
  fileId: string;
  pending: PendingEditState;
  onApplyEdit: (fieldKey: string, group: string, action: "set" | "remove", value?: unknown) => Promise<void>;
  onClearEdit: (fieldKey: string) => Promise<void>;
  onSaved: (res: SaveAsResponse) => void;
}) {
  const domain = domainForSections(analysis.sections.map((s) => s.section_id));
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // Classic tags dropdown
  const [dropdownKey, setDropdownKey] = useState("");
  const [dropdownValue, setDropdownValue] = useState("");

  // Free-form custom tag
  const [customKey, setCustomKey] = useState("");
  const [customValue, setCustomValue] = useState("");
  const [customGroup, setCustomGroup] = useState("");

  const pendingCount = Object.keys(pending).length;

  const handleSave = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const res = await api.saveAs(fileId);
      onSaved(res);
    } catch (e) {
      setSaveError(e instanceof ApiError ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  };

  if (!domain) {
    return (
      <div className="card p-5">
        <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Insert Metadata</h3>
        <p className="text-sm text-[var(--color-grey-400)]">
          This file's format doesn't expose a writable metadata domain, so there are no default tags to offer here.
        </p>
      </div>
    );
  }

  const tags = CATALOG[domain];

  const addTag = async (tag: QuickTag) => {
    const value = (drafts[tag.key] ?? "").trim();
    if (!value) return;
    await onApplyEdit(tag.key, tag.group, "set", value);
  };

  const removeTag = async (tag: QuickTag) => {
    await onClearEdit(tag.key);
  };

  const extended = EXTENDED_CATALOG[domain] ?? [];
  const selectedDropdownTag = extended.find((t) => t.key === dropdownKey) ?? null;

  const addDropdownTag = async () => {
    const value = dropdownValue.trim();
    if (!selectedDropdownTag || !value) return;
    await onApplyEdit(selectedDropdownTag.key, selectedDropdownTag.group, "set", value);
    setDropdownValue("");
    setDropdownKey("");
  };

  const addCustomTag = async () => {
    const key = customKey.trim();
    const value = customValue.trim();
    if (!key || !value) return;
    await onApplyEdit(key, customGroup.trim() || "Custom", "set", value);
    setCustomKey("");
    setCustomValue("");
    setCustomGroup("");
  };

  return (
    <div className="card p-5" id="insert-metadata">
      <h3 className="mb-1 text-sm font-semibold uppercase tracking-wide text-[var(--color-grey-500)]">Insert Metadata</h3>
      <p className="mb-4 text-xs text-[var(--color-grey-400)]">
        Default tags commonly used in {DOMAIN_LABEL[domain]}. Fill in a value and add it — it stages below like any
        other edit, and nothing is written to the file until you save.
      </p>

      <div className="flex flex-col divide-y divide-[var(--color-border)]">
        {tags.map((tag) => {
          const staged = pending[tag.key];
          return (
            <div key={tag.key} className="flex flex-col gap-2 py-2.5 first:pt-0 last:pb-0 sm:flex-row sm:items-center">
              <div className="sm:w-44 sm:shrink-0">
                <p className="text-sm font-medium text-[var(--color-ink)]">{tag.label}</p>
                <p className="mono text-[10px] text-[var(--color-grey-400)]">{tag.key}</p>
              </div>
              <input
                type="text"
                value={drafts[tag.key] ?? (staged && staged.action === "set" ? String(staged.value ?? "") : "")}
                onChange={(e) => setDrafts((d) => ({ ...d, [tag.key]: e.target.value }))}
                placeholder={tag.placeholder}
                className="flex-1 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
              />
              {staged ? (
                <div className="flex shrink-0 items-center gap-2">
                  <span className="badge bg-[var(--color-orange-50)] text-[var(--color-orange-700)]">Staged</span>
                  <button
                    className="text-xs text-[var(--color-grey-400)] hover:text-[var(--color-danger)]"
                    onClick={() => removeTag(tag)}
                    type="button"
                  >
                    Remove
                  </button>
                </div>
              ) : (
                <button
                  className="btn-secondary shrink-0 rounded-lg px-3 py-1.5 text-sm"
                  onClick={() => addTag(tag)}
                  type="button"
                >
                  + Add
                </button>
              )}
            </div>
          );
        })}
      </div>

      {extended.length > 0 && (
        <div className="mt-4 border-t border-[var(--color-border)] pt-4">
          <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--color-grey-400)]">
            More classic tags ({tags.length + extended.length} available for this file type)
          </p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <select
              value={dropdownKey}
              onChange={(e) => setDropdownKey(e.target.value)}
              className="rounded-lg border border-[var(--color-border-strong)] bg-[var(--color-paper)] px-3 py-1.5 text-sm text-[var(--color-ink)] outline-none focus:border-[var(--color-orange-400)] sm:w-52 sm:shrink-0"
            >
              <option value="">Choose a tag…</option>
              {extended.map((t) => (
                <option key={t.key} value={t.key}>
                  {t.label}
                </option>
              ))}
            </select>
            <input
              type="text"
              value={dropdownValue}
              onChange={(e) => setDropdownValue(e.target.value)}
              placeholder={selectedDropdownTag ? selectedDropdownTag.placeholder : "Select a tag first"}
              disabled={!selectedDropdownTag}
              className="flex-1 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)] disabled:opacity-50"
            />
            <button
              className="btn-secondary shrink-0 rounded-lg px-3 py-1.5 text-sm"
              onClick={addDropdownTag}
              disabled={!selectedDropdownTag || !dropdownValue.trim()}
              type="button"
            >
              + Add Tag
            </button>
          </div>
          {selectedDropdownTag && <p className="mono mt-1 text-[10px] text-[var(--color-grey-400)]">{selectedDropdownTag.key}</p>}
        </div>
      )}

      <div className="mt-4 border-t border-[var(--color-border)] pt-4">
        <p className="mb-2 text-xs font-medium uppercase tracking-wide text-[var(--color-grey-400)]">Custom metadata tag</p>
        <p className="mb-2 text-[11px] text-[var(--color-grey-400)]">{CUSTOM_KEY_HELP[domain]}</p>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
          <input
            type="text"
            value={customKey}
            onChange={(e) => setCustomKey(e.target.value)}
            placeholder="Tag key"
            className="mono rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)] sm:w-52 sm:shrink-0"
          />
          <input
            type="text"
            value={customValue}
            onChange={(e) => setCustomValue(e.target.value)}
            placeholder="Value"
            className="flex-1 rounded-lg border border-[var(--color-border-strong)] px-3 py-1.5 text-sm outline-none focus:border-[var(--color-orange-400)]"
          />
          <button
            className="btn-secondary shrink-0 rounded-lg px-3 py-1.5 text-sm"
            onClick={addCustomTag}
            disabled={!customKey.trim() || !customValue.trim()}
            type="button"
          >
            + Add Custom Tag
          </button>
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[var(--color-border)] pt-4">
        <p className="text-xs text-[var(--color-grey-400)]">
          {pendingCount} pending change{pendingCount === 1 ? "" : "s"} across the editor.
        </p>
        <button
          className="btn-primary rounded-lg px-4 py-1.5 text-sm font-medium"
          onClick={handleSave}
          disabled={saving || pendingCount === 0}
          type="button"
        >
          {saving ? "Saving…" : "Save Edited File"}
        </button>
      </div>
      {saveError && <p className="mt-2 text-sm text-[var(--color-danger)]">{saveError}</p>}
    </div>
  );
}
