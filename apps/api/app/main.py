from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers import webhooks, org, regulations, requirements, dashboard, reports

app = FastAPI(title="Regulation-as-Code Compiler API")

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}
