from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from teachloop.feedback import compare_learning_outcomes
from teachloop.knowledge_base import LocalVectorKnowledgeBase
from teachloop.lesson import regenerate_lesson_module, regenerate_practice_group, review_output
from teachloop.llm_service import (
    EducationLLMService,
    LLMConfig,
    OpenAICompatibleClient,
    validate_generated_item,
)
from teachloop.skill_registry import selected_skills, skills_for_stage
from teachloop.storage import TeachLoopStore
from teachloop.subject_packs import (
    demo_path,
    grades_for_subject,
    list_subject_packs,
    load_subject_pack,
    subject_names,
    topics_for_subject,
)
from teachloop.ui import (
    inject_apple_glass_theme,
    render_brand,
    render_hero,
    render_page_header,
    render_section_label,
    render_status,
    workflow_stage,
)
from teachloop.word_export import (
    build_delivery_zip,
    build_feedback_students_csv,
    build_group_roster_csv,
)
from teachloop.workflow import run_teaching_workflow

ROOT = Path(__file__).parent
DEMO_PATH = ROOT / "data" / "demo_class.csv"
POST_DEMO_PATH = ROOT / "data" / "demo_post_class.csv"
INEQUALITY_DEMO_PATH = ROOT / "data" / "demo_inequality.csv"
INEQUALITY_POST_DEMO_PATH = ROOT / "data" / "demo_inequality_post.csv"
DB_PATH = ROOT / "data" / "teachloop.db"
KB_PATH = ROOT / "data" / "kb_index.json"
MAX_UPLOAD_MB = int(os.getenv("TEACHLOOP_MAX_UPLOAD_MB", "20"))


st.set_page_config(
    page_title="TeachLoop · 教师智能工作台",
    page_icon="📘",
    layout="wide",
    initial_sidebar_state="expanded",
)
inject_apple_glass_theme()


@st.cache_resource
def get_store() -> TeachLoopStore:
    return TeachLoopStore(DB_PATH)


@st.cache_resource
def get_knowledge_base() -> LocalVectorKnowledgeBase:
    knowledge_base = LocalVectorKnowledgeBase(KB_PATH)
    default_text = (ROOT / "knowledge_base" / "curriculum.md").read_text(encoding="utf-8")
    knowledge_base.add_text(default_text, source="内置：一元一次方程教学知识库")
    inequality_text = (ROOT / "knowledge_base" / "inequality.md").read_text(encoding="utf-8")
    knowledge_base.add_text(inequality_text, source="内置：一元一次不等式教学知识库")
    for pack in list_subject_packs():
        curriculum_path = Path(pack["directory"]) / "curriculum" / "index.md"
        if curriculum_path.exists():
            knowledge_base.add_text(
                curriculum_path.read_text(encoding="utf-8"),
                source=f"内置：{pack['name']}学科包索引",
            )
    return knowledge_base


@st.cache_resource
def get_cached_llm_service(
    base_url: str, model: str, api_key: str, temperature: float
) -> EducationLLMService:
    config = LLMConfig(
        base_url=base_url,
        model=model,
        api_key=api_key,
        temperature=temperature,
    )
    return EducationLLMService(OpenAICompatibleClient(config))


def current_llm_service() -> EducationLLMService | None:
    if not st.session_state.get("llm_enabled", False):
        return None
    if not st.session_state.get("llm_data_consent", False):
        return None
    model = st.session_state.get("llm_model", "").strip()
    base_url = st.session_state.get("llm_base_url", "").strip()
    if not model or not base_url:
        return None
    return get_cached_llm_service(
        base_url,
        model,
        st.session_state.get("llm_api_key", ""),
        float(st.session_state.get("llm_temperature", 0.2)),
    )


def json_download(label: str, payload: dict, filename: str, key: str) -> None:
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
    st.download_button(label, content, filename, "application/json", key=key)


def csv_template_bytes(include_link: bool = False) -> bytes:
    columns = [
        "student_id", "question_id", "knowledge_point", "student_answer",
        "student_work", "correct", "response_time_sec",
    ]
    if include_link:
        columns.append("linked_pre_question_id")
    return ("\ufeff" + ",".join(columns) + "\n").encode("utf-8")


def clear_draft_on_task_change() -> None:
    for key in (
        "workflow_result",
        "working_version",
        "teacher_decision",
        "module_locks",
        "feedback_result",
    ):
        st.session_state.pop(key, None)


