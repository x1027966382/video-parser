"""抖音解析器 — 视频 + 图集"""
from __future__ import annotations
import json
import logging
import re
from urllib.parse import unquote

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.input_normalizer import InputNormalizer

logger = logging.getLogger(__name__)

_SHARE_URL_RE = re.compile(r"https?://(?:v\.)?douyin\.com/[^\s\"'<>]+")
_RENDER_DATA_RE = re.compile(r'<script id="RENDER_DATA" type="application/json">(.*?)</script>', re.DOTALL)
_NEXT_DATA_RE = re.compile(r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL)
_ROUTER_RE = re.compile(r'window\._ROUTER_DATA\s*=\s*(\{.*?\})\s*</script>', re.DOTALL)
_VIDEO_RE = re.compile(r'"playAddr"\s*:\s*"([^"]+)"')


class DouyinExtractor(BaseExtractor):
    name = "douyin"
    url_patterns = [r"douyin\.com", r"iesdouyin\.com", r"v\.douyin\.com"]

    async def resolve(self, raw: str) -> str:
        """处理分享口令 / 短链"""
        m = _SHARE_URL_RE.search(raw)
        if m:
            url = m.group(0)
        else:
            url = raw
        url = url.rstrip("，。；！？,.!?;")
        if "v.douyin.com" in url or "iesdouyin.com" in url:
            from app.core.fetcher import unified_fetcher
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            html = await self.fetch_html(url, headers={
                "Referer": "https://www.douyin.com/",
                "Accept-Language": "zh-CN,zh;q=0.9",
            })
            data = self._extract_json(html)
            if not data:
                return self.reject("未提取到页面数据")
            return self._build(data, url)
        except Exception as e:
            logger.warning("douyin error: %s", e)
            return self.reject(str(e))

    def _extract_json(self, html):
        for (re_db, is_url) in [
            (_RENDER_DATA_RE, True),
            (_NEXT_DATA_RE, False),
            (_ROUTER_RE, False),
        ]:
            m = re_db.search(html)
            if m:
                raw = m.group(1)
                if is_url and "%" in raw[:200]:
                    raw = unquote(raw)
                try:
                    return json.loads(raw)
                except Exception:
                    continue
        m = _VIDEO_RE.search(html)
        if m:
            return {"_direct": m.group(1).replace("\\u002F", "/")}
        return None

    def _walk(self, obj, video_url="", images=None, title="", author="", avatar="", cover="", music=""):
        if obj is None:
            return video_url, images or [], title, author, avatar, cover, music
        imgs = images or []
        if isinstance(obj, dict):
            if not video_url:
                for key in ("playAddr", "play_addr", "playApi", "src", "url_list"):
                    val = obj.get(key)
                    if isinstance(val, list) and val:
                        video_url = str(val[0])
                    elif isinstance(val, str):
                        video_url = val
                    if video_url:
                        video_url = video_url.replace("\\u002F", "/")
                        video_url = re.sub(r'[?&]watermark=[^&]*', '', video_url)
                        break
            if not imgs:
                for key in ("images", "imagesList", "image_list", "img_list"):
                    if key in obj and isinstance(obj[key], list):
                        for img in obj[key]:
                            if isinstance(img, str):
                                imgs.append(img.replace("\\u002F", "/"))
                            elif isinstance(img, dict):
                                u = (img.get("url_list") or [""])[0] or img.get("url", "")
                                if u:
                                    imgs.append(str(u).replace("\\u002F", "/"))
            if not title:
                for key in ("desc", "title", "caption"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        title = obj[key]; break
            if not author:
                for key in ("nickname", "nick_name", "author_name", "name"):
                    if isinstance(obj.get(key), str) and obj[key]:
                        author = obj[key]; break
            if not avatar:
                val = obj.get("avatar") or obj.get("avatar_thumb") or obj.get("avatarUrl")
                if isinstance(val, str):
                    avatar = val.replace("\\u002F", "/")
                elif isinstance(val, dict):
                    u = (val.get("url_list") or [""])[0]
                    if u: avatar = str(u).replace("\\u002F", "/")
            if not cover:
                val = obj.get("cover") or obj.get("cover_url") or obj.get("origin_cover")
                if isinstance(val, str):
                    cover = val.replace("\\u002F", "/")
                elif isinstance(val, dict):
                    u = (val.get("url_list") or [""])[0]
                    if u: cover = str(u).replace("\\u002F", "/")
            if not music:
                val = obj.get("music") or obj.get("music_url")
                if isinstance(val, str):
                    music = val.replace("\\u002F", "/")
                elif isinstance(val, dict):
                    u = val.get("play_url") or val.get("url")
                    if u: music = str(u).replace("\\u002F", "/")
            for v in obj.values():
                video_url, imgs, title, author, avatar, cover, music = self._walk(v, video_url, imgs, title, author, avatar, cover, music)
        elif isinstance(obj, list):
            for v in obj:
                video_url, imgs, title, author, avatar, cover, music = self._walk(v, video_url, imgs, title, author, avatar, cover, music)
        return video_url, imgs, title, author, avatar, cover, music

    def _build(self, data, source_url):
        if isinstance(data, dict) and "_direct" in data:
            return MediaMeta(success=True, platform=self.name, type=MediaType.VIDEO,
                             video=data["_direct"], source_url=source_url)
        vu, imgs, title, author, avatar, cover, music = self._walk(data)
        if vu:
            return MediaMeta(success=True, platform=self.name, type=MediaType.VIDEO,
                             video=vu, title=(title or ""), author=(author or ""),
                             avatar=(avatar or ""), cover=(cover or ""), music=(music or ""),
                             source_url=source_url)
        if imgs:
            return MediaMeta(success=True, platform=self.name, type=MediaType.IMAGE,
                             images=imgs, title=(title or ""), author=(author or ""),
                             avatar=(avatar or ""), cover=(cover or ""), source_url=source_url)
        return self.reject("未提取到媒体")


extractor_registry.register(DouyinExtractor())