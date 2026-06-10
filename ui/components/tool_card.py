"""Tool card component for displaying tool execution results."""

import streamlit as st
from ui.components.risk_badge import render_risk_badge


def render_tool_card(
    tool_name: str,
    status: str,
    description: str = "",
    risk_level: str = "info",
    output: str = "",
    duration_ms: float | None = None,
    params: dict | None = None,
    expand: bool = False,
) -> None:
    """Render a card showing a single tool execution.

    Args:
        tool_name: Tool name/ID.
        status: Execution status (success/error/running/pending).
        description: Human-readable description.
        risk_level: Tool risk level (critical/high/medium/low/info).
        output: Execution output text.
        duration_ms: Execution duration in milliseconds.
        params: Input parameters dict.
        expand: Whether to expand the card by default.
    """
    # Status styling
    status_config = {
        "success": {"icon": "✅", "bg": "#e8f5e9", "border": "#4caf50"},
        "error": {"icon": "❌", "bg": "#ffebee", "border": "#f44336"},
        "running": {"icon": "⏳", "bg": "#e3f2fd", "border": "#2196f3"},
        "pending": {"icon": "⏸️", "bg": "#f5f5f5", "border": "#9e9e9e"},
    }
    sc = status_config.get(status, status_config["pending"])

    with st.container():
        # Header row
        c1, c2, c3, c4 = st.columns([0.05, 2, 1, 1])
        with c1:
            st.markdown(f"### {sc['icon']}")
        with c2:
            st.markdown(f"**{tool_name}**")
            if description:
                st.caption(description)
        with c3:
            st.markdown(render_risk_badge(risk_level), unsafe_allow_html=True)
        with c4:
            st.caption(status.upper())
            if duration_ms is not None:
                st.caption(f"{duration_ms:.0f}ms")

        # Expandable detail
        with st.expander("📄 详情", expanded=expand):
            if params:
                st.caption("**输入参数**")
                st.json(params)
            if output:
                st.caption("**输出**")
                st.code(output, language="text" if status == "error" else None)

    st.markdown("---")


def render_tool_grid(tools: list[dict], cols: int = 2) -> None:
    """Render tools in a responsive grid layout.

    Each tool dict:
        - name (str)
        - status (str)
        - description (str, optional)
        - risk_level (str, optional)
        - enabled (bool, optional)
    """
    if not tools:
        st.info("暂无可用工具")
        return

    rows = [tools[i : i + cols] for i in range(0, len(tools), cols)]
    for row in rows:
        row_cols = st.columns(cols)
        for idx, tool in enumerate(row):
            with row_cols[idx]:
                enabled = tool.get("enabled", True)
                status_icon = "✅" if enabled else "🚫"
                risk = tool.get("risk_level", "info")
                risk_html = render_risk_badge(risk)
                st.markdown(
                    f"### {status_icon} {tool['name']} {risk_html}",
                    unsafe_allow_html=True,
                )
                if tool.get("description"):
                    st.caption(tool["description"])
                st.divider()
