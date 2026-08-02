"""微视解析器 — 腾讯系"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"/s/([0-9A-Za-z]+)")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)
_LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


class WeishiExtractor(BaseExtractor):
    name = "weishi"
    url_patterns = [r"weishi\.qq\.com", r"isee\.weishi\.qq\.com"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "isee.weishi.qq.com" in url:
            from app.core.fetcher import unified_fetcher
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            html = await self.fetch_html(
                url,
                headers={"Referer": "https://weishi.qq.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            # 1. JSON-LD
            m = _LDJSON_RE.search(html)
            if m:
                try:
                    ld = json.loads(m.group(1))
                    if isinstance(ld, list):
                        ld = ld[0]
                    video = ld.get("contentUrl") or ld.get("url") or ""
                    if video:
                        return MediaMeta(
                            success=True, platform=self.name, type=MediaType.VIDEO,
                            title=ld.get("name") or "", cover=ld.get("thumbnailUrl") or "",
                            video=video, source_url=url,
                        )
                except Exception:
                    pass
            # 2. __NEXT_DATA__
            m = _NEXT_DATA_RE.search(html)
            if m:
                try:
                    data = json.loads(m.group(1))
                    self._done = False
                    r = self._walk_build(data, url)
                    if r:
                        return r
                except Exception:
                    pass
            return self.reject("未提取到页面数据")
        except Exception as e:
            logger.warning("weishi error: %s", e)
            return self.reject(str(e))

    def _walk_build(self, obj, source_url, video="", title="", cover=""):
        if isinstance(obj, dict):
            if not video:
                for key in ("video_url", "play_url", "main_url", "url"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.startswith("http"):
                        video = val.replace("\\u002F", "/")
                        break
            if not title:
                for key in ("title", "desc", "caption"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        title = obj[key]
                        break
            if not cover:
                val = obj.get("cover") or obj.get("poster") or obj.get("thumb")
                if isinstance(val, str):
                    cover = val.replace("\\u002F", "/")
            for v in obj.values():
                r = self._walk_build(v, source_url, video, title, cover)
                if r:
                    return r
        elif isinstance(obj, list):
            for v in obj:
                r = self._walk_build(v, source_url, video, title, cover)
                if r:
                    return r
        if video and not self._done:
            self._done = True
            return MediaMeta(success=True, platform=self.name, type=MediaType.VIDEO,
                             video=video, title=title, cover=cover, source_url=source_url)
        return None


extractor_registry.register(WeishiExtractor())