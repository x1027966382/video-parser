"""Twitter/X 解析器 — 基于 yt-dlp 兜底（反爬严，API 签名复杂）"""
from __future__ import annotations
import asyncio
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)

_STATUS_ID_RE = re.compile(r"/status/(\d+)")


class TwitterExtractor(BaseExtractor):
    name = "twitter"
    url_patterns = [r"twitter\.com", r"x\.com", r"t\.co"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "t.co" in url:
            from app.core.fetcher import unified_fetcher
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            if not _STATUS_ID_RE.search(url):
                return self.reject("无法提取 status id")
            return await asyncio.to_thread(self._parse_sync, url)
        except Exception as e:
            logger.warning("twitter error: %s", e)
            return self.reject(str(e))

    def _parse_sync(self, url: str) -> MediaMeta:
        import yt_dlp

        ydl_opts = {"quiet": True, "skip_download": True, "noplaylist": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return self.reject("yt-dlp 无返回")

            video = (info.get("formats") or [{}])[0].get("url") or info.get("url") or ""
            images = []
            for t in info.get("thumbnails") or []:
                u = t.get("url") if isinstance(t, dict) else None
                if u:
                    images.append(u)

            if not video and not images:
                return self.reject("未提取到媒体")

            common = dict(
                success=True, platform=self.name,
                title=info.get("title") or "",
                author=info.get("uploader") or info.get("uploader_id") or "",
                cover=info.get("thumbnail") or "",
                view=info.get("view_count") or 0,
                like=info.get("like_count") or 0,
                comment=info.get("comment_count") or 0,
                source_url=url,
            )
            if images and not video:
                common.update(type=MediaType.IMAGE, images=images)
                return MediaMeta(**common)
            common.update(type=MediaType.VIDEO, video=video)
            return MediaMeta(**common)


extractor_registry.register(TwitterExtractor())
