from __future__ import annotations

from pathlib import Path

import pytest

from app.security.paths import ensure_no_overwrite, safe_join, sanitize_display_name


def test_sanitize_display_name_strips_path_separators():
    assert sanitize_display_name("../../etc/passwd") == "passwd"
    assert sanitize_display_name("report:final*.pdf") != "report:final*.pdf"


def test_safe_join_blocks_traversal(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    with pytest.raises(ValueError):
        safe_join(root, "..", "..", "etc", "passwd")


def test_safe_join_allows_normal_path(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    result = safe_join(root, "sub", "file.txt")
    assert str(result).startswith(str(root))


def test_ensure_no_overwrite_raises_on_existing(tmp_path):
    f = tmp_path / "exists.txt"
    f.write_text("x")
    with pytest.raises(FileExistsError):
        ensure_no_overwrite(f)


def test_ensure_no_overwrite_allows_new_path(tmp_path):
    f = tmp_path / "new.txt"
    ensure_no_overwrite(f)  # should not raise
