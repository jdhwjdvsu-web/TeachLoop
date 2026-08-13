from __future__ import annotations

from html import escape

import streamlit as st


APPLE_GLASS_CSS = r"""
<style>
:root {
  --tl-ink: #182033;
  --tl-muted: #667085;
  --tl-blue: #1677ff;
  --tl-blue-dark: #0764e8;
  --tl-line: rgba(255, 255, 255, 0.78);
  --tl-glass: rgba(255, 255, 255, 0.66);
  --tl-glass-strong: rgba(255, 255, 255, 0.82);
  --tl-shadow: 0 18px 55px rgba(45, 61, 98, 0.11);
}

html, body, [class*="css"] {
  font-family: -apple-system, BlinkMacSystemFont, "SF Pro Display", "SF Pro Text",
    "PingFang SC", "Microsoft YaHei", "Segoe UI", sans-serif;
}

[data-testid="stAppViewContainer"] {
  color: var(--tl-ink);
  background:
    radial-gradient(circle at 8% 0%, rgba(114, 184, 255, 0.28), transparent 30rem),
    radial-gradient(circle at 92% 4%, rgba(188, 151, 255, 0.22), transparent 32rem),
    radial-gradient(circle at 65% 100%, rgba(102, 220, 195, 0.17), transparent 30rem),
    linear-gradient(145deg, #f7f9fd 0%, #f1f4fa 52%, #f8f9fc 100%);
  background-attachment: fixed;
}

[data-testid="stHeader"] {
  background: rgba(247, 249, 253, 0.58);
  backdrop-filter: blur(24px) saturate(150%);
  -webkit-backdrop-filter: blur(24px) saturate(150%);
  border-bottom: 1px solid rgba(255, 255, 255, 0.74);
}

[data-testid="stMainBlockContainer"] {
  max-width: 1280px;
  padding-top: 1.6rem;
  padding-bottom: 4rem;
}

[data-testid="stSidebar"] {
  background: rgba(246, 248, 252, 0.72);
  backdrop-filter: blur(30px) saturate(155%);
  -webkit-backdrop-filter: blur(30px) saturate(155%);
  border-right: 1px solid rgba(255, 255, 255, 0.84);
  box-shadow: 16px 0 44px rgba(31, 45, 77, 0.045);
}

[data-testid="stSidebarContent"] {
  padding: 1.2rem 1rem 2rem;
}

.tl-brand {
  display: flex;
  align-items: center;
  gap: 0.78rem;
  padding: 0.42rem 0.18rem 1.25rem;
}
.tl-brand-mark {
  width: 42px;
  height: 42px;
  display: grid;
  place-items: center;
  border-radius: 14px;
  color: white;
  font-weight: 750;
  font-size: 1.08rem;
  letter-spacing: -0.04em;
  background: linear-gradient(145deg, #54a6ff 0%, #0969e8 78%);
  box-shadow: 0 10px 24px rgba(22, 119, 255, 0.27), inset 0 1px rgba(255,255,255,.65);
}
.tl-brand-name { font-size: 1rem; font-weight: 760; letter-spacing: -0.025em; }
.tl-brand-meta { color: var(--tl-muted); font-size: 0.72rem; margin-top: 0.08rem; }

[data-testid="stSidebar"] [data-testid="stRadio"] > div {
  gap: 0.36rem;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label {
  padding: 0.68rem 0.72rem;
  border-radius: 13px;
  border: 1px solid transparent;
  transition: 150ms ease;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
  background: rgba(255,255,255,.62);
  border-color: rgba(255,255,255,.84);
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {
  background: rgba(255,255,255,.86);
  border-color: rgba(255,255,255,.98);
  color: #0969e8;
  box-shadow: 0 8px 22px rgba(42, 62, 99, .09);
}

.tl-hero {
  position: relative;
  overflow: hidden;
  padding: clamp(1.5rem, 4vw, 2.45rem);
  margin-bottom: 1.25rem;
  border: 1px solid rgba(255,255,255,.9);
  border-radius: 30px;
  background:
    linear-gradient(132deg, rgba(255,255,255,.9), rgba(255,255,255,.56)),
    linear-gradient(90deg, rgba(56,144,255,.12), rgba(144,91,255,.08));
  backdrop-filter: blur(28px) saturate(145%);
  -webkit-backdrop-filter: blur(28px) saturate(145%);
  box-shadow: var(--tl-shadow), inset 0 1px rgba(255,255,255,.94);
}
.tl-hero::after {
  content: "";
  position: absolute;
  right: -5rem;
  top: -8rem;
  width: 21rem;
  height: 21rem;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(62,139,255,.24), rgba(150,93,255,.08) 48%, transparent 70%);
  pointer-events: none;
}
.tl-eyebrow {
  color: var(--tl-blue);
  font-size: .72rem;
  line-height: 1;
  font-weight: 760;
  letter-spacing: .13em;
  text-transform: uppercase;
  margin-bottom: .85rem;
}
.tl-hero h1 {
  position: relative;
  z-index: 1;
  margin: 0;
  max-width: 820px;
  font-size: clamp(2rem, 4.8vw, 3.65rem);
  line-height: 1.04;
  letter-spacing: -.055em;
  color: #11182a;
}
.tl-hero p {
  position: relative;
  z-index: 1;
  max-width: 760px;
  margin: 1rem 0 0;
  color: #5f6b7e;
  font-size: 1rem;
  line-height: 1.75;
}
.tl-hero-badges { display: flex; flex-wrap: wrap; gap: .55rem; margin-top: 1.25rem; }
.tl-badge {
  display: inline-flex;
  align-items: center;
  gap: .4rem;
  padding: .42rem .7rem;
  border-radius: 999px;
  color: #40506a;
  font-size: .76rem;
  font-weight: 650;
  background: rgba(255,255,255,.66);
  border: 1px solid rgba(255,255,255,.92);
  box-shadow: 0 5px 14px rgba(41,58,91,.06);
}
.tl-badge-dot { width: 7px; height: 7px; border-radius: 50%; background: #27b77c; box-shadow: 0 0 0 4px rgba(39,183,124,.12); }

.tl-steps {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: .55rem;
  margin: 0 0 1.4rem;
}
.tl-step {
  padding: .72rem .82rem;
  border-radius: 15px;
  color: #7b8494;
  font-size: .76rem;
  font-weight: 660;
  background: rgba(255,255,255,.43);
  border: 1px solid rgba(255,255,255,.66);
}
.tl-step strong { display: block; font-size: .68rem; letter-spacing: .06em; margin-bottom: .16rem; }
.tl-step.active {
  color: #075fce;
  background: rgba(255,255,255,.83);
  border-color: rgba(255,255,255,.98);
  box-shadow: 0 8px 20px rgba(26,94,179,.1);
}
.tl-step.done { color: #15805a; }

.tl-page-head { margin: 1.6rem 0 1rem; }
.tl-page-head .tl-eyebrow { margin-bottom: .52rem; }
.tl-page-head h2 { margin: 0; color: #172033; font-size: clamp(1.55rem, 3vw, 2.15rem); letter-spacing: -.04em; }
.tl-page-head p { margin: .55rem 0 0; color: var(--tl-muted); line-height: 1.65; max-width: 760px; }
.tl-section-label { font-size: .75rem; font-weight: 760; letter-spacing: .08em; color: #69758a; text-transform: uppercase; margin: .2rem 0 .35rem; }
.tl-status {
  display: inline-flex;
  align-items: center;
  gap: .45rem;
  padding: .45rem .72rem;
  border-radius: 999px;
  color: #176b50;
  background: rgba(222, 249, 238, .78);
  border: 1px solid rgba(255,255,255,.9);
  font-size: .78rem;
  font-weight: 680;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  background: var(--tl-glass);
  border: 1px solid rgba(255,255,255,.88) !important;
  border-radius: 23px !important;
  box-shadow: 0 14px 38px rgba(42, 57, 91, .075), inset 0 1px rgba(255,255,255,.9);
  backdrop-filter: blur(22px) saturate(145%);
  -webkit-backdrop-filter: blur(22px) saturate(145%);
}

[data-testid="stMetric"] {
  padding: 1rem 1.05rem;
  border-radius: 18px;
  background: rgba(255,255,255,.66);
  border: 1px solid rgba(255,255,255,.9);
  box-shadow: 0 9px 24px rgba(42,58,90,.06);
}
[data-testid="stMetricLabel"] { color: #6f798b; }
[data-testid="stMetricValue"] { color: #172033; letter-spacing: -.035em; }

.stButton > button, .stDownloadButton > button {
  min-height: 2.65rem;
  border-radius: 999px;
  border: 1px solid rgba(255,255,255,.9);
  font-weight: 690;
  transition: transform 120ms ease, box-shadow 120ms ease, background 120ms ease;
  background: rgba(255,255,255,.76);
  box-shadow: 0 7px 18px rgba(35,52,86,.075);
}
.stButton > button:hover, .stDownloadButton > button:hover {
  transform: translateY(-1px);
  border-color: rgba(255,255,255,1);
  box-shadow: 0 10px 24px rgba(35,52,86,.12);
}
.stButton > button[kind="primary"] {
  color: white;
  background: linear-gradient(180deg, #278aff 0%, #0969e8 100%);
  border-color: rgba(255,255,255,.35);
  box-shadow: 0 11px 25px rgba(22,119,255,.26), inset 0 1px rgba(255,255,255,.35);
}
.stButton > button[kind="primary"]:hover { background: linear-gradient(180deg, #328fff, #0863d9); }

[data-baseweb="input"] > div,
[data-baseweb="select"] > div,
[data-baseweb="textarea"] > div,
[data-testid="stNumberInput"] input {
  background: rgba(255,255,255,.72) !important;
  border-color: rgba(255,255,255,.92) !important;
  border-radius: 13px !important;
  box-shadow: inset 0 0 0 1px rgba(28,57,103,.05), 0 6px 14px rgba(39,56,89,.04);
}
[data-testid="stFileUploaderDropzone"] {
  background: rgba(255,255,255,.54);
  border: 1px dashed rgba(37,111,214,.28);
  border-radius: 18px;
}

[data-testid="stTabs"] [data-baseweb="tab-list"] {
  gap: .35rem;
  padding: .32rem;
  border-radius: 15px;
  background: rgba(222,228,239,.55);
  width: fit-content;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
  height: 2.55rem;
  padding: 0 1rem;
  border-radius: 12px;
  color: #667085;
}
[data-testid="stTabs"] [aria-selected="true"] {
  color: #1269d7;
  background: rgba(255,255,255,.9);
  box-shadow: 0 6px 16px rgba(42,58,91,.09);
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] { display: none; }

[data-testid="stExpander"] {
  border: 1px solid rgba(255,255,255,.86);
  border-radius: 17px;
  overflow: hidden;
  background: rgba(255,255,255,.48);
}

[data-testid="stDataFrame"], [data-testid="stTable"] {
  border-radius: 16px;
  overflow: hidden;
  border: 1px solid rgba(255,255,255,.85);
}

[data-testid="stAlert"] {
  border-radius: 16px;
  border: 1px solid rgba(255,255,255,.82);
  backdrop-filter: blur(12px);
}

h1, h2, h3 { letter-spacing: -.035em; }
hr { border-color: rgba(100,116,139,.12) !important; }
#MainMenu,
footer,
[data-testid="stStatusWidget"],
[data-testid="stAppDeployButton"] {
  display: none !important;
}

[data-testid="stSidebar"] input[type="radio"] {
  accent-color: var(--tl-blue) !important;
}

@media (max-width: 760px) {
  [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
  .tl-hero { border-radius: 24px; }
  .tl-steps { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  [data-testid="stHorizontalBlock"] { gap: .55rem; }
}
</style>
"""


