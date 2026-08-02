"""TikTok 解析器 — 视频 + 图集（HTML 提取优先，yt-dlp 兜底）"""
from __future__ import annotations
import asyncio
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"/video/(\d+)")
_SIGI_STATE_RE = re.compile(
    r'<script id="SIGI_STATE" type="application/json">(.*?)</script>', re.DOTALL
)
_UNIVERSAL_RE = re.compile(
    r'window\.__UNIVERSAL_DATA_FOR_REHYDRATION__\s*=\s*(\{.*?\});', re.DOTALL
)


class TiktokExtractor(BaseExtractor):
    name = "tiktok"
    url_patterns = [r"tiktok\.com", r"vm\.tiktok\.com", r"vt\.tiktok\.com"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "vm.tiktok.com" in url or "vt.tiktok.com" in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            video_id = self._extract_video_id(url)
            if not video_id:
                return self.reject("无法提取 video id")
            html = await self.fetch_html(
                f"https://www.tiktok.com/@anyuser/video/{video_id}",
                headers={
                    "Referer": "https://www.tiktok.com/",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            data = self._extract_json(html)
            meta = self._build(data, url) if data else None
            if meta and meta.is_valid():
                return meta
            # 页面提取失败，退回 yt-dlp
            meta = await asyncio.to_thread(self._parse_sync, url)
            if meta and meta.is_valid():
                return meta
            return self.reject("未提取到媒体")
        except Exception as e:
            logger.warning("tiktok error: %s", e)
            return self.reject(str(e))

    # ── 工具 ──

    def _extract_video_id(self, url: str):
        m = _VIDEO_ID_RE.search(url)
        return m.group(1) if m else None

    def _extract_json(self, html):
        for pat in (_SIGI_STATE_RE, _UNIVERSAL_RE):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    continue
        return None

    def _find_items(self, data):
        """从 SIGI_STATE / UNIVERSAL_DATA 中定位条目"""
        if not isinstance(data, dict):
            return []
        items = []
        for key in ("ItemModule", "itemModule", "items"):
            module = data.get(key)
            if isinstance(module, dict):
                items.extend(v for v in module.values() if isinstance(v, dict))
        return items

    def _build(self, data, source_url):
        for item in self._find_items(data):
            meta = self._item_to_meta(item, source_url)
            if meta:
                return meta
        return None

    def _item_to_meta(self, item: dict, source_url: str) -> MediaMeta | None:
        video_obj = item.get("video")
        if not isinstance(video_obj, dict):
            video_obj = {}

        # playAddr: 字符串 / {urlList} / playAddrList[].src
        video = ""
        play_addr = item.get("playAddr") or video_obj.get("playAddr") or ""
        if isinstance(play_addr, dict):
            play_addr = play_addr.get("urlList") or play_addr.get("src") or ""
        if isinstance(play_addr, list):
            play_addr = play_addr[0] if play_addr else ""
        if isinstance(play_addr, str):
            video = play_addr
        if not video:
            for p in video_obj.get("playAddrList") or []:
                if isinstance(p, dict) and p.get("src"):
                    video = p["src"]
                    break
        if video.startswith("//"):
            video = "https:" + video

        # 图集：imagePost.images[].imageURL.urlList[0]
        images = []
        image_post = item.get("imagePost")
        if isinstance(image_post, dict):
            for img in image_post.get("images") or []:
                if not isinstance(img, dict):
                    continue
                image_url = img.get("imageURL")
                if isinstance(image_url, dict):
                    url_list = image_url.get("urlList") or []
                    if url_list:
                        images.append(url_list[0])

        if not video and not images:
            return None

        author = item.get("author") or ""
        if isinstance(author, dict):
            author = author.get("nickname") or author.get("uniqueId") or ""
        music = ""
        mus = item.get("music") or {}
        if isinstance(mus, dict):
            music = mus.get("playUrl") or mus.get("url") or ""

        common = dict(
            success=True, platform=self.name,
            title=item.get("desc") or item.get("title") or "",
            author=str(author or ""),
            cover=video_obj.get("cover") or item.get("cover") or "",
            music=music,
            like=item.get("diggCount") or item.get("likeCount") or 0,
            comment=item.get("commentCount") or 0,
            view=item.get("playCount") or item.get("viewCount") or 0,
            share=item.get("shareCount") or 0,
            publish_time=str(item.get("createTime") or ""),
            source_url=source_url,
        )
        if images and not video:
            common.update(type=MediaType.IMAGE, images=images)
            return MediaMeta(**common)
        common.update(type=MediaType.VIDEO, video=video)
        return MediaMeta(**common)

    def _parse_sync(self, url: str) -> MediaMeta:
        try:
            import yt_dlp
        except ImportError:
            return self.reject("yt-dlp 未安装")
        ydl_opts = {"quiet": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            if not info:
                return self.reject("yt-dlp 无返回")
            video = info.get("url") or info.get("webpage_url") or ""
            if not video:
                return self.reject("yt-dlp 未找到视频")
            return MediaMeta(
                success=True, platform=self.name, type=MediaType.VIDEO,
                title=info.get("title") or "",
                author=info.get("uploader") or info.get("uploader_id") or "",
                cover=info.get("thumbnail") or "",
                duration=int(info.get("duration") or 0),
                video=video,
                source_url=url,
            )


extractor_registry.register(TiktokExtractor())
