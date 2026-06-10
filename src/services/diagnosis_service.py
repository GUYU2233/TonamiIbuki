from collections.abc import AsyncIterator
from datetime import datetime, timezone
from random import randint, uniform
from uuid import uuid4

from src.models import (
    ApprovalRequest,
    CaseRecord,
    DiagnosisEvent,
    DiagnosisRequest,
    DiagnosisSession,
    RAGQuery,
    RiskLevel,
    SessionState,
    ToolCall,
)
from src.services.audit_service import audit_service
from src.services.case_service import case_service
from src.services.diagnosis_graph import langgraph_engine
from src.services.ops_service import ops_service
from src.services.rag_service import rag_service
from src.services.sqlite_store import sqlite_store
from src.services.tool_service import tool_registry


class DiagnosisService:
    def __init__(self) -> None:
        self.sessions: dict[str, DiagnosisSession] = {}
        self._load_persisted_sessions()

    def _load_persisted_sessions(self) -> None:
        for item in sqlite_store.list_sessions():
            session = DiagnosisSession.model_validate(item)
            self.sessions[session.session_id] = session

    def _persist(self, session: DiagnosisSession) -> None:
        sqlite_store.upsert_session(session.session_id, session.state, session.model_dump(mode="json"))

    def create(self, request: DiagnosisRequest) -> DiagnosisSession:
        session = DiagnosisSession(alert=request.alert)
        self.sessions[session.session_id] = session
        self._persist(session)
        audit_service.write("agent", "diagnosis.create", session.session_id, request.model_dump(mode="json"))
        return session

    def get(self, session_id: str) -> DiagnosisSession | None:
        session = self.sessions.get(session_id)
        if session:
            return session
        persisted = sqlite_store.get_session(session_id)
        if persisted:
            session = DiagnosisSession.model_validate(persisted)
            self.sessions[session_id] = session
            return session
        return None

    def list(self) -> list[DiagnosisSession]:
        return sorted(self.sessions.values(), key=lambda session: session.updated_at, reverse=True)

    def status(self) -> dict:
        graph_status = langgraph_engine.status()
        return {
            "ready": True,
            "backend": graph_status["backend"],
            "nodes": graph_status["nodes"],
            "active_sessions": len(self.sessions),
            "waiting_approvals": len(
                [session for session in self.sessions.values() if session.state == SessionState.waiting_approval]
            ),
        }

    def _append(self, session: DiagnosisSession, step: str, status: str, message: str, payload: dict | None = None) -> DiagnosisEvent:
        event = DiagnosisEvent(
            session_id=session.session_id,
            step=step,
            status=status,
            message=message,
            payload=payload or {},
        )
        session.events.append(event)
        session.updated_at = datetime.now(timezone.utc)
        self._persist(session)
        return event

    def _select_tool(self, analysis_text: str) -> ToolCall:
        lowered = analysis_text.lower()
        if "error-db-104" in lowered or "连接池" in lowered:
            return tool_registry.enrich("kill_db_session", {"max_sessions": 3})
        if "crashloop" in lowered or "pod" in lowered:
            return tool_registry.enrich("rollback_deployment", {"namespace": "default", "deployment": "app"})
        if "磁盘" in lowered or "disk" in lowered:
            return tool_registry.enrich("cleanup_logs", {"path": "/var/log/nginx", "days": 7})
        return tool_registry.enrich("check_metrics", {"window": "15m"})

    def _needs_approval(self, tool: ToolCall) -> bool:
        order = [RiskLevel.low, RiskLevel.medium, RiskLevel.high, RiskLevel.critical]
        threshold = RiskLevel.high
        return order.index(tool.risk_level) >= order.index(threshold)

    async def run_sync(self, request: DiagnosisRequest) -> DiagnosisSession:
        last_session_id = ""
        async for event in self.run(request):
            last_session_id = event.session_id
        # If LangGraph produced a report without waiting for approval, ensure it's saved
        session = self.sessions.get(last_session_id, None)
        if session and session.state == SessionState.completed and not session.report:
            # Fallback: build report from events
            session.report = self._build_report(session)
            self._persist(session)
        return session

    def evidence_chain(self, session_id: str) -> dict:
        session = self.sessions[session_id]
        return {
            "session_id": session_id,
            "state": session.state,
            "nodes": [
                {"id": event.step, "label": event.step.title(), "status": event.status, "message": event.message}
                for event in session.events
            ],
            "edges": [
                {"source": session.events[idx].step, "target": session.events[idx + 1].step}
                for idx in range(len(session.events) - 1)
            ],
        }

    def report_markdown(self, session_id: str) -> str:
        session = self.sessions[session_id]
        if not session.report:
            session.report = self._build_report(session)
        return session.report

    def convert_to_case(self, session_id: str) -> CaseRecord:
        session = self.sessions[session_id]
        report = self.report_markdown(session_id)
        case = CaseRecord(
            title=f"{session.alert.service} - {session.alert.title}",
            category=session.alert.service or "incident",
            root_cause=self._infer_root_cause(session),
            resolution=report,
            status="draft",
        )
        saved = case_service.add(case)
        audit_service.write("agent", "diagnosis.convert_to_case", session_id, saved.model_dump(mode="json"))
        return saved

    def _infer_root_cause(self, session: DiagnosisSession) -> str:
        for event in session.events:
            if event.step == "diagnosis":
                causes = event.payload.get("probable_causes") or []
                if causes:
                    return "；".join(causes[:3])
        return "基于诊断证据链推断，需人工复核最终根因。"

    def metrics_snapshot(self) -> dict:
        return {
            "cpu_usage": round(uniform(35, 85), 2),
            "memory_usage": round(uniform(45, 88), 2),
            "error_rate": round(uniform(0.1, 9.5), 2),
            "p95_latency_ms": randint(80, 1500),
            "active_sessions": len(self.sessions),
            "waiting_approvals": len([session for session in self.sessions.values() if session.state == SessionState.waiting_approval]),
        }

    async def run(self, request: DiagnosisRequest) -> AsyncIterator[DiagnosisEvent]:
        session = self.create(request)
        yield self._append(session, "monitor", "completed", "Monitor Agent 已接收告警", {"alert": request.alert.model_dump(mode="json")})

        # Delegate to LangGraph engine — pass session_id via a mutable dict
        request_overrides = {"session_id": session.session_id, "alert": request.alert, "auto_execute": request.auto_execute}
        graph_state = await langgraph_engine.arun_from_parts(
            session_id=session.session_id,
            alert=request.alert,
            auto_execute=request.auto_execute,
        )

        # Replay LangGraph events into the session
        for event_dict in graph_state.get("events", [])[1:]:  # skip first (already yielded above)
            yield self._append(
                session,
                event_dict["step"],
                event_dict["status"],
                event_dict["message"],
                event_dict.get("payload", {}),
            )

        # Handle pending approval
        if graph_state.get("pending_approval"):
            try:
                tool = ToolCall.model_validate_json(graph_state.get("tool_json", "{}"))
            except Exception:
                tool = None
            session.pending_tool = tool
            session.state = SessionState.waiting_approval
            self._persist(session)
            return

        # Complete
        session.report = graph_state.get("report", "")
        session.state = SessionState.completed
        self._persist(session)

    def approve(self, session_id: str, request: ApprovalRequest) -> DiagnosisSession:
        session = self.sessions[session_id]
        audit_service.write(request.operator, "diagnosis.approve", session_id, request.model_dump(mode="json"))
        sqlite_store.record_approval(session_id, request.operator, request.approved, request.comment)
        if not request.approved:
            session.state = SessionState.rejected
            self._append(session, "supervisor", "rejected", "人工拒绝高风险操作", request.model_dump(mode="json"))
            self._persist(session)
            return session
        if session.pending_tool:
            result = tool_registry.execute(session.pending_tool, actor=request.operator)
            self._append(session, "execution", "completed", "审批通过后完成工具调用", result.model_dump(mode="json"))
            session.pending_tool = None
        session.report = self._build_report(session)
        session.state = SessionState.completed
        self._persist(session)
        self._append(session, "report", "completed", "Report Agent 生成诊断报告", {"report": session.report})
        return session

    def _build_report(self, session: DiagnosisSession) -> str:
        facts = [f"- **{event.step}** / {event.status}：{event.message}" for event in session.events]
        tool_lines: list[str] = []
        for event in session.events:
            if event.step == "execution":
                payload = event.payload
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
        return (
            "# 诊断报告\n\n"
            f"- 会话：`{session.session_id}`\n"
            f"- 告警：{session.alert.title}\n"
            f"- 服务：{session.alert.service}\n"
            f"- 状态：{session.state}\n\n"
            "## 处理阶段\n"
            + "\n".join(facts)
            + "\n\n## 工具执行证据\n"
            + ("\n".join(tool_lines) if tool_lines else "- 暂无工具执行，可能正在等待审批或仅完成分析。")
            + "\n\n## 相关案例\n"
            + "\n".join(case_lines)
        )


diagnosis_service = DiagnosisService()
