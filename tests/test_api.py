from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rag_query_returns_citations():
    # Ensure only the base runbooks are loaded (reload resets from KB_PATH which
    # includes bulk imports from previous tests – so reload doesn't help here).
    # Instead we import the exact document we need and query against it.
    client.post("/api/rag/import", json={
        "title": "ERROR-DB-104 数据库连接池耗尽处理",
        "source": "manual/db-104",
        "tags": ["database", "connection-pool"],
        "content": "ERROR-DB-104 表示数据库连接池耗尽。检查连接池配置、慢查询、最大连接数和网络延迟。",
    })
    response = client.post("/api/rag/query", json={"query": "ERROR-DB-104 连接池", "top_k": 3})
    assert response.status_code == 200
    data = response.json()
    assert data["citations"]
    # At least one citation should match the query
    found = any("ERROR-DB-104" in c["content"] or "ERROR-DB-104" in c["title"] for c in data["citations"])
    assert found, f"Expected ERROR-DB-104 in citations, got: {data['citations']}"


def test_alert_analysis():
    response = client.post(
        "/api/alert/analyze",
        json={
            "title": "订单服务 ERROR-DB-104",
            "severity": "critical",
            "host": "prod-app-01",
            "service": "order-service",
            "description": "timeout acquiring connection，连接池耗尽",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["risk_level"] == "high"
    assert data["probable_causes"]


def test_security_headers_on_api():
    response = client.get("/api/cases")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_import_knowledge_and_query():
    # Import a fresh doc and verify it appears in search results
    response = client.post(
        "/api/rag/import",
        json={
            "title": "Nginx 502 网关错误排查",
            "source": "manual/nginx_502.md",
            "tags": ["nginx", "502"],
            "content": "Nginx 502 通常与上游服务不可达、连接超时或反向代理配置错误有关。排查Nginx 502上游不可达方法包括检查PHP-FPM状态和端口监听。",
        },
    )
    assert response.status_code == 200
    assert response.json()["total_documents"] >= 1
    query = client.post("/api/rag/query", json={"query": "Nginx 502 上游不可达", "top_k": 3})
    # At least one of the top results should mention 502
    titles = [c["title"] for c in query.json()["citations"]]
    found = any("502" in t or "Nginx 502" in t for t in titles)
    assert found, f"Expected 502-related citation, got titles: {titles}"


def test_add_case():
    response = client.post(
        "/api/cases",
        json={
            "title": "Redis big key 导致延迟升高",
            "category": "cache",
            "root_cause": "热点 big key 删除阻塞主线程。",
            "resolution": "使用 unlink 分批清理并拆分 key。",
        },
    )
    assert response.status_code == 200
    assert response.json()["title"] == "Redis big key 导致延迟升高"


def test_monitor_metrics_and_topology():
    metrics = client.get("/api/monitor/metrics")
    assert metrics.status_code == 200
    assert "cpu_usage" in metrics.json()
    topology = client.get("/api/topology")
    assert topology.status_code == 200
    assert topology.json()["nodes"]
    assert topology.json()["edges"]


def test_ticket_process():
    response = client.post(
        "/api/ticket/process",
        json={"title": "业务系统 timeout", "description": "接口响应慢", "priority": "P2", "requester": "tester"},
    )
    assert response.status_code == 200
    assert response.json()["category"] in {"performance", "incident"}


def test_run_sync_evidence_and_report():
    response = client.post(
        "/api/diagnosis/run-sync",
        json={
            "alert": {
                "title": "Pod CrashLoopBackOff",
                "severity": "critical",
                "host": "prod-k8s",
                "service": "payment-service",
                "description": "pod CrashLoopBackOff after deployment",
            },
            "auto_execute": True,
        },
    )
    assert response.status_code == 200
    session = response.json()
    evidence = client.get(f"/api/diagnosis/{session['session_id']}/evidence")
    assert evidence.status_code == 200
    assert evidence.json()["nodes"]
    report = client.get(f"/api/diagnosis/{session['session_id']}/report")
    assert report.status_code == 200
    assert "诊断报告" in report.json()["report"]


def test_tools_policy_and_self_check():
    policy = client.get("/api/tools/policy")
    assert policy.status_code == 200
    assert policy.json()["approval_threshold"] == "high"
    tools = client.get("/api/tools")
    assert tools.status_code == 200
    assert any(item["risk_level"] == "high" for item in tools.json())
    self_check = client.get("/api/system/self-check")
    assert self_check.status_code == 200
    assert self_check.json()["status"] == "ok"


def test_convert_diagnosis_to_case():
    response = client.post(
        "/api/diagnosis/run-sync",
        json={
            "alert": {
                "title": "磁盘使用率超过 90%",
                "severity": "warning",
                "host": "prod-log-01",
                "service": "nginx",
                "description": "disk usage high，日志增长过快",
            },
            "auto_execute": True,
        },
    )
    assert response.status_code == 200
    session = response.json()
    case_response = client.post(f"/api/diagnosis/{session['session_id']}/case")
    assert case_response.status_code == 200
    assert case_response.json()["status"] == "draft"


def test_prompts_and_mock_llm():
    prompts = client.get("/api/prompts")
    assert prompts.status_code == 200
    assert "diagnosis" in prompts.json()
    prompt = client.get("/api/prompts/diagnosis")
    assert prompt.status_code == 200
    response = client.post("/api/llm/chat", json={"prompt": "分析 ERROR-DB-104", "system": prompt.json()["content"]})
    assert response.status_code == 200
    assert response.json()["provider"] == "mock"


def test_rag_bulk_import_and_evaluate():
    bulk = client.post("/api/rag/bulk-import", json={"directory": "data/knowledge", "include_patterns": ["*.md"]})
    assert bulk.status_code == 200
    assert bulk.json()["imported_documents"] >= 1
    eval_response = client.post(
        "/api/rag/evaluate?top_k=5",
        json=[{"query": "ERROR-DB-104 连接池耗尽如何处理", "expected_doc_ids": ["kb-db-104"]}],
    )
    assert eval_response.status_code == 200
    assert eval_response.json()["total"] == 1
    assert eval_response.json()["hit_rate"] >= 0


def test_audit_filter():
    client.post("/api/llm/chat", json={"prompt": "审计筛选测试"})
    response = client.get("/api/audit/logs", params={"limit": 10, "action": "http.request"})
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_vector_index_status():
    client.post("/api/rag/reload")
    response = client.get("/api/rag/vector-index")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["backend"] == "chromadb"


def test_embedding_and_reranker_status():
    # Embedding status
    emb = client.get("/api/rag/embedding-status")
    assert emb.status_code == 200
    emb_data = emb.json()
    assert emb_data["ready"] is True
    assert emb_data["provider"] in ("mock", "openai", "ollama")
    assert emb_data["dim"] > 0
    # Reranker status
    rerank = client.get("/api/rag/reranker-status")
    assert rerank.status_code == 200
    rerank_data = rerank.json()
    assert rerank_data["ready"] is True
    assert rerank_data["provider"] in ("mock", "cross-encoder")
    # Self-check includes both
    sc = client.get("/api/system/self-check")
    assert sc.status_code == 200
    checks = sc.json()["checks"]
    assert "embedding" in checks
    assert "reranker" in checks


def test_approval_records_are_persisted():
    response = client.post(
        "/api/diagnosis/run-sync",
        json={
            "alert": {
                "title": "订单服务 ERROR-DB-104",
                "severity": "critical",
                "host": "prod-db",
                "service": "order-service",
                "description": "ERROR-DB-104 timeout acquiring connection",
            },
            "auto_execute": True,
        },
    )
    session = response.json()
    approve = client.post(
        f"/api/diagnosis/{session['session_id']}/approve",
        json={"approved": False, "operator": "tester", "comment": "unit test reject"},
    )
    assert approve.status_code == 200
    approvals = client.get(f"/api/diagnosis/{session['session_id']}/approvals")
    assert approvals.status_code == 200
    assert approvals.json()[0]["operator"] == "tester"


def test_rbac_users_and_auth():
    # Clean up any leftover from previous runs
    client.delete("/api/rbac/users/test_rbac")

    # Status
    status = client.get("/api/rbac/status")
    assert status.status_code == 200
    assert status.json()["ready"] is True
    assert status.json()["users"] >= 1

    # List users
    users = client.get("/api/rbac/users")
    assert users.status_code == 200
    assert any(u["username"] == "admin" for u in users.json())

    # Create user
    new_user = client.post(
        "/api/rbac/users",
        json={"username": "test_rbac", "password": "test123", "role": "viewer"},
    )
    assert new_user.status_code == 200
    assert new_user.json()["role"] == "viewer"
    token = new_user.json()["token"]
    assert len(token) > 10

    # Auth with token
    users2 = client.get("/api/rbac/users", headers={"X-API-Token": token})
    assert users2.status_code == 200

    # Duplicate user
    dup = client.post(
        "/api/rbac/users",
        json={"username": "test_rbac", "password": "test123", "role": "viewer"},
    )
    assert dup.status_code == 409

    # Update role
    updated = client.put(
        "/api/rbac/users/test_rbac/role",
        json={"role": "operator"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "operator"

    # Regenerate token
    new_token = client.post("/api/rbac/users/test_rbac/token")
    assert new_token.status_code == 200
    assert new_token.json()["token"] != token

    # Delete user
    deleted = client.delete("/api/rbac/users/test_rbac")
    assert deleted.status_code == 200

    # Self-check includes RBAC
    sc = client.get("/api/system/self-check")
    assert sc.status_code == 200
    assert "rbac" in sc.json()["checks"]
