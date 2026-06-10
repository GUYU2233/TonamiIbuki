from datetime import datetime
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SessionState(str, Enum):
    running = "running"
    waiting_approval = "waiting_approval"
    completed = "completed"
    failed = "failed"
    rejected = "rejected"


class AlertRequest(BaseModel):
    source: str = "monitor"
    title: str
    severity: Literal["info", "warning", "critical"] = "warning"
    host: str = "unknown"
    service: str = "unknown"
    description: str
    metrics: dict[str, Any] = Field(default_factory=dict)


class AlertAnalysis(BaseModel):
    summary: str
    probable_causes: list[str]
    risk_level: RiskLevel
    recommended_actions: list[str]
    evidence: list[str]


class TicketRequest(BaseModel):
    ticket_id: str = Field(default_factory=lambda: f"T-{uuid4().hex[:8]}")
    title: str
    description: str
    requester: str = "user"
    priority: Literal["P1", "P2", "P3", "P4"] = "P3"


class TicketResponse(BaseModel):
    ticket_id: str
    category: str
    urgency: str
    suggested_resolution: str
    next_steps: list[str]


class RAGQuery(BaseModel):
    query: str
    top_k: int = 5


class RAGDocument(BaseModel):
    doc_id: str
    title: str
    source: str
    content: str
    tags: list[str] = Field(default_factory=list)
    score: float = 0.0


class RAGAnswer(BaseModel):
    answer: str
    citations: list[RAGDocument]


class KnowledgeImportRequest(BaseModel):
    title: str
    content: str
    source: str = "manual"
    tags: list[str] = Field(default_factory=list)


class KnowledgeImportResponse(BaseModel):
    document: RAGDocument
    total_documents: int


class KnowledgeBulkImportRequest(BaseModel):
    directory: str = "data/knowledge"
    include_patterns: list[str] = Field(default_factory=lambda: ["*.md", "*.txt", "*.log", "*.conf"])


class KnowledgeBulkImportResponse(BaseModel):
    imported_documents: int
    total_documents: int
    sources: list[str]


class RAGEvalItem(BaseModel):
    query: str
    expected_doc_ids: list[str]


class RAGEvalResult(BaseModel):
    total: int
    top_k: int
    hit_count: int
    hit_rate: float
    details: list[dict[str, Any]]


class LLMChatRequest(BaseModel):
    prompt: str
    system: str = "你是企业 IT 运维智能体。"
    temperature: float = 0.2


class LLMChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    cached: bool = False


class AuditQuery(BaseModel):
    limit: int = 100
    actor: str | None = None
    action: str | None = None
    target: str | None = None


class DiagnosisRequest(BaseModel):
    alert: AlertRequest
    auto_execute: bool = True


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.low


class ToolResult(BaseModel):
    name: str
    success: bool
    output: str
    risk_level: RiskLevel = RiskLevel.low
    sandbox_log: str | None = None
    rollback_hint: str | None = None


class ApprovalRequest(BaseModel):
    approved: bool
    operator: str = "admin"
    comment: str = ""


class DiagnosisEvent(BaseModel):
    session_id: str
    step: str
    status: str
    message: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DiagnosisSession(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid4().hex)
    state: SessionState = SessionState.running
    alert: AlertRequest
    events: list[DiagnosisEvent] = Field(default_factory=list)
    pending_tool: ToolCall | None = None
    report: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CaseRecord(BaseModel):
    case_id: str = Field(default_factory=lambda: f"C-{uuid4().hex[:8]}")
    title: str
    category: str
    root_cause: str
    resolution: str
    status: Literal["draft", "reviewed", "closed"] = "reviewed"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AuditLog(BaseModel):
    event_id: str = Field(default_factory=lambda: uuid4().hex)
    actor: str
    action: str
    target: str
    detail: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