def show_source_evidence(items: list[dict]) -> None:
    if not items:
        st.caption("当前教案未检索到教材依据。可先到“教材知识库”上传资料。")
        return
    for index, item in enumerate(items, start=1):
        location = f"第 {item['page']} 页" if item.get("page") else f"片段 {item.get('section', index)}"
        with st.expander(f"[{index}] {item['source']} · {location} · 相似度 {item['score']:.3f}"):
            st.write(item["text"])


def render_result_overview(result: dict) -> None:
    profile = result["class_profile"]
    lesson = result["lesson_plan"]
    materials = result["practice_sets"]
    review = result["quality_report"]
    llm_status = result.get("llm_status", {})
    capability = result.get("capability_context", {})

    subject_pack = capability.get("subject_pack", {})
    if subject_pack:
        st.caption(
            f"本次加载：{subject_pack.get('name')}学科包 v{subject_pack.get('version')}"
            f" · {subject_pack.get('validator')} · {subject_pack.get('status')}"
        )

    if llm_status.get("used"):
        st.success(f"模型增强已启用：{llm_status.get('model', '')}")
    elif llm_status.get("message"):
        st.caption(llm_status["message"])
    for warning in llm_status.get("warnings", []):
        st.warning(warning)

    tab1, tab2, tab3, tab4 = st.tabs(["班级学情", "差异化教案", "分层练习", "质量审查"])
    with tab1:
        c1, c2, c3 = st.columns(3)
        c1.metric("学生数", profile["student_count"])
        c2.metric("答题记录", profile["record_count"])
        c3.metric("整体正确率", f"{profile['overall_accuracy']:.1%}")
        knowledge_frame = pd.DataFrame(profile["knowledge_points"])
        knowledge_frame["accuracy"] = knowledge_frame["accuracy"].map(lambda value: f"{value:.1%}")
        st.subheader("知识点掌握情况")
        st.dataframe(knowledge_frame, width="stretch")
        st.subheader("主要错因")
        error_frame = pd.DataFrame(profile["error_distribution"])
        if not error_frame.empty:
            st.bar_chart(error_frame.set_index("name"))
        st.subheader("学生分组花名册")
        st.dataframe(pd.DataFrame(profile.get("student_details", [])), width="stretch", hide_index=True)
        st.download_button(
            "下载 A/B/C 分组名单 CSV",
            build_group_roster_csv(result),
            "TeachLoop_分组花名册.csv",
            "text/csv",
            key="download_roster_overview",
        )
        time_analysis = profile.get("time_analysis", {})
        st.caption(
            f"班级平均用时 {time_analysis.get('overall_average_response_time_sec', 0)} 秒 · "
            f"正确但偏慢 {time_analysis.get('slow_correct_count', 0)} 条 · "
            f"错误且过快 {time_analysis.get('fast_wrong_count', 0)} 条"
        )
        if profile.get("llm_findings"):
            st.subheader("模型对复杂步骤的补充发现")
            for finding in profile["llm_findings"]:
                st.markdown(f"- {finding}")

    with tab2:
        st.subheader(lesson["title"])
        st.markdown("**教学目标**")
        for item in lesson["objectives"]:
            st.markdown(f"- {item}")
        st.markdown("**教学策略**")
        for item in lesson["key_strategies"]:
            st.markdown(f"- {item}")
        if lesson.get("classroom_questions"):
            st.markdown("**课堂提问**")
            for item in lesson["classroom_questions"]:
                st.markdown(f"- {item}")
        st.dataframe(pd.DataFrame(lesson["timeline"]), width="stretch")
        st.markdown("**教材与教学资料依据**")
        show_source_evidence(lesson.get("source_evidence", []))
        st.warning(lesson["teacher_boundary"])

    with tab3:
        st.caption(f"本次重点错因：{materials['focus_error']}")
        for group in ("A_基础巩固", "B_重点纠错", "C_拓展提升"):
            st.subheader(group)
            st.dataframe(pd.DataFrame(materials[group]), width="stretch")
        st.subheader("随堂测")
        st.json(materials["exit_ticket"], expanded=True)

    with tab4:
        if review["passed"]:
            st.success(result["final_message"])
        else:
            st.error(result["final_message"])
        st.json(review, expanded=True)
        st.info("AI 输出必须由教师审核确认后才能用于课堂或正式评价。")


