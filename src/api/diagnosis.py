from fastapi import APIRouter, HTTPException
from sse_starlette.sse import EventSourceResponse

from src.models import ApprovalRequest, DiagnosisRequest
from src.services.diagnosis_service import diagnosis_service
from src.services.sqlite_store import sqlite_store

router = APIRouter(prefix="/api/diagnosis", tags=["diagnosis"])


@router.post("/run")
async def run_diagnosis(request: DiagnosisRequest) -> EventSourceResponse:
    async def event_generator():
        async for event in diagnosis_service.run(request):
            yield {"event": event.step, "data": event.model_dump_json()}

    return EventSourceResponse(event_generator())


@router.post("/run-sync")
async def run_diagnosis_sync(request: DiagnosisRequest):
    return await diagnosis_service.run_sync(request)


@router.get("/sessions")
def list_sessions():
    return diagnosis_service.list()


@router.get("/{session_id}/status")
def get_status(session_id: str):
    session = diagnosis_service.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    return session


@router.get("/{session_id}/evidence")
def get_evidence(session_id: str):
    if not diagnosis_service.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return diagnosis_service.evidence_chain(session_id)


@router.get("/{session_id}/approvals")
def get_approvals(session_id: str):
    if not diagnosis_service.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return sqlite_store.list_approvals(session_id)


@router.get("/{session_id}/report")
def get_report(session_id: str):
    if not diagnosis_service.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_id": session_id, "report": diagnosis_service.report_markdown(session_id)}


@router.post("/{session_id}/case")
def convert_to_case(session_id: str):
    if not diagnosis_service.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return diagnosis_service.convert_to_case(session_id)


@router.post("/{session_id}/approve")
def approve(session_id: str, request: ApprovalRequest):
    if not diagnosis_service.get(session_id):
        raise HTTPException(status_code=404, detail="session not found")
    return diagnosis_service.approve(session_id, request)
