from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db import init_db
from app.routers import modbus_router, threshold_router
from app.services.threshold_service import seed_default_rules

app = FastAPI(title="Modbus 工业协议数据采集监控", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(modbus_router.router, prefix="/api")
app.include_router(threshold_router.router, prefix="/api")


@app.on_event("startup")
def startup():
    init_db()
    seed_default_rules()


@app.get("/api/health")
def health():
    return {"status": "ok"}
