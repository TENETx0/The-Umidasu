"""Metadata Copy & Paste — transfer compatible writable field values from
one analyzed file's metadata onto another, staged as pending edits on the
target (never written to disk directly; the normal Save As / verification
flow still applies)."""
from __future__ import annotations

from app.models.schemas import AnalysisResult, CopyFieldResult
from app.services.domains import is_compatible


def compute_copy_candidates(source: AnalysisResult, target: AnalysisResult,
                             field_keys: list[str] | None) -> list[CopyFieldResult]:
    target_section_ids = {s.section_id for s in target.sections}

    source_fields = [f for s in source.sections for f in s.fields if f.writable]
    if field_keys:
        wanted = set(field_keys)
        source_fields = [f for f in source_fields if f.key in wanted]

    results: list[CopyFieldResult] = []
    for f in source_fields:
        if f.normalized_value in (None, ""):
            continue  # nothing meaningful to copy
        compatible, reason = is_compatible(f.key, target_section_ids)
        results.append(CopyFieldResult(
            key=f.key, label=f.label, value=f.normalized_value,
            compatible=compatible, staged=False, reason=reason,
        ))
    return results
