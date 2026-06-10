"""服务拓扑图组件 — 基于 Graphviz 的系统架构可视化."""

import streamlit as st
import graphviz

def _build_default_topology() -> graphviz.Digraph:
    dot = graphviz.Digraph("topology", format="svg")
    dot.attr(rankdir="LR", bgcolor="transparent")
    dot.attr("node", shape="box", style="rounded,filled", fontname="sans-serif", fontsize="11")
    dot.attr("edge", fontname="sans-serif", fontsize="9", color="#888888")

    dot.node("user", "用户", shape="plaintext", fontsize="13")
    dot.node("lb", "Nginx LB\n:80/:443", fillcolor="#e3f2fd", color="#1976d2")
    dot.node("api", "FastAPI 后端\n:8000", fillcolor="#e8f5e9", color="#388e3c")
    dot.node("streamlit", "Streamlit 前端\n:8080", fillcolor="#fff3e0", color="#f57c00")
    dot.node("chromadb", "ChromaDB\n向量存储", fillcolor="#fce4ec", color="#c62828")
    dot.node("sqlite", "SQLite\n持久化", fillcolor="#f3e5f5", color="#7b1fa2")
    dot.node("kb", "知识库", fillcolor="#e0f7fa", color="#00695c")
    dot.node("llm", "LLM API\n(OpenAI/Ollama)", fillcolor="#fff9c4", color="#f9a825")

    dot.edge("user", "lb")
    dot.edge("lb", "streamlit", "Web UI")
    dot.edge("lb", "api", "REST API")
    dot.edge("api", "llm", "LLM 调用")
    dot.edge("api", "chromadb", "向量检索")
    dot.edge("api", "sqlite", "状态/案例")
    dot.edge("api", "kb", "RAG 检索")
    dot.edge("streamlit", "api", "API 代理")

    return dot

def render_topology(edges: list[dict] | None = None, nodes: list[dict] | None = None) -> None:
    if nodes is None and edges is None:
        dot = _build_default_topology()
    else:
        dot = graphviz.Digraph("topology", format="svg")
        dot.attr(rankdir="LR", bgcolor="transparent")
        dot.attr("node", shape="box", style="rounded,filled", fontname="sans-serif", fontsize="11")
        dot.attr("edge", fontname="sans-serif", fontsize="9", color="#888888")

        for n in (nodes or []):
            dot.node(
                n["id"],
                n.get("label", n["id"]),
                fillcolor=n.get("fillcolor", "#f5f5f5"),
                color=n.get("color", "#9e9e9e"),
                shape=n.get("shape", "box"),
            )
        for e in (edges or []):
            dot.edge(e["source"], e["target"], label=e.get("label", ""))

    st.graphviz_chart(dot, use_container_width=True)
