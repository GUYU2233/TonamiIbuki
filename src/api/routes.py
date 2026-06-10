from fastapi import APIRouter
from fastapi.responses import JSONResponse

from src.models import (
    AlertRequest,
    AuditQuery,
    CaseRecord,
    KnowledgeBulkImportRequest,
    KnowledgeImportRequest,
    LLMChatRequest,
    RAGEvalItem,
    RAGQuery,
    TicketRequest,
)
from src.services.audit_service import audit_service
from src.services.case_service import case_service
from src.services.ops_service import ops_service
from src.services.rag_service import rag_service
from src.services.diagnosis_service import diagnosis_service
from src.services.tool_service import tool_registry
from src.services.llm_service import llm_service
from src.services.prompt_service import prompt_service
from src.services.vector_index import chroma_vector_index
from src.services.embedding_service import embedding_service
from src.services.reranker_service import reranker_service
from src.services.phasemanager import Phase, PhaseManager, PHASE_OWNERS, PHASE_DESCRIPTIONS
from src.services.rbac_service import rbac_service, Role

router = APIRouter(prefix="/api", tags=["ops"])


@router.post("/alert/analyze")
def analyze_alert(request: AlertRequest):
    return ops_service.analyze_alert(request)


@router.post("/ticket/process")
def process_ticket(request: TicketRequest):
    return ops_service.process_ticket(request)


@router.get("/prompts")
def list_prompts():
    return prompt_service.list_prompts()


@router.get("/prompts/{name}")
def get_prompt(name: str):
    return {"name": name, "content": prompt_service.get(name)}


@router.post("/llm/chat")
def llm_chat(request: LLMChatRequest):
    return llm_service.chat(request)


@router.get("/monitor/metrics")
def monitor_metrics():
    return diagnosis_service.metrics_snapshot()


@router.get("/system/self-check")
def system_self_check():
    metrics = diagnosis_service.metrics_snapshot()
    audits = audit_service.list(limit=5)
    cases = case_service.list()
    return {
        "status": "ok",
        "checks": {
            "api": "ok",
            "rag_documents": len(rag_service.documents),
            "vector_index": chroma_vector_index.status(),
            "embedding": embedding_service.status(),
            "reranker": reranker_service.status(),
            "rbac": rbac_service.status(),
            "case_records": len(cases),
            "recent_audit_logs": len(audits),
            "tool_mode": tool_registry.policy()["mode"],
            "waiting_approvals": metrics["waiting_approvals"],
        },
    }


@router.get("/tools")
def list_tools():
    return tool_registry.list_tools()


@router.get("/tools/policy")
def tool_policy():
    return tool_registry.policy()


@router.get("/topology")
def topology():
    return {
        "nodes": [
            {"id": "user", "label": "用户入口", "group": "edge"},
            {"id": "gateway", "label": "API Gateway", "group": "app"},
            {"id": "order", "label": "order-service", "group": "app"},
            {"id": "redis", "label": "Redis", "group": "cache"},
            {"id": "mysql", "label": "MySQL", "group": "database"},
            {"id": "agent", "label": "TonamiIbuki Agent", "group": "aiops"},
        ],
        "edges": [
            {"source": "user", "target": "gateway"},
            {"source": "gateway", "target": "order"},
            {"source": "order", "target": "redis"},
            {"source": "order", "target": "mysql"},
            {"source": "agent", "target": "order"},
            {"source": "agent", "target": "mysql"},
        ],
    }


@router.post("/rag/query")
def query_rag(request: RAGQuery):
    return rag_service.query(request)


@router.post("/rag/import")
def import_knowledge(request: KnowledgeImportRequest):
    return rag_service.import_document(request)


@router.post("/rag/bulk-import")
def bulk_import_knowledge(request: KnowledgeBulkImportRequest):
    return rag_service.bulk_import(request)


@router.post("/rag/evaluate")
def evaluate_rag(items: list[RAGEvalItem], top_k: int = 5):
    return rag_service.evaluate(items, top_k=top_k)


@router.post("/rag/reload")
def reload_knowledge():
    return {"total_documents": rag_service.reload()}


@router.get("/rag/vector-index")
def vector_index_status():
    return chroma_vector_index.status()


@router.get("/rag/embedding-status")
def embedding_status():
    return embedding_service.status()


@router.get("/rag/reranker-status")
def reranker_status():
    return reranker_service.status()


@router.get("/diagnosis/phases")
def list_phases():
    """Return all diagnosis phases with owner and description for UI display."""
    return {
        "phases": [
            {
                "name": phase.value,
                "owner": PHASE_OWNERS.get(phase, ""),
                "description": PHASE_DESCRIPTIONS.get(phase, ""),
            }
            for phase in Phase
        ]
    }


@router.get("/cases")
def list_cases():
    return case_service.list()


@router.post("/cases")
def add_case(request: CaseRecord):
    return case_service.add(request)


@router.get("/audit/logs")
def list_audit_logs(limit: int = 100, actor: str | None = None, action: str | None = None, target: str | None = None):
    return audit_service.query(limit=limit, actor=actor, action=action, target=target)


# ---------------------------------------------------------------------------
# RBAC endpoints
# ---------------------------------------------------------------------------

@router.get("/rbac/status")
def rbac_status():
    return rbac_service.status()


@router.get("/rbac/users")
def list_rbac_users():
    return rbac_service.list_users()


@router.post("/rbac/users")
def create_rbac_user(request: dict):
    username = request.get("username", "")
    password = request.get("password", "")
    role_str = request.get("role", "viewer")
    try:
        role = Role(role_str)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": f"Invalid role: {role_str}"})
    user = rbac_service.create_user(username, password, role)
    if not user:
        return JSONResponse(status_code=409, content={"error": f"User {username} already exists"})
    return {
        "username": user.username,
        "role": user.role.value,
        "token": user.token_hash,  # plain token returned once
        "created_at": user.created_at,
    }


@router.put("/rbac/users/{username}/role")
def update_rbac_role(username: str, request: dict):
    role_str = request.get("role", "")
    try:
        role = Role(role_str)
    except ValueError:
        return JSONResponse(status_code=400, content={"error": f"Invalid role: {role_str}"})
    if not rbac_service.update_role(username, role):
        return JSONResponse(status_code=404, content={"error": f"User {username} not found"})
    return {"username": username, "role": role.value}


@router.post("/rbac/users/{username}/token")
def regenerate_rbac_token(username: str):
    token = rbac_service.regenerate_token(username)
    if not token:
        return JSONResponse(status_code=404, content={"error": f"User {username} not found"})
    return {"username": username, "token": token}


@router.delete("/rbac/users/{username}")
def delete_rbac_user(username: str):
    if not rbac_service.delete_user(username):
        return JSONResponse(status_code=404, content={"error": f"User {username} not found"})
    return {"deleted": username}
