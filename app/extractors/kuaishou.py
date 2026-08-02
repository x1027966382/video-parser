"""快手解析器 — 短视频 + 图集"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)

_VIDEO_ID_RE = re.compile(r"/(?:short-video|fw/photo)/([0-9a-zA-Z]+)")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)
_STATE_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", re.DOTALL)


class KuaishouExtractor(BaseExtractor):
    name = "kuaishou"
    url_patterns = [r"kuaishou\.com", r"v\.kuaishou\.com", r"v\.kwai\.com", r"gifshow\.com"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "v.kuaishou.com" in url or "v.kwai.com" in url or "gifshow.com" in url:
            from app.core.fetcher import unified_fetcher
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            video_id = self._extract_video_id(url)
            if not video_id:
                return self.reject("无法提取视频 id")
            html = await self.fetch_html(
                f"https://www.kuaishou.com/short-video/{video_id}",
                headers={"Referer": "https://www.kuaishou.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            data = self._extract_data(html)
            if not data:
                return self.reject("未提取到页面数据")
            return self._build(data, url)
        except Exception as e:
            logger.warning("kuaishou error: %s", e)
            return self.reject(str(e))

    def _extract_video_id(self, url: str):
        m = _VIDEO_ID_RE.search(url)
        return m.group(1) if m else None

    def _extract_data(self, html):
        for pat in (_NEXT_DATA_RE, _STATE_RE):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    continue
        return None

    def _build(self, data, source_url):
        photo = data
        try:
            photo = data["props"]["pageProps"]["photoDetail"]["photo"]
        except Exception:
            pass

        title = photo.get("caption") or photo.get("title") or ""
        author = photo.get("user_name") or photo.get("author") or ""
        avatar = photo.get("headurl") or photo.get("user_head_url") or ""
        cover = photo.get("coverUrl") or photo.get("cover") or ""
        publish = str(photo.get("timestamp") or "") or str(photo.get("createTime") or "")
        like = photo.get("realLikeCount") or photo.get("likeCount") or 0
        comment = photo.get("commentCount") or 0
        share = photo.get("shareCount") or 0

        video = ""
        if photo.get("photoUrl"):
            video = photo["photoUrl"]
        elif photo.get("manifest") and isinstance(photo["manifest"], list):
            for mf in photo["manifest"]:
                if isinstance(mf, dict) and mf.get("url"):
                    video = mf["url"]
                    break

        images = []
        for ext in photo.get("ext_params") or []:
            if isinstance(ext, dict) and ext.get("url"):
                images.append(ext["url"])

        if not video and not images:
            return self.reject("未提取到媒体")

        common = dict(
            success=True, platform=self.name, title=title, author=author,
            avatar=avatar, cover=cover, like=like, comment=comment, share=share,
            publish_time=publish, source_url=source_url,
        )
        if images and not video:
            common.update(type=MediaType.IMAGE, images=images)
            return MediaMeta(**common)
        common.update(type=MediaType.VIDEO, video=video)
        return MediaMeta(**common)


extractor_registry.register(KuaishouExtractor())