"""LangGraph-based multi-agent diagnosis engine.
from __future__ import annotations

Replaces the sequential simulation in diagnosis_service.py with a real
StateGraph that supports:
- Conditional routing (human approval for high-risk tools)
- State persistence via MemorySaver (checkpointer)
- Streaming events
"""


import asyncio
import json
from datetime import datetime, timezone
from typing import Annotated, TypedDict

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import add_messages
    _LANGGRAPH_AVAILABLE = True
except ImportError:
    _LANGGRAPH_AVAILABLE = False
    MemorySaver = None  # type: ignore
    StateGraph = None  # type: ignore
    END = None  # type: ignore
    add_messages = lambda *args, **kwargs: []  # type: ignore

from src.models import (
    AlertRequest,
    DiagnosisEvent,
    DiagnosisSession,
    DiagnosisRequest,
    RAGQuery,
    RiskLevel,
    SessionState,
    ToolCall,
    ToolResult,
)
from src.services.audit_service import audit_service
from src.services.ops_service import ops_service
from src.services.rag_service import rag_service
from src.services.tool_service import ToolRegistry

# Lazy singleton
_tool_registry: ToolRegistry | None = None


def _get_tool_registry() -> ToolRegistry:
    global _tool_registry
    if _tool_registry is None:
        _tool_registry = ToolRegistry(simulate=True)
    return _tool_registry
from src.services.phasemanager import Phase, PhaseManager


# ---------------------------------------------------------------------------
# State definition (LangGraph compatible)
# ---------------------------------------------------------------------------

class DiagnosisState(TypedDict):
    session_id: str
    alert_json: str  # JSON serialized AlertRequest
    analysis_json: str
    rag_json: str
    tool_json: str
    result_json: str
    report: str
    events: list[dict]
    state: str
    auto_execute: bool
    pending_approval: bool


# ---------------------------------------------------------------------------
# Node functions
# ---------------------------------------------------------------------------

