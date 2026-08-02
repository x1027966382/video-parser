"""小红书解析器 — 图文 + 视频"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)

_NOTE_ID_RE = re.compile(r"/(?:explore|discovery/item|item)/([0-9a-zA-Z]+)")
_STATE_RE = re.compile(r"<script>window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*</script>", re.DOTALL)
_STATE2_RE = re.compile(r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\});", re.DOTALL)
_NUXT_RE = re.compile(r"window\.__NUXT__\s*=\s*(\{.*?\});", re.DOTALL)
_LDJSON_RE = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.DOTALL)


class XiaohongshuExtractor(BaseExtractor):
    name = "xiaohongshu"
    url_patterns = [r"xiaohongshu\.com", r"xhslink\.com"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "xhslink.com" in url:
            from app.core.fetcher import unified_fetcher
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            note_id = self._extract_note_id(url)
            if not note_id:
                return self.reject("无法提取 note id")
            html = await self.fetch_html(
                f"https://www.xiaohongshu.com/explore/{note_id}",
                headers={"Referer": "https://www.xiaohongshu.com/", "Accept-Language": "zh-CN,zh;q=0.9"},
            )
            data = self._extract_state(html)
            if not data:
                return self.reject("未提取到页面数据")
            return self._build(data, url)
        except Exception as e:
            logger.warning("xiaohongshu error: %s", e)
            return self.reject(str(e))

    def _extract_note_id(self, url):
        m = _NOTE_ID_RE.search(url)
        return m.group(1) if m else None

    def _extract_state(self, html):
        for pat in (_STATE_RE, _STATE2_RE, _NUXT_RE):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    continue
        m = _LDJSON_RE.search(html)
        if m:
            try:
                return json.loads(m.group(1))
            except Exception:
                pass
        return None

    def _build(self, data, source_url):
        note = data
        if "note" in data and isinstance(data["note"], dict):
            note = data["note"].get("noteDetailMap") or data["note"]
        if isinstance(note, dict) and "noteDetailMap" in note:
            for val in note["noteDetailMap"].values():
                if isinstance(val, dict) and "note" in val:
                    note = val["note"]
                    break

        title = note.get("title") or note.get("desc") or ""
        author = (note.get("user") or {}).get("nickname", "")
        avatar = (note.get("user") or {}).get("avatar", "")

        cover = note.get("cover") or ""
        image_list = note.get("imageList") or []
        if not cover and image_list:
            first = image_list[0]
            if isinstance(first, dict):
                cover = first.get("url") or first.get("urlDefault") or ""
            elif isinstance(first, str):
                cover = first

        images = []
        for img in image_list:
            if isinstance(img, dict):
                u = img.get("url") or img.get("urlDefault") or (img.get("infoList") or [{}])[0].get("url", "")
                if u:
                    images.append(u)
            elif isinstance(img, str):
                images.append(img)

        video = ""
        v = note.get("video") or {}
        if isinstance(v, dict):
            video = v.get("url") or (v.get("consumer") or {}).get("origin_video_key", "")
            if video and not video.startswith("http"):
                video = f"https://sns-video-bd.xhscdn.com/{video}"

        if not video and not images:
            return self.reject("未提取到媒体")

        interact = note.get("interactInfo") or {}
        common = dict(
            success=True, platform=self.name, title=title, author=author,
            avatar=avatar, cover=cover, images=images,
            like=interact.get("likedCount") or 0,
            comment=interact.get("commentCount") or 0,
            share=interact.get("sharedCount") or 0,
            publish_time=str(note.get("time") or "") or str(note.get("createTime") or ""),
            source_url=source_url,
        )
        if images and not video:
            common.update(type=MediaType.IMAGE)
            return MediaMeta(**common)
        common.update(type=MediaType.VIDEO, video=video)
        return MediaMeta(**common)


extractor_registry.register(XiaohongshuExtractor())