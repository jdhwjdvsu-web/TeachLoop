from __future__ import annotations

from collections import defaultdict
from typing import Any

from .diagnosis import diagnose_class, normalize_correct


def _map(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {str(item[key]): item for item in items}


def _student_kp_map(profile: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item["student_id"]), str(item["knowledge_point"])): item
        for item in profile.get("student_knowledge", [])
    }


def compare_learning_outcomes(
    before_profile: dict[str, Any], after_records: list[dict[str, Any]]
) -> dict[str, Any]:
    after_profile = diagnose_class(
        after_records,
        subject=before_profile.get("subject"),
        topic=before_profile.get("topic"),
    )
    before_kp = _map(before_profile.get("knowledge_points", []), "name")
    after_kp = _map(after_profile.get("knowledge_points", []), "name")
    knowledge_changes: list[dict[str, Any]] = []
    for name in sorted(set(before_kp) | set(after_kp)):
        before_value = before_kp.get(name, {}).get("accuracy")
        after_value = after_kp.get(name, {}).get("accuracy")
        change = None if before_value is None or after_value is None else round(float(after_value) - float(before_value), 3)
        knowledge_changes.append({
            "knowledge_point": name,
            "before_accuracy": before_value,
            "after_accuracy": after_value,
            "change": change,
            "status": "未测" if after_value is None else ("仍需干预" if float(after_value) < 0.8 else "基本掌握"),
        })

    before_questions = _map(before_profile.get("question_stats", []), "question_id")
    linked_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in after_records:
        linked = str(row.get("linked_pre_question_id", "")).strip()
        if linked:
            linked_groups[linked].append(row)
    question_anchor_changes = []
    for pre_question_id, rows in sorted(linked_groups.items()):
        before = before_questions.get(pre_question_id)
        after_accuracy = sum(normalize_correct(row.get("correct")) for row in rows) / len(rows)
        question_anchor_changes.append({
            "pre_question_id": pre_question_id,
            "post_question_ids": "、".join(sorted({str(row.get("question_id", "")) for row in rows})),
            "knowledge_point": str(rows[0].get("knowledge_point", "")),
            "before_accuracy": before.get("accuracy") if before else None,
            "after_accuracy": round(after_accuracy, 3),
            "change": None if before is None else round(after_accuracy - float(before["accuracy"]), 3),
            "mapped": before is not None,
        })

    warnings: list[str] = []
    if len(after_records) != int(before_profile.get("record_count", 0)):
        warnings.append("前后测答题记录数量不一致，整体正确率变化仅供参考。")
    if set(before_kp) != set(after_kp):
        warnings.append("前后测知识点集合不一致；缺失知识点标记为“未测”，未按 0% 处理。")
    mapped_count = sum(len(rows) for rows in linked_groups.values())
    if not linked_groups:
        warnings.append("随堂测未提供 linked_pre_question_id，无法进行题目级锚点对照。")
    elif mapped_count != len(after_records):
        warnings.append("部分随堂测记录缺少题目映射，题目级对照只覆盖已映射记录。")

    before_errors = {item["name"]: int(item["count"]) for item in before_profile.get("error_distribution", [])}
    after_errors = {item["name"]: int(item["count"]) for item in after_profile.get("error_distribution", [])}
    error_changes = [{
        "error_type": name, "before_count": before_errors.get(name, 0),
        "after_count": after_errors.get(name, 0),
        "reduction": before_errors.get(name, 0) - after_errors.get(name, 0),
    } for name in sorted(set(before_errors) | set(after_errors))]
    error_changes.sort(key=lambda item: item["reduction"], reverse=True)

    before_students = _map(before_profile.get("student_details", []), "student_id")
    after_students = _map(after_profile.get("student_details", []), "student_id")
    before_student_kp = _student_kp_map(before_profile)
    after_student_kp = _student_kp_map(after_profile)
    student_changes = []
    for student_id in sorted(set(before_students) | set(after_students)):
        kp_names = sorted(
            {kp for sid, kp in before_student_kp if sid == student_id}
            | {kp for sid, kp in after_student_kp if sid == student_id}
        )
        for kp in kp_names:
            before = before_student_kp.get((student_id, kp), {})
            after = after_student_kp.get((student_id, kp), {})
            before_accuracy = before.get("accuracy")
            after_accuracy = after.get("accuracy")
            student_changes.append({
                "student_id": student_id, "knowledge_point": kp,
                "before_accuracy": before_accuracy, "after_accuracy": after_accuracy,
                "change": None if before_accuracy is None or after_accuracy is None else round(float(after_accuracy) - float(before_accuracy), 3),
                "main_error": after.get("main_error", before.get("main_error", "无")),
                "after_group": after_students.get(student_id, {}).get("group", "未测"),
                "continue_intervention": after_students.get(student_id, {}).get("group") in {"A_基础巩固", "B_重点纠错"},
            })

    intervention_students = sorted({
        item["student_id"] for item in after_profile.get("student_details", [])
        if item.get("group") in {"A_基础巩固", "B_重点纠错"}
    })
    suggestions = [
        f"继续强化“{item['knowledge_point']}”，结合当前高频错因安排短讲解、针对练习和即时检查。"
        for item in knowledge_changes if item["after_accuracy"] is not None and float(item["after_accuracy"]) < 0.8
    ] or ["班级主要知识点已基本掌握，可进入综合应用与迁移练习。"]

    return {
        "before_overall_accuracy": before_profile["overall_accuracy"],
        "after_overall_accuracy": after_profile["overall_accuracy"],
        "overall_change": round(after_profile["overall_accuracy"] - before_profile["overall_accuracy"], 3),
        "comparison_reliability": "题目级已映射" if linked_groups and not warnings else "有限对照",
        "comparison_warnings": warnings,
        "knowledge_changes": knowledge_changes,
        "question_anchor_changes": question_anchor_changes,
        "error_changes": error_changes,
        "student_changes": student_changes,
        "continued_intervention_students": intervention_students,
        "next_lesson_suggestions": suggestions,
        "after_profile": after_profile,
        "boundary": "课后分析用于辅助教师调整教学，不作为学生正式评价。",
    }
