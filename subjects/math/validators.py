from __future__ import annotations

from typing import Any

from teachloop.math_validation import validate_inequality_answer, validate_solution


def validate_item(topic: str, item: dict[str, Any], config: dict[str, Any]) -> bool:
    question = str(item.get("question", "")).split("：", 1)[-1].strip().rstrip("。")
    answer = str(item.get("answer", "")).strip()
    if not question or not answer:
        return False
    if "不等式" in topic:
        return validate_inequality_answer(question, answer)
    if "=" not in question:
        return False
    candidate = answer.split("=", 1)[-1].strip()
    return validate_solution(question, candidate)