def render_prepare_page(
    knowledge_base: LocalVectorKnowledgeBase,
    llm_service: EducationLLMService | None,
) -> None:
    render_page_header(
        "STEP 01 · START",
        "开始一次智能备课",
        "选择班级与课题，系统会读取匿名课前测数据，并结合教材依据生成可编辑教案。",
    )

    with st.container(border=True):
        render_section_label("01 · 设置教学任务")
        c1, c2, c3, c4 = st.columns(4)
        subject = c1.selectbox(
            "学科",
            subject_names(),
            key="prepare_subject",
            on_change=clear_draft_on_task_change,
        )
        grade = c2.selectbox(
            "年级",
            grades_for_subject(subject),
            key="prepare_grade",
            on_change=clear_draft_on_task_change,
        )
        topics = topics_for_subject(subject, grade)
        topic = c3.selectbox(
            "课题",
            topics,
            key="prepare_topic",
            on_change=clear_draft_on_task_change,
        )
        duration = c4.number_input("课时（分钟）", 20, 90, 45, 5, key="prepare_duration")
        pack = load_subject_pack(subject)
        st.caption(
            f"已加载 {subject}学科包 v{pack.get('version')} · "
            f"验证方式：{pack.get('validator')} · 状态：{pack.get('status')}"
        )
        with st.expander("查看本次 Agent 能力编排", expanded=False):
            for stage, label in (
                ("diagnosis", "学情诊断"),
                ("planning", "教学设计"),
                ("assessment", "形成性评价"),
                ("feedback", "课后反思"),
            ):
                names = [skill["name"] for skill in skills_for_stage(stage, subject)]
                st.markdown(f"**{label}：** {'、'.join(names)}")

    with st.container(border=True):
        render_section_label("02 · 导入课前学情")
        st.download_button(
            "下载课前测 CSV 模板",
            csv_template_bytes(),
            "TeachLoop_课前测模板.csv",
            "text/csv",
            key="download_pre_template",
        )
        uploaded = st.file_uploader(
            "拖入匿名课前测 CSV；也可以先用内置演示数据体验",
            type=["csv"],
            key="pre_csv",
        )
        default_path = demo_path(subject)
        frame = pd.read_csv(uploaded) if uploaded is not None else pd.read_csv(default_path)
        if uploaded is None:
            st.info("当前使用内置匿名演示数据，不会影响你的历史版本。")
        with st.expander("预览课前数据", expanded=False):
            st.dataframe(frame, width="stretch")

    if st.button(
        "分析学情并生成教案  →",
        type="primary",
        key="generate_plan",
        use_container_width=True,
    ):
        query = f"{subject} {grade} {topic} 教学目标 典型错因 教学策略 分层练习"
        evidence = knowledge_base.search(query, top_k=4)
        with st.spinner("正在执行学情诊断、教材检索与备课工作流……"):
            result = run_teaching_workflow(
                records=frame.to_dict(orient="records"),
                teacher_request={
                    "subject": subject,
                    "grade": grade,
                    "topic": topic,
                    "duration": int(duration),
                },
                curriculum_context=evidence,
                llm_service=llm_service,
            )
        st.session_state["workflow_result"] = result
        st.session_state["working_version"] = copy.deepcopy(result)
        st.session_state["teacher_decision"] = "待确认"
        st.session_state["module_locks"] = {
            "objectives": False,
            "key_strategies": False,
            "timeline": False,
            "A_基础巩固": False,
            "B_重点纠错": False,
            "C_拓展提升": False,
        }
        st.session_state["editor_revision"] = st.session_state.get("editor_revision", 0) + 1

    result = st.session_state.get("workflow_result")
    if result:
        if result.get("validation_errors"):
            st.error("；".join(result["validation_errors"]))
        else:
            render_page_header(
                "RESULT · AI DRAFT",
                "备课初稿已生成",
                "先查看学情依据和自动审查结果，再进入教师确认页面完成修改与定稿。",
            )
            render_result_overview(result)
            json_download("下载 AI 初稿", result, "teachloop_ai_draft.json", "draft_download")


