from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers import webhooks, org, regulations

app = FastAPI(title="Regulation-as-Code Compiler API")

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

@app.get("/health")
async def health_check():
    return {"status": "ok"}
