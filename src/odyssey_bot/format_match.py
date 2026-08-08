"""Strict IMAX 70mm format detection — rejects plain 70mm / digital IMAX."""
from __future__ import annotations

import re

IMAX_70MM_RE = re.compile(r"imax\s*70\s*mm", re.IGNORECASE)


def is_imax_70mm(text: str) -> bool:
    """True only when text indicates native IMAX 70mm (not plain 70mm alone)."""
    return bool(IMAX_70MM_RE.search(text))
