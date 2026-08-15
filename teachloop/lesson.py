from __future__ import annotations

import copy
from typing import Any

from .subject_packs import infer_subject, misconception_strategy, topic_config

GROUPS = ("A_基础巩固", "B_重点纠错", "C_拓展提升")


def _fit_timeline(items: list[dict[str, Any]], duration: int) -> list[dict[str, Any]]:
    timeline = copy.deepcopy(items)
    if not timeline:
        return [{"minutes": duration, "stage": "教学活动", "activity": "由教师补充课堂活动。"}]
    original_total = sum(int(item.get("minutes", 0)) for item in timeline) or duration
    allocated = []
    for item in timeline:
        minutes = max(1, round(int(item.get("minutes", 0)) * duration / original_total))
        allocated.append({**item, "minutes": minutes})
    allocated[-1]["minutes"] += duration - sum(item["minutes"] for item in allocated)
    return allocated


def build_lesson_plan(
    profile: dict[str, Any],
    request: dict[str, Any],
    curriculum_context: list[dict[str, Any]] | None = None,
    capability_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    topic = str(request.get("topic", "一元一次方程"))
    subject = str(request.get("subject") or infer_subject(topic))
    config = topic_config(topic, subject)
    weak_points = profile.get("knowledge_points", [])[:3]
    key_errors = [item["main_error"] for item in weak_points if item["main_error"] != "无"]
    strategies = [misconception_strategy(subject, name) for name in key_errors]
    if not strategies:
        strategies = ["使用示例、追问和即时反馈，根据学生当堂表现调整支架。"]
    duration = int(request.get("duration", 45))
    return {
        "title": f"{subject} · {topic}：基于班级学情的差异化教学",
        "subject": subject,
        "grade": request.get("grade", "七年级"),
        "duration_minutes": duration,
        "evidence_summary": {
            "overall_accuracy": profile.get("overall_accuracy", 0),
            "weak_points": [item["name"] for item in weak_points],
            "key_errors": key_errors,
        },
        "objectives": list(config.get("objectives", [])),
        "key_strategies": strategies,
        "classroom_questions": list(config.get("classroom_questions", [])),
        "source_evidence": curriculum_context or [],
        "timeline": _fit_timeline(list(config.get("timeline", [])), duration),
        "capability_context": capability_context or {},
        "teacher_boundary": "本方案为备课辅助结果，开放性评价、实验安排和正式教学结论均须由教师审核。",
    }


def regenerate_lesson_module(
    module: str,
    profile: dict[str, Any],
    request: dict[str, Any],
    current_plan: dict[str, Any],
    variant: int = 1,
) -> Any:
    fresh = build_lesson_plan(
        profile,
        request,
        current_plan.get("source_evidence", []),
        current_plan.get("capability_context", {}),
    )
    if module not in {"objectives", "key_strategies", "timeline"}:
        raise ValueError(f"不支持重新生成模块：{module}")
    value = copy.deepcopy(fresh[module])
    if module == "key_strategies" and variant % 2:
        value.append("在关键节点加入全班即时投票，根据错误选项决定是否补充讲解。")
    if module == "timeline" and variant % 2 and len(value) > 3:
        value[0]["activity"] = "展示匿名高频表现，先让学生独立判断，再说明依据。"
    return value


def generate_practice_sets(
    profile: dict[str, Any], request: dict[str, Any] | None = None
) -> dict[str, Any]:
    topic = str((request or {}).get("topic") or profile.get("topic", "一元一次方程"))
    subject = str((request or {}).get("subject") or profile.get("subject") or infer_subject(topic))
    config = topic_config(topic, subject)
    main_error = "概念未形成"
    if profile.get("error_distribution"):
        main_error = profile["error_distribution"][0]["name"]
    sets = copy.deepcopy(config.get("practice_sets", {}))
    exit_ticket = copy.deepcopy(config.get("exit_ticket", {}))
    exit_ticket["target_knowledge_points"] = [
        item["name"] for item in profile.get("knowledge_points", [])[:2]
    ]
    return {
        "focus_error": main_error,
        **{group: list(sets.get(group, [])) for group in GROUPS},
        "exit_ticket": exit_ticket,
        "validation_mode": "自动校验" if subject in {"数学", "物理"} else "量规＋教师复核",
    }


def regenerate_practice_group(
    group: str, profile: dict[str, Any], variant: int = 1
) -> list[dict[str, str]]:
    if group not in GROUPS:
        raise ValueError(f"不支持重新生成练习组：{group}")
    fresh = generate_practice_sets(profile)[group]
    return list(reversed(fresh)) if variant % 2 else fresh


def review_output(lesson_plan: dict[str, Any], practice_sets: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    total_minutes = sum(int(item["minutes"]) for item in lesson_plan.get("timeline", []))
    expected = int(lesson_plan.get("duration_minutes", 0))
    if total_minutes != expected:
        issues.append(f"课堂环节合计 {total_minutes} 分钟，与设定的 {expected} 分钟不一致")
    if not lesson_plan.get("evidence_summary", {}).get("weak_points"):
        issues.append("教案没有关联班级薄弱知识点")
    for group in GROUPS:
        if not practice_sets.get(group):
            issues.append(f"缺少 {group} 练习")
    capability = lesson_plan.get("capability_context", {})
    if not capability.get("subject_pack"):
        issues.append("未记录本次使用的学科能力包")
    key_errors = lesson_plan.get("evidence_summary", {}).get("key_errors", [])
    subject = lesson_plan.get("subject", "数学")
    strategies = lesson_plan.get("key_strategies", [])
    if key_errors and not any(
        misconception_strategy(subject, error) in strategies for error in key_errors[:2]
    ):
        issues.append("教学策略未对准班级最高频错因")
    weak_points = set(lesson_plan.get("evidence_summary", {}).get("weak_points", [])[:2])
    covered = set(practice_sets.get("exit_ticket", {}).get("target_knowledge_points", []))
    if weak_points and not weak_points.intersection(covered):
        issues.append("随堂测未标记覆盖班级薄弱知识点")

    def complexity(items: list[dict[str, Any]]) -> float:
        if not items:
            return 0.0
        values = []
        for item in items:
            question = str(item.get("question", ""))
            values.append(len(question) + 4 * sum(question.count(symbol) for symbol in "()+-*/"))
        return sum(values) / len(values)

    if complexity(practice_sets.get("C_拓展提升", [])) < 0.7 * complexity(practice_sets.get("A_基础巩固", [])):
        issues.append("C 组练习的题面复杂度低于 A 组，难度梯度可能无效")
    return {
        "passed": not issues,
        "issues": issues,
        "checks": ["课时一致性", "学情依据", "错因—策略对齐", "随堂测覆盖", "三层难度梯度", "学科包追溯", "教师确认边界"],
    }
