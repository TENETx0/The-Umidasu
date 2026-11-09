from __future__ import annotations

import hashlib

from app.services.hashing import compute_entropy_and_histogram, compute_hashes


def test_compute_hashes_matches_hashlib(tmp_path):
    f = tmp_path / "data.bin"
    content = b"The Umidasu test content" * 100
    f.write_bytes(content)

    result = compute_hashes(f)
    assert result.sha256 == hashlib.sha256(content).hexdigest()
    assert result.md5 == hashlib.md5(content).hexdigest()
    assert result.sha1 == hashlib.sha1(content).hexdigest()
    assert result.sha512 == hashlib.sha512(content).hexdigest()
    assert "broken" in result.security_notes["md5"].lower()


def test_entropy_zero_for_constant_bytes(tmp_path):
    f = tmp_path / "zeros.bin"
    f.write_bytes(b"\x00" * 1000)
    entropy, histogram = compute_entropy_and_histogram(f)
    assert entropy == 0.0
    assert histogram[0] == 1000


def test_entropy_high_for_random_bytes(tmp_path):
    import os
    f = tmp_path / "random.bin"
    f.write_bytes(os.urandom(100_000))
    entropy, _ = compute_entropy_and_histogram(f)
    assert entropy > 7.5  # near-max 8.0 bits/byte for truly random data
