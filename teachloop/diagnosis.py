from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

import pandas as pd


REQUIRED_COLUMNS = {
    "student_id",
    "question_id",
    "knowledge_point",
    "student_answer",
    "student_work",
    "correct",
    "response_time_sec",
}


def normalize_correct(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes", "y", "正确"}


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["没有可分析的答题记录"]
    missing = REQUIRED_COLUMNS - set(records[0])
    errors = [f"缺少字段：{name}" for name in sorted(missing)]
    if any(not str(row.get("student_id", "")).strip() for row in records):
        errors.append("存在空的 student_id")
    return errors


def infer_error_type(row: dict[str, Any]) -> str:
    if normalize_correct(row.get("correct")):
        return "掌握"

    declared = str(row.get("declared_error", "")).strip()
    if declared:
        return declared

    work = str(row.get("student_work", "")).replace(" ", "")
    answer = str(row.get("student_answer", "")).replace(" ", "")

    if any(pattern in work for pattern in ("除以负数方向不变", "乘负数方向不变", "x>-3", "x>=-3")):
        return "乘除负数未改变不等号方向"
    if any(pattern in work for pattern in ("严格不等式画实心", "非严格不等式画空心", "端点包含错误")):
        return "数轴端点开闭错误"
    if any(pattern in work for pattern in ("解集方向画反", "数轴方向向右", "数轴方向向左")):
        return "数轴方向错误"
    if any(pattern in work for pattern in ("<==", ">==", "边界取等错误")):
        return "解集边界错误"

    move_sign_patterns = ("=7+3", "=9+5", "=4+2", "移项符号不变")
    bracket_patterns = ("-(x+2)=-x+2", "-(x-3)=-x-3", "去括号同号")
    denominator_patterns = ("x+1=8", "2*x+1=12", "只乘一项", "漏乘")
    balance_patterns = ("x+1=5", "只除左边", "两边操作不同")

    if any(pattern in work for pattern in move_sign_patterns):
        return "移项忘记变号"
    if any(pattern in work for pattern in bracket_patterns):
        return "去括号符号错误"
    if any(pattern in work for pattern in denominator_patterns):
        return "去分母漏乘"
    if any(pattern in work for pattern in balance_patterns):
        return "等式两边操作不一致"
    if answer in {"", "不会", "?"}:
        return "概念未形成"
    return "计算错误"


def diagnose_class(records: list[dict[str, Any]]) -> dict[str, Any]:
    frame = pd.DataFrame(records).copy()
    frame["correct_bool"] = frame["correct"].map(normalize_correct)
    frame["error_type"] = [infer_error_type(row) for row in records]

    students = int(frame["student_id"].nunique())
    overall_accuracy = float(frame["correct_bool"].mean())

    knowledge_points: list[dict[str, Any]] = []
    for name, group in frame.groupby("knowledge_point", sort=False):
        accuracy = float(group["correct_bool"].mean())
        wrong = group.loc[~group["correct_bool"]]
        error_counts = Counter(wrong["error_type"].tolist())
        knowledge_points.append(
            {
                "name": str(name),
                "attempts": int(len(group)),
                "accuracy": round(accuracy, 3),
                "affected_students": int(wrong["student_id"].nunique()),
                "main_error": error_counts.most_common(1)[0][0] if error_counts else "无",
            }
        )

    knowledge_points.sort(key=lambda item: item["accuracy"])
    wrong_frame = frame.loc[~frame["correct_bool"]]
    errors = [
        {"name": name, "count": int(count)}
        for name, count in Counter(wrong_frame["error_type"]).most_common()
    ]

    per_student: dict[str, list[bool]] = defaultdict(list)
    for row in frame.itertuples():
        per_student[str(row.student_id)].append(bool(row.correct_bool))

    groups = {"A_基础巩固": [], "B_重点纠错": [], "C_拓展提升": []}
    for student_id, results in per_student.items():
        accuracy = sum(results) / len(results)
        if accuracy < 0.5:
            groups["A_基础巩固"].append(student_id)
        elif accuracy < 0.8:
            groups["B_重点纠错"].append(student_id)
        else:
            groups["C_拓展提升"].append(student_id)

    return {
        "student_count": students,
        "record_count": int(len(frame)),
        "overall_accuracy": round(overall_accuracy, 3),
        "knowledge_points": knowledge_points,
        "error_distribution": errors,
        "student_groups": groups,
        "diagnosis_note": "基于匿名答题记录、学生关键步骤和确定性规则生成；教师需复核。",
    }
