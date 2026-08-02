from __future__ import annotations

import logging
import json
import urllib.request
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import Base, engine, check_db_connection
from app.core.dependencies import request_logger
from app.core.logging_config import setup_logging
from app.core.seed import run_seed

# Import SEMUA module agar Base.metadata mengenalinya untuk create_all & alembic
from app.modules.role.routes import router as role_router
from app.modules.user.routes import router as user_router
from app.modules.product.routes import router as product_router
from app.modules.auth.routes import router as auth_router
from app.modules.order.routes import router as order_router
from app.modules.invoice.routes import router as invoice_router
from app.modules.provider.routes import router as provider_router
from app.modules.model.routes import router as model_router
from app.modules.conversation.routes import router as conversation_router
from app.modules.doc.routes import router as doc_router
from app.modules.permission.routes import router as permission_router
from app.modules.payment.routes import router as payment_router
from app.modules.summary.routes import router as summary_router
from app.modules.book.routes import router as book_router

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

    # 🌱 Seed default roles, permissions, dan admin user
    try:
        run_seed()
    except Exception as exc:
        logger.warning("⚠️  Seeding skipped / failed: %s", exc)

    yield

    # --- Shutdown ---
    logger.info("Shutting down %s.", settings.APP_NAME)


def get_active_ngrok_url() -> str | None:
    """Mengambil URL tunnel ngrok yang sedang aktif secara otomatis."""
    try:
        with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=1.0) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                tunnels = data.get("tunnels", [])
                for tunnel in tunnels:
                    public_url = tunnel.get("public_url", "")
                    if public_url.startswith("https://"):
                        return public_url
    except Exception:
        pass
    return None


servers_list = [
    {"url": "http://localhost:8002", "description": "Development Server"}
]

ngrok_url = get_active_ngrok_url()
if ngrok_url:
    servers_list.append({"url": ngrok_url, "description": "Development Server (ngrok tunnel)"})


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "A modular, production-ready FastAPI backend with JWT authentication, "
        "Redis token binding, full Role-Based Access Control (RBAC) with "
        "permissions, pagination, and soft-delete across multiple resource "
        "modules (users, products, orders, invoices, etc.)."
    ),
    version=settings.APP_VERSION,
    docs_url=None,
    redoc_url=None,
    lifespan=lifespan,
    servers=servers_list,
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
async def log_and_rate_limit(request, call_next):
    """Middleware untuk logging terstruktur dan rate limiting."""
    return await request_logger(request, call_next)

# --- Routers ---
app.include_router(auth_router)
app.include_router(role_router)
app.include_router(user_router)
app.include_router(permission_router)  # ← NEW
app.include_router(product_router)
app.include_router(order_router)
app.include_router(invoice_router)
app.include_router(provider_router)
app.include_router(model_router)
app.include_router(conversation_router)
app.include_router(doc_router)
app.include_router(payment_router)
app.include_router(summary_router)
app.include_router(book_router)


@app.get("/", tags=["General"], summary="Welcome message")
def read_root():
    """Endpoint root — kembalikan pesan selamat datang."""
    return {"message": f"Welcome to {settings.APP_NAME} v{settings.APP_VERSION}"}


@app.get("/health", tags=["General"], summary="Health check endpoint")
def health_check():
    """
    Endpoint health check yang mengembalikan status aplikasi dan database.
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
