from __future__ import annotations

from typing import Any

from .diagnosis import diagnose_class


def _knowledge_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["name"]: item for item in profile.get("knowledge_points", [])}


def _error_map(profile: dict[str, Any]) -> dict[str, int]:
    return {item["name"]: int(item["count"]) for item in profile.get("error_distribution", [])}


def compare_learning_outcomes(
    before_profile: dict[str, Any],
    after_records: list[dict[str, Any]],
) -> dict[str, Any]:
    after_profile = diagnose_class(after_records)
    before_kp = _knowledge_map(before_profile)
    after_kp = _knowledge_map(after_profile)
    knowledge_changes: list[dict[str, Any]] = []

    for name in sorted(set(before_kp) | set(after_kp)):
        before_accuracy = float(before_kp.get(name, {}).get("accuracy", 0))
        after_accuracy = float(after_kp.get(name, {}).get("accuracy", 0))
        knowledge_changes.append(
            {
                "knowledge_point": name,
                "before_accuracy": round(before_accuracy, 3),
                "after_accuracy": round(after_accuracy, 3),
                "change": round(after_accuracy - before_accuracy, 3),
                "status": "仍需干预" if after_accuracy < 0.8 else "基本掌握",
            }
        )

    before_errors = _error_map(before_profile)
    after_errors = _error_map(after_profile)
    error_changes = []
    for name in sorted(set(before_errors) | set(after_errors)):
        before_count = before_errors.get(name, 0)
        after_count = after_errors.get(name, 0)
        error_changes.append(
            {
                "error_type": name,
                "before_count": before_count,
                "after_count": after_count,
                "reduction": before_count - after_count,
            }
        )
    error_changes.sort(key=lambda item: item["reduction"], reverse=True)

    intervention_students = sorted(
        set(after_profile["student_groups"]["A_基础巩固"])
        | set(after_profile["student_groups"]["B_重点纠错"])
    )
    next_lesson_suggestions = []
    for item in knowledge_changes:
        if item["after_accuracy"] < 0.8:
            next_lesson_suggestions.append(
                f"继续强化“{item['knowledge_point']}”，安排短讲解、针对练习和即时检查。"
            )
    if not next_lesson_suggestions:
        next_lesson_suggestions.append("班级主要知识点已基本掌握，可进入综合应用与迁移练习。")

    return {
        "before_overall_accuracy": before_profile["overall_accuracy"],
        "after_overall_accuracy": after_profile["overall_accuracy"],
        "overall_change": round(
            after_profile["overall_accuracy"] - before_profile["overall_accuracy"], 3
        ),
        "knowledge_changes": knowledge_changes,
        "error_changes": error_changes,
        "continued_intervention_students": intervention_students,
        "next_lesson_suggestions": next_lesson_suggestions,
        "after_profile": after_profile,
        "boundary": "课后分析用于辅助教师调整教学，不作为学生正式评价。",
    }

