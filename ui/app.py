"""TonamiIbuki — 企业 IT 运维 AIOps 智能体前端 (Streamlit)."""

import streamlit as st
import requests
import json
import time
import sys, os
from datetime import datetime, timezone

# Ensure /app is on Python path (for Docker)
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
API_BASE = os.getenv("API_BASE", "http://backend:8000")

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
        st.error(f"API error ({r.status_code}): {r.text[:300]}")
    except Exception as e:
        st.error(f"Backend connection failed: {e}")
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
    st.caption("Enterprise IT Operations AIOps Agent")

    status = fetch_status()
    if status:
        st.success(f"Backend Online · v{status.get('version', '?')}")
    else:
        st.error("Backend Offline")

    st.divider()

    page = st.radio(
        "Navigation",
        [
            "Dashboard",
            "Diagnosis",
            "Case Library",
            "Tool Management",
            "System Topology",
            "User Management",
        ],
    )

    st.divider()
    st.caption(f"(c) 2024 TonamiIbuki · {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

# ---------------------------------------------------------------------------
# Page: Dashboard
# ---------------------------------------------------------------------------
if page == "Dashboard":
    st.title("Dashboard")

    # Metrics row
    c1, c2, c3, c4, c5 = st.columns(5)
    cases = fetch_cases()
    tools = fetch_tools()
    c1.metric("Cases", len(cases))
    c2.metric("Tools", len(tools))
    c3.metric("Knowledge Entries", status.get("kb_docs", "?"))
    c4.metric("LLM Provider", status.get("llm_provider", "?"))
    c5.metric("Vector Store", status.get("vector_store", "?"))

    st.divider()

    # Risk summary
    st.subheader("Risk Overview")
    risk_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "info": 0}
    for case in cases:
        level = case.get("risk_level", "info")
        if level in risk_counts:
            risk_counts[level] += 1
    render_risk_bar(risk_counts)

    # Recent cases
    st.subheader("Recent Cases")
    if cases:
        for case in cases[:5]:
            with st.expander(
                f"{case.get('id', '?')[:8]} — {case.get('title', 'Untitled')}  "
                f"({case.get('created_at', '')[:10]})",
            ):
                c1, c2 = st.columns([2, 1])
                with c1:
                    st.text(case.get("description", "")[:500])
                with c2:
                    show_risk_badge(case.get("risk_level", "info"))
                    st.caption(f"Status: {case.get('status', '?')}")
                    st.caption(f"Phase: {case.get('phase', '?')}")
    else:
        st.info("No cases yet — go to Diagnosis to create one")

    # Phase indicator demo
    st.divider()
    st.subheader("System Phase")
    render_phase_indicator("ANALYSIS")

# ---------------------------------------------------------------------------
# Page: Diagnosis
# ---------------------------------------------------------------------------
elif page == "Diagnosis":
    st.title("Diagnosis")

    # Input form
    with st.form("diagnosis_form"):
        title = st.text_input("Title", placeholder="e.g. Production Nginx 502 Error")
        description = st.text_area(
            "Description",
            placeholder="Describe the incident: symptoms, impact scope, occurrence time...",
            height=120,
        )
        c1, c2, c3 = st.columns(3)
        with c1:
            severity = st.selectbox("Severity", ["low", "medium", "high", "critical"], index=1)
        with c2:
            env = st.selectbox("Environment", ["production", "staging", "development"], index=0)
        with c3:
            use_rag = st.checkbox("Enable RAG Retrieval", value=True)

        submitted = st.form_submit_button("Start Diagnosis", type="primary", use_container_width=True)

    if submitted and title and description:
        with st.spinner("Diagnosing..."):
            result = _api_post("/api/diagnose", {
                "title": title,
                "description": description,
                "severity": severity,
                "environment": env,
                "use_rag": use_rag,
            })

        if result:
            st.success("Diagnosis complete.")

            # Phase indicator
            phase = result.get("phase", "ANALYSIS")
            render_phase_indicator(phase)

            st.divider()

            # Root cause
            st.subheader("Root Cause Analysis")
            root_cause = result.get("root_cause", {})
            c1, c2 = st.columns([3, 1])
            with c1:
                st.markdown(root_cause.get("summary", "None"))
            with c2:
                show_risk_badge(root_cause.get("risk_level", severity))

            # Evidence timeline
            st.subheader("Evidence Timeline")
            evidence = result.get("evidence", [])
            render_evidence_summary(evidence)
            render_evidence_timeline(evidence, max_items=15)

            # RAG results
            rag_results = result.get("rag_results", [])
            if rag_results:
                st.subheader("Knowledge Base Matches")
                for doc in rag_results[:5]:
                    with st.expander(f"Doc: {doc.get('title', '?')} (score: {doc.get('score', 0):.2f})"):
                        st.text(doc.get("content", "")[:500])

            # Tool executions
            tool_runs = result.get("tool_runs", [])
            if tool_runs:
                st.subheader("Tool Execution Log")
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
            st.subheader("Remediation Plan")
            fix_plan = result.get("fix_plan", {})
            steps = fix_plan.get("steps", [])
            if steps:
                for i, step in enumerate(steps, 1):
                    st.markdown(f"{i}. {step}")
            else:
                st.text(fix_plan.get("summary", "No remediation plan available"))

            # Report
            report = result.get("report", "")
            if report:
                st.subheader("Diagnosis Report")
                st.markdown(report)

            # Phase stepper for manual advance
            st.divider()
            new_phase = render_phase_stepper(phase)
            if new_phase:
                st.info(f"Phase switched: {phase} -> {new_phase}")

