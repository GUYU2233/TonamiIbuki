from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.api.diagnosis import router as diagnosis_router
from src.api.routes import router as ops_router
from src.middleware import SecurityAuditMiddleware

app = FastAPI(title=settings.APP_NAME, version="0.1.0")

app.add_middleware(SecurityAuditMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ops_router)
app.include_router(diagnosis_router)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME, "env": settings.ENV}
