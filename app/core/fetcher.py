"""Layer 3: 统一的媒体获取器 — 下载/流/HTML抓取"""
from __future__ import annotations
import asyncio
import sys
from typing import AsyncIterator, Optional

import httpx

from app.config import settings

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Encoding": "identity",
}

# 各平台常用 Referer 轮询（部分 CDN 会校验）
_DEFAULT_REFERERS = [
    "https://www.douyin.com/",
    "https://www.kuaishou.com/",
    "https://www.xiaohongshu.com/",
    "https://www.bilibili.com/",
    "https://www.youtube.com/",
    "https://www.instagram.com/",
    "",  # 无 Referer 兜底
]


class UnifiedFetcher:
    """统一获取器 — 所有网络 I/O 的归宿"""

    async def fetch_html(
        self, url: str, method: str = "GET",
        headers: dict | None = None, retries: int = 3,
    ) -> str:
        """抓取页面文本（带重试）"""
        timeout = float(settings.request_timeout)
        last_exc: Exception | None = None
        h = {**_HEADERS, **(headers or {})}
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(timeout, connect=15.0),
                    follow_redirects=True,
                    proxy=settings.proxy or None,
                ) as client:
                    resp = await client.request(method, url, headers=h)
                    if resp.status_code >= 400:
                        raise httpx.HTTPStatusError(
                            f"HTTP {resp.status_code}", request=resp.request, response=resp)
                    return resp.text
            except Exception as exc:
                last_exc = exc
                if attempt < retries - 1:
                    await asyncio.sleep(1 + attempt * 2)
        raise last_exc  # type: ignore[misc]

    async def fetch_json(
        self, url: str, headers: dict | None = None,
    ) -> dict:
        """抓取 JSON（用于 API 调用 — 微博 ajax 等）"""
        h = {**_HEADERS, **(headers or {})}
        async with httpx.AsyncClient(
            timeout=float(settings.request_timeout),
            follow_redirects=True,
            proxy=settings.proxy or None,
        ) as client:
            resp = await client.get(url, headers=h)
            resp.raise_for_status()
            return resp.json()

    async def fetch_redirect_url(self, url: str) -> str:
        """只做重定向解析，不取内容体"""
        try:
            async with httpx.AsyncClient(
                timeout=10.0,
                follow_redirects=True,
                proxy=settings.proxy or None,
            ) as client:
                resp = await client.get(url, headers={**_HEADERS, "Range": "bytes=0-0"})
                return str(resp.url)
        except Exception:
            return url

    async def stream(
        self, url: str,
        referers: list[str] | None = None,
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        """流式下载远端媒体文件。

        会用多个 Referer 轮询尝试，失败就切下一个。
        """
        refs = referers or _DEFAULT_REFERERS
        last_exc = None
        for ref in refs:
            h = {**_HEADERS}
            if ref:
                h["Referer"] = ref
            try:
                async with httpx.AsyncClient(
                    timeout=float(settings.request_timeout),
                    proxy=settings.proxy or None,
                ) as client:
                    async with client.stream("GET", url, headers=h) as resp:
                        if resp.status_code < 400:
                            async for chunk in resp.aiter_bytes(chunk_size):
                                yield chunk
                            return
            except Exception as exc:
                last_exc = exc
        print(f"[fetcher] 下载失败（所有 Referer 轮询）: {url[:80]} → {last_exc}",
              file=sys.stderr)

    async def download_to(
        self, url: str, dest: str,
        referers: list[str] | None = None,
        chunk_callback=None,
    ) -> bool:
        """下载远端媒体到本地文件路径。成功返回 True。"""
        try:
            it = self.stream(url, referers=referers)
            with open(dest, "wb") as f:
                async for chunk in it:
                    f.write(chunk)
                    if chunk_callback:
                        chunk_callback(len(chunk))
            return True
        except Exception:
            return False


# 全局唯一实例
unified_fetcher = UnifiedFetcher()