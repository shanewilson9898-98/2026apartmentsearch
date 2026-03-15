from __future__ import annotations

import re
from typing import Iterable


def infer_bool_from_text(texts: Iterable[str], patterns: Iterable[str]) -> bool:
    haystack = " ".join(texts).lower()
    return any(re.search(pattern, haystack) for pattern in patterns)


def infer_completeness_score(address: str | None, rent: int | None, description: str, images: list[str]) -> float:
    score = 0.0
    if address:
        score += 0.35
    if rent is not None:
        score += 0.2
    if description.strip():
        score += 0.25
    if images:
        score += 0.2
    return round(score, 2)
