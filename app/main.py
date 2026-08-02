"""FastAPI 入口"""
from __future__ import annotations
import logging

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import router
from app.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Video Parser API v2",
    description="多平台短视频/图集解析服务 — 统一提取 + 下载 + 反代",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.on_event("startup")
async def on_startup():
    # 延迟加载解析器（只在这里触发一次）
    from app.core import extractor_registry
    try:
        extractor_registry.ensure_loaded()
    except Exception as e:
        logger.warning("部分解析器加载失败: %s", e)
    logger.info("Video Parser v2 启动完成 — 端口=%s 平台=%d",
                settings.port, len(extractor_registry.list_platforms()))

# 静态文件（Web UI）
from fastapi.staticfiles import StaticFiles
import os

_static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.port,
        log_level=settings.log_level.lower(),
    )