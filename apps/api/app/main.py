import logging
import time
from uuid import uuid4
from fastapi import FastAPI, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text
from app.core.logging_config import setup_logging_and_sentry, request_id_var
from app.core.config import settings
from app.db.session import get_db
from app.api.routers import webhooks, org, regulations, requirements, dashboard, reports

setup_logging_and_sentry()
logger = logging.getLogger("api")

app = FastAPI(title="Regulation-as-Code Compiler API")

@app.middleware("http")
async def request_id_and_logging_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID", str(uuid4()))
    token = request_id_var.set(req_id)
    start_time = time.time()
    
    logger.info(f"HTTP Request Started: {request.method} {request.url.path}")
    
    try:
        response = await call_next(request)
        process_time = round((time.time() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = req_id
        logger.info(f"HTTP Request Completed: {request.method} {request.url.path} - Status: {response.status_code} ({process_time}ms)")
        return response
    except Exception as e:
        process_time = round((time.time() - start_time) * 1000, 2)
        logger.error(f"HTTP Request Failed: {request.method} {request.url.path} - Error: {str(e)} ({process_time}ms)", exc_info=True)
        raise
    finally:
        request_id_var.reset(token)

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.status_code, "message": exc.detail, "details": []}}
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": 422, "message": "Validation Error", "details": exc.errors()}}
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled server exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": 500, "message": "Internal Server Error", "details": [str(exc)]}}
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
app.include_router(org.router, prefix="/api", tags=["org"])
app.include_router(regulations.router, tags=["regulations"])
app.include_router(requirements.router, tags=["requirements"])
app.include_router(dashboard.router, tags=["dashboard"])
app.include_router(reports.router, tags=["reports"])

from app.api.routers import api_keys, developer, systems, notifications, jobs
app.include_router(api_keys.router, prefix="/api/v1/settings/api-keys", tags=["api_keys"])
app.include_router(developer.router, prefix="/api/v1", tags=["developer"])
app.include_router(systems.router, prefix="/api/v1/systems", tags=["systems"])
app.include_router(notifications.router, tags=["notifications"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])

async def perform_health_check(db):
    db_status = "ok"
    redis_status = "ok"
    
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"error: {str(e)}"
        
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        await r.ping()
        await r.aclose()
    except Exception as e:
        redis_status = f"error: {str(e)}"
        
    status = "ok" if db_status == "ok" and redis_status == "ok" else "degraded"
    return {
        "status": status,
        "database": db_status,
        "redis": redis_status,
        "version": "1.0.0",
        "timestamp": time.time()
    }

@app.get("/health")
@app.get("/api/health")
async def health_check_endpoint(db = Depends(get_db)):
    return await perform_health_check(db)

@app.get("/api/test-error")
async def test_error_endpoint():
    logger.error("Test error endpoint triggered for Sentry validation", exc_info=True)
    raise RuntimeError("Intentional Test Error for Sentry validation in Phase 14")
