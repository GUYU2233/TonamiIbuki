"""Streamlit UI components for TonamiIbuki."""

import json

import graphviz
import streamlit as st


def render_topology_graph(nodes: list[dict], edges: list[dict]) -> None:
    """Render a business topology graph using graphviz."""
    dot = graphviz.Digraph()
    colors = {
        "edge": "lightblue",
        "app": "lightgoldenrod1",
        "cache": "palegreen",
        "database": "mistyrose",
        "aiops": "plum1",
    }
    for node in nodes:
        dot.node(
            node["id"],
            node.get("label", node["id"]),
            style="filled",
            fillcolor=colors.get(node.get("group"), "white"),
        )
    for edge in edges:
        dot.edge(edge["source"], edge["target"])
    st.graphviz_chart(dot)


def render_evidence_timeline(events: list[dict]) -> None:
    """Render diagnosis events as a timeline with phase indicators."""
    if not events:
        st.info("暂无事件记录")
        return
    for event in events:
        phase = event.get("phase", {})
        phase_name = phase.get("phase", "unknown") if isinstance(phase, dict) else "unknown"
        phase_owner = phase.get("owner", "") if isinstance(phase, dict) else ""
        phase_progress = phase.get("progress_percent", 0) if isinstance(phase, dict) else 0
        col_icon, col_body = st.columns([0.05, 0.95])
        with col_icon:
            if event["status"] == "completed":
                st.success("✅")
            elif event["status"] == "waiting_approval":
                st.warning("⏸️")
            else:
                st.info("⏳")
        with col_body:
            st.markdown(f"**{event['step'].upper()}** — {event['message']}")
            if phase_name != "unknown":
                st.caption(f"阶段：{phase_name} ({phase_owner}) · 进度：{phase_progress}%")
            if event.get("payload") and isinstance(event["payload"], dict):
                with st.expander("详情"):
                    st.json(event["payload"])


def render_risk_badge(risk_level: str) -> None:
    """Render a colored risk level badge."""
    colors = {
        "low": "green",
        "medium": "orange",
        "high": "red",
        "critical": "darkred",
    }
    emoji = {"low": "🟢", "medium": "🟡", "high": "🟠", "critical": "🔴"}
    st.markdown(
        f"<span style='color:{colors.get(risk_level, 'gray')};font-weight:bold'>{emoji.get(risk_level, '⚪')} {risk_level.upper()}</span>",
        unsafe_allow_html=True,
    )


def render_phase_indicator(current_phase: str | None = None) -> None:
    """Render a horizontal phase progress indicator."""
    phases = [
        ("analysis", "分析"),
        ("planning", "规划"),
        ("execution", "执行"),
        ("verification", "验证"),
        ("completion", "完成"),
    ]
    phase_order = {p[0]: i for i, p in enumerate(phases)}
    current_idx = phase_order.get(current_phase or "", -1)

    cols = st.columns(len(phases))
    for i, (phase_key, phase_label) in enumerate(phases):
        with cols[i]:
            if i < current_idx:
                st.success(f"✅ {phase_label}")
            elif i == current_idx:
                st.info(f"🔄 {phase_label}")
            else:
                st.caption(f"⏳ {phase_label}")


def render_tool_card(tool: dict) -> None:
    """Render a tool call as a card with risk badge and details."""
    name = tool.get("name", "unknown")
    risk = tool.get("risk_level", "low")
    desc = tool.get("description", "")
    params = tool.get("parameters", {})

    with st.container(border=True):
        col1, col2 = st.columns([3, 1])
        with col1:
            st.markdown(f"**{name}**")
            st.caption(desc)
        with col2:
            render_risk_badge(risk)
        if params:
            with st.expander("参数"):
                st.json(params)
