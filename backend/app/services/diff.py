"""Metadata Difference Highlighting — a pure field_map -> field_map diff.

Used both for the Snapshot-vs-current comparison (server-side) and can be
reused by the frontend's real-time overlay (which merges in not-yet-saved
pending edits on top of a server-computed baseline diff).
"""
from __future__ import annotations

from app.models.schemas import DiffEntry, MetadataDiff


def _norm(v):
    if isinstance(v, (list, dict)):
        return repr(v)
    return v


def diff_field_maps(before: dict[str, object], after: dict[str, object],
                     labels: dict[str, str] | None = None) -> MetadataDiff:
    labels = labels or {}
    before_keys = set(before.keys())
    after_keys = set(after.keys())

    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    common = before_keys & after_keys
    modified = sorted(k for k in common if _norm(before[k]) != _norm(after[k]))

    return MetadataDiff(
        added=[DiffEntry(key=k, label=labels.get(k, k), before=None, after=after[k]) for k in added],
        removed=[DiffEntry(key=k, label=labels.get(k, k), before=before[k], after=None) for k in removed],
        modified=[DiffEntry(key=k, label=labels.get(k, k), before=before[k], after=after[k]) for k in modified],
    )


def build_field_map(sections, writable_only: bool = True) -> tuple[dict[str, object], dict[str, str]]:
    """Build (field_map, label_map) from a list of MetadataSection."""
    field_map: dict[str, object] = {}
    label_map: dict[str, str] = {}
    for section in sections:
        for f in section.fields:
            if writable_only and not f.writable:
                continue
            field_map[f.key] = f.normalized_value
            label_map[f.key] = f.label
    return field_map, label_map