def render_teacher_review_page(
    store: TeachLoopStore,
    llm_service: EducationLLMService | None,
) -> None:
    render_page_header(
        "STEP 03 · REVIEW",
        "由教师完成最后判断",
        "修改、锁定或局部重写任意模块。只有教师明确接受后，系统才会生成最终 Word 交付包。",
    )
    if "working_version" not in st.session_state:
        st.info("还没有可审核的教案。请先到“开始备课”生成一份 AI 初稿。")
        return

    working = st.session_state["working_version"]
    plan = working["lesson_plan"]
    materials = working["practice_sets"]
    profile = working["class_profile"]
    request = working["teacher_request"]
    locks = st.session_state.setdefault("module_locks", {})
    revision = st.session_state.get("editor_revision", 0)

    design_tab, practice_tab, delivery_tab = st.tabs(["教学设计", "分层练习", "确认与交付"])

    with design_tab:
        status = st.session_state.get("teacher_decision", "待确认")
        render_status(f"当前状态：{status}")
        with st.expander("查看本教案引用的教材依据", expanded=False):
            show_source_evidence(plan.get("source_evidence", []))
        rewrite_instruction = st.text_input(
            "给 AI 的局部修改要求（可选）",
            placeholder="例如：增加小组讨论，并把语言改得更适合七年级学生",
            key=f"rewrite_instruction_{revision}",
        )

    def rewrite_or_fallback(module: str, current: object, fallback):
        if llm_service is not None and rewrite_instruction.strip():
            try:
                rewritten = llm_service.rewrite_module(
                    module,
                    current,
                    rewrite_instruction,
                    {
                        "teacher_request": request,
                        "class_profile": profile,
                        "source_evidence": plan.get("source_evidence", []),
                    },
                )
                if module in {"objectives", "key_strategies"}:
                    if not isinstance(rewritten, list) or not all(isinstance(item, str) for item in rewritten):
                        raise ValueError("模型返回类型不符合该模块要求")
                elif module == "timeline":
                    if not isinstance(rewritten, list) or sum(int(item["minutes"]) for item in rewritten) != int(request["duration"]):
                        raise ValueError("模型课堂时间线格式或总时长不正确")
                elif module in {"A_基础巩固", "B_重点纠错", "C_拓展提升"}:
                    if not isinstance(rewritten, list) or len(rewritten) < 2:
                        raise ValueError("模型至少需要返回两道练习")
                    if not all(validate_generated_item(request["topic"], item) for item in rewritten):
                        raise ValueError("模型练习未通过 SymPy 门禁")
                st.success(f"{module} 已按教师意见由模型局部重写。")
                return rewritten
            except Exception as error:
                st.warning(f"模型局部重写失败，已回退规则生成：{error}")
        return fallback()

    with design_tab:
        render_section_label("教学目标")
        locks["objectives"] = st.checkbox("锁定教学目标", value=locks.get("objectives", False), key=f"lock_obj_{revision}")
        objectives_text = st.text_area(
            "每行一个教学目标",
            value="\n".join(plan["objectives"]),
            height=130,
            key=f"objectives_{revision}",
        )
        if st.button("重新生成教学目标", disabled=locks["objectives"], key=f"regen_obj_{revision}"):
            plan["objectives"] = rewrite_or_fallback(
                "objectives",
                plan["objectives"],
                lambda: regenerate_lesson_module("objectives", profile, request, plan, revision),
            )
            st.session_state["editor_revision"] = revision + 1
            st.rerun()

        render_section_label("教学策略")
        locks["key_strategies"] = st.checkbox("锁定教学策略", value=locks.get("key_strategies", False), key=f"lock_strategy_{revision}")
        strategies_text = st.text_area(
            "每行一条教学策略",
            value="\n".join(plan["key_strategies"]),
            height=130,
            key=f"strategies_{revision}",
        )
        if st.button("重新生成教学策略", disabled=locks["key_strategies"], key=f"regen_strategy_{revision}"):
            plan["key_strategies"] = rewrite_or_fallback(
                "key_strategies",
                plan["key_strategies"],
                lambda: regenerate_lesson_module("key_strategies", profile, request, plan, revision),
            )
            st.session_state["editor_revision"] = revision + 1
            st.rerun()

        render_section_label("课堂活动")
        locks["timeline"] = st.checkbox("锁定课堂活动", value=locks.get("timeline", False), key=f"lock_timeline_{revision}")
        timeline_frame = st.data_editor(
            pd.DataFrame(plan["timeline"]),
            num_rows="dynamic",
            width="stretch",
            key=f"timeline_{revision}",
        )
        if st.button("重新生成课堂活动", disabled=locks["timeline"], key=f"regen_timeline_{revision}"):
            plan["timeline"] = rewrite_or_fallback(
                "timeline",
                plan["timeline"],
                lambda: regenerate_lesson_module("timeline", profile, request, plan, revision),
            )
            st.session_state["editor_revision"] = revision + 1
            st.rerun()

    edited_groups: dict[str, pd.DataFrame] = {}
    with practice_tab:
        st.caption("A 组侧重基础，B 组针对主要错因，C 组用于迁移与提升。")
        for group in ("A_基础巩固", "B_重点纠错", "C_拓展提升"):
            with st.expander(group, expanded=True):
                locks[group] = st.checkbox(
                    f"锁定 {group}", value=locks.get(group, False), key=f"lock_{group}_{revision}"
                )
                edited_groups[group] = st.data_editor(
                    pd.DataFrame(materials[group]),
                    num_rows="dynamic",
                    width="stretch",
                    key=f"editor_{group}_{revision}",
                )
                if st.button(
                    f"重新生成 {group}", disabled=locks[group], key=f"regen_{group}_{revision}"
                ):
                    materials[group] = rewrite_or_fallback(
                        group,
                        materials[group],
                        lambda group=group: regenerate_practice_group(group, profile, revision),
                    )
                    st.session_state["editor_revision"] = revision + 1
                    st.rerun()

    with delivery_tab:
        render_section_label("教师意见")
        teacher_note = st.text_area(
            "审核意见或课堂备注",
            placeholder="记录你对本次教案的判断，或说明仍需调整的部分。",
            key=f"teacher_note_{revision}",
        )

    def apply_edits() -> None:
        plan["objectives"] = [line.strip() for line in objectives_text.splitlines() if line.strip()]
        plan["key_strategies"] = [line.strip() for line in strategies_text.splitlines() if line.strip()]
        plan["timeline"] = timeline_frame.to_dict(orient="records")
        for group, edited in edited_groups.items():
            materials[group] = edited.to_dict(orient="records")
        working["quality_report"] = review_output(plan, materials)
        working["final_message"] = (
            "教师修改版本已通过自动检查。"
            if working["quality_report"]["passed"]
            else "教师修改版本存在自动检查提示，请复核。"
        )
        working["teacher_review"] = {
            "decision": st.session_state.get("teacher_decision", "待确认"),
            "note": teacher_note,
            "locked_modules": [name for name, locked in locks.items() if locked],
        }
        st.session_state["working_version"] = working

    with delivery_tab:
        render_section_label("确认操作")
        c1, c2 = st.columns(2)
        if c1.button("保存当前修改", key=f"apply_{revision}", use_container_width=True):
            apply_edits()
            st.success("修改已保存到当前工作版本。")
        if c2.button("接受并定稿", type="primary", key=f"accept_{revision}", use_container_width=True):
            st.session_state["teacher_decision"] = "已接受"
            apply_edits()
            working["teacher_review"]["decision"] = "已接受"
            st.success("教师已确认，可以保存最终版本并下载 Word 交付包。")

        with st.expander("需要驳回或继续调整？", expanded=False):
            if st.button("驳回 AI 初稿", key=f"reject_{revision}"):
                st.session_state["teacher_decision"] = "已驳回"
                apply_edits()
                working["teacher_review"]["decision"] = "已驳回"
                st.warning("已驳回；可以返回前两个标签继续修改或重新生成。")

        if st.button("保存到历史版本", key=f"save_final_{revision}", use_container_width=True):
            apply_edits()
            decision = st.session_state.get("teacher_decision", "待确认")
            if decision != "已接受":
                st.error("请先点击“接受并定稿”，确认教师已完成最终审核。")
            else:
                working["teacher_review"]["decision"] = decision
                version_id = store.save_version(plan["title"], "教师已确认", working, teacher_note)
                st.session_state["last_saved_version_id"] = version_id
                st.success(f"最终版本已保存，版本编号 #{version_id}。")

        json_download("下载当前 JSON", working, "teachloop_teacher_version.json", f"teacher_download_{revision}")
        if st.session_state.get("teacher_decision") == "已接受":
            delivery_zip = build_delivery_zip(working, st.session_state.get("feedback_result"))
            st.download_button(
                "下载完整 Word 交付包",
                delivery_zip,
                "TeachLoop_教师交付包.zip",
                "application/zip",
                key=f"word_delivery_{revision}",
                use_container_width=True,
            )
        else:
            st.caption("完成教师定稿后开放 Word 最终交付包。")


