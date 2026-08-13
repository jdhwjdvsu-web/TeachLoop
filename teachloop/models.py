from __future__ import annotations

from typing import Any, TypedDict


class TeachingState(TypedDict, total=False):
    teacher_request: dict[str, Any]
    records: list[dict[str, Any]]
    curriculum_context: list[dict[str, Any]]
    capability_context: dict[str, Any]
    validation_errors: list[str]
    class_profile: dict[str, Any]
    lesson_plan: dict[str, Any]
    practice_sets: dict[str, Any]
    quality_report: dict[str, Any]
    llm_status: dict[str, Any]
    final_message: str