# ---------------------------------------------------------------------------
# Page: Case Library
# ---------------------------------------------------------------------------
elif page == "Case Library":
    st.title("Case Library")

    cases = fetch_cases()
    if not cases:
        st.info("No cases yet")
    else:
        # Filter bar
        c1, c2 = st.columns(2)
        with c1:
            search = st.text_input("Search cases", placeholder="Keyword...")
        with c2:
            status_filter = st.selectbox("Status filter", ["All", "open", "in_progress", "resolved", "closed"])

        filtered = cases
        if search:
            filtered = [c for c in filtered if search.lower() in json.dumps(c, ensure_ascii=False).lower()]
        if status_filter != "All":
            filtered = [c for c in filtered if c.get("status") == status_filter]

        st.caption(f"{len(filtered)} records")

        for case in filtered:
            with st.container():
                c1, c2, c3 = st.columns([3, 1, 1])
                with c1:
                    st.markdown(f"**{case.get('title', 'Untitled')}**")
                    st.caption(case.get("description", "")[:120])
                with c2:
                    show_risk_badge(case.get("risk_level", "info"))
                with c3:
                    st.caption(f"{case.get('created_at', '')[:10]}")
                st.divider()

# ---------------------------------------------------------------------------
# Page: Tool Management
# ---------------------------------------------------------------------------
elif page == "Tool Management":
    st.title("Tool Management")

    tools = fetch_tools()

    # Tool grid
    st.subheader("Registered Tools")
    render_tool_grid(tools, cols=2)

    # Tool execution demo
    st.divider()
    st.subheader("Tool Execution Test")

    if tools:
        tool_names = [t.get("name", str(i)) for i, t in enumerate(tools)]
        selected_tool = st.selectbox("Select tool", tool_names)
        test_params = st.text_input("Parameters (JSON)", placeholder='{"key": "value"}')

        if st.button("Execute", use_container_width=True):
            try:
                params = json.loads(test_params) if test_params.strip() else {}
            except json.JSONDecodeError:
                st.error("Invalid JSON format")
                params = {}

            with st.spinner("Executing..."):
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
# Page: System Topology
# ---------------------------------------------------------------------------
elif page == "System Topology":
    st.title("System Topology")

    st.caption("Service architecture and dependencies")

    # Render default topology
    render_topology()

    st.divider()
    st.subheader("Service Endpoints")

    services = [
        {"name": "FastAPI Backend", "url": API_BASE, "status": "Online" if status else "Offline"},
        {"name": "Streamlit Frontend", "url": "http://127.0.0.1:8080", "status": "Online"},
        {"name": "ChromaDB", "url": "persistent://data/chroma_db", "status": "Online" if status.get("vector_store") else "Offline"},
        {"name": "SQLite", "url": "data/tonamiibuki.db", "status": "Online"},
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
    st.markdown(f"[OpenAPI Docs]({API_BASE}/docs)")

# ---------------------------------------------------------------------------
# Page: User Management
# ---------------------------------------------------------------------------
elif page == "User Management":
    st.title("User Management")

    users = fetch_users()

    if users:
        st.subheader(f"Users ({len(users)})")
        for u in users:
            c1, c2, c3, c4 = st.columns([2, 1, 1, 1])
            with c1:
                st.markdown(f"**{u.get('username', '?')}**")
            with c2:
                st.caption(f"Role: {u.get('role', '?')}")
            with c3:
                enabled = u.get("enabled", True)
                st.caption("Enabled" if enabled else "Disabled")
            with c4:
                st.caption(f"Created: {u.get('created_at', '')[:10]}")
    else:
        st.info("No users — create one via the API first")

    st.divider()

    # Add user form
    st.subheader("Add User")
    with st.form("add_user_form"):
        new_username = st.text_input("Username")
        new_password = st.text_input("Password", type="password")
        new_role = st.selectbox("Role", ["operator", "viewer"])
        if st.form_submit_button("Create User", use_container_width=True):
            if new_username and new_password:
                result = _api_post("/api/rbac/users", {
                    "username": new_username,
                    "password": new_password,
                    "role": new_role,
                })
                if result:
                    st.success(f"User {new_username} created")
                    st.rerun()
            else:
                st.warning("Username and password required")
