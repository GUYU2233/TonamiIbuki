from src.models import AlertAnalysis, AlertRequest, RiskLevel, TicketRequest, TicketResponse
from src.services.audit_service import audit_service
from src.services.rag_service import rag_service
from src.models import RAGQuery


class OpsService:
    def analyze_alert(self, alert: AlertRequest) -> AlertAnalysis:
        text = f"{alert.title} {alert.description} {alert.service}".lower()
        causes: list[str] = []
        actions: list[str] = []
        risk = RiskLevel.medium
        if "error-db-104" in text or "连接池" in text or "db" in text:
            causes.extend(["数据库连接池耗尽", "慢 SQL 或长事务占用连接", "下游数据库实例容量不足"])
            actions.extend(["检查连接池 active/max 指标", "检索 ERROR-DB-104 处置手册", "必要时审批 kill_db_session"])
            risk = RiskLevel.high
        elif "crashloop" in text or "pod" in text:
            causes.extend(["容器启动失败", "配置或 Secret 缺失", "健康检查配置不合理"])
            actions.extend(["查看 Pod Events", "拉取上一轮容器日志", "必要时审批 rollback_deployment"])
            risk = RiskLevel.high
        elif "磁盘" in text or "disk" in text:
            causes.extend(["日志轮转失效", "临时文件堆积", "删除文件仍被进程占用"])
            actions.extend(["确认目录占用", "归档或清理日志", "修复 logrotate"])
            risk = RiskLevel.medium
        else:
            causes.append("需要结合指标和日志进一步确认")
            actions.append("启动多智能体诊断流程")
        rag = rag_service.query(RAGQuery(query=f"{alert.title} {alert.description}", top_k=3))
        evidence = [doc.title for doc in rag.citations]
        result = AlertAnalysis(
            summary=f"{alert.host}/{alert.service} 出现 {alert.severity} 告警：{alert.title}",
            probable_causes=causes,
            risk_level=risk,
            recommended_actions=actions,
            evidence=evidence,
        )
        audit_service.write("agent", "alert.analyze", alert.host, result.model_dump(mode="json"))
        return result

    def process_ticket(self, ticket: TicketRequest) -> TicketResponse:
        text = f"{ticket.title} {ticket.description}".lower()
        if any(keyword in text for keyword in ["权限", "账号", "password", "login"]):
            category = "access"
            resolution = "按权限工单流程核验申请人、资源范围和审批链。"
        elif any(keyword in text for keyword in ["慢", "latency", "超时", "timeout"]):
            category = "performance"
            resolution = "收集指标、链路追踪和近期变更，优先定位瓶颈服务。"
        else:
            category = "incident"
            resolution = "转入智能体诊断流程并关联告警证据。"
        response = TicketResponse(
            ticket_id=ticket.ticket_id,
            category=category,
            urgency=ticket.priority,
            suggested_resolution=resolution,
            next_steps=["补充影响范围", "关联监控告警", "记录处理证据"],
        )
        audit_service.write("agent", "ticket.process", ticket.ticket_id, response.model_dump(mode="json"))
        return response


ops_service = OpsService()
