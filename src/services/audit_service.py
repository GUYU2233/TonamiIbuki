import json
from typing import Any

from config.settings import settings
from src.models import AuditLog


class AuditService:
    def write(self, actor: str, action: str, target: str, detail: dict[str, Any] | None = None) -> AuditLog:
        log = AuditLog(actor=actor, action=action, target=target, detail=detail or {})
        settings.AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with settings.AUDIT_LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(log.model_dump_json() + "\n")
        return log

    def list(self, limit: int = 100) -> list[AuditLog]:
        if not settings.AUDIT_LOG_PATH.exists():
            return []
        lines = settings.AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines()[-limit:]
        return [AuditLog.model_validate(json.loads(line)) for line in lines if line.strip()]

    def query(self, limit: int = 100, actor: str | None = None, action: str | None = None, target: str | None = None) -> list[AuditLog]:
        logs = self.list(limit=10000)
        if actor:
            logs = [log for log in logs if actor.lower() in log.actor.lower()]
        if action:
            logs = [log for log in logs if action.lower() in log.action.lower()]
        if target:
            logs = [log for log in logs if target.lower() in log.target.lower()]
        return logs[-limit:]


audit_service = AuditService()
