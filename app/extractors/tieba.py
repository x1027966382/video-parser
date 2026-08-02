"""百度贴吧解析器 — 帖子图文/视频"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)

_TID_RE = re.compile(r"/(?:p|post)/(\d+)")
_IMAGE_RE = re.compile(r'https?://imgsa?\.baidu\.com/it/u=[^"\'&\s]+')


class TiebaExtractor(BaseExtractor):
    name = "tieba"
    url_patterns = [r"tieba\.baidu\.com", r"\.tb\.cn"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if ".tb.cn" in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            tid = self._extract_tid(url)
            if not tid:
                return self.reject("无法提取帖子 id")
            # 贴吧 API：帖子内容（pc 版 json 接口）
            api = f"https://tieba.baidu.com/p/{tid}"
            html = await self.fetch_html(
                api,
                headers={"Referer": "https://tieba.baidu.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            return self._build(html, url)
        except Exception as e:
            logger.warning("tieba error: %s", e)
            return self.reject(str(e))

    def _extract_tid(self, url):
        m = _TID_RE.search(url)
        if m:
            return m.group(1)
        # 兜底：URL 末尾数字
        m = re.search(r"/(\d{5,})(?:[?#].*)?$", url)
        return m.group(1) if m else None

    def _build(self, html, source_url):
        # 1. JSON-LD / 页面内嵌 JSON
        m = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)
        title = ""
        author = ""
        if m:
            try:
                ld = json.loads(m.group(1))
                if isinstance(ld, list):
                    ld = ld[0]
                title = ld.get("headline") or ld.get("name") or ""
            except Exception:
                pass
        # 标题兜底
        if not title:
            m = re.search(r"<title>(.*?)</title>", html, re.DOTALL)
            if m:
                title = re.sub(r"<[^>]+>", "", m.group(1)).strip()
                title = re.sub(r"_百度贴吧$", "", title)

        # 图片：百度贴吧图片 URL 形态
        images = []
        for m in _IMAGE_RE.finditer(html):
            u = m.group(0).replace("&amp;", "&")
            if u not in images:
                images.append(u)
            if len(images) >= 20:
                break

        # 视频：提取视频直链
        video = ""
        m = re.search(r'"video_src"\s*:\s*"([^"]+)"', html)
        if m:
            video = m.group(1).replace("\\u002F", "/")
        if not video:
            m = re.search(r'class="video.*?data-url="([^"]+)"', html, re.DOTALL)
            if m:
                video = m.group(1)

        if not video and not images:
            return self.reject("未提取到媒体")

        common = dict(
            success=True, platform=self.name, title=title, author=author,
            images=images, source_url=source_url,
        )
        if video:
            common.update(type=MediaType.VIDEO, video=video)
            return MediaMeta(**common)
        common.update(type=MediaType.IMAGE)
        return MediaMeta(**common)


extractor_registry.register(TiebaExtractor())