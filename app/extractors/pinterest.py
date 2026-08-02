"""Pinterest 解析器 — 图片/视频 Pin"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)

_PIN_ID_RE = re.compile(r"/pin/([0-9A-Za-z_-]+)")
_LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)
_STATE_RE = re.compile(r"__NEXT_DATA__\s*=\s*(\{.*?\})\s*</script>", re.DOTALL)


class PinterestExtractor(BaseExtractor):
    name = "pinterest"
    url_patterns = [r"pinterest\.com", r"pin\.it"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "pin.it" in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            pin_id = self._extract_pin_id(url)
            if not pin_id:
                return self.reject("无法提取 pin id")
            html = await self.fetch_html(
                f"https://www.pinterest.com/pin/{pin_id}/",
                headers={"Referer": "https://www.pinterest.com/", "Accept-Language": "en-US,en;q=0.9"},
            )
            data = self._extract_data(html)
            if data:
                return self._build(data, url)
            # 兜底：直接正则找图片 URL
            m = re.search(r'"images"\s*:\s*\{"[^"]+":\s*\{"url":\s*"([^"]+)"', html)
            if m:
                return MediaMeta(success=True, platform=self.name, type=MediaType.IMAGE,
                                 images=[m.group(1).replace("\\u002F", "/")],
                                 source_url=url)
            return self.reject("未提取到页面数据")
        except Exception as e:
            logger.warning("pinterest error: %s", e)
            return self.reject(str(e))

    def _extract_pin_id(self, url):
        m = _PIN_ID_RE.search(url)
        return m.group(1) if m else None

    def _extract_data(self, html):
        for pat in (_LDJSON_RE, _STATE_RE):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    continue
        return None

    def _walk(self, obj, images=None, title="", author="", video="", cover=""):
        if obj is None:
            return images or [], title, author, video, cover
        imgs = images or []
        if isinstance(obj, dict):
            # 图片 URL
            if len(imgs) < 20:
                for key in ("url", "imageURL", "imageUrl", "url_original", "originUrl"):
                    val = obj.get(key)
                    if isinstance(val, str) and ("https://i.pinimg.com" in val or ".jpg" in val or ".png" in val):
                        if val not in imgs:
                            imgs.append(val.replace("\\u002F", "/"))
                        break
            if not title:
                for key in ("title", "alt", "description"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        title = obj[key]
                        break
            if not author:
                for key in ("author_name", "full_name", "display_name", "name"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        author = obj[key]
                        break
            if not video:
                val = obj.get("video_url") or obj.get("contentUrl")
                if isinstance(val, str) and val.startswith("http"):
                    video = val.replace("\\u002F", "/")
            if not cover:
                val = obj.get("thumbnailUrl") or obj.get("cover")
                if isinstance(val, str) and val.startswith("http"):
                    cover = val.replace("\\u002F", "/")
            for v in obj.values():
                imgs, title, author, video, cover = self._walk(v, imgs, title, author, video, cover)
        elif isinstance(obj, list):
            for v in obj:
                imgs, title, author, video, cover = self._walk(v, imgs, title, author, video, cover)
        return imgs, title, author, video, cover

    def _build(self, data, source_url):
        imgs, title, author, video, cover = self._walk(data)
        if video:
            return MediaMeta(success=True, platform=self.name, type=MediaType.VIDEO,
                             video=video, title=title, author=author, cover=cover,
                             source_url=source_url)
        if imgs:
            return MediaMeta(success=True, platform=self.name, type=MediaType.IMAGE,
                             images=imgs[:20], title=title, author=author, cover=cover or imgs[0],
                             source_url=source_url)
        return self.reject("未提取到媒体")


extractor_registry.register(PinterestExtractor())