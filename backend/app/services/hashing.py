"""Cryptographic hashing and entropy/byte-histogram analysis."""
from __future__ import annotations

import hashlib
import math
from pathlib import Path

from app.models.schemas import FileHashes

_CHUNK = 1024 * 1024

HASH_SECURITY_NOTES = {
    "md5": "Cryptographically broken (collision attacks practical). Useful only for quick integrity checks, not trust.",
    "sha1": "Cryptographically weakened (collision attacks demonstrated, e.g. SHAttered). Avoid for security-critical integrity.",
    "sha256": "Currently considered cryptographically strong and collision-resistant for integrity verification.",
    "sha512": "Currently considered cryptographically strong; longer digest, similar security margin to SHA-256.",
}


def compute_hashes(path: Path) -> FileHashes:
    md5 = hashlib.md5()
    sha1 = hashlib.sha1()
    sha256 = hashlib.sha256()
    sha512 = hashlib.sha512()
    with path.open("rb") as f:
        while chunk := f.read(_CHUNK):
            md5.update(chunk)
            sha1.update(chunk)
            sha256.update(chunk)
            sha512.update(chunk)
    return FileHashes(
        md5=md5.hexdigest(),
        sha1=sha1.hexdigest(),
        sha256=sha256.hexdigest(),
        sha512=sha512.hexdigest(),
        security_notes=HASH_SECURITY_NOTES,
    )


def compute_entropy_and_histogram(path: Path, max_bytes: int = 8 * 1024 * 1024) -> tuple[float, list[int]]:
    """Shannon entropy (bits/byte) and a 256-bucket histogram.

    Computed over at most `max_bytes` to bound cost on huge files; this is
    documented to the user as a sampled measurement when the file exceeds
    the sample window.
    """
    counts = [0] * 256
    total = 0
    with path.open("rb") as f:
        while total < max_bytes:
            chunk = f.read(min(_CHUNK, max_bytes - total))
            if not chunk:
                break
            for b in chunk:
                counts[b] += 1
            total += len(chunk)
    if total == 0:
        return 0.0, counts
    entropy = 0.0
    for c in counts:
        if c:
            p = c / total
            entropy -= p * math.log2(p)
    return round(entropy, 4), counts
