"""Instagram 解析器 — Reels / Posts（图片或视频）"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)

_MEDIA_ID_RE = re.compile(r"/(?:reel|p|tv)/([0-9A-Za-z_-]+)")
_LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
_SHARED_RE = re.compile(r"window\._sharedData\s*=\s*(\{.*?\});", re.DOTALL)


class InstagramExtractor(BaseExtractor):
    name = "instagram"
    url_patterns = [r"instagram\.com", r"ig\.me", r"instagr\.am"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "ig.me" in url or "instagram.com/" not in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            media_id = self._extract_media_id(url)
            if not media_id:
                return self.reject("无法提取 media id")
            html = await self.fetch_html(
                f"https://www.instagram.com/p/{media_id}/",
                headers={"Referer": "https://www.instagram.com/", "Accept-Language": "en-US,en;q=0.9"},
            )
            data = self._extract_share_data(html)
            if not data:
                return self.reject("未提取到页面数据")
            return self._build(data, url)
        except Exception as e:
            logger.warning("instagram error: %s", e)
            return self.reject(str(e))

    def _extract_media_id(self, url):
        m = _MEDIA_ID_RE.search(url)
        return m.group(1) if m else None

    def _extract_share_data(self, html):
        m = _LDJSON_RE.search(html)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        m = _SHARED_RE.search(html)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return None

    @staticmethod
    def _parse_duration(val) -> int:
        if isinstance(val, (int, float)):
            return int(val)
        s = str(val or "")
        m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", s)
        if m:
            return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)
        return 0

    def _build(self, data, source_url):
        if "@graph" in data:
            for item in data["@graph"]:
                if item.get("@type") == "VideoObject":
                    return self._video_result(item, source_url)
                if item.get("@type") == "ImageObject":
                    return self._image_result(item, source_url)
        return self.reject("未找到媒体信息")

    def _video_result(self, item, source_url):
        video = item.get("contentUrl") or ""
        if not video:
            return self.reject("未找到视频直链")
        return MediaMeta(
            success=True, platform=self.name, type=MediaType.VIDEO,
            title=item.get("name") or "",
            author=(item.get("author") or {}).get("name", ""),
            cover=item.get("thumbnailUrl") or "",
            video=video,
            duration=self._parse_duration(item.get("duration")),
            source_url=source_url,
        )

    def _image_result(self, item, source_url):
        img = item.get("contentUrl") or ""
        if not img:
            return self.reject("未找到图片")
        return MediaMeta(
            success=True, platform=self.name, type=MediaType.IMAGE,
            title=item.get("name") or "",
            author=(item.get("author") or {}).get("name", ""),
            cover=item.get("thumbnailUrl") or "",
            images=[img],
            source_url=source_url,
        )


extractor_registry.register(InstagramExtractor())