"""Risk badge component for displaying risk levels with consistent styling."""

import streamlit as st

# Risk level configuration
_RISK_CONFIG = {
    "critical": {"icon": "🔴", "color": "#c62828", "bg": "#ffebee", "label": "严重"},
    "high": {"icon": "🟠", "color": "#e65100", "bg": "#fff3e0", "label": "高"},
    "medium": {"icon": "🟡", "color": "#f9a825", "bg": "#fffde7", "label": "中"},
    "low": {"icon": "🟢", "color": "#2e7d32", "bg": "#e8f5e9", "label": "低"},
    "info": {"icon": "🔵", "color": "#1565c0", "bg": "#e3f2fd", "label": "信息"},
    "unknown": {"icon": "⚪", "color": "#616161", "bg": "#f5f5f5", "label": "未知"},
}


def _normalize(level: str) -> str:
    level = level.lower().strip()
    if level in _RISK_CONFIG:
        return level
    # aliases
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
    """Return an HTML badge string for the given risk level.

    Args:
        level: Risk level string (critical/high/medium/low/info).
        show_label: Whether to show the Chinese label.

    Returns:
        HTML string for the badge.
    """
    cfg = _RISK_CONFIG[_normalize(level)]
    label = cfg["label"] if show_label else ""
    return (
        f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;'
        f'background:{cfg["bg"]};color:{cfg["color"]};font-weight:600;font-size:0.85em;'
        f'white-space:nowrap;">{cfg["icon"]} {label}</span>'
    )


def show_risk_badge(level: str, show_label: bool = True) -> None:
    """Display a risk badge inline using st.markdown."""
    st.markdown(render_risk_badge(level, show_label), unsafe_allow_html=True)


def render_risk_bar(risks: dict[str, int]) -> None:
    """Render a horizontal bar of risk counts.

    Args:
        risks: Dict mapping risk level to count, e.g. {"critical": 2, "high": 5}.
    """
    if not risks:
        st.caption("无风险数据")
        return

    order = ["critical", "high", "medium", "low", "info"]
    cols = st.columns(len(order))
    for i, level in enumerate(order):
        cnt = risks.get(level, 0)
        cfg = _RISK_CONFIG[level]
        cols[i].metric(
            f"{cfg['icon']} {cfg['label']}",
            cnt,
            delta_color="off",
        )


def risk_selectbox(label: str = "风险等级", default: str = "medium") -> str:
    """A styled selectbox for risk levels."""
    options = ["critical", "high", "medium", "low", "info"]
    return st.selectbox(
        label,
        options,
        index=options.index(default) if default in options else 2,
        format_func=lambda x: f"{_RISK_CONFIG[x]['icon']} {_RISK_CONFIG[x]['label']}",
    )