def render_feedback_page(
    store: TeachLoopStore, llm_service: EducationLLMService | None = None
) -> None:
    render_page_header(
        "STEP 04 · FEEDBACK",
        "看见课堂真正带来的变化",
        "上传随堂测，比较课前与课后表现，定位仍需干预的学生，并生成下一课建议。",
    )
    result = st.session_state.get("workflow_result")
    if not result or result.get("validation_errors"):
        st.info("请先完成一次课前诊断和备课生成。")
        return

    with st.container(border=True):
        render_section_label("课堂结果")
        st.download_button(
            "下载随堂测 CSV 模板",
            csv_template_bytes(include_link=True),
            "TeachLoop_随堂测模板.csv",
            "text/csv",
            key="download_post_template",
        )
        uploaded = st.file_uploader(
            "上传随堂测 CSV；也可以使用内置课后演示数据",
            type=["csv"],
            key="post_csv",
        )
        subject = result.get("teacher_request", {}).get("subject", "数学")
        default_path = demo_path(subject, post_class=True)
        frame = pd.read_csv(uploaded) if uploaded is not None else pd.read_csv(default_path)
        if uploaded is None:
            st.info("当前使用内置课后演示数据。")
        if st.toggle("直接在页面录入或修改随堂测", key="direct_post_entry"):
            frame = st.data_editor(
                frame,
                num_rows="dynamic",
                width="stretch",
                key="post_data_editor",
            )
        with st.expander("预览随堂测数据"):
            st.dataframe(frame, width="stretch")

    if st.button(
        "比较课前与课后效果  →",
        type="primary",
        key="analyze_feedback",
        use_container_width=True,
    ):
        feedback = compare_learning_outcomes(
            result["class_profile"], frame.to_dict(orient="records")
        )
        if llm_service is not None:
            feedback = llm_service.enhance_feedback(feedback, result.get("teacher_request", {}))
        st.session_state["feedback_result"] = feedback
        feedback_id = store.save_feedback(result["lesson_plan"]["title"], feedback)
        st.session_state["last_feedback_id"] = feedback_id

    feedback = st.session_state.get("feedback_result")
    if not feedback:
        return

    c1, c2, c3 = st.columns(3)
    c1.metric("课前正确率", f"{feedback['before_overall_accuracy']:.1%}")
    c2.metric("课后正确率", f"{feedback['after_overall_accuracy']:.1%}")
    c3.metric("整体变化", f"{feedback['overall_change']:+.1%}")
    llm_feedback_status = feedback.get("feedback_llm_status", {})
    if llm_feedback_status.get("message"):
        st.caption(llm_feedback_status["message"])
    st.caption(f"对照可信度：{feedback.get('comparison_reliability', '有限对照')}")
    for warning in feedback.get("comparison_warnings", []):
        st.warning(warning)

    st.subheader("知识点掌握变化")
    knowledge_frame = pd.DataFrame(feedback["knowledge_changes"])
    st.dataframe(
        knowledge_frame,
        width="stretch",
        column_config={
            "before_accuracy": st.column_config.NumberColumn("课前", format="percent"),
            "after_accuracy": st.column_config.NumberColumn("课后", format="percent"),
            "change": st.column_config.NumberColumn("变化", format="percent"),
        },
    )

    st.subheader("错因减少情况")
    st.dataframe(pd.DataFrame(feedback["error_changes"]), width="stretch")
    if feedback.get("question_anchor_changes"):
        st.subheader("题目级锚点对照")
        st.dataframe(pd.DataFrame(feedback["question_anchor_changes"]), width="stretch", hide_index=True)
    st.subheader("仍需继续干预的学生组")
    st.write("、".join(feedback["continued_intervention_students"]) or "暂无")
    st.subheader("学生级前后变化")
    st.dataframe(pd.DataFrame(feedback.get("student_changes", [])), width="stretch", hide_index=True)
    st.download_button(
        "下载学生干预明细 CSV",
        build_feedback_students_csv(feedback),
        "TeachLoop_学生干预明细.csv",
        "text/csv",
        key="feedback_students_download",
    )
    st.subheader("下一节课建议")
    for suggestion in feedback["next_lesson_suggestions"]:
        st.markdown(f"- {suggestion}")
    st.warning(feedback["boundary"])
    json_download("下载课后反馈报告", feedback, "teachloop_feedback.json", "feedback_download")
    st.download_button(
        "下载含课后建议的 Word 交付包",
        build_delivery_zip(st.session_state.get("working_version", result), feedback),
        "TeachLoop_课后完整交付包.zip",
        "application/zip",
        key="feedback_word_delivery",
    )


