"""TonamiIbuki — 企业 IT 运维 AIOps 智能体前端 (Streamlit)."""

import streamlit as st
import requests
import json
import time
from datetime import datetime, timezone

st.set_page_config(
    page_title="TonamiIbuki · AIOps",
    page_icon="ui/icon.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --- Component imports ---
from ui.components import (
    render_topology,
    render_evidence_timeline,
    render_evidence_summary,
    show_risk_badge,
    render_risk_bar,
    render_phase_indicator,
    render_phase_stepper,
    render_tool_card,
    render_tool_grid,
)

# --- Constants ---
API_BASE = "http://127.0.0.1:8000"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def _api_get(path: str) -> dict | None:
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None


def _api_post(path: str, payload: dict) -> dict | None:
    try:
        r = requests.post(f"{API_BASE}{path}", json=payload, timeout=30)
        if r.status_code == 200:
            return r.json()
        st.error(f"API 错误 ({r.status_code}): {r.text[:300]}")
    except Exception as e:
        st.error(f"连接后端失败: {e}")
    return None


@st.cache_data(ttl=10)
def fetch_status() -> dict:
    return _api_get("/health") or {}


def fetch_tools() -> list[dict]:
    data = _api_get("/api/tools")
    if isinstance(data, dict):
        return data.get("tools", [])
    return []


def fetch_cases(limit: int = 20) -> list[dict]:
    data = _api_get(f"/api/cases?limit={limit}")
    if isinstance(data, dict):
        return data.get("cases", [])
    return []


def fetch_users() -> list[dict]:
    data = _api_get("/api/rbac/users")
    if isinstance(data, dict):
        return data.get("users", [])
    return []


# ---------------------------------------------------------------------------
# sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("ui/icon.png", width=80)
    st.title("TonamiIbuki")
    st.caption("企业 IT 运维 AIOps 智能体")

    status = fetch_status()
    if status:
        st.success(f"✅ 后端在线 · v{status.get('version', '?')}")
    else:
        st.error("❌ 后端离线")

    st.divider()

    page = st.radio(
        "导航",
        [
            "🏠 总览仪表板",
            "🔧 诊断中心",
            "📋 案例库",
            "🛠️ 工具管理",
            "📊 系统拓扑",
            "👥 用户管理",
        ],
    )

    st.divider()
    st.caption(f"© 2024 TonamiIbuki · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

# ---------------------------------------------------------------------------
# Page: 总览仪表板
# ---------------------------------------------------------------------------
if page == "🏠 总览仪表板":
    st.title("🏠 总览仪表板")

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    cases = fetch_cases()
    tools = fetch_tools()
    c1.metric("📋 案例总数", len(cases))
    c2.metric("🛠️ 工具数", len(tools))
    c3.metric("📚 知识条目", status.get("kb_docs", "?"))
    c4.metric("⚙️ LLM", status.get("llm_provider", "?"))
    c5.metric("📦 向量存储", status.get("vector_store", "?"))

    st.divider()

    # Risk summary
    st.subheader("📊 风险概览")
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for case in cases:
        level = case.get("risk_level", "info")
        if level in risk_counts:
            risk_counts[level] += 1
    render_risk_bar(risk_counts)

    # Recent cases
    st.subheader("📋 最近案例")
    if cases:
        for case in cases[:5]:
            with st.expander(
                f"{case.get('id', '?')[:8]} — {case.get('title', '无标题')}  "
                f"({case.get('created_at', '')[:10]})",
            ):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.text(case.get("description", "")[:500])
                with c2:
                    show_risk_badge(case.get("risk_level", "info"))
                    st.caption(f"状态: {case.get('status', '?')}")
                    st.caption(f"阶段: {case.get('phase', '?')}")
    else:
        st.info("暂无案例 — 前往「诊断中心」创建第一个诊断")

    # Phase indicator demo
    st.divider()
    st.subheader("⏳ 系统阶段")
    render_phase_indicator("ANALYSIS")

# ---------------------------------------------------------------------------
# Page: 诊断中心
# ---------------------------------------------------------------------------
elif page == "🔧 诊断中心":
    st.title("🔧 诊断中心")

    # Input form
    with st.form("diagnosis_form"):
        title = st.text_input("标题", placeholder="例如：生产环境 Nginx 502 错误")
        description = st.text_area(
            "故障描述",
            placeholder="请详细描述故障现象、影响范围、发生时间等...",
            height=120,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            severity = st.selectbox("严重程度", ["low", "medium", "high", "critical"], index=1)
        with c2:
            env = st.selectbox("环境", ["production", "staging", "development"], index=0)
        with c3:
            use_rag = st.checkbox("启用 RAG 检索", value=True)

        submitted = st.form_submit_button("🚀 开始诊断", type="primary", use_container_width=True)

    if submitted and title and description:
        with st.spinner("正在诊断..."):
            result = _api_post("/api/diagnose", {
                "title": title,
                "description": description,
                "severity": severity,
                "environment": env,
                "use_rag": use_rag,
            })

        if result:
            st.success("诊断完成！")

            # Phase indicator
            phase = result.get("phase", "ANALYSIS")
            render_phase_indicator(phase)

            st.divider()

            # Root cause
            st.subheader("🔍 根因分析")
            root_cause = result.get("root_cause", {})
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(root_cause.get("summary", "无"))
            with c2:
                show_risk_badge(root_cause.get("risk_level", severity))

            # Evidence timeline
            st.subheader("📋 证据时间线")
            evidence = result.get("evidence", [])
            render_evidence_summary(evidence)
            render_evidence_timeline(evidence, max_items=15)

            # RAG results
            rag_results = result.get("rag_results", [])
            if rag_results:
                st.subheader("📚 知识库匹配")
                for doc in rag_results[:5]:
                    with st.expander(f"📄 {doc.get('title', '?')} (score: {doc.get('score', 0):.2f})"):
                        st.text(doc.get("content", "")[:500])

            # Tool executions
            tool_runs = result.get("tool_runs", [])
            if tool_runs:
                st.subheader("⚡ 工具执行记录")
                for tr in tool_runs:
                    render_tool_card(
                        tool_name=tr.get("tool_name", "unknown"),
                        status=tr.get("status", "pending"),
                        description=tr.get("description", ""),
                        risk_level=tr.get("risk_level", "info"),
                        output=tr.get("output", ""),
                        duration_ms=tr.get("duration_ms"),
                        params=tr.get("params"),
                    )

            # Fix plan
            st.subheader("📋 修复方案")
            fix_plan = result.get("fix_plan", {})
            steps = fix_plan.get("steps", [])
            if steps:
                for i, step in enumerate(steps, 1):
                    st.markdown(f"{i}. {step}")
            else:
                st.text(fix_plan.get("summary", "暂无修复方案"))

            # Report
            report = result.get("report", "")
            if report:
                st.subheader("📝 诊断报告")
                st.markdown(report)

            # Phase stepper for manual advance
            st.divider()
            new_phase = render_phase_stepper(phase)
            if new_phase:
                st.info(f"阶段已切换: {phase} → {new_phase}")
                # In a real app this would call the backend to update

# ---------------------------------------------------------------------------
# Page: 案例库
# ---------------------------------------------------------------------------
elif page == "📋 案例库":
    st.title("📋 案例库")

    cases = fetch_cases()
    if not cases:
        st.info("暂无案例")
    else:
        # Filter bar
        c1, c2 = st.columns(2)
        with c1:
            search = st.text_input("🔍 搜索案例", placeholder="关键词...")
        with c2:
            status_filter = st.selectbox("状态筛选", ["全部", "open", "in_progress", "resolved", "closed"])

        filtered = cases
        if search:
            filtered = [c for c in filtered if search.lower() in json.dumps(c, ensure_ascii=False).lower()]
        if status_filter != "全部":
            filtered = [c for c in filtered if c.get("status") == status_filter]

        st.caption(f"共 {len(filtered)} 条记录")

        for case in filtered:
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.markdown(f"**{case.get('title', '无标题')}**")
                    st.caption(case.get("description", "")[:120])
                with c2:
                    show_risk_badge(case.get("risk_level", "info"))
                with c3:
                    st.caption(f"🕐 {case.get('created_at', '')[:10]}")
                st.divider()

# ---------------------------------------------------------------------------
# Page: 工具管理
# ---------------------------------------------------------------------------
elif page == "🛠️ 工具管理":
    st.title("🛠️ 工具管理")

    tools = fetch_tools()

    # Tool grid
    st.subheader("已注册工具")
    render_tool_grid(tools, cols=2)

    # Tool execution demo
    st.divider()
    st.subheader("⚡ 工具执行测试")

    if tools:
        tool_names = [t.get("name", str(i)) for i, t in enumerate(tools)]
        selected_tool = st.selectbox("选择工具", tool_names)
        test_params = st.text_input("参数 (JSON)", placeholder='{"key": "value"}')

        if st.button("▶️ 执行", use_container_width=True):
            try:
                params = json.loads(test_params) if test_params.strip() else {}
            except json.JSONDecodeError:
                st.error("JSON 格式错误")
                params = {}

            with st.spinner("执行中..."):
                result = _api_post("/api/tools/execute", {
                    "tool_name": selected_tool,
                    "params": params,
                })

            if result:
                render_tool_card(
                    tool_name=result.get("tool_name", selected_tool),
                    status=result.get("status", "success"),
                    description=result.get("description", ""),
                    risk_level=result.get("risk_level", "info"),
                    output=result.get("output", ""),
                    duration_ms=result.get("duration_ms"),
                    params=params,
                    expand=True,
                )

# ---------------------------------------------------------------------------
# Page: 系统拓扑
# ---------------------------------------------------------------------------
elif page == "📊 系统拓扑":
    st.title("📊 系统拓扑")

    st.caption("服务架构与依赖关系")

    # Render default topology
    render_topology()

    st.divider()
    st.subheader("📡 服务端点")

    services = [
        {"name": "FastAPI Backend", "url": "http://127.0.0.1:8000", "status": "✅" if status else "❌"},
        {"name": "Streamlit Frontend", "url": "http://127.0.0.1:8080", "status": "✅"},
        {"name": "ChromaDB", "url": "persistent://data/chroma_db", "status": "✅" if status.get("vector_store") else "❌"},
        {"name": "SQLite", "url": "data/tonamiibuki.db", "status": "✅"},
    ]

    for svc in services:
        c1, c2, c3 = st.columns([2, 3, 1])
        with c1:
            st.markdown(f"**{svc['name']}**")
        with c2:
            st.code(svc["url"], language=None)
        with c3:
            st.markdown(svc["status"])

    # API docs link
    st.divider()
    st.markdown("[📖 OpenAPI Docs](http://127.0.0.1:8000/docs)")

# ---------------------------------------------------------------------------
# Page: 用户管理
# ---------------------------------------------------------------------------
elif page == "👥 用户管理":
    st.title("👥 用户管理")

    users = fetch_users()

    if users:
        st.subheader(f"用户列表 ({len(users)})")
        for u in users:
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                st.markdown(f"**{u.get('username', '?')}**")
            with c2:
                st.caption(f"角色: {u.get('role', '?')}")
            with c3:
                enabled = u.get("enabled", True)
                st.caption("✅ 启用" if enabled else "🚫 禁用")
            with c4:
                st.caption(f"创建: {u.get('created_at', '')[:10]}")
    else:
        st.info("暂无用户 — 请先通过 API 创建用户")

    st.divider()

    # Add user form
    st.subheader("➕ 添加用户")
    with st.form("add_user_form"):
        new_username = st.text_input("用户名")
        new_password = st.text_input("密码", type="password")
        new_role = st.selectbox("角色", ["operator", "viewer"])
        if st.form_submit_button("创建用户", use_container_width=True):
            if new_username and new_password:
                result = _api_post("/api/rbac/users", {
                    "username": new_username,
                    "password": new_password,
                    "role": new_role,
                })
                if result:
                    st.success(f"用户 {new_username} 创建成功")
                    st.rerun()
            else:
                st.warning("请填写用户名和密码")
