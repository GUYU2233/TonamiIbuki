"""API routes — TonamiIbuki AIOps backend."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, Request, Query
from fastapi.responses import JSONResponse

from src.models import (
    DiagnosisRequest,
    UserCreate,
    TokenRequest,
    RAGQuery,
    CaseRecord,
)
from src.services.llm_service import LLMService
from src.services.rag_service import RAGService
from src.services.diagnosis_service import DiagnosisService
from src.services.tool_service import ToolRegistry
from src.services.case_service import CaseService
from src.services.audit_service import AuditService
from src.services.phasemanager import PhaseManager
from src.services.rbac_service import RBACService
from src.services.evaluation_service import EvaluationService

router = APIRouter(prefix="/api")

# ---------------------------------------------------------------------------
# Service singletons (lazy init)
# ---------------------------------------------------------------------------
_services: dict = {}


def _svc(name: str):
    if name not in _services:
        if name == "llm":
            _services[name] = LLMService()
        elif name == "rag":
            _services[name] = RAGService()
        elif name == "diagnosis":
            _services[name] = DiagnosisService()
        elif name == "tools":
            _services[name] = ToolRegistry(simulate=True)
        elif name == "cases":
            _services[name] = CaseService()
        elif name == "audit":
            _services[name] = AuditService()
        elif name == "phase":
            _services[name] = PhaseManager()
        elif name == "rbac":
            _services[name] = RBACService()
        elif name == "evaluation":
            _services[name] = EvaluationService()
    return _services[name]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@router.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


# ---------------------------------------------------------------------------
# Diagnosis
# ---------------------------------------------------------------------------
@router.post("/diagnose")
async def diagnose(req: DiagnosisRequest):
    audit = _svc("audit")
    audit.write("system", "diagnosis_start", req.alert.title)
    try:
        result = await _svc("diagnosis").run_sync(req)
        audit.write("system", "diagnosis_complete", result.session_id)
        return result.model_dump(mode="json")
    except Exception as e:
        audit.write("system", "diagnosis_error", str(e))
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
@router.get("/tools")
async def list_tools():
    return {"tools": _svc("tools").list_tools()}


@router.post("/tools/execute")
async def execute_tool(req: Request):
    body = await req.json()
    result = _svc("tools").execute(body.get("tool_name", ""), body.get("params", {}))
    _svc("audit").write("system", "tool_execute", body.get("tool_name", ""))
    return result


@router.post("/tools/kubectl/{action}")
async def kubectl_action(action: str, req: Request):
    body = await req.json() if await req.body() else {}
    result = _svc("tools").execute(f"kubectl_{action}", body.get("params", body))
    _svc("audit").write("system", "tool_execute", f"kubectl_{action}")
    return result


@router.post("/tools/ansible/{action}")
async def ansible_action(action: str, req: Request):
    body = await req.json() if await req.body() else {}
    result = _svc("tools").execute(f"ansible_{action}", body.get("params", body))
    _svc("audit").write("system", "tool_execute", f"ansible_{action}")
    return result


@router.post("/tools/ssh/{action}")
async def ssh_action(action: str, req: Request):
    body = await req.json() if await req.body() else {}
    result = _svc("tools").execute(f"ssh_{action}", body.get("params", body))
    _svc("audit").write("system", "tool_execute", f"ssh_{action}")
    return result


# ---------------------------------------------------------------------------
# Cases
# ---------------------------------------------------------------------------
@router.get("/cases")
async def list_cases(limit: int = Query(20, ge=1, le=100)):
    cases = _svc("cases").list()
    return {"cases": cases[:limit]}


@router.post("/cases")
async def create_case(req: Request):
    body = await req.json()
    from uuid import uuid4
    record = CaseRecord(
        title=body.get("title", ""),
        category=body.get("category", "general"),
        root_cause=body.get("root_cause", body.get("description", "")),
        resolution=body.get("resolution", ""),
        status=body.get("status", "draft"),
    )
    # Preserve case_id if provided, otherwise auto-generated
    if body.get("id"):
        record.case_id = body["id"]
    case = _svc("cases").add(record)
    _svc("audit").write("system", "case_create", case.case_id)
    return case.model_dump(mode="json")


@router.get("/cases/{case_id}")
async def get_case(case_id: str):
    cases = _svc("cases").list()
    for c in cases:
        if c.case_id == case_id:
            return c.model_dump(mode="json")
    raise HTTPException(status_code=404, detail="Case not found")


# ---------------------------------------------------------------------------
# RAG / Knowledge base
# ---------------------------------------------------------------------------
@router.get("/rag/search")
async def rag_search(q: str = Query(..., min_length=1), top_k: int = Query(5, ge=1, le=20)):
    result = _svc("rag").query(RAGQuery(query=q, top_k=top_k))
    citations = result.citations if hasattr(result, "citations") else []
    return {"query": q, "results": [c.model_dump(mode="json") for c in citations]}


@router.get("/rag/status")
async def rag_status():
    return _svc("rag").get_status()


# ---------------------------------------------------------------------------
# Embedding & Reranker
# ---------------------------------------------------------------------------
@router.get("/embedding/status")
async def embedding_status():
    from src.services.embedding_service import EmbeddingService
    svc = EmbeddingService()
    return svc.status()


@router.get("/reranker/status")
async def reranker_status():
    from src.services.reranker_service import RerankerService
    svc = RerankerService()
    return svc.status()


# ---------------------------------------------------------------------------
# Phase management
# ---------------------------------------------------------------------------
@router.get("/phases")
async def get_phases():
    pm: PhaseManager = _svc("phase")
    return pm.snapshot()


@router.post("/phases/advance")
async def advance_phase(req: Request):
    from src.services.phasemanager import Phase
    body = await req.json()
    target = body.get("phase", "")
    pm: PhaseManager = _svc("phase")
    try:
        # Accept both string and Phase enum (case-insensitive)
        if isinstance(target, str):
            target_lower = target.lower()
            # Find matching phase by lowercased value
            target_phase = None
            for p in Phase:
                if p.value == target_lower:
                    target_phase = p
                    break
            if target_phase is None:
                raise ValueError(f"Unknown phase: {target}")
        else:
            target_phase = target
        pm.jump_to(target_phase)
        _svc("audit").write("system", "phase_advance", target_phase.value)
        return pm.snapshot()
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------
@router.get("/rbac/users")
async def list_users():
    return {"users": _svc("rbac").list_users()}


@router.post("/rbac/users")
async def create_user(req: UserCreate):
    from src.services.rbac_service import Role
    try:
        role = Role(req.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {req.role}")
    user = _svc("rbac").create_user(req.username, req.password, role)
    if not user:
        return JSONResponse(status_code=409, content={"detail": "User already exists"})
    _svc("audit").write("system", "user_create", req.username)
    return {"username": user.username, "role": user.role.value, "token": user.token_hash}


@router.delete("/rbac/users/{username}")
async def delete_user(username: str):
    ok = _svc("rbac").delete_user(username)
    if not ok:
        raise HTTPException(status_code=404, detail="User not found")
    _svc("audit").write("system", "user_delete", username)
    return {"detail": "deleted"}


@router.post("/rbac/token")
async def create_token(req: TokenRequest):
    token = _svc("rbac").create_token(req.username, req.password)
    if not token:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return {"token": token}


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------
@router.get("/evaluation")
async def run_evaluation():
    metrics = await _svc("evaluation").evaluate()
    return {"summary": metrics.summary, "queries": metrics.queries}


@router.get("/evaluation/queries")
async def list_eval_queries():
    queries = _svc("evaluation").load_test_queries()
    return {"queries": queries, "count": len(queries)}


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------
@router.get("/audit")
async def list_audit(limit: int = Query(50, ge=1, le=200)):
    return {"entries": [e.model_dump(mode="json") for e in _svc("audit").list(limit)]}
