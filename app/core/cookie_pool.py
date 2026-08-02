"""多账号 Cookie 池 — 轮询 + 失效检测"""
from __future__ import annotations
import time
from typing import Optional


class CookiePool:
    """简易多账号 Cookie 池。线程不安全。"""

    def __init__(self):
        self._pool: dict[str, list[dict]] = {}  # platform → [{"value": "…", "expired": False}, ...]

    def add(self, platform: str, cookie: str, meta: dict | None = None) -> None:
        """添加一个 Cookie"""
        entry: dict = {"value": cookie, "expired": False, "added": time.time(), "meta": meta or {}}
        self._pool.setdefault(platform, []).append(entry)

    def get(self, platform: str) -> Optional[str]:
        """轮询取一个未失效的 Cookie"""
        candidates = self._pool.get(platform) or []
        alive = [c for c in candidates if not c.get("expired")]
        if not alive:
            return None
        # round-robin
        cookie = alive.pop(0)
        alive.append(cookie)
        return cookie["value"]

    def mark_expired(self, platform: str, cookie: str) -> None:
        """标记某个 Cookie 失效"""
        for c in self._pool.get(platform, []):
            if c["value"] == cookie:
                c["expired"] = True
                break

    def list_platforms(self) -> list[str]:
        return sorted(self._pool.keys())

    def clear_platform(self, platform: str) -> None:
        self._pool.pop(platform, None)

    def stats(self) -> dict:
        return {
            p: {
                "total": len(cs),
                "alive": sum(1 for c in cs if not c.get("expired")),
            }
            for p, cs in self._pool.items()
        }


# 全局唯一实例
cookie_pool = CookiePool()