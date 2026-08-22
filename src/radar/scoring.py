import math
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Tuple


def clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return max(minimum, min(maximum, value))


def log_scale(value: float, reference: float = 100.0) -> float:
    if value <= 0:
        return 0.0
    return clamp((math.log1p(value) / math.log1p(reference)) * 100.0)


def velocity(history: List[Tuple[float, datetime]]) -> float:
    if len(history) < 2:
        return 0.0
    current, current_time = history[0]
    previous, previous_time = history[1]
    hours = max((current_time - previous_time).total_seconds() / 3600.0, 1.0)
    return max(0.0, current - previous) / hours


def acceleration(history: List[Tuple[float, datetime]]) -> float:
    if len(history) < 3:
        return 1.0
    today = velocity(history[:2])
    prior = velocity(history[1:3])
    if prior <= 0:
        return 4.0 if today > 0 else 1.0
    return clamp(today / prior, 0.0, 10.0)


def novelty_score(first_seen: datetime, now: datetime) -> float:
    age_days = max(0.0, (now - first_seen).total_seconds() / 86400.0)
    if age_days < 3: return 100.0
    if age_days < 7: return 90.0
    if age_days < 14: return 75.0
    if age_days < 30: return 50.0
    if age_days < 90: return 25.0
    return 10.0


def cross_source_score(source_count: int) -> float:
    return {0: 0.0, 1: 20.0, 2: 50.0, 3: 75.0, 4: 90.0}.get(min(source_count, 4), 100.0)


def lifecycle(score: float, first_seen: datetime, acceleration_value: float, thresholds: Dict[str, int], now: datetime) -> str:
    age_days = (now - first_seen).total_seconds() / 86400.0
    if age_days < 1.0:
        return "NEW"
    if acceleration_value < 0.7 and score < thresholds.get("rising", 65):
        return "COOLING"
    if score >= thresholds.get("trending", 80): return "TRENDING"
    if score >= thresholds.get("rising", 65): return "RISING"
    if score >= thresholds.get("emerging", 45): return "EMERGING"
    return "WATCHLIST"


def early_signal_score(momentum: float, acceleration_value: float, cross_source: float, novelty: float,
                       relevance: float, source_quality: float, saturation_penalty: float) -> Dict[str, float]:
    score = (0.25 * momentum + 0.20 * acceleration_value + 0.20 * cross_source + 0.15 * novelty +
             0.10 * relevance + 0.10 * source_quality - saturation_penalty)
    return {"score": round(clamp(score), 2), "momentum": round(momentum, 2), "acceleration": round(acceleration_value, 2),
            "cross_source": round(cross_source, 2), "novelty": round(novelty, 2), "relevance": round(relevance, 2),
            "source_quality": round(source_quality, 2), "saturation_penalty": round(saturation_penalty, 2)}
