"""抖音解析器 — 视频 + 图集（基于 Web API）"""
from __future__ import annotations
import json
import logging
import re
from urllib.parse import urlparse, parse_qs

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)

# 匹配分享链接
_SHARE_URL_RE = re.compile(r"https?://(?:v\.)?douyin\.com/[^\s\"'<>]+")

# aweme_id 提取正则（从各种 URL 格式中提取）
_AWEME_ID_RE = re.compile(r"(?:aweme_id|item_id|video_id)[=/](\d{15,20})")

# 常用 Referer
_REFERER = "https://www.douyin.com/"
_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)


class DouyinExtractor(BaseExtractor):
    name = "douyin"
    url_patterns = [r"douyin\.com", r"iesdouyin\.com", r"v\.douyin\.com"]

    async def resolve(self, raw: str) -> str:
        """处理分享口令 / 短链 → 真实 URL"""
        m = _SHARE_URL_RE.search(raw)
        if m:
            url = m.group(0)
        else:
            url = raw
        url = url.rstrip("，。；！？,.!?;")
        if "v.douyin.com" in url or "iesdouyin.com" in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    def _extract_aweme_id(self, url: str) -> str | None:
        """从 URL 提取 aweme_id"""
        # 1. 直接参数
        parsed = urlparse(url)
        qs = parse_qs(parsed.query)
        for key in ("aweme_id", "item_id", "video_id"):
            if key in qs and qs[key]:
                return qs[key][0]
        # 2. 路径中
        m = _AWEME_ID_RE.search(url)
        if m:
            return m.group(1)
        return None

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            aweme_id = self._extract_aweme_id(url)
            if not aweme_id:
                return self.reject("无法提取 aweme_id")

            # 调用 Web API 获取详情
            api_url = "https://www.douyin.com/aweme/v1/web/aweme/detail/"
            params = {
                "aweme_id": aweme_id,
                "aid": "6383",
                "device_platform": "webapp",
                "version_name": "23.5.0",
            }
            headers = {
                "Referer": _REFERER,
                "User-Agent": _UA,
                "Accept": "application/json",
            }
            json_data = await unified_fetcher.fetch_json(api_url, headers=headers)
            aweme = json_data.get("aweme_detail")
            if not aweme:
                return self.reject("API 返回空数据")
            return self._build(aweme, url)
        except Exception as e:
            logger.warning("douyin error: %s", e)
            return self.reject(str(e))

    def _build(self, aweme: dict, source_url: str) -> MediaMeta:
        """从 aweme_detail 构建 MediaMeta"""
        # 视频
        video = aweme.get("video", {})
        play_addr = video.get("play_addr", {})
        url_list = play_addr.get("url_list", [])
        video_url = url_list[0] if url_list else ""
        # 去水印参数
        if video_url:
            video_url = video_url.replace("playwm", "play")

        # 图集
        images = []
        if aweme.get("images"):
            for img in aweme["images"]:
                url_list = img.get("url_list", [])
                if url_list:
                    images.append(url_list[0])

        # 作者
        author = aweme.get("author", {})
        nickname = author.get("nickname", "")
        avatar = author.get("avatar_thumb", {}).get("url_list", [""])[0]
        if isinstance(avatar, dict):
            avatar = avatar.get("url_list", [""])[0]

        # 封面
        cover = video.get("origin_cover", {}).get("url_list", [""])[0]
        if not cover:
            cover = video.get("cover", {}).get("url_list", [""])[0]

        # 音乐
        music = aweme.get("music", {})
        music_url = music.get("play_url", {}).get("url_list", [""])[0]

        # 基础信息
        title = aweme.get("desc", "") or ""
        duration = video.get("duration", 0) // 1000  # ms -> s
        stats = aweme.get("statistics", {})

        if video_url:
            return MediaMeta(
                success=True,
                platform=self.name,
                type=MediaType.VIDEO,
                video=video_url,
                title=title,
                author=nickname,
                avatar=avatar,
                cover=cover,
                music=music_url,
                duration=duration,
                like=stats.get("digg_count", 0),
                comment=stats.get("comment_count", 0),
                share=stats.get("share_count", 0),
                view=stats.get("play_count", 0),
                watermark=False,
                source_url=source_url,
            )
        if images:
            return MediaMeta(
                success=True,
                platform=self.name,
                type=MediaType.IMAGE,
                images=images,
                title=title,
                author=nickname,
                avatar=avatar,
                cover=cover,
                source_url=source_url,
            )
        return self.reject("未提取到媒体")


extractor_registry.register(DouyinExtractor())