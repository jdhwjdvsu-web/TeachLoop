from __future__ import annotations

import re
from fractions import Fraction
from typing import Any


def _number(text: str) -> float | None:
    match = re.search(r"(-?\d+(?:\.\d+)?(?:/\d+(?:\.\d+)?)?)", text)
    if not match:
        return None
    try:
        return float(Fraction(match.group(1)))
    except (ValueError, ZeroDivisionError):
        return None


def _quantities(text: str, units: str) -> list[tuple[float, str]]:
    matches = re.findall(rf"(\d+(?:\.\d+)?)\s*({units})", text)
    return [(float(value), unit) for value, unit in matches]


def _length_si(value: float, unit: str) -> float:
    return value * 1000 if unit == "km" else value


def _time_si(value: float, unit: str) -> float:
    return value * {"s": 1, "min": 60, "h": 3600}[unit]


def _speed_si(value: float, unit: str) -> float:
    return value / 3.6 if unit == "km/h" else value


def validate_item(topic: str, item: dict[str, Any], config: dict[str, Any]) -> bool:
    question = str(item.get("question", "")).strip()
    answer = str(item.get("answer", "")).strip()
    answer_value = _number(answer)
    if not question or not answer or answer_value is None:
        return False
    answer_unit_match = re.search(r"(m/s|km/h|km|m|s|h)\b", answer)
    if not answer_unit_match:
        return False
    answer_unit = answer_unit_match.group(1)

    lengths = _quantities(question, r"km|m")
    times = _quantities(question, r"min|h|s")
    speeds = _quantities(question, r"km/h|m/s")
    if "求路程" in question and speeds and times:
        expected = _speed_si(*speeds[0]) * _time_si(*times[0])
        actual = _length_si(answer_value, answer_unit)
        return abs(actual - expected) <= max(1e-6, abs(expected) * 0.01)
    if ("求速度" in question or "平均速度" in question or "比较速度" in question) and lengths and times:
        length_values = [_length_si(*item) for item in lengths]
        time_values = [_time_si(*item) for item in times]
        if len(length_values) == len(time_values) > 1 and "比较" in question:
            expected_values = [length / time for length, time in zip(length_values, time_values)]
            expected = expected_values[0]
            if any(abs(value - expected) > 1e-6 for value in expected_values[1:]):
                return True  # 非相等比较由教师复核排序表述
        else:
            expected = sum(length_values) / sum(time_values)
        actual = _speed_si(answer_value, answer_unit)
        return abs(actual - expected) <= max(1e-6, abs(expected) * 0.01)
    return True
