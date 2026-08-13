from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from .diagnosis import diagnose_class, validate_records
from .lesson import build_lesson_plan, generate_practice_sets, review_output
from .models import TeachingState
from .skill_registry import orchestration_manifest
from .subject_packs import infer_subject, pack_summary

try:
    from .llm_service import EducationLLMService
except ImportError:  # pragma: no cover - optional runtime guard
    EducationLLMService = object  # type: ignore[assignment,misc]


def validate_input_node(state: TeachingState) -> TeachingState:
    return {"validation_errors": validate_records(state.get("records", []))}


def diagnose_node(state: TeachingState) -> TeachingState:
    profile = diagnose_class(state["records"])
    request = state.get("teacher_request", {})
    profile["topic"] = request.get("topic", "一元一次方程")
    profile["subject"] = request.get("subject") or infer_subject(profile["topic"])
    return {"class_profile": profile}


def load_capabilities_node(state: TeachingState) -> TeachingState:
    request = dict(state.get("teacher_request", {}))
    topic = str(request.get("topic", "一元一次方程"))
    subject = str(request.get("subject") or infer_subject(topic))
    request["subject"] = subject
    return {
        "teacher_request": request,
        "capability_context": {
            "subject_pack": pack_summary(subject, topic),
            "education_skills": orchestration_manifest(subject),
        },
    }


def plan_node(state: TeachingState) -> TeachingState:
    return {
        "lesson_plan": build_lesson_plan(
            state["class_profile"],
            state["teacher_request"],
            state.get("curriculum_context", []),
            state.get("capability_context", {}),
        )
    }


def materials_node(state: TeachingState) -> TeachingState:
    return {
        "practice_sets": generate_practice_sets(
            state["class_profile"], state.get("teacher_request", {})
        )
    }


def review_node(state: TeachingState) -> TeachingState:
    report = review_output(state["lesson_plan"], state["practice_sets"])
    message = "已通过自动检查，等待教师最终审核。" if report["passed"] else "自动检查发现问题，请教师处理。"
    return {"quality_report": report, "final_message": message}


def route_after_validation(state: TeachingState) -> str:
    return "invalid" if state.get("validation_errors") else "valid"


def invalid_node(state: TeachingState) -> TeachingState:
    return {"final_message": "输入数据不完整，工作流已安全停止。"}


def build_workflow(llm_service: EducationLLMService | None = None):
    graph = StateGraph(TeachingState)
    graph.add_node("validate_input", validate_input_node)
    graph.add_node("invalid_input", invalid_node)
    graph.add_node("load_capabilities", load_capabilities_node)
    graph.add_node("diagnose_class", diagnose_node)
    graph.add_node("plan_lesson", plan_node)
    graph.add_node("generate_materials", materials_node)
    def llm_enrich_node(state: TeachingState) -> TeachingState:
        if llm_service is None:
            return {
                "llm_status": {
                    "used": False,
                    "model": "",
                    "warnings": [],
                    "message": "未启用大模型，使用确定性规则版本。",
                }
            }
        profile, plan, materials = llm_service.enhance(
            state["records"],
            state["class_profile"],
            state["lesson_plan"],
            state["practice_sets"],
            state["teacher_request"],
        )
        status = materials.pop("llm_status", {})
        return {
            "class_profile": profile,
            "lesson_plan": plan,
            "practice_sets": materials,
            "llm_status": status,
        }

    graph.add_node("llm_enrichment", llm_enrich_node)
    graph.add_node("review_quality", review_node)
    graph.add_edge(START, "validate_input")
    graph.add_conditional_edges(
        "validate_input",
        route_after_validation,
        {"invalid": "invalid_input", "valid": "load_capabilities"},
    )
    graph.add_edge("invalid_input", END)
    graph.add_edge("load_capabilities", "diagnose_class")
    graph.add_edge("diagnose_class", "plan_lesson")
    graph.add_edge("plan_lesson", "generate_materials")
    graph.add_edge("generate_materials", "llm_enrichment")
    graph.add_edge("llm_enrichment", "review_quality")
    graph.add_edge("review_quality", END)
    return graph.compile()


def run_teaching_workflow(
    records: list[dict],
    teacher_request: dict,
    curriculum_context: list[dict] | None = None,
    llm_service: EducationLLMService | None = None,
) -> TeachingState:
    app = build_workflow(llm_service=llm_service)
    return app.invoke(
        {
            "records": records,
            "teacher_request": teacher_request,
            "curriculum_context": curriculum_context or [],
        }
    )
