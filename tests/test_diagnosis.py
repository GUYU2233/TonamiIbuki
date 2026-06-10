from src.models import AlertRequest, DiagnosisRequest
from src.services.diagnosis_service import diagnosis_service


async def collect_events(request):
    events = []
    async for event in diagnosis_service.run(request):
        events.append(event)
    return events


def test_high_risk_diagnosis_waits_for_approval(anyio_backend):
    import anyio

    request = DiagnosisRequest(
        alert=AlertRequest(
            title="订单服务 ERROR-DB-104 连接池耗尽",
            severity="critical",
            host="prod-app-01",
            service="order-service",
            description="timeout acquiring connection",
        ),
        auto_execute=True,
    )
    events = anyio.run(collect_events, request)
    assert events[-1].status == "waiting_approval"
    session = diagnosis_service.get(events[-1].session_id)
    assert session is not None
    assert session.pending_tool is not None