def render_knowledge_page(knowledge_base: LocalVectorKnowledgeBase) -> None:
    render_page_header(
        "LIBRARY · LOCAL FIRST",
        "建立你的教材知识库",
        "上传教材或自建资料，系统会按页解析并建立本地索引。备课时自动引用来源与页码。",
    )
    st.info("知识库默认在本机处理，不会把教材发送到外部模型服务。")

    sources = knowledge_base.sources()
    st.metric("知识片段总数", knowledge_base.count)
    if sources:
        source_frame = pd.DataFrame(sources)
        source_frame["pages"] = source_frame["pages"].map(lambda pages: ", ".join(map(str, pages)))
        st.dataframe(source_frame, width="stretch")
        with st.expander("管理已有资料", expanded=False):
            selected_source = st.selectbox("选择资料", [item["source"] for item in sources], key="manage_kb_source")
            renamed_source = st.text_input("新名称", value=selected_source, key="rename_kb_source")
            c1, c2 = st.columns(2)
            if c1.button("重命名资料", key="rename_kb"):
                changed = knowledge_base.rename_source(selected_source, renamed_source.strip())
                st.success(f"已更新 {changed} 个知识片段。")
                st.rerun()
            if c2.button("删除所选资料", key="delete_kb"):
                removed = knowledge_base.delete_source(selected_source)
                st.success(f"已删除 {removed} 个知识片段。")
                st.rerun()

    uploaded = st.file_uploader("上传 PDF、Markdown 或 TXT", type=["pdf", "md", "txt"], key="kb_file")
    source_name = st.text_input(
        "资料名称",
        value=uploaded.name if uploaded is not None else "",
        key="kb_source_name",
    )
    if st.button("解析并加入知识库", type="primary", disabled=uploaded is None, key="index_kb"):
        data = uploaded.getvalue()
        if len(data) > MAX_UPLOAD_MB * 1024 * 1024:
            st.error(f"文件超过 {MAX_UPLOAD_MB}MB，当前配置暂不处理。")
        else:
            try:
                if uploaded.name.lower().endswith(".pdf"):
                    added = knowledge_base.add_pdf(data, source_name or uploaded.name)
                else:
                    text = data.decode("utf-8", errors="replace")
                    added = knowledge_base.add_text(text, source_name or uploaded.name)
                st.success(f"已新增 {added} 个知识片段。重复内容会自动跳过。")
            except Exception as error:
                st.error(f"资料解析失败：{error}")

    st.subheader("检索预览")
    query = st.text_input("输入备课主题或知识点", "一元一次方程 典型错因", key="kb_query")
    if st.button("检索教材依据", key="search_kb"):
        st.session_state["kb_search_results"] = knowledge_base.search(query, top_k=6)
        st.session_state["kb_search_stats"] = knowledge_base.last_search_stats
    if st.session_state.get("kb_search_stats"):
        stats = st.session_state["kb_search_stats"]
        st.caption(f"候选片段 {stats.get('candidates', 0)} · 命中 {stats.get('hits', 0)} · 最高 BM25 分数 {stats.get('top_score', 0)}")
    show_source_evidence(st.session_state.get("kb_search_results", []))


