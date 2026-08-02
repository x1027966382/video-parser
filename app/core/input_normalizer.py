"""Layer 1: 输入归一化 — 把各种输入形态（纯URL/分享口令/短链）变成标准 URL"""
from __future__ import annotations
import re
from typing import Optional

import httpx

from app.config import settings


# 平台 URL 特征（用于自动识别）
PLATFORM_PATTERNS = {
    "douyin": [
        r"douyin\.com",
        r"iesdouyin\.com",
        r"v\.douyin\.com",
    ],
    "tiktok": [
        r"tiktok\.com",
        r"vm\.tiktok\.com",
        r"vt\.tiktok\.com",
        r"m\.tiktok\.com",
    ],
    "kuaishou": [
        r"kuaishou\.com",
        r"v\.kuaishou\.com",
        r"v\.kwai\.com",
        r"gifshow\.com",
    ],
    "xiaohongshu": [
        r"xiaohongshu\.com",
        r"xhslink\.com",
    ],
    "weibo": [
        r"weibo\.com",
        r"weibo\.cn",
        r"(?:^|[/.])t\.cn(?:[/?#]|$)",
    ],
    "youtube": [
        r"youtube\.com",
        r"youtu\.be",
        r"youtube-nocookie\.com",
    ],
    "instagram": [
        r"instagram\.com",
        r"ig\.me",
        r"instagr\.am",
    ],
    "bilibili": [
        r"bilibili\.com",
        r"b23\.tv",
        r"bili2233\.cn",
    ],
    "twitter": [
        r"^https?://(?:www\.)?(?:twitter|x)\.com",
        r"(?:^|[/.])t\.co(?:[/?#]|$)",
    ],
    "pinterest": [
        r"pinterest\.com",
        r"pin\.it",
    ],
    "pipixia": [
        r"pipix\.com",
        r"pipixia\.com",
        r"h5\.pipix\.com",
    ],
    "xigua": [
        r"ixigua\.com",
        r"xigua\.com",
        r"www\.ixigua\.com",
    ],
    "weishi": [
        r"weishi\.qq\.com",
        r"isee\.weishi\.qq\.com",
    ],
    "tieba": [
        r"tieba\.baidu\.com",
        r"\.tb\.cn",
        r"\.bdimg\.com",
    ],
}


# 匹配分享文本中的 URL（排除集不能含 .，否则 https://v.douyin.com 会被截断）
SHARE_URL_RE = re.compile(r"https?://[^\s，。；！？,\"'<>]+")


def detect_platform_by_url(url: str) -> Optional[str]:
    """根据 URL 识别平台（大小写不敏感）"""
    if not url:
        return None
    url_lc = url.lower()
    for platform, patterns in PLATFORM_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, url_lc, re.IGNORECASE):
                return platform
    return None


class InputNormalizer:
    """输入归一化器：把任何形态的输入 → 标准 URL"""

    @staticmethod
    def extract_url_from_text(text: str) -> str:
        """从分享文本里提取 URL；纯 URL 直接返回"""
        if not text:
            return ""
        text = text.strip()
        if text.startswith("http"):
            # 直接是 URL，去掉可能的尾部标点
            url = re.search(r"https?://[^\s，。；！？,\"'<>]+", text)
            return url.group(0).rstrip("，。；！？,.!?;") if url else text
        # 分享口令
        m = SHARE_URL_RE.search(text)
        return m.group(0).rstrip("，。；！？,.!?;") if m else text

    @staticmethod
    async def resolve_redirect(url: str, timeout: float = 10.0) -> str:
        """解析短链 302 跳转，返回最终 URL"""
        if not url:
            return url
        try:
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/120.0.0.0 Safari/537.36"
                    ),
                },
                proxy=settings.proxy or None,
            ) as client:
                # Range: bytes=0-0 是快速 HEAD 等价
                resp = await client.get(url, headers={"Range": "bytes=0-0"})
                return str(resp.url)
        except Exception:
            return url

    @classmethod
    async def normalize(cls, raw: str) -> str:
        """入口：任何输入 → 标准 URL"""
        url = cls.extract_url_from_text(raw)
        if not url:
            return url
        # 短链域名做一次重定向解析
        short_domains = (
            "v.douyin.com", "iesdouyin.com", "v.kuaishou.com",
            "v.kwai.com", "xhslink.com", "t.cn", "b23.tv", "bili2233.cn",
            "vm.tiktok.com", "vt.tiktok.com", "t.co", "pin.it",
            "tb.cn", "h5.pipix.com",
        )
        if any(d in url.lower() for d in short_domains):
            url = await cls.resolve_redirect(url)
        return url