def _monitor_node(state: DiagnosisState) -> dict:
    alert = AlertRequest.model_validate_json(state["alert_json"])
    events: list[dict] = state.get("events", [])
    pm = PhaseManager()
    pm.jump_to(Phase.ANALYSIS)
    events.append(
        {
            "step": "monitor",
            "status": "completed",
            "message": "Monitor Agent 已接收告警",
            "payload": alert.model_dump(mode="json"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": pm.snapshot(),
        }
    )
    return {"events": events}


def _diagnosis_node(state: DiagnosisState) -> dict:
    alert = AlertRequest.model_validate_json(state["alert_json"])
    analysis = ops_service.analyze_alert(alert)
    events: list[dict] = state.get("events", [])
    pm = PhaseManager()
    pm.jump_to(Phase.PLANNING)
    events.append(
        {
            "step": "diagnosis",
            "status": "completed",
            "message": "Diagnosis Agent 完成根因候选分析",
            "payload": analysis.model_dump(mode="json"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": pm.snapshot(),
        }
    )
    return {"analysis_json": analysis.model_dump_json(), "events": events}


def _rag_node(state: DiagnosisState) -> dict:
    alert = AlertRequest.model_validate_json(state["alert_json"])
    analysis_json = state.get("analysis_json", "{}")
    try:
        analysis = json.loads(analysis_json)
    except json.JSONDecodeError:
        analysis = {}
    causes = " ".join(analysis.get("probable_causes", []))
    query_text = f"{alert.title} {alert.description} {causes}"
    rag = rag_service.query(RAGQuery(query=query_text, top_k=3))
    events: list[dict] = state.get("events", [])
    events.append(
        {
            "step": "rag",
            "status": "completed",
            "message": "RAG Agent 返回处置证据",
            "payload": rag.model_dump(mode="json"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"rag_json": rag.model_dump_json(), "events": events}


def _code_node(state: DiagnosisState) -> dict:
    alert = AlertRequest.model_validate_json(state["alert_json"])
    try:
        analysis = json.loads(state.get("analysis_json", "{}"))
    except json.JSONDecodeError:
        analysis = {}
    tool = _select_tool(f"{alert.title} {alert.description} {' '.join(analysis.get('probable_causes', []))}")
    events: list[dict] = state.get("events", [])
    events.append(
        {
            "step": "code",
            "status": "completed",
            "message": "Code Agent 生成可执行操作",
            "payload": tool.model_dump(mode="json"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"tool_json": tool.model_dump_json(), "events": events}


def _execution_node(state: DiagnosisState) -> dict:
    try:
        tool = ToolCall.model_validate_json(state["tool_json"])
    except Exception:
        return {"result_json": "{}"}
    result = _get_tool_registry().execute(tool.name, tool.arguments)
    events: list[dict] = state.get("events", [])
    pm = PhaseManager()
    pm.jump_to(Phase.EXECUTION)
    events.append(
        {
            "step": "execution",
            "status": "completed",
            "message": "Execution Agent 完成工具调用",
            "payload": result,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": pm.snapshot(),
        }
    )
    return {"result_json": json.dumps(result, default=str), "events": events}


def _report_node(state: DiagnosisState) -> dict:
    events: list[dict] = state.get("events", [])
    report = _build_report_from_state(state, events)
    pm = PhaseManager()
    pm.jump_to(Phase.COMPLETION)
    events.append(
        {
            "step": "report",
            "status": "completed",
            "message": "Report Agent 生成诊断报告",
            "payload": {"report": report},
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "phase": pm.snapshot(),
        }
    )
    return {"report": report, "state": SessionState.completed.value, "events": events}


def _supervisor_hold_node(state: DiagnosisState) -> dict:
    """Placeholder node when waiting for human approval."""
    events: list[dict] = state.get("events", [])
    try:
        tool = ToolCall.model_validate_json(state["tool_json"])
    except Exception:
        tool = None
    events.append(
        {
            "step": "supervisor",
            "status": "waiting_approval",
            "message": "高风险操作已暂停，等待人工审批",
            "payload": tool.model_dump(mode="json") if tool else {},
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {"events": events, "state": SessionState.waiting_approval.value, "pending_approval": True}


# ---------------------------------------------------------------------------
# Conditional edges
# ---------------------------------------------------------------------------

def _needs_approval(state: DiagnosisState) -> str:
    """Decide whether to execute or hold for human approval."""
    auto_execute = state.get("auto_execute", False)
    if not auto_execute:
        return "report"  # skip execution entirely
    try:
        tool = ToolCall.model_validate_json(state.get("tool_json", "{}"))
    except Exception:
        return "report"
    order = [RiskLevel.low, RiskLevel.medium, RiskLevel.high, RiskLevel.critical]
    if order.index(tool.risk_level) >= order.index(RiskLevel.high):
        return "supervisor_hold"
    return "execution"


# ---------------------------------------------------------------------------
# Tool selection (shared logic)
# ---------------------------------------------------------------------------

def _select_tool(analysis_text: str) -> ToolCall:
    lowered = analysis_text.lower()
    if "error-db-104" in lowered or "连接池" in lowered:
        return ToolCall(name="kill_db_session", arguments={"max_sessions": 3}, risk_level=RiskLevel.critical)
    if "crashloop" in lowered or "pod" in lowered:
        return ToolCall(name="rollback_deployment", arguments={"namespace": "default", "deployment": "app"}, risk_level=RiskLevel.high)
    if "磁盘" in lowered or "disk" in lowered:
        return ToolCall(name="cleanup_logs", arguments={"path": "/var/log/nginx", "days": 7}, risk_level=RiskLevel.medium)
    return ToolCall(name="check_metrics", arguments={"window": "15m"}, risk_level=RiskLevel.low)


# ---------------------------------------------------------------------------
# Report building
# ---------------------------------------------------------------------------

def _build_report_from_state(state: DiagnosisState, events: list[dict]) -> str:
    from src.services.case_service import case_service

    facts = [f"- **{e['step']}** / {e['status']}：{e['message']}" for e in events]
    tool_lines: list[str] = []
    for e in events:
        if e["step"] == "execution":
            payload = e.get("payload", {})
            tool_lines.extend(
                [
                    f"- 工具：`{payload.get('name')}`",
                    f"- 结果：{payload.get('output')}",
                    f"- 风险：{payload.get('risk_level')}",
                    f"- 沙箱日志：{payload.get('sandbox_log')}",
                    f"- 回滚建议：{payload.get('rollback_hint') or '无'}",
                ]
            )
    cases = case_service.list()[:2]
    case_lines = [f"- {case.title}：{case.resolution[:120]}..." for case in cases]
    alert = AlertRequest.model_validate_json(state["alert_json"])
    return (
        "# 诊断报告 (LangGraph)\n\n"
        f"- 会话：`{state['session_id']}`\n"
        f"- 告警：{alert.title}\n"
        f"- 服务：{alert.service}\n"
        f"- 状态：{state.get('state', 'unknown')}\n\n"
        "## 处理阶段\n"
        + "\n".join(facts)
        + "\n\n## 工具执行证据\n"
        + ("\n".join(tool_lines) if tool_lines else "- 暂无工具执行，可能正在等待审批或仅完成分析。")
        + "\n\n## 相关案例\n"
        + "\n".join(case_lines)
    )


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------

def build_diagnosis_graph() -> StateGraph:
    """Construct the multi-agent diagnosis StateGraph."""
    workflow = StateGraph(DiagnosisState)

    # Add nodes
    workflow.add_node("monitor", _monitor_node)
    workflow.add_node("diagnosis", _diagnosis_node)
    workflow.add_node("rag", _rag_node)
    workflow.add_node("code", _code_node)
    workflow.add_node("execution", _execution_node)
    workflow.add_node("report", _report_node)
    workflow.add_node("supervisor_hold", _supervisor_hold_node)

    # Edges
    workflow.set_entry_point("monitor")
    workflow.add_edge("monitor", "diagnosis")
    workflow.add_edge("diagnosis", "rag")
    workflow.add_edge("rag", "code")

    # Conditional: auto_execute + risk → execution or supervisor_hold or report
    workflow.add_conditional_edges(
        "code",
        _needs_approval,
        {
            "execution": "execution",
            "supervisor_hold": "supervisor_hold",
            "report": "report",
        },
    )

    workflow.add_edge("execution", "report")
    workflow.add_edge("report", END)
    workflow.add_edge("supervisor_hold", END)

    return workflow


# ---------------------------------------------------------------------------
# LangGraph diagnosis engine (singleton)
# ---------------------------------------------------------------------------

class LangGraphDiagnosisEngine:
    """Wraps the LangGraph StateGraph with compile + streaming + checkpointer."""

    def __init__(self) -> None:
        if not _LANGGRAPH_AVAILABLE:
            self._graph = None
            self._checkpointer = None
            self._compiled = None
        else:
            self._graph = build_diagnosis_graph()
            self._checkpointer = MemorySaver()
            self._compiled = self._graph.compile(checkpointer=self._checkpointer)

    @property
    def compiled(self):
        return self._compiled

    def status(self) -> dict:
        if not _LANGGRAPH_AVAILABLE:
            return {"ready": False, "backend": "langgraph (unavailable)", "nodes": []}
        return {"ready": True, "backend": "langgraph", "nodes": list(self._graph.nodes.keys())}

    async def arun(self, request: DiagnosisRequest) -> dict:
        """Run the graph asynchronously and return final state."""
        return await self.arun_from_parts(
            session_id=request.session_id if hasattr(request, 'session_id') else (request.alert.title[:20] if request.alert else "unknown"),
            alert=request.alert,
            auto_execute=request.auto_execute,
        )

    async def arun_from_parts(self, session_id: str, alert, auto_execute: bool) -> dict:
        """Run the graph with explicit parameters (avoids Pydantic field issues)."""
        if not _LANGGRAPH_AVAILABLE:
            return {
                "session_id": session_id,
                "state": "completed",
                "report": "LangGraph is not installed. Please install langgraph>=0.2.0.",
                "events": [],
            }
        # ... rest of method
        initial_state: DiagnosisState = {
            "session_id": session_id,
            "alert_json": alert.model_dump_json() if hasattr(alert, 'model_dump_json') else alert.model_dump_json(),
            "analysis_json": "",
            "rag_json": "",
            "tool_json": "",
            "result_json": "",
            "report": "",
            "events": [],
            "state": SessionState.running.value,
            "auto_execute": auto_execute,
            "pending_approval": False,
        }
        config = {"configurable": {"thread_id": session_id or "default"}}
        final_state = await self._compiled.ainvoke(initial_state, config)
        return final_state

    def run_sync(self, request: DiagnosisRequest) -> dict:
        """Run the graph synchronously."""
        return asyncio.run(self.arun(request))


langgraph_engine = LangGraphDiagnosisEngine()
