"""工具卡片组件 — 工具执行结果展示."""

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
    status_config = {
        "success": {"bg": "#e8f5e9", "border": "#4caf50", "label": "成功"},
        "error": {"bg": "#ffebee", "border": "#f44336", "label": "失败"},
        "running": {"bg": "#e3f2fd", "border": "#2196f3", "label": "执行中"},
        "pending": {"bg": "#f5f5f5", "border": "#9e9e9e", "label": "等待中"},
    }
    sc = status_config.get(status, status_config["pending"])

    with st.container():
        c1, c2, c3, c4 = st.columns([0.02, 2, 1, 1])
        with c2:
            st.markdown(f"**{tool_name}**")
            if description:
                st.caption(description)
        with c3:
            st.markdown(render_risk_badge(risk_level), unsafe_allow_html=True)
        with c4:
            st.caption(sc["label"])
            if duration_ms is not None:
                st.caption(f"{duration_ms:.0f}ms")

        with st.expander("详情", expanded=expand):
            if params:
                st.caption("**参数**")
                st.json(params)
            if output:
                st.caption("**输出**")
                st.code(output, language="text" if status == "error" else None)

    st.markdown("---")

def render_tool_grid(tools: list[dict], cols: int = 2) -> None:
    if not tools:
        st.info("暂无可用工具")
        return

    rows = [tools[i : i + cols] for i in range(0, len(tools), cols)]
    for row in rows:
        row_cols = st.columns(cols)
        for idx, tool in enumerate(row):
            with row_cols[idx]:
                enabled = tool.get("enabled", True)
                status_text = "已启用" if enabled else "已禁用"
                risk = tool.get("risk_level", "info")
                risk_html = render_risk_badge(risk)
                st.markdown(
                    f"### [{status_text}] {tool['name']} {risk_html}",
                    unsafe_allow_html=True,
                )
                if tool.get("description"):
                    st.caption(tool["description"])
                st.divider()
