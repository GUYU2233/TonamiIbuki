"""Phase indicator component showing the 5-phase lifecycle progress."""

import streamlit as st

# Phase definitions
PHASES = [
    {"key": "ANALYSIS", "icon": "🔍", "label": "分析", "desc": "收集信息、初步诊断"},
    {"key": "PLANNING", "icon": "📋", "label": "规划", "desc": "制定修复方案"},
    {"key": "EXECUTION", "icon": "⚡", "label": "执行", "desc": "执行修复操作"},
    {"key": "VERIFICATION", "icon": "✅", "label": "验证", "desc": "验证修复结果"},
    {"key": "COMPLETION", "icon": "🏁", "label": "完成", "desc": "生成报告、归档案例"},
]

PHASE_ORDER = [p["key"] for p in PHASES]
PHASE_MAP = {p["key"]: p for p in PHASES}


def _phase_index(phase_key: str) -> int:
    try:
        return PHASE_ORDER.index(phase_key)
    except ValueError:
        return -1


def render_phase_indicator(current_phase: str, inline: bool = False) -> None:
    """Render a horizontal phase progress indicator.

    Args:
        current_phase: Current phase key (ANALYSIS/PLANNING/EXECUTION/VERIFICATION/COMPLETION).
        inline: If True, render compact inline version.
    """
    cur_idx = _phase_index(current_phase)

    if inline:
        # Compact version: single row
        cols = st.columns(len(PHASES))
        for i, phase in enumerate(PHASES):
            key = phase["key"]
            icon = phase["icon"]
            if i < cur_idx:
                # completed
                cols[i].markdown(f"~~{icon}~~ ✅")
            elif i == cur_idx:
                # active
                cols[i].markdown(f"**{icon}**")
            else:
                # pending
                cols[i].markdown(f"{icon}")
        return

    # Full version: progress bar + card
    # Progress bar
    total = len(PHASES) - 1  # 0-4 → 4 steps
    progress = max(0, min(cur_idx, total)) / max(total, 1)
    st.progress(progress, text=f"阶段: {PHASE_MAP.get(current_phase, {}).get('label', current_phase)}/{PHASE_MAP[PHASES[-1]['key']]['label']}")

    # Phase cards
    cols = st.columns(len(PHASES))
    for i, phase in enumerate(PHASES):
        key = phase["key"]
        icon = phase["icon"]
        label = phase["label"]

        if i < cur_idx:
            bg = "#e8f5e9"
            border = "#4caf50"
            status = "✅"
        elif i == cur_idx:
            bg = "#e3f2fd"
            border = "#2196f3"
            status = "⏳"
        else:
            bg = "#f5f5f5"
            border = "#e0e0e0"
            status = "⏸️"

        cols[i].markdown(
            f'<div style="text-align:center;padding:8px 4px;border-radius:8px;'
            f'background:{bg};border:2px solid {border};font-size:0.85em;">'
            f'<div style="font-size:1.3em;">{icon}</div>'
            f'<div style="font-weight:600;">{label}</div>'
            f'<div style="font-size:0.75em;color:#888;">{status}</div>'
            f"</div>",
            unsafe_allow_html=True,
        )


def render_phase_stepper(current_phase: str) -> str | None:
    """Render a stepper that lets the user manually advance phases.

    Returns:
        The selected new phase if changed, else None.
    """
    cur_idx = _phase_index(current_phase)

    # Show current phase card
    phase_info = PHASE_MAP.get(current_phase, PHASES[0])
    st.info(f"**当前阶段**: {phase_info['icon']} {phase_info['label']} — {phase_info['desc']}")

    # Navigation buttons
    c1, c2, c3 = st.columns([1, 2, 1])
    prev_phase = PHASE_ORDER[cur_idx - 1] if cur_idx > 0 else None
    next_phase = PHASE_ORDER[cur_idx + 1] if cur_idx < len(PHASE_ORDER) - 1 else None

    if c1.button("⬅️ 上一阶段", disabled=prev_phase is None, use_container_width=True):
        return prev_phase
    if c3.button("下一阶段 ➡️", disabled=next_phase is None, use_container_width=True):
        return next_phase

    return None
