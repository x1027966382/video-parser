"""LRU 元数据缓存 — 同 URL 10 分钟内直接返缓存，避免重复爬"""
from __future__ import annotations
import time
from collections import OrderedDict
from typing import Optional

from app.core.models import MediaMeta


class MetadataCache:
    """线程不安全的轻量 LRU。FastAPI async 单线程用没问题。"""

    max_size: int = 500
    ttl: float = 600.0  # 10 min

    def __init__(self, max_size: int = 500, ttl: float = 600.0):
        self.max_size = max_size
        self.ttl = ttl
        self._store: OrderedDict[str, tuple[float, MediaMeta]] = OrderedDict()

    def get(self, url: str) -> Optional[MediaMeta]:
        """取缓存；过期则删。"""
        entry = self._store.get(url)
        if not entry:
            return None
        ts, meta = entry
        if time.monotonic() - ts > self.ttl:
            del self._store[url]
            return None
        # LRU touch
        self._store.move_to_end(url)
        return meta

    def set(self, url: str, meta: MediaMeta):
        """写入缓存"""
        if len(self._store) >= self.max_size:
            self._store.popitem(last=False)  # 淘汰最旧的
        self._store[url] = (time.monotonic(), meta)

    def clear(self):
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# 全局唯一实例
metadata_cache = MetadataCache()