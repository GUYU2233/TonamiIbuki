"""Risk badge component for displaying risk levels with consistent styling."""

import streamlit as st

_RISK_CONFIG = {
    "critical": {"color": "#c62828", "bg": "#ffebee", "label": "Critical"},
    "high": {"color": "#e65100", "bg": "#fff3e0", "label": "High"},
    "medium": {"color": "#f9a825", "bg": "#fffde7", "label": "Medium"},
    "low": {"color": "#2e7d32", "bg": "#e8f5e9", "label": "Low"},
    "info": {"color": "#1565c0", "bg": "#e3f2fd", "label": "Info"},
    "unknown": {"color": "#616161", "bg": "#f5f5f5", "label": "Unknown"},
}

def _normalize(level: str) -> str:
    level = level.lower().strip()
    if level in _RISK_CONFIG:
        return level
    aliases = {
        "severe": "critical",
        "danger": "critical",
        "red": "critical",
        "orange": "high",
        "yellow": "medium",
        "green": "low",
        "blue": "info",
    }
    return aliases.get(level, "unknown")

def render_risk_badge(level: str, show_label: bool = True) -> str:
    cfg = _RISK_CONFIG[_normalize(level)]
    label = cfg["label"] if show_label else ""
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'background:{cfg["bg"]};color:{cfg["color"]};font-weight:600;font-size:0.85em;'
        f'white-space:nowrap;">{label}</span>'
    )

def show_risk_badge(level: str, show_label: bool = True) -> None:
    st.markdown(render_risk_badge(level, show_label), unsafe_allow_html=True)

def render_risk_bar(risks: dict[str, int]) -> None:
    if not risks:
        st.caption("No risk data")
        return

    order = ["critical", "high", "medium", "low", "info"]
    cols = st.columns(len(order))
    for i, level in enumerate(order):
        cnt = risks.get(level, 0)
        cfg = _RISK_CONFIG[level]
        cols[i].metric(
            f"{cfg['label']}",
            cnt,
            delta_color="off",
        )

def risk_selectbox(label: str = "Risk Level", default: str = "medium") -> str:
    options = ["critical", "high", "medium", "low", "info"]
    return st.selectbox(
        label,
        options,
        index=options.index(default) if default in options else 2,
        format_func=lambda x: _RISK_CONFIG[x]["label"],
    )
