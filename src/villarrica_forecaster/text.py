from __future__ import annotations

import re
import unicodedata


def strip_accents(value: str) -> str:
    """Normalize accents for robust Spanish/English column matching."""

    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def normalize_token(value: str) -> str:
    """Lowercase, accent-strip, and collapse non-alphanumeric separators."""

    stripped = strip_accents(value).lower()
    return re.sub(r"[^a-z0-9]+", " ", stripped).strip()
