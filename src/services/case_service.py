from src.models import CaseRecord
from src.services.sqlite_store import sqlite_store


SEED_CASES = [
    CaseRecord(
        title="订单服务 ERROR-DB-104 连接池耗尽",
        category="database",
        root_cause="慢 SQL 导致连接占满，应用连接池无法及时释放。",
        resolution="临时扩容连接池并 kill 长事务，随后增加索引 idx_order_created_at。",
    ),
    CaseRecord(
        title="Kubernetes Pod CrashLoopBackOff",
        category="container",
        root_cause="新版本环境变量 REDIS_URL 缺失，启动健康检查失败。",
        resolution="回滚版本并补齐 ConfigMap，重新发布后恢复。",
    ),
    CaseRecord(
        title="磁盘使用率超过 90%",
        category="system",
        root_cause="日志轮转策略失效，nginx access log 快速增长。",
        resolution="执行日志归档清理，修复 logrotate 配置并增加告警阈值。",
    ),
]


class CaseService:
    def _ensure_seed(self) -> None:
        if not sqlite_store.list_cases():
            for case in SEED_CASES:
                sqlite_store.upsert_case(case.case_id, case.status, case.model_dump(mode="json"))

    def list(self) -> list[CaseRecord]:
        self._ensure_seed()
        return [CaseRecord.model_validate(item) for item in sqlite_store.list_cases()]

    def save_all(self, cases: list[CaseRecord]) -> None:
        for case in cases:
            sqlite_store.upsert_case(case.case_id, case.status, case.model_dump(mode="json"))

    def add(self, case: CaseRecord) -> CaseRecord:
        sqlite_store.upsert_case(case.case_id, case.status, case.model_dump(mode="json"))
        return case


case_service = CaseService()
