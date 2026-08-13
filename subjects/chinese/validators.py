from __future__ import annotations

from typing import Any


def validate_item(topic: str, item: dict[str, Any], config: dict[str, Any]) -> bool:
    question = str(item.get("question", "")).strip()
    answer = str(item.get("answer", "")).strip()
    purpose = str(item.get("purpose", "")).strip()
    return bool(question and answer and purpose and len(answer) >= 8)

