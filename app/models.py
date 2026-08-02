"""Pydantic API 模型 — 仅用于请求/响应序列化"""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    url: str = Field(..., description="视频/图片链接、分享口令、或含链接的文本")
    platform: Optional[str] = Field(None, description="指定平台 (/parse/{platform})")


class BatchRequest(BaseModel):
    urls: List[str] = Field(..., description="一次解析多个链接（最多 50 个）")
    platform: Optional[str] = Field(None, description="指定平台")


class ParseResponse(BaseModel):
    success: bool = True
    platform: Optional[str] = None
    type: Optional[str] = None  # video / image / audio / mixed
    title: Optional[str] = None
    author: Optional[str] = None
    avatar: Optional[str] = None
    cover: Optional[str] = None
    video: Optional[str] = None
    music: Optional[str] = None
    images: List[str] = []
    duration: Optional[int] = None
    publish_time: Optional[str] = None
    like: Optional[int] = None
    comment: Optional[int] = None
    share: Optional[int] = None
    view: Optional[int] = None
    watermark: bool = False
    fingerprint: Optional[str] = None
    source_url: Optional[str] = None
    nfo: Optional[str] = None
    cached: Optional[bool] = None

    @classmethod
    def from_media_meta(cls, meta):
        """从 core MediaMeta 转换为 API 响应"""
        return cls(**{k: v for k, v in meta.to_dict().items() if v or v is False or v == 0})


class BatchResult(BaseModel):
    total: int = 0
    success: int = 0
    failed: int = 0
    items: List[ParseResponse]


class HealthResponse(BaseModel):
    status: str = "ok"
    platforms: int = 0
    platforms_list: List[str] = []
    cache_size: int = 0


class CookieAddRequest(BaseModel):
    platform: str
    cookie: str


class ProgressSummary(BaseModel):
    task_id: str
    done: int = 0
    total: int = 0
    status: str = "pending"