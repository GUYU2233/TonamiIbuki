"""TonamiIbuki — FastAPI application entry point."""
from __future__ import annotations


from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.settings import settings
from src.api.routes import router
from src.security.rate_limiter import rate_limit_middleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    print(f"TonamiIbuki v0.2.0 starting on port {settings.PORT}...")
    yield
    # Shutdown
    print("TonamiIbuki shutting down...")


app = FastAPI(
    title="TonamiIbuki · AIOps",
    version="0.2.0",
    description="企业 IT 运维 AIOps 智能体系统",
    lifespan=lifespan,
)

# ---------------------------------------------------------------------------
# CORS — refined per plan 7.3
# ---------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "Retry-After"],
    max_age=3600,
)

# ---------------------------------------------------------------------------
# Rate limiting — plan 7.2
# ---------------------------------------------------------------------------
app.middleware("http")(rate_limit_middleware)

# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------
app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}
