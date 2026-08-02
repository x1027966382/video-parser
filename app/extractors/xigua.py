"""西瓜视频解析器 — 字节系，结构接近抖音"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)

_ITEM_ID_RE = re.compile(r"/(\d{10,})")
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)
_STATE_RE = re.compile(r"window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>", re.DOTALL)
_VIDEO_RE = re.compile(r'"main_url"\s*:\s*"([^"]+)"')


class XiguaExtractor(BaseExtractor):
    name = "xigua"
    url_patterns = [r"ixigua\.com", r"xigua\.com"]

    async def resolve(self, raw: str) -> str:
        return raw.strip().rstrip("，。；！？,.!?;")

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            html = await self.fetch_html(
                url,
                headers={"Referer": "https://www.ixigua.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            data = self._extract_data(html)
            if data:
                return self._build(data, url)
            # 兜底：直接正则
            m = _VIDEO_RE.search(html)
            if m:
                import base64
                try:
                    vurl = base64.b64decode(m.group(1)).decode()
                    return MediaMeta(success=True, platform=self.name, type=MediaType.VIDEO,
                                     video=vurl, source_url=url)
                except Exception:
                    pass
            return self.reject("未提取到页面数据")
        except Exception as e:
            logger.warning("xigua error: %s", e)
            return self.reject(str(e))

    def _extract_data(self, html):
        for pat in (_NEXT_DATA_RE, _STATE_RE):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    continue
        return None

    def _walk(self, obj, video="", images=None, title="", author="", cover=""):
        if obj is None:
            return video, images or [], title, author, cover
        imgs = images or []
        if isinstance(obj, dict):
            if not video:
                for key in ("main_url", "play_addr", "playApi", "url"):
                    val = obj.get(key)
                    if isinstance(val, str) and val.startswith("http"):
                        video = val.replace("\\u002F", "/")
                        break
            if not imgs:
                for key in ("images", "image_list"):
                    if key in obj and isinstance(obj[key], list):
                        for img in obj[key]:
                            if isinstance(img, str):
                                imgs.append(img.replace("\\u002F", "/"))
                            elif isinstance(img, dict):
                                u = (img.get("url_list") or [""])[0] or img.get("url", "")
                                if u:
                                    imgs.append(str(u).replace("\\u002F", "/"))
            if not title:
                for key in ("title", "desc"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        title = obj[key]
                        break
            if not author:
                for key in ("name", "nickname", "author_name"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        author = obj[key]
                        break
            if not cover:
                val = obj.get("cover") or obj.get("poster_url") or obj.get("origin_cover")
                if isinstance(val, str):
                    cover = val.replace("\\u002F", "/")
                elif isinstance(val, dict):
                    u = (val.get("url_list") or [""])[0]
                    if u:
                        cover = str(u).replace("\\u002F", "/")
            for v in obj.values():
                video, imgs, title, author, cover = self._walk(v, video, imgs, title, author, cover)
        elif isinstance(obj, list):
            for v in obj:
                video, imgs, title, author, cover = self._walk(v, video, imgs, title, author, cover)
        return video, imgs, title, author, cover

    def _build(self, data, source_url):
        video, imgs, title, author, cover = self._walk(data)
        if video:
            return MediaMeta(success=True, platform=self.name, type=MediaType.VIDEO,
                             video=video, title=title, author=author, cover=cover,
                             source_url=source_url)
        if imgs:
            return MediaMeta(success=True, platform=self.name, type=MediaType.IMAGE,
                             images=imgs, title=title, author=author, cover=cover,
                             source_url=source_url)
        return self.reject("未提取到媒体")


extractor_registry.register(XiguaExtractor())