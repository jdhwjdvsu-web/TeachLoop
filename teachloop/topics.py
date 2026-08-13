from __future__ import annotations

from typing import Any

from .subject_packs import infer_subject, list_subject_packs, topic_config


TOPIC_EQUATION = "一元一次方程"
TOPIC_INEQUALITY = "一元一次不等式"
SUPPORTED_TOPICS = [
    topic
    for pack in list_subject_packs()
    for topic in pack.get("topics", {})
]


def topic_pack(topic: str, subject: str | None = None) -> dict[str, Any]:
    return topic_config(topic, subject or infer_subject(topic))

