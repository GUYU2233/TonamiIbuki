"""阶段指示器组件 — 五阶段生命周期进度展示."""

import streamlit as st

PHASES = [
    {"key": "ANALYSIS", "label": "分析", "desc": "收集信息，初步诊断"},
    {"key": "PLANNING", "label": "规划", "desc": "制定修复方案"},
    {"key": "EXECUTION", "label": "执行", "desc": "执行修复操作"},
    {"key": "VERIFICATION", "label": "验证", "desc": "验证修复效果"},
    {"key": "COMPLETION", "label": "完成", "desc": "生成报告，归档案例"},
]

PHASE_ORDER = [p["key"] for p in PHASES]
PHASE_MAP = {p["key"]: p for p in PHASES}

def _phase_index(phase_key: str) -> int:
    try:
        return PHASE_ORDER.index(phase_key)
    except ValueError:
        return -1

def render_phase_indicator(current_phase: str, inline: bool = False) -> None:
    cur_idx = _phase_index(current_phase)

    if inline:
        cols = st.columns(len(PHASES))
        for i, phase in enumerate(PHASES):
            label = phase["label"]
            if i < cur_idx:
                cols[i].markdown(f"~~{label}~~ [已完成]")
            elif i == cur_idx:
                cols[i].markdown(f"**{label}**")
            else:
                cols[i].markdown(f"{label}")
        return

    total = len(PHASES) - 1
    progress = max(0, min(cur_idx, total)) / max(total, 1)
    st.progress(progress, text=f"当前阶段: {PHASE_MAP.get(current_phase, {}).get('label', current_phase)} / {PHASES[-1]['label']}")

    cols = st.columns(len(PHASES))
    for i, phase in enumerate(PHASES):
        label = phase["label"]
        if i < cur_idx:
            bg, border, status = "#e8f5e9", "#4caf50", "已完成"
        elif i == cur_idx:
            bg, border, status = "#e3f2fd", "#2196f3", "进行中"
        else:
            bg, border, status = "#f5f5f5", "#e0e0e0", "待开始"

        cols[i].markdown(
            f'<div style="text-align:center;padding:8px 4px;border-radius:8px;'
            f'background:{bg};border:2px solid {border};font-size:0.85em;">'
            f'<div style="font-weight:600;">{label}</div>'
            f'<div style="font-size:0.75em;color:#888;">{status}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )

def render_phase_stepper(current_phase: str) -> str | None:
    cur_idx = _phase_index(current_phase)
    phase_info = PHASE_MAP.get(current_phase, PHASES[0])
    st.info(f"**当前阶段**: {phase_info['label']} — {phase_info['desc']}")

    c1, c2, c3 = st.columns([1, 2, 1])
    prev_phase = PHASE_ORDER[cur_idx - 1] if cur_idx > 0 else None
    next_phase = PHASE_ORDER[cur_idx + 1] if cur_idx < len(PHASE_ORDER) - 1 else None

    if c1.button("上一步", disabled=prev_phase is None, use_container_width=True):
        return prev_phase
    if c3.button("下一步", disabled=next_phase is None, use_container_width=True):
        return next_phase

    return None
