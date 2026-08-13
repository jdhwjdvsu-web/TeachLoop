from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

import httpx

from .subject_packs import infer_subject, load_subject_pack, validate_subject_item


@dataclass(frozen=True)
class LLMConfig:
    base_url: str
    model: str
    api_key: str = ""
    temperature: float = 0.2
    timeout_seconds: float = 60.0


class OpenAICompatibleClient:
    """Minimal server-side client for OpenAI-compatible Chat Completions APIs."""

    def __init__(self, config: LLMConfig, transport: httpx.BaseTransport | None = None):
        self.config = config
        self._client = httpx.Client(timeout=config.timeout_seconds, transport=transport)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "X-Client-Request-Id": str(uuid.uuid4()),
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        return headers

    def _url(self, endpoint: str) -> str:
        return f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    def test_connection(self) -> dict[str, Any]:
        try:
            response = self._client.get(self._url("models"), headers=self._headers())
            response.raise_for_status()
            data = response.json()
            model_ids = [item.get("id", "") for item in data.get("data", [])]
            return {"ok": True, "models": model_ids, "message": "连接成功"}
        except Exception as error:
            return {"ok": False, "models": [], "message": str(error)}

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        response = self._client.post(
            self._url("chat/completions"),
            headers=self._headers(),
            json={
                "model": self.config.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": self.config.temperature,
            },
        )
        response.raise_for_status()
        payload = response.json()
        content = payload["choices"][0]["message"]["content"]
        if isinstance(content, list):
            content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
        return parse_json_content(str(content))


def parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("模型没有返回可解析的 JSON")
        value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("模型 JSON 顶层必须是对象")
    return value


def _equation_from_question(question: str) -> str:
    text = question.split("：", maxsplit=1)[-1].strip()
    return text.rstrip("。")


def _candidate_value(answer: str) -> str:
    return answer.split("=", maxsplit=1)[-1].strip()


def validate_generated_item(topic: str, item: dict[str, Any]) -> bool:
    return validate_subject_item(infer_subject(topic), topic, item)


class EducationLLMService:
    def __init__(self, client: OpenAICompatibleClient):
        self.client = client

    def enhance(
        self,
        records: list[dict[str, Any]],
        profile: dict[str, Any],
        lesson_plan: dict[str, Any],
        practice_sets: dict[str, Any],
        request: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        wrong_samples = [
            {
                "knowledge_point": row.get("knowledge_point"),
                "student_answer": row.get("student_answer"),
                "student_work": row.get("student_work"),
            }
            for row in records
            if str(row.get("correct", "")).lower() not in {"true", "1", "yes", "正确"}
        ][:12]
        safe_profile = {
            "overall_accuracy": profile.get("overall_accuracy"),
            "knowledge_points": profile.get("knowledge_points"),
            "error_distribution": profile.get("error_distribution"),
            "student_groups": {key: len(value) for key, value in profile.get("student_groups", {}).items()},
        }
        evidence = [
            {"source": item.get("source"), "page": item.get("page"), "text": item.get("text", "")[:500]}
            for item in lesson_plan.get("source_evidence", [])
        ]
        prompt = {
            "task": "根据匿名学情、教材依据和学科能力包优化教案，并生成可复核的分层练习。",
            "subject": request.get("subject") or infer_subject(str(request.get("topic", ""))),
            "topic": request.get("topic"),
            "grade": request.get("grade"),
            "duration_minutes": request.get("duration"),
            "class_profile": safe_profile,
            "anonymous_wrong_samples": wrong_samples,
            "evidence": evidence,
            "capability_context": lesson_plan.get("capability_context", {}),
            "required_json": {
                "complex_step_findings": ["string"],
                "objectives": ["string"],
                "key_strategies": ["string"],
                "classroom_questions": ["string"],
                "timeline": [{"minutes": 5, "stage": "string", "activity": "string"}],
                "practice_sets": {
                    "A_基础巩固": [{"question": "只写可解析的代数式", "answer": "string", "purpose": "string"}],
                    "B_重点纠错": [],
                    "C_拓展提升": [],
                },
            },
            "constraints": [
                "只返回 JSON，不要 Markdown。",
                "不得出现学生姓名或正式评价结论。",
                "课堂时间总和必须等于设定课时。",
                "练习题必须符合当前学科包的题型与评价规则。",
                "数学和物理计算结果必须通过确定性验证；语文开放题必须给出量规而非唯一答案。",
            ],
        }
        system = (
            "你是辅助教师备课的教育设计 Agent。你必须依据学情提供可追溯建议，"
            "不替代教师判断，并严格输出请求中的 JSON 结构。"
        )
        try:
            generated = self.client.complete_json(system, json.dumps(prompt, ensure_ascii=False))
            plan = dict(lesson_plan)
            materials = dict(practice_sets)
            warnings: list[str] = []

            for field in ("objectives", "key_strategies", "classroom_questions"):
                value = generated.get(field)
                if isinstance(value, list) and value and all(isinstance(item, str) for item in value):
                    plan[field] = value

            timeline = generated.get("timeline")
            if isinstance(timeline, list) and timeline:
                try:
                    total = sum(int(item["minutes"]) for item in timeline)
                    if total == int(request.get("duration", 45)):
                        plan["timeline"] = timeline
                    else:
                        warnings.append("模型课堂时间不匹配，已保留规则教案时间线。")
                except (KeyError, TypeError, ValueError):
                    warnings.append("模型课堂时间线格式无效，已保留规则版本。")

            generated_sets = generated.get("practice_sets", {})
            for group in ("A_基础巩固", "B_重点纠错", "C_拓展提升"):
                candidates = generated_sets.get(group, []) if isinstance(generated_sets, dict) else []
                valid = [item for item in candidates if isinstance(item, dict) and validate_generated_item(request.get("topic", ""), item)]
                if len(valid) >= 2:
                    materials[group] = valid
                elif candidates:
                    warnings.append(f"{group} 的模型题目未通过 SymPy 门禁，已保留规则题目。")

            findings = generated.get("complex_step_findings", [])
            enhanced_profile = dict(profile)
            if isinstance(findings, list):
                enhanced_profile["llm_findings"] = [str(item) for item in findings]

            status = {
                "used": True,
                "model": self.client.config.model,
                "warnings": warnings,
                "message": f"已使用大模型增强；练习已通过{load_subject_pack(request.get('subject') or infer_subject(str(request.get('topic', '')))).get('validator')}门禁。",
            }
            return enhanced_profile, plan, {**materials, "llm_status": status}
        except Exception as error:
            status = {
                "used": False,
                "model": self.client.config.model,
                "warnings": [str(error)],
                "message": "大模型调用失败，已自动回退到确定性规则版本。",
            }
            return profile, lesson_plan, {**practice_sets, "llm_status": status}

    def rewrite_module(
        self,
        module: str,
        content: Any,
        teacher_note: str,
        context: dict[str, Any],
    ) -> Any:
        payload = {
            "module": module,
            "current_content": content,
            "teacher_request": teacher_note,
            "context": context,
            "instruction": "只返回 JSON：{\"content\": 重写后的同类型内容}。",
        }
        result = self.client.complete_json(
            "你是教师协作备课 Agent。保留教师明确要求，不修改其他模块，只返回 JSON。",
            json.dumps(payload, ensure_ascii=False),
        )
        if "content" not in result:
            raise ValueError("模型局部重写缺少 content 字段")
        return result["content"]