def inject_apple_glass_theme() -> None:
    st.markdown(APPLE_GLASS_CSS, unsafe_allow_html=True)


def render_brand() -> None:
    st.markdown(
        """
        <div class="tl-brand">
          <div class="tl-brand-mark">TL</div>
          <div><div class="tl-brand-name">TeachLoop</div><div class="tl-brand-meta">教师智能工作台</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero(stage: int) -> None:
    stage = max(1, min(stage, 4))
    steps = [
        ("01", "诊断学情"),
        ("02", "生成教案"),
        ("03", "教师确认"),
        ("04", "课后反馈"),
    ]
    step_html = "".join(
        f'<div class="tl-step {"done" if index < stage else "active" if index == stage else ""}">'
        f'<strong>{number}</strong>{label}</div>'
        for index, (number, label) in enumerate(steps, start=1)
    )
    st.markdown(
        """
        <section class="tl-hero">
          <div class="tl-eyebrow">AI-ASSISTED TEACHING</div>
          <h1>让每一次备课，都从真实学情开始。</h1>
          <p>从课前诊断到差异化教案，再到教师确认与课后调整。流程清楚、结果可编辑，AI 始终是助手。</p>
          <div class="tl-hero-badges">
            <span class="tl-badge"><span class="tl-badge-dot"></span>本地优先</span>
            <span class="tl-badge">教师最终确认</span>
            <span class="tl-badge">学科结果校验</span>
          </div>
        </section>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(f'<div class="tl-steps">{step_html}</div>', unsafe_allow_html=True)


def render_page_header(kicker: str, title: str, description: str) -> None:
    st.markdown(
        f"""
        <header class="tl-page-head">
          <div class="tl-eyebrow">{escape(kicker)}</div>
          <h2>{escape(title)}</h2>
          <p>{escape(description)}</p>
        </header>
        """,
        unsafe_allow_html=True,
    )


def render_section_label(text: str) -> None:
    st.markdown(f'<div class="tl-section-label">{escape(text)}</div>', unsafe_allow_html=True)


def render_status(text: str) -> None:
    st.markdown(
        f'<div class="tl-status"><span class="tl-badge-dot"></span>{escape(text)}</div>',
        unsafe_allow_html=True,
    )


def workflow_stage() -> int:
    if st.session_state.get("feedback_result"):
        return 4
    if st.session_state.get("teacher_decision") == "已接受":
        return 3
    if st.session_state.get("workflow_result"):
        return 2
    return 1
