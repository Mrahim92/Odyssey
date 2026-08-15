"""AMC showtime URL helpers."""
from __future__ import annotations

import re
from urllib.parse import urljoin

AMC_BASE = "https://www.amctheatres.com"
_SHOWTIME_ID_RE = re.compile(r"/showtimes/(\d+)")


def normalize_amc_purchase_url(url: str) -> str:
    """Return the seat-selection URL AMC actually serves (without /seats many links 404)."""
    normalized = urljoin(AMC_BASE, url).rstrip("/")
    match = _SHOWTIME_ID_RE.search(normalized)
    if not match:
        return normalized
    showtime_id = match.group(1)
    return f"{AMC_BASE}/showtimes/{showtime_id}/seats"
