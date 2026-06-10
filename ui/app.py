"""TonamiIbuki 企业 IT 运维智能体系统 – Streamlit 前端."""

import json
from datetime import datetime

import requests
import streamlit as st

from ui.components import (
    render_evidence_timeline,
    render_phase_indicator,
    render_risk_badge,
    render_tool_card,
    render_topology_graph,
)

st.set_page_config(page_title="TonamiIbuki企业 IT 运维智能体系统", layout="wide")
st.title("TonamiIbuki企业 IT 运维智能体系统")

API_BASE = st.sidebar.text_input("API 地址", "http://127.0.0.1:8000")
API_TOKEN = st.sidebar.text_input("API Token", "", type="password")


def headers() -> dict[str, str]:
    return {"X-API-Token": API_TOKEN} if API_TOKEN else {}


def api_get(path: str, **params):
    return requests.get(f"{API_BASE}{path}", params=params, headers=headers(), timeout=20)


def api_post(path: str, payload: dict | None = None):
    return requests.post(f"{API_BASE}{path}", json=payload or {}, headers=headers(), timeout=60)


# ---------------------------------------------------------------------------
# Dashboard runtime fragment
# ---------------------------------------------------------------------------

def render_runtime_status() -> None:
    health = api_get("/health").json()
    metrics = api_get("/api/monitor/metrics").json()
    sessions = api_get("/api/diagnosis/sessions").json()
    cases = api_get("/api/cases").json()
    waiting = [item for item in sessions if item["state"] == "waiting_approval"]
    st.caption(f"运行态势数据最后刷新：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("服务状态", health["status"])
    col2.metric("CPU", f"{metrics['cpu_usage']}%")
    col3.metric("P95 延迟", f"{metrics['p95_latency_ms']} ms")
    col4.metric("待审批", len(waiting))
    col5.metric("案例数量", len(cases))
    st.markdown("### 最近诊断")
    st.dataframe(
        [
            {
                "session_id": item["session_id"],
                "state": item["state"],
                "alert": item["alert"]["title"],
                "updated_at": item["updated_at"],
            }
            for item in sessions[:10]
        ],
        use_container_width=True,
    )


@st.fragment(run_every="5s")
def render_runtime_status_5s() -> None:
    render_runtime_status()


@st.fragment(run_every="10s")
def render_runtime_status_10s() -> None:
    render_runtime_status()


@st.fragment(run_every="30s")
def render_runtime_status_30s() -> None:
    render_runtime_status()


def render_runtime_status_panel(auto_refresh: bool, refresh_interval: int) -> None:
    if not auto_refresh:
        render_runtime_status()
    elif refresh_interval <= 5:
        render_runtime_status_5s()
    elif refresh_interval <= 10:
        render_runtime_status_10s()
    else:
        render_runtime_status_30s()


# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------

page = st.sidebar.radio(
    "功能",
    ["驾驶舱", "告警诊断", "审批队列", "工单处理", "知识库", "LLM与Prompt", "案例库", "安全策略", "审计日志", "用户管理"],
)

if page == "驾驶舱":
    auto_refresh = st.sidebar.checkbox("运行态势数据自动刷新", True)
    refresh_interval = st.sidebar.select_slider("运行态势刷新档位", options=[5, 10, 30], value=5)
else:
    auto_refresh = False
    refresh_interval = 5

# =========================================================================
# 驾驶舱
# =========================================================================
if page == "驾驶舱":
    st.subheader("系统运行态势")
    st.caption(
        f"仅运行态势数据局部刷新；自动刷新：{'开启' if auto_refresh else '关闭'}；"
        f"当前间隔档位：{'5s' if refresh_interval <= 5 else '10s' if refresh_interval <= 10 else '30s'}"
    )
    render_runtime_status_panel(auto_refresh, refresh_interval)
    st.markdown("### 业务拓扑")
    topology = api_get("/api/topology").json()
    render_topology_graph(topology["nodes"], topology["edges"])
    st.markdown("### 系统自检")
    self_check = api_get("/api/system/self-check").json()
    st.json(self_check)

# =========================================================================
# 告警诊断
# =========================================================================
elif page == "告警诊断":
    st.subheader("多智能体诊断演示")
    with st.form("alert"):
        title = st.text_input("告警标题", "订单服务 ERROR-DB-104 连接池耗尽")
        host = st.text_input("主机/集群", "prod-app-01")
        service = st.text_input("服务", "order-service")
        severity = st.selectbox("级别", ["warning", "critical", "info"], index=1)
        description = st.text_area("描述", "接口超时升高，日志出现 ERROR-DB-104 timeout acquiring connection")
        auto_execute = st.checkbox("自动执行低风险动作，高风险进入审批", True)
        submitted = st.form_submit_button("启动完整诊断")
    if submitted:
        payload = {
            "alert": {
                "title": title,
                "host": host,
                "service": service,
                "severity": severity,
                "description": description,
            },
            "auto_execute": auto_execute,
        }
        session = api_post("/api/diagnosis/run-sync", payload).json()
        st.session_state["last_session_id"] = session["session_id"]
        st.success(f"诊断会话已创建：{session['session_id']}，状态：{session['state']}")

        # Phase indicator
        render_phase_indicator()

        st.markdown("### 阶段事件")
        render_evidence_timeline(session["events"])

        # Evidence chain topology
        evidence = api_get(f"/api/diagnosis/{session['session_id']}/evidence").json()
        st.markdown("### 证据链")
        render_topology_graph(evidence["nodes"], evidence["edges"])

        # Report
        report = api_get(f"/api/diagnosis/{session['session_id']}/report").json()["report"]
        col_report, col_case = st.columns([1, 1])
        col_report.download_button(
            "下载诊断报告",
            report,
            file_name=f"diagnosis-{session['session_id']}.md",
        )
        if col_case.button("沉淀为案例", key=f"case-{session['session_id']}"):
            st.json(api_post(f"/api/diagnosis/{session['session_id']}/case").json())
        st.markdown(report)

# =========================================================================
# 审批队列
# =========================================================================
elif page == "审批队列":
    st.subheader("HITL 高风险操作审批")
    sessions = api_get("/api/diagnosis/sessions").json()
    waiting = [item for item in sessions if item["state"] == "waiting_approval"]
    if not waiting:
        st.success("当前没有待审批操作。")
    for session in waiting:
        st.markdown(f"### {session['alert']['title']}")
        tool = session.get("pending_tool", {})
        if tool:
            render_tool_card(tool)
        else:
            st.code(json.dumps(session["pending_tool"], ensure_ascii=False, indent=2))
        comment = st.text_input("审批意见", key=f"comment-{session['session_id']}")
        col1, col2 = st.columns(2)
        if col1.button("批准", key=f"approve-{session['session_id']}"):
            result = api_post(
                f"/api/diagnosis/{session['session_id']}/approve",
                {"approved": True, "operator": "admin", "comment": comment},
            ).json()
            st.success("已批准并执行")
            st.markdown(result.get("report", ""))
        if col2.button("拒绝", key=f"reject-{session['session_id']}"):
            st.json(
                api_post(
                    f"/api/diagnosis/{session['session_id']}/approve",
                    {"approved": False, "operator": "admin", "comment": comment},
                ).json()
            )

# =========================================================================
# 工单处理
# =========================================================================
elif page == "工单处理":
    st.subheader("ITSM 工单智能处理")
    with st.form("ticket"):
        title = st.text_input("工单标题", "业务系统访问超时")
        requester = st.text_input("申请人", "ops-user")
        priority = st.selectbox("优先级", ["P1", "P2", "P3", "P4"], index=2)
        description = st.text_area("工单描述", "用户反馈订单接口响应慢并偶发 timeout。")
        submitted = st.form_submit_button("分析工单")
    if submitted:
        data = api_post(
            "/api/ticket/process",
            {"title": title, "requester": requester, "priority": priority, "description": description},
        ).json()
        st.json(data)

# =========================================================================
# 知识库
# =========================================================================
elif page == "知识库":
    tab_query, tab_import, tab_bulk, tab_eval = st.tabs(["检索问答", "导入手册", "批量导入", "RAG评测"])
    with tab_query:
        query = st.text_input("问题", "ERROR-DB-104 如何处理？")
        if st.button("检索"):
            data = api_post("/api/rag/query", {"query": query, "top_k": 5}).json()
            st.markdown(data["answer"])
            for doc in data["citations"]:
                st.caption(f"{doc['title']} · {doc['source']} · score={doc['score']}")
                st.write(doc["content"])
    with tab_import:
        with st.form("kb-import"):
            title = st.text_input("标题")
            source = st.text_input("来源", "manual")
            tags = st.text_input("标签，逗号分隔")
            content = st.text_area("内容", height=200)
            submitted = st.form_submit_button("导入并重建索引")
        if submitted:
            payload = {
                "title": title,
                "source": source,
                "tags": [tag.strip() for tag in tags.split(",") if tag.strip()],
                "content": content,
            }
            st.json(api_post("/api/rag/import", payload).json())
    with tab_bulk:
        directory = st.text_input("文档目录", "data/knowledge")
        patterns = st.text_input("文件模式", "*.md,*.txt,*.log,*.conf")
        if st.button("批量导入并分块"):
            st.json(
                api_post(
                    "/api/rag/bulk-import",
                    {
                        "directory": directory,
                        "include_patterns": [p.strip() for p in patterns.split(",") if p.strip()],
                    },
                ).json()
            )
    with tab_eval:
        st.info("使用内置评测集验证 Top-K 命中率，也可通过 API 传入自定义评测项。")
        if st.button("运行默认 RAG 评测"):
            eval_items = [
                {"query": "ERROR-DB-104 连接池耗尽如何处理", "expected_doc_ids": ["kb-db-104"]},
                {"query": "Pod CrashLoopBackOff 怎么排查", "expected_doc_ids": ["kb-k8s-crashloop"]},
                {"query": "磁盘使用率超过 90% 日志清理", "expected_doc_ids": ["kb-disk-90"]},
            ]
            st.json(api_post("/api/rag/evaluate?top_k=5", eval_items).json())

# =========================================================================
# LLM与Prompt
# =========================================================================
elif page == "LLM与Prompt":
    st.subheader("LLM Provider 与 Prompt 模板")
    prompts = api_get("/api/prompts").json()
    selected = st.selectbox("Prompt 模板", prompts)
    if selected:
        prompt_content = api_get(f"/api/prompts/{selected}").json()["content"]
        st.text_area("系统 Prompt", prompt_content, height=180)
    user_prompt = st.text_area("用户输入", "请分析 ERROR-DB-104 连接池耗尽告警并给出处置建议。")
    if st.button("调用 LLM"):
        st.json(
            api_post(
                "/api/llm/chat",
                {
                    "system": prompt_content if selected else "你是企业 IT 运维智能体。",
                    "prompt": user_prompt,
                },
            ).json()
        )

# =========================================================================
# 案例库
# =========================================================================
elif page == "案例库":
    tab_list, tab_add = st.tabs(["案例列表", "新增案例"])
    with tab_list:
        for case in api_get("/api/cases").json():
            st.markdown(f"### {case['title']}")
            st.write(case["root_cause"])
            st.success(case["resolution"])
    with tab_add:
        with st.form("case-add"):
            title = st.text_input("案例标题")
            category = st.text_input("分类", "incident")
            root_cause = st.text_area("根因")
            resolution = st.text_area("解决方案")
            submitted = st.form_submit_button("保存案例")
        if submitted:
            st.json(
                api_post(
                    "/api/cases",
                    {"title": title, "category": category, "root_cause": root_cause, "resolution": resolution},
                ).json()
            )

# =========================================================================
# 安全策略
# =========================================================================
elif page == "安全策略":
    st.subheader("工具风险策略与沙箱说明")
    policy = api_get("/api/tools/policy").json()
    tools = api_get("/api/tools").json()
    st.markdown("### 执行策略")
    st.json(policy)
    st.markdown("### 工具目录")
    for tool in tools:
        render_tool_card(tool)
    st.info("高风险工具会进入 HITL 审批；所有工具执行都会写入审计日志和 data/sandbox 下的沙箱记录。")

# =========================================================================
# 审计日志
# =========================================================================
elif page == "审计日志":
    st.subheader("审计日志")
    col1, col2, col3, col4 = st.columns(4)
    limit = col1.number_input("数量", min_value=10, max_value=1000, value=100, step=10)
    actor = col2.text_input("Actor 包含")
    action = col3.text_input("Action 包含")
    target = col4.text_input("Target 包含")
    params = {"limit": int(limit)}
    if actor:
        params["actor"] = actor
    if action:
        params["action"] = action
    if target:
        params["target"] = target
    logs = api_get("/api/audit/logs", **params).json()
    st.dataframe(logs, use_container_width=True)
    st.code(json.dumps(logs, ensure_ascii=False, indent=2))

# =========================================================================
# 用户管理 (RBAC)
# =========================================================================
elif page == "用户管理":
    st.subheader("RBAC 用户与权限管理")
    status = api_get("/api/rbac/status").json()
    st.metric("用户总数", status["users"])
    col_admin, col_op, col_viewer = st.columns(3)
    col_admin.metric("管理员", status["roles"].get("admin", 0))
    col_op.metric("运维人员", status["roles"].get("operator", 0))
    col_viewer.metric("只读用户", status["roles"].get("viewer", 0))

    st.markdown("### 用户列表")
    users = api_get("/api/rbac/users").json()
    st.dataframe(users, use_container_width=True)

    st.markdown("### 新建用户")
    with st.form("rbac-create"):
        new_username = st.text_input("用户名", key="rbac-new-user")
        new_password = st.text_input("密码", type="password", key="rbac-new-pass")
        new_role = st.selectbox("角色", ["viewer", "operator", "admin"], key="rbac-new-role")
        submitted = st.form_submit_button("创建用户")
    if submitted and new_username:
        result = api_post(
            "/api/rbac/users",
            {"username": new_username, "password": new_password, "role": new_role},
        )
        if result.status_code == 200:
            data = result.json()
            st.success(f"用户 {data['username']} 创建成功！Token: `{data['token']}`")
            st.warning("请立即保存 Token，仅显示一次！")
        else:
            st.error(result.json().get("error", "创建失败"))

    st.markdown("### 管理用户")
    selected_user = st.selectbox("选择用户", [u["username"] for u in users], key="rbac-select")
    if selected_user:
        col_role, col_token, col_delete = st.columns(3)
        with col_role:
            new_role_val = st.selectbox("修改角色", ["viewer", "operator", "admin"], key="rbac-role-update")
            if st.button("更新角色", key="rbac-btn-role"):
                r = requests.put(
                    f"{API_BASE}/api/rbac/users/{selected_user}/role",
                    json={"role": new_role_val},
                    headers=headers(),
                    timeout=10,
                )
                st.json(r.json())
        with col_token:
            if st.button("重新生成 Token", key="rbac-btn-token"):
                r = requests.post(
                    f"{API_BASE}/api/rbac/users/{selected_user}/token",
                    headers=headers(),
                    timeout=10,
                )
                data = r.json()
                st.warning(f"新 Token: `{data.get('token', 'N/A')}`")
        with col_delete:
            if st.button("删除用户", key="rbac-btn-delete", type="secondary"):
                r = requests.delete(
                    f"{API_BASE}/api/rbac/users/{selected_user}",
                    headers=headers(),
                    timeout=10,
                )
                st.json(r.json())
