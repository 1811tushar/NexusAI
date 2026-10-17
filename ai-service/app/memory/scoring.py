"""Long-term memory scoring (AI-ME-02, contract 10.2): score = 0.5*relevance + 0.3*exp(-ageDays/30) + 0.2*importance. Pure functions."""
from __future__ import annotations

import math

MIN_RELEVANCE = 0.35     # floor: below this a memory is never recalled (it is not about this question)
TOP_N = 5
DEDUPE_SIMILARITY = 0.92


def recency(age_days: float) -> float:
    return math.exp(-max(0.0, age_days) / 30.0)


def recall_score(relevance: float, age_days: float, importance: float) -> float:
    return 0.5 * relevance + 0.3 * recency(age_days) + 0.2 * importance


def importance_for(overall_confidence: float | None, verified: int, total: int) -> float:
    """0.3..1.0: more confident and more verified findings are worth remembering longer."""
    conf = 0.0 if overall_confidence is None else max(0.0, min(1.0, overall_confidence))
    share = (verified / total) if total else 0.0
    return round(max(0.0, min(1.0, 0.3 + 0.5 * conf + 0.2 * share)), 3)
