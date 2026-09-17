from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import db
from app.routers import alarm_router, modbus_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Modbus 工业协议数据采集监控", version="2.0.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(modbus_router.router, prefix="/api")
app.include_router(alarm_router.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok"}