def render_capabilities_page() -> None:
    render_page_header(
        "AGENT · CAPABILITIES",
        "通用能力与学科包",
        "通用教学 Skill 负责流程方法，学科包负责题型、错因、量规和确定性验证；增加学科不需要重写整个平台。",
    )
    skills = selected_skills()
    packs = list_subject_packs()
    c1, c2, c3 = st.columns(3)
    c1.metric("精选通用 Skill", len(skills))
    c2.metric("首批学科包", len(packs))
    c3.metric("可选课题", sum(len(pack.get("topics", {})) for pack in packs))

    render_section_label("学科能力包")
    for pack in packs:
        with st.container(border=True):
            st.subheader(f"{pack['name']} · {pack.get('status', '试用')}")
            st.caption(pack.get("description", ""))
            st.write("课题：" + "、".join(pack.get("topics", {}).keys()))
            st.write(f"验证方式：{pack.get('validator')} · 版本：{pack.get('version')}")

    render_section_label("第一批通用教学 Skill")
    skill_frame = pd.DataFrame(
        [
            {
                "能力": item["name"],
                "上游 Skill ID": item["id"],
                "应用阶段": "、".join(item.get("stages", [])),
                "适用学科": "、".join(item.get("subjects", [])),
            }
            for item in skills
        ]
    )
    st.dataframe(skill_frame, width="stretch", hide_index=True)
    st.info(
        "能力映射参考 education-agent-skills（Gareth Manning，CC BY-SA 4.0）。"
        "当前版本只登记精选 Skill 的标识与编排关系，未复制 165 个 Skill 正文。"
    )


