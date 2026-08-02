"""YouTube 解析器 — 基于 yt-dlp"""
from __future__ import annotations
import asyncio
import logging

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)


class YouTubeExtractor(BaseExtractor):
    name = "youtube"
    url_patterns = [r"youtube\.com", r"youtu\.be", r"youtube-nocookie\.com"]

    async def resolve(self, raw: str) -> str:
        return raw.strip().rstrip("，。；！？,.!?;")

    async def extract(self, url: str) -> MediaMeta:
        try:
            return await asyncio.to_thread(self._parse_sync, url)
        except Exception as e:
            logger.warning("youtube error: %s", e)
            return self.reject(str(e))

    def _parse_sync(self, url: str) -> MediaMeta:
        import yt_dlp

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "noplaylist": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return self.reject("yt-dlp 无返回")

            formats = info.get("formats") or []

            def fmt_key(f):
                return (f.get("height") or 0, f.get("tbr") or 0)

            video_only = [
                f for f in formats
                if f.get("vcodec") and f.get("vcodec") != "none"
                and f.get("acodec") in (None, "none") and f.get("url")
            ]
            muxed = [
                f for f in formats
                if f.get("vcodec") and f.get("vcodec") != "none"
                and f.get("acodec") and f.get("acodec") != "none" and f.get("url")
            ]
            audio_only = [
                f for f in formats
                if f.get("acodec") and f.get("acodec") != "none"
                and (not f.get("vcodec") or f.get("vcodec") == "none") and f.get("url")
            ]

            video_url = ""
            if video_only:
                video_url = max(video_only, key=fmt_key)["url"]
            elif muxed:
                video_url = max(muxed, key=fmt_key)["url"]

            audio_url = ""
            if audio_only:
                audio_url = max(audio_only, key=fmt_key)["url"]

            if not video_url:
                video_url = info.get("url") or ""

            if not video_url and not audio_url:
                return self.reject("未找到可用流")

            # 字幕
            subs = {}
            for lang, tracks in (info.get("subtitles") or {}).items():
                if tracks:
                    subs[lang] = tracks[-1].get("url") or ""

            return MediaMeta(
                success=True, platform=self.name, type=MediaType.VIDEO,
                title=info.get("title") or "",
                author=info.get("uploader") or info.get("channel") or "",
                avatar=info.get("thumbnail") or "",
                cover=info.get("thumbnail") or "",
                duration=int(info.get("duration") or 0),
                video=video_url,
                music=audio_url,
                publish_time=str(info.get("upload_date") or ""),
                like=info.get("like_count") or 0,
                comment=info.get("comment_count") or 0,
                share=info.get("repost_count") or 0,
                view=info.get("view_count") or 0,
                extra={"subtitles": subs},
                source_url=url,
            )


extractor_registry.register(YouTubeExtractor())