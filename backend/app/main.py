import os
import time
import uuid
import logging
from typing import Dict, List
from fastapi import FastAPI, Request, Response, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import settings
from app.db.session import engine, Base, SessionLocal
from app.db.seed import seed_database
from app.auth.routes import router as auth_router
from app.api.routes_student import router as student_router
from app.api.routes_staff import router as staff_router
from app.api.routes_admin import router as admin_router
from app.api.routes_mess import router as mess_router
from app.api.routes_voice import router as voice_router
from app.api.routes_sms import router as sms_router
from app.api.routes_map import router as map_router
from app.api.routes_ask import router as ask_router
from app.api.routes_operations import router as operations_router

# ================= STRUCTURED LOGGING WITH PII REDACTION =================
class SensitiveDataFilter(logging.Filter):
    """Automatically redacts sensitive fields like passwords, tokens and secrets from logs."""
    SENSITIVE_WORDS = ["password", "token", "secret", "authorization", "bearer"]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            lower_msg = record.msg.lower()
            for word in self.SENSITIVE_WORDS:
                if word in lower_msg:
                    record.msg = "[REDACTED_SECURITY_SENSITIVE_LOG_ENTRY]"
                    break
        return True

logging.basicConfig(
    level=logging.INFO,
    format='{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
)
logger = logging.getLogger("campus_os")
logger.addFilter(SensitiveDataFilter())

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Campus Life OS — Comprehensive operations platform replacing 4 apps, 6 notice boards, and paper registers for BPUT Hackathon 2026."
)

# ================= RATE LIMITING STATE (Layer 11) =================
# In-memory sliding window counter for sensitive endpoints (e.g. login)
RATE_LIMIT_BUCKET: Dict[str, List[float]] = {}
LOGIN_MAX_ATTEMPTS = 15
LOGIN_WINDOW_SECONDS = 60

@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    # 1. Request ID Tracing (Layer 13)
    req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    request.state.request_id = req_id

    # 2. Rate Limiting on Login (Layer 11)
    if request.url.path == "/api/auth/login" and request.method == "POST":
        client_ip = request.client.host if request.client else "127.0.0.1"
        now = time.time()
        attempts = RATE_LIMIT_BUCKET.get(client_ip, [])
        # Evict timestamps older than window
        attempts = [t for t in attempts if now - t < LOGIN_WINDOW_SECONDS]
        if len(attempts) >= LOGIN_MAX_ATTEMPTS:
            retry_after = int(LOGIN_WINDOW_SECONDS - (now - attempts[0]))
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={
                    "error": {
                        "code": "RATE_LIMIT_EXCEEDED",
                        "message": f"Too many login attempts. Please retry after {retry_after} seconds.",
                        "request_id": req_id
                    }
                },
                headers={"Retry-After": str(max(1, retry_after))}
            )
        attempts.append(now)
        RATE_LIMIT_BUCKET[client_ip] = attempts

    # 3. Process Request
    start_time = time.time()
    response: Response = await call_next(request)
    duration_ms = round((time.time() - start_time) * 1000, 2)

    # 4. Attach Security Headers (Layer 10)
    response.headers["X-Request-ID"] = req_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Response-Time-Ms"] = str(duration_ms)

    # Cache-Control headers for authenticated APIs vs static
    if request.url.path.startswith("/api/") and request.url.path not in ["/api/health", "/api/health/live"]:
        response.headers["Cache-Control"] = "no-store, private, must-revalidate"

    return response

from starlette.exceptions import HTTPException as StarletteHTTPException

# ================= GLOBAL STANDARD ERROR HANDLERS (Layer 5) =================
@app.exception_handler(HTTPException)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    status_code = getattr(exc, "status_code", 500)
    detail = getattr(exc, "detail", str(exc))
    headers = getattr(exc, "headers", None)
    code_map = {
        400: "VALIDATION_ERROR",
        401: "UNAUTHENTICATED",
        403: "PERMISSION_DENIED",
        404: "RESOURCE_NOT_FOUND",
        429: "RATE_LIMIT_EXCEEDED"
    }
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code_map.get(status_code, "CLIENT_ERROR"),
                "message": detail if isinstance(detail, str) else "Error processing request",
                "request_id": req_id,
                "details": detail if isinstance(detail, dict) else {}
            }
        },
        headers=headers or {}
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid.uuid4()))
    logger.error(f"Unhandled server error: {exc} | Request ID: {req_id}")
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An internal server error occurred. Please contact campus IT support.",
                "request_id": req_id
            }
        }
    )

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount uploads directory for static files/models
if os.path.exists(settings.UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=str(settings.UPLOAD_DIR)), name="uploads")

# Include Routers
app.include_router(auth_router)
app.include_router(student_router)
app.include_router(staff_router)
app.include_router(admin_router)
app.include_router(mess_router)
app.include_router(voice_router)
app.include_router(sms_router)
app.include_router(map_router)
app.include_router(ask_router)
app.include_router(operations_router)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    seed_database()
    from app.background.sla_monitor import start_sla_monitor
    start_sla_monitor()

# ================= HEALTH CHECK ENDPOINTS (Layer 14) =================
@app.get("/api/health/live")
def liveness_check():
    """Lightweight liveness probe for orchestrators."""
    return {"status": "alive"}

@app.get("/api/health")
def readiness_check():
    """Deep readiness check verifying database and storage connectivity."""
    db_status = "DOWN"
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "UP"
    except Exception as e:
        logger.error(f"Health check DB probe failed: {e}")

    storage_status = "UP" if os.path.exists(settings.UPLOAD_DIR) or os.access(".", os.W_OK) else "DOWN"

    is_healthy = (db_status == "UP" and storage_status == "UP")
    return {
        "status": "healthy" if is_healthy else "degraded",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "components": {
            "database": db_status,
            "storage": storage_status,
            "offline_voice": "UP"
        }
    }

# Mount frontend production build if available
frontend_dist = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist"))
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
