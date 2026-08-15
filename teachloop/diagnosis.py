from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any

import pandas as pd

from .subject_packs import infer_subject, load_subject_pack

REQUIRED_COLUMNS = {
    "student_id", "question_id", "knowledge_point", "student_answer",
    "student_work", "correct", "response_time_sec",
}
TRUE_VALUES = {"true", "1", "yes", "y", "正确"}
FALSE_VALUES = {"false", "0", "no", "n", "错误"}


def normalize_correct(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in TRUE_VALUES


def _valid_correct(value: Any) -> bool:
    return isinstance(value, bool) or str(value).strip().lower() in TRUE_VALUES | FALSE_VALUES


def _safe_time(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and 0 < number <= 7200 else None


def validate_records(records: list[dict[str, Any]]) -> list[str]:
    if not records:
        return ["没有可分析的答题记录"]
    errors: list[str] = []
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(records, start=2):
        missing = REQUIRED_COLUMNS - set(row)
        for name in sorted(missing):
            errors.append(f"第 {index} 行：缺少字段 {name}")
        if missing:
            continue
        student_id = str(row.get("student_id", "")).strip()
        question_id = str(row.get("question_id", "")).strip()
        if not student_id:
            errors.append(f"第 {index} 行：student_id 不能为空")
        if not question_id:
            errors.append(f"第 {index} 行：question_id 不能为空")
        if not str(row.get("knowledge_point", "")).strip():
            errors.append(f"第 {index} 行：knowledge_point 不能为空")
        if not _valid_correct(row.get("correct")):
            errors.append(f"第 {index} 行：correct 值非法")
        if _safe_time(row.get("response_time_sec")) is None:
            errors.append(f"第 {index} 行：response_time_sec 必须是 0 到 7200 秒之间的数字")
        key = (student_id, question_id)
        if student_id and question_id and key in seen:
            errors.append(f"第 {index} 行：学生 {student_id} 的题目 {question_id} 重复")
        seen.add(key)
    return errors


def infer_error_type(
    row: dict[str, Any], subject: str | None = None, topic: str | None = None
) -> str:
    if normalize_correct(row.get("correct")):
        return "掌握"
    declared = str(row.get("declared_error", "")).strip()
    if declared:
        return declared
    resolved_subject = subject or infer_subject(str(topic or "一元一次方程"))
    pack = load_subject_pack(resolved_subject)
    searchable = "".join(
        str(row.get(key, "")) for key in ("student_answer", "student_work", "knowledge_point")
    ).replace(" ", "").lower()
    for name, config in pack.get("misconceptions", {}).items():
        if not isinstance(config, dict):
            continue
        patterns = [str(item).replace(" ", "").lower() for item in config.get("patterns", [])]
        if any(pattern and pattern in searchable for pattern in patterns):
            return str(name)
        if any(re.search(str(pattern), searchable, re.IGNORECASE) for pattern in config.get("regex_patterns", [])):
            return str(name)
    answer = str(row.get("student_answer", "")).strip().lower()
    if answer in {"", "不会", "?", "不知道", "i don't know", "idk"}:
        return str(pack.get("default_blank_error", "概念未形成"))
    return str(pack.get("default_error", "需要教师复核"))


def diagnose_class(
    records: list[dict[str, Any]], subject: str | None = None, topic: str | None = None
) -> dict[str, Any]:
    resolved_subject = subject or infer_subject(str(topic or "一元一次方程"))
    frame = pd.DataFrame(records).copy()
    frame["correct_bool"] = frame["correct"].map(normalize_correct)
    frame["response_time"] = pd.to_numeric(frame["response_time_sec"], errors="coerce")
    frame["error_type"] = [infer_error_type(row, resolved_subject, topic) for row in records]

    kp_medians = frame.groupby("knowledge_point")["response_time"].median().to_dict()
    frame["time_ratio"] = frame.apply(
        lambda row: float(row["response_time"]) / max(float(kp_medians.get(row["knowledge_point"], 1)), 1),
        axis=1,
    )
    frame["slow_correct"] = frame["correct_bool"] & (frame["time_ratio"] >= 1.35)
    frame["fast_wrong"] = (~frame["correct_bool"]) & (frame["time_ratio"] <= 0.65)

    knowledge_points: list[dict[str, Any]] = []
    for name, group in frame.groupby("knowledge_point", sort=False):
        wrong = group.loc[~group["correct_bool"]]
        counts = Counter(wrong["error_type"].tolist())
        knowledge_points.append({
            "name": str(name), "attempts": int(len(group)),
            "accuracy": round(float(group["correct_bool"].mean()), 3),
            "average_response_time_sec": round(float(group["response_time"].mean()), 1),
            "slow_correct_count": int(group["slow_correct"].sum()),
            "fast_wrong_count": int(group["fast_wrong"].sum()),
            "affected_students": int(wrong["student_id"].nunique()),
            "main_error": counts.most_common(1)[0][0] if counts else "无",
        })
    knowledge_points.sort(key=lambda item: item["accuracy"])
    wrong_frame = frame.loc[~frame["correct_bool"]]
    errors = [{"name": name, "count": int(count)} for name, count in Counter(wrong_frame["error_type"]).most_common()]

    groups = {"A_基础巩固": [], "B_重点纠错": [], "C_拓展提升": []}
    student_details: list[dict[str, Any]] = []
    student_knowledge: list[dict[str, Any]] = []
    for student_id, group in frame.groupby("student_id", sort=True):
        accuracy = float(group["correct_bool"].mean())
        slow_count = int(group["slow_correct"].sum())
        fast_wrong_count = int(group["fast_wrong"].sum())
        counts = Counter(group.loc[~group["correct_bool"], "error_type"].tolist())
        main_error = counts.most_common(1)[0][0] if counts else "无"
        if accuracy < 0.5 or fast_wrong_count >= max(1, len(group) // 2):
            assigned = "A_基础巩固"
        elif accuracy < 0.8 or slow_count > 0:
            assigned = "B_重点纠错"
        else:
            assigned = "C_拓展提升"
        groups[assigned].append(str(student_id))
        student_details.append({
            "student_id": str(student_id), "group": assigned,
            "accuracy": round(accuracy, 3),
            "average_response_time_sec": round(float(group["response_time"].mean()), 1),
            "main_error": main_error, "slow_correct_count": slow_count,
            "fast_wrong_count": fast_wrong_count,
        })
        for knowledge_point, kp_group in group.groupby("knowledge_point", sort=True):
            kp_counts = Counter(kp_group.loc[~kp_group["correct_bool"], "error_type"].tolist())
            student_knowledge.append({
                "student_id": str(student_id), "knowledge_point": str(knowledge_point),
                "attempts": int(len(kp_group)),
                "accuracy": round(float(kp_group["correct_bool"].mean()), 3),
                "main_error": kp_counts.most_common(1)[0][0] if kp_counts else "无",
            })

    question_stats = [{
        "question_id": str(question_id),
        "knowledge_point": str(group["knowledge_point"].mode().iloc[0]),
        "attempts": int(len(group)), "accuracy": round(float(group["correct_bool"].mean()), 3),
    } for question_id, group in frame.groupby("question_id", sort=True)]
    anomalies = [{
        "student_id": str(row.student_id), "question_id": str(row.question_id),
        "knowledge_point": str(row.knowledge_point),
        "response_time_sec": round(float(row.response_time), 1),
        "signal": "正确但耗时偏长" if row.slow_correct else "错误且作答过快",
    } for row in frame.loc[frame["slow_correct"] | frame["fast_wrong"]].itertuples()]

    return {
        "subject": resolved_subject, "student_count": int(frame["student_id"].nunique()),
        "record_count": int(len(frame)), "overall_accuracy": round(float(frame["correct_bool"].mean()), 3),
        "knowledge_points": knowledge_points, "question_stats": question_stats,
        "error_distribution": errors, "student_groups": groups,
        "student_details": student_details, "student_knowledge": student_knowledge,
        "time_analysis": {
            "overall_average_response_time_sec": round(float(frame["response_time"].mean()), 1),
            "slow_correct_count": int(frame["slow_correct"].sum()),
            "fast_wrong_count": int(frame["fast_wrong"].sum()), "anomalies": anomalies,
        },
        "diagnosis_note": "基于匿名答题记录、学科包错因规则、正确率与作答时间共同生成；教师需复核。",
    }