def render_history_page(store: TeachLoopStore) -> None:
    render_page_header(
        "ARCHIVE · VERSIONS",
        "所有定稿，清楚留存",
        "查看教师已确认的历史版本，随时重新下载 JSON 或完整 Word 交付包。",
    )
    version_tab, feedback_tab = st.tabs(["教师定稿", "课后反馈"])
    with version_tab:
        all_versions = store.list_versions(limit=100)
        subjects = [""] + sorted({item.get("subject", "") for item in all_versions if item.get("subject")})
        selected_subject = st.selectbox("按学科筛选", subjects, format_func=lambda value: value or "全部学科")
        topics = [""] + sorted({item.get("topic", "") for item in all_versions if item.get("topic") and (not selected_subject or item.get("subject") == selected_subject)})
        selected_topic = st.selectbox("按课题筛选", topics, format_func=lambda value: value or "全部课题")
        versions = store.list_versions(subject=selected_subject, topic=selected_topic)
        if not versions:
            st.info("还没有符合条件的教师最终版本。")
        else:
            st.dataframe(pd.DataFrame([{"版本": item["id"], "学科": item.get("subject", ""), "课题": item.get("topic", ""), "标题": item["title"], "状态": item["status"], "保存时间": item["created_at"]} for item in versions]), width="stretch", hide_index=True)
            selected_id = st.selectbox("查看版本", [item["id"] for item in versions])
            selected = next(item for item in versions if item["id"] == selected_id)
            st.write(selected["teacher_note"] or "无教师备注")
            render_result_overview(selected["payload"])
            json_download("下载所选版本", selected["payload"], f"teachloop_version_{selected_id}.json", f"history_download_{selected_id}")
            st.download_button("下载所选版本 Word 交付包", build_delivery_zip(selected["payload"], st.session_state.get("feedback_result")), f"TeachLoop_版本_{selected_id}.zip", "application/zip", key=f"history_word_{selected_id}")
    with feedback_tab:
        feedbacks = store.list_feedbacks()
        if not feedbacks:
            st.info("还没有保存课后反馈。")
        else:
            st.dataframe(pd.DataFrame([{"编号": item["id"], "教案": item["lesson_title"], "保存时间": item["created_at"]} for item in feedbacks]), width="stretch", hide_index=True)
            feedback_id = st.selectbox("查看反馈", [item["id"] for item in feedbacks])
            selected_feedback = next(item for item in feedbacks if item["id"] == feedback_id)["payload"]
            st.json(selected_feedback, expanded=False)
            st.download_button("下载学生干预明细 CSV", build_feedback_students_csv(selected_feedback), f"TeachLoop_反馈_{feedback_id}_学生明细.csv", "text/csv", key=f"history_feedback_{feedback_id}")


store = get_store()
knowledge_base = get_knowledge_base()

with st.sidebar:
    render_brand()
    page = st.radio(
        "工作区",
        ["开始备课", "教师审核", "课后反馈", "教材知识库", "能力与学科包", "历史版本"],
        label_visibility="collapsed",
    )
    st.divider()
    with st.expander("大模型设置", expanded=False):
        model_enabled = st.toggle("启用 OpenAI-compatible 模型", key="llm_enabled")
        if model_enabled:
            st.text_input("Base URL", "https://api.openai.com/v1", key="llm_base_url")
            st.text_input("模型名称", placeholder="填写服务实际提供的模型 ID", key="llm_model")
            st.text_input("API Key", type="password", key="llm_api_key")
            st.slider("Temperature", 0.0, 1.0, 0.2, 0.1, key="llm_temperature")
            st.checkbox(
                "我确认允许将匿名、最小化学情发送到所配置的模型服务",
                key="llm_data_consent",
            )
            if st.button("测试模型连接", key="test_llm_connection"):
                service = current_llm_service()
                if service is None:
                    st.error("请填写 Base URL、模型名称并勾选数据授权。")
                else:
                    connection = service.client.test_connection()
                    if connection["ok"]:
                        st.success(connection["message"])
                    else:
                        st.error(connection["message"])
    st.divider()
    st.caption("演示数据均为匿名模拟数据。AI 结果需由教师最终确认。")

llm_service = current_llm_service()

render_hero(workflow_stage())

if page == "开始备课":
    render_prepare_page(knowledge_base, llm_service)
elif page == "教师审核":
    render_teacher_review_page(store, llm_service)
elif page == "课后反馈":
    render_feedback_page(store, llm_service)
elif page == "教材知识库":
    render_knowledge_page(knowledge_base)
elif page == "能力与学科包":
    render_capabilities_page()
else:
    render_history_page(store)
