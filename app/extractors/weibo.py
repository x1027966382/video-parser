"""微博解析器 — 单条微博视频/图文"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)


class WeiboExtractor(BaseExtractor):
    name = "weibo"
    url_patterns = [r"weibo\.com", r"weibo\.cn", r"t\.cn"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "t.cn" in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            status_id = self._extract_status_id(url)
            if not status_id:
                return self.reject("无法提取 status id")
            html = await self.fetch_html(
                f"https://weibo.com/ajax/statuses/show?id={status_id}",
                headers={"Referer": "https://weibo.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            try:
                data = json.loads(html)
            except Exception:
                return self.reject("接口返回非 JSON")
            if not data or data.get("ok") != 1:
                return self.reject("接口返回失败")
            return self._build(data.get("data") or {}, url)
        except Exception as e:
            logger.warning("weibo error: %s", e)
            return self.reject(str(e))

    def _extract_status_id(self, url):
        # detail/status 前缀
        m = re.search(r"/(?:detail|status)/([0-9A-Za-z]+)", url)
        if m:
            return m.group(1)
        # /uid/mid 形态
        m = re.search(r"/\d+/([0-9A-Za-z]+)(?:[?#].*)?$", url)
        if m:
            return m.group(1)
        # 兜底：非纯数字段
        m = re.search(r"/([0-9A-Za-z]+)(?:[?#].*)?$", url)
        if m and not m.group(1).isdigit():
            return m.group(1)
        return None

    def _build(self, data, source_url):
        title = re.sub(r"<[^>]+>", "", data.get("text_raw") or data.get("text") or "")
        author = (data.get("user") or {}).get("screen_name", "")
        avatar = (data.get("user") or {}).get("avatar_hd", "")
        publish = str(data.get("created_at") or "")

        images = []
        for pic in data.get("pic_ids") or []:
            images.append(f"https://wx{int(pic[0]) % 4 + 1}.sinaimg.cn/large/{pic}")

        video = ""
        video_info = data.get("video_info") or {}
        if isinstance(video_info, dict):
            for stream in video_info.get("stream_url") or []:
                if isinstance(stream, dict) and stream.get("url"):
                    video = stream["url"]
                    break
            if not video:
                video = video_info.get("video_src") or ""

        if not video and not images:
            return self.reject("未提取到任何媒体")

        common = dict(
            success=True, platform=self.name, title=title, author=author,
            avatar=avatar, images=images, publish_time=publish, source_url=source_url,
        )
        if images and not video:
            common.update(type=MediaType.IMAGE)
            return MediaMeta(**common)
        common.update(type=MediaType.VIDEO, video=video)
        return MediaMeta(**common)


extractor_registry.register(WeiboExtractor())