import json
from datetime import datetime, timezone
from uuid import uuid4

from config.settings import settings
from src.models import RiskLevel, ToolCall, ToolResult
from src.services.audit_service import audit_service


class ToolRegistry:
    def __init__(self) -> None:
        self.risk_map = {
            "kubectl_describe_pod": RiskLevel.low,
            "kubectl_logs": RiskLevel.low,
            "check_metrics": RiskLevel.low,
            "restart_service": RiskLevel.medium,
            "rollback_deployment": RiskLevel.high,
            "kill_db_session": RiskLevel.high,
            "cleanup_logs": RiskLevel.medium,
        }
        self.descriptions = {
            "kubectl_describe_pod": "查看 Pod 事件和状态，只读操作。",
            "kubectl_logs": "查看容器日志，只读操作。",
            "check_metrics": "读取监控指标，只读操作。",
            "restart_service": "重启应用服务，中风险，会造成短暂抖动。",
            "rollback_deployment": "回滚 Kubernetes Deployment，高风险，需要审批。",
            "kill_db_session": "终止数据库长事务会话，高风险，需要审批。",
            "cleanup_logs": "清理历史日志，中风险，需要保留证据。",
        }
        self.rollback_hints = {
            "restart_service": "若重启后异常，立即回滚到上一实例并恢复流量。",
            "rollback_deployment": "如回滚失败，暂停发布并恢复上一 ReplicaSet。",
            "kill_db_session": "若业务受影响，通知 DBA 检查事务并恢复连接池配置。",
            "cleanup_logs": "如误删日志，优先从归档备份恢复。",
        }

    def enrich(self, name: str, arguments: dict) -> ToolCall:
        return ToolCall(name=name, arguments=arguments, risk_level=self.risk_map.get(name, RiskLevel.low))

    def list_tools(self) -> list[dict]:
        return [
            {"name": name, "risk_level": risk, "description": self.descriptions.get(name, "运维工具")}
            for name, risk in sorted(self.risk_map.items())
        ]

    def policy(self) -> dict:
        return {
            "mode": settings.TOOL_MODE,
            "approval_threshold": settings.RISK_APPROVAL_THRESHOLD,
            "rules": [
                "low 风险工具可自动执行",
                "medium 风险工具记录沙箱日志并可自动执行",
                "high/critical 风险工具必须进入 HITL 审批",
                "所有工具调用写入审计日志和沙箱执行记录",
            ],
        }

    def _write_sandbox_log(self, call: ToolCall, result: str, actor: str) -> str:
        settings.SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
        log_path = settings.SANDBOX_DIR / f"tool-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}.json"
        payload = {
            "actor": actor,
            "tool": call.model_dump(mode="json"),
            "result": result,
            "mode": settings.TOOL_MODE,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        log_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(log_path)

    def execute(self, call: ToolCall, actor: str = "agent") -> ToolResult:
        audit_service.write(actor=actor, action="tool.execute", target=call.name, detail=call.model_dump(mode="json"))
        outputs = {
            "check_metrics": "CPU 62%，内存 71%，错误率 8.4%，数据库连接池 active=100/max=100。",
            "kubectl_describe_pod": "Events: Back-off restarting failed container；Readiness probe failed。",
            "kubectl_logs": "ERROR missing environment variable REDIS_URL。",
            "restart_service": "模拟重启服务完成，实例健康检查通过。",
            "rollback_deployment": "模拟回滚 deployment 至上一稳定版本，Pod 状态 Running。",
            "kill_db_session": "模拟终止 3 个长事务会话，连接池 active 降至 42。",
            "cleanup_logs": "模拟清理 /var/log/nginx 旧日志，释放 18GB。",
        }
        output = outputs.get(call.name, "模拟工具执行完成。")
        sandbox_log = self._write_sandbox_log(call, output, actor)
        return ToolResult(
            name=call.name,
            success=True,
            output=output,
            risk_level=call.risk_level,
            sandbox_log=sandbox_log,
            rollback_hint=self.rollback_hints.get(call.name),
        )


tool_registry = ToolRegistry()
