"""Builds JSON / CSV / HTML inspection reports."""
from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime, timezone

from app.models.schemas import AnalysisResult


def build_json_report(analysis: AnalysisResult, before: AnalysisResult | None = None) -> str:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "application": "The Umidasu",
        "analysis": analysis.model_dump(),
    }
    if before:
        payload["before"] = before.model_dump()
    return json.dumps(payload, indent=2, default=str)


def build_csv_report(analysis: AnalysisResult) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["section", "status", "group", "key", "label", "value_type", "value", "writable", "sensitive", "source_parser"])
    for section in analysis.sections:
        for f in section.fields:
            writer.writerow([section.title, section.status.value, f.group, f.key, f.label, f.value_type,
                              str(f.normalized_value), f.writable, f.sensitive, f.source_parser])
    return buf.getvalue()


def _esc(s) -> str:
    return html.escape(str(s)) if s is not None else ""


def build_html_report(analysis: AnalysisResult, before: AnalysisResult | None = None) -> str:
    rows = []
    for section in analysis.sections:
        rows.append(f'<h3>{_esc(section.title)} <span class="status status-{section.status.value}">{_esc(section.status.value)}</span></h3>')
        if section.detail_message:
            rows.append(f'<p class="muted">{_esc(section.detail_message)}</p>')
        if section.warnings:
            rows.append('<ul class="warnings">' + "".join(f"<li>{_esc(w)}</li>" for w in section.warnings) + "</ul>")
        if section.fields:
            rows.append('<table><thead><tr><th>Group</th><th>Field</th><th>Value</th><th>Writable</th></tr></thead><tbody>')
            for f in section.fields:
                rows.append(f"<tr><td>{_esc(f.group)}</td><td>{_esc(f.label)}</td><td>{_esc(f.normalized_value)}</td><td>{'Yes' if f.writable else 'No'}</td></tr>")
            rows.append("</tbody></table>")

    comparison_html = ""
    if before:
        comparison_html = "<h2>Before / After Comparison</h2>" + _build_comparison_table(before, analysis)

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>The Umidasu — Inspection Report</title>
<style>
  :root {{
    --orange: #ff7a1a; --orange-dark: #e3650a; --grey: #6b7280; --grey-light: #f4f4f3;
    --border: #e5e0da; --bg: #ffffff; --text: #2a2622;
  }}
  body {{ font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 2rem; }}
  h1 {{ color: var(--orange-dark); border-bottom: 3px solid var(--orange); padding-bottom: .5rem; }}
  h2 {{ color: var(--orange-dark); margin-top: 2.5rem; }}
  h3 {{ background: var(--grey-light); padding: .5rem .75rem; border-left: 4px solid var(--orange); margin-top: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; margin-bottom: 1rem; }}
  th, td {{ border: 1px solid var(--border); padding: .4rem .6rem; font-size: .9rem; text-align: left; }}
  th {{ background: var(--grey-light); color: var(--grey); }}
  tr:nth-child(even) {{ background: #fafafa; }}
  .muted {{ color: var(--grey); font-style: italic; }}
  .warnings {{ color: #a85400; background: #fff3e6; padding: .5rem 1.5rem; border-radius: 4px; }}
  .status {{ font-size: .75rem; padding: .1rem .5rem; border-radius: 10px; background: var(--grey-light); color: var(--grey); margin-left: .5rem; }}
  .status-extracted_successfully {{ background: #fde8d6; color: var(--orange-dark); }}
  .meta {{ color: var(--grey); font-size: .85rem; }}
</style>
</head>
<body>
<h1>The Umidasu — File Inspection Report</h1>
<p class="meta">Generated {_esc(datetime.now(timezone.utc).isoformat())}</p>
<h2>File Identity</h2>
<table>
<tr><th>Original Filename</th><td>{_esc(analysis.identity.original_filename)}</td></tr>
<tr><th>Detected Format</th><td>{_esc(analysis.identity.detected_format)}</td></tr>
<tr><th>MIME Type</th><td>{_esc(analysis.identity.mime_type)}</td></tr>
<tr><th>Size</th><td>{_esc(analysis.identity.size_human)} ({analysis.identity.size_bytes} bytes)</td></tr>
<tr><th>Extension Matches Format</th><td>{'Yes' if analysis.identity.extension_matches_format else 'No — MISMATCH'}</td></tr>
<tr><th>SHA-256</th><td><code>{_esc(analysis.hashes.sha256)}</code></td></tr>
<tr><th>SHA-512</th><td><code>{_esc(analysis.hashes.sha512)}</code></td></tr>
<tr><th>SHA-1</th><td><code>{_esc(analysis.hashes.sha1)}</code></td></tr>
<tr><th>MD5</th><td><code>{_esc(analysis.hashes.md5)}</code></td></tr>
<tr><th>Entropy</th><td>{analysis.entropy} bits/byte</td></tr>
</table>
{comparison_html}
<h2>Metadata Sections</h2>
{''.join(rows)}
</body>
</html>"""


def _build_comparison_table(before: AnalysisResult, after: AnalysisResult) -> str:
    before_map = {f.key: f.normalized_value for s in before.sections for f in s.fields}
    after_map = {f.key: f.normalized_value for s in after.sections for f in s.fields}
    all_keys = sorted(set(before_map) | set(after_map))
    rows = []
    for k in all_keys:
        b, a = before_map.get(k, "—"), after_map.get(k, "—")
        if b == a:
            continue
        rows.append(f"<tr><td>{_esc(k)}</td><td>{_esc(b)}</td><td>{_esc(a)}</td></tr>")
    if not rows:
        return "<p class='muted'>No field-level differences detected.</p>"
    return "<table><thead><tr><th>Field</th><th>Before</th><th>After</th></tr></thead><tbody>" + "".join(rows) + "</tbody></table>"
