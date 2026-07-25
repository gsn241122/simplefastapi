from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine, check_db_connection
from app.core.dependencies import request_logger
from app.core.logging_config import setup_logging
from app.modules.user.routes import router as user_router
from app.modules.product.routes import router as product_router
from app.modules.auth.routes import router as auth_router
from app.modules.order.routes import router as order_router
from app.modules.invoice.routes import router as invoice_router

from scalar_fastapi import get_scalar_api_reference

# Setup logging sebelum apapun
setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifecycle handler untuk startup dan shutdown aplikasi."""
    # --- Startup ---
    logger.info("Starting up %s v%s [env=%s]", settings.APP_NAME, settings.APP_VERSION, settings.ENVIRONMENT)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables synchronized.")
    yield
    # --- Shutdown ---
    logger.info("Shutting down %s.", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "SimpleFastAPI APP"
    ),
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- CORS Middleware ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.effective_cors_origins or ["*"],
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-Request-ID"],
)

# --- Request Logging & Rate Limiting Middleware ---
@app.middleware("http")
async def log_and_rate_limit(request: Request, call_next):
    """Middleware untuk logging terstruktur dan rate limiting."""
    return await request_logger(request, call_next)

# --- Routers ---
app.include_router(auth_router)
app.include_router(user_router)
app.include_router(product_router)
app.include_router(order_router)
app.include_router(invoice_router)

@app.get("/scalar", include_in_schema=False)
async def scalar_html():
    """
    Menyediakan halamanScalar UI untuk API di module ini.
    """
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="SimpleFastAPI Application API",
        show_sidebar=True
    )

@app.get("/", tags=["General"], summary="Welcome message")
def read_root():
    """Endpoint root — kembalikan pesan selamat datang."""
    return {"message": f"Welcome to {settings.APP_NAME} v{settings.APP_VERSION}"}


@app.get("/health", tags=["General"], summary="Health check endpoint")
def health_check():
    """
    Endpoint health check yang mengembalikan status aplikasi dan database.

    Berguna untuk load balancer, Docker HEALTHCHECK, dan monitoring.
    """
    db_ok = check_db_connection()
    status_str = "healthy" if db_ok else "degraded"
    payload = {
        "status": status_str,
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_ok else "unavailable",
    }
    http_status = 200 if db_ok else 503
    return JSONResponse(content=payload, status_code=http_status)
