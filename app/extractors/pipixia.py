"""皮皮虾解析器 — 视频 + 图集"""
from __future__ import annotations
import json
import logging
import re

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType

logger = logging.getLogger(__name__)

_ITEM_ID_RE = re.compile(r"/item/([0-9a-zA-Z]+)")
_INITIAL_STATE_RE = re.compile(
    r"window\.__INITIAL_STATE__\s*=\s*(\{.*?\})\s*;?\s*</script>", re.DOTALL
)
_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>', re.DOTALL
)


class PipixiaExtractor(BaseExtractor):
    name = "pipixia"
    url_patterns = [r"pipix\.com"]

    async def resolve(self, raw: str) -> str:
        return raw.strip().rstrip("，。；！？,.!?;")

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            item_id = self._extract_item_id(url)
            if not item_id:
                return self.reject("无法提取 item id")
            html = await self.fetch_html(
                f"https://h5.pipix.com/item/{item_id}",
                headers={
                    "Referer": "https://h5.pipix.com/",
                    "Accept-Language": "zh-CN,zh;q=0.9",
                },
            )
            data = self._extract_json(html)
            if not data:
                return self.reject("未提取到页面数据")
            return self._build(data, url)
        except Exception as e:
            logger.warning("pipixia error: %s", e)
            return self.reject(str(e))

    # ── 工具 ──

    def _extract_item_id(self, url: str):
        m = _ITEM_ID_RE.search(url)
        return m.group(1) if m else None

    def _extract_json(self, html):
        for pat in (_INITIAL_STATE_RE, _NEXT_DATA_RE):
            m = pat.search(html)
            if m:
                try:
                    return json.loads(m.group(1))
                except Exception:
                    continue
        return None

    def _find_item(self, data):
        """定位条目对象：detail.item / item / data.item 等常见路径"""
        if not isinstance(data, dict):
            return data
        for path in (("detail", "item"), ("item",), ("data", "item"), ("data",)):
            cur = data
            ok = True
            for p in path:
                if isinstance(cur, dict) and p in cur:
                    cur = cur[p]
                else:
                    ok = False
                    break
            if ok and isinstance(cur, dict):
                return cur
        return data

    def _walk(self, obj, key):
        """递归遍历，按 key 提取所有值"""
        if isinstance(obj, dict):
            if key in obj:
                yield obj[key]
            for v in obj.values():
                yield from self._walk(v, key)
        elif isinstance(obj, list):
            for v in obj:
                yield from self._walk(v, key)

    def _build(self, data, source_url: str) -> MediaMeta:
        item = self._find_item(data)

        # 视频直链
        video_obj = item.get("video") if isinstance(item, dict) else None
        if not isinstance(video_obj, dict):
            video_obj = {}
        video = video_obj.get("video_url") or ""
        if not video:
            for v in video_obj.get("video_list") or []:
                if isinstance(v, dict) and v.get("url"):
                    video = v["url"]
                    break
        if not video:
            video = next((u for u in self._walk(item, "video_url") if u), "")
        if not video:
            for v in self._walk(item, "video_list"):
                if isinstance(v, list):
                    for e in v:
                        if isinstance(e, dict) and e.get("url"):
                            video = e["url"]
                            break
                if video:
                    break

        # 图集
        images = []
        for img in (item.get("images") or []) if isinstance(item, dict) else []:
            if isinstance(img, str):
                images.append(img)
            elif isinstance(img, dict):
                url = img.get("url") or ""
                if not url:
                    url_list = img.get("url_list") or []
                    if url_list and isinstance(url_list[0], dict):
                        url = url_list[0].get("url") or ""
                if url:
                    images.append(url)

        if not video and not images:
            return self.reject("未提取到媒体")

        # 封面
        cover = ""
        cover_obj = video_obj.get("cover") or item.get("cover") or {}
        if isinstance(cover_obj, dict):
            url_list = cover_obj.get("url_list") or []
            if url_list and isinstance(url_list[0], dict):
                cover = url_list[0].get("url") or ""

        # 作者
        author_obj = item.get("author") if isinstance(item, dict) else None
        if isinstance(author_obj, dict):
            author = author_obj.get("name") or author_obj.get("author_name") or ""
        else:
            author = str(author_obj or "")

        common = dict(
            success=True, platform=self.name,
            title=(item.get("title") or item.get("desc") or item.get("description") or "")
            if isinstance(item, dict) else "",
            author=author,
            cover=cover,
            like=item.get("digg_count") or item.get("like_count") or 0,
            comment=item.get("comment_count") or 0,
            view=item.get("view_count") or 0,
            share=item.get("share_count") or 0,
            publish_time=str(item.get("create_time") or item.get("publish_time") or ""),
            source_url=source_url,
        )
        if images and not video:
            common.update(type=MediaType.IMAGE, images=images)
            return MediaMeta(**common)
        common.update(type=MediaType.VIDEO, video=video)
        return MediaMeta(**common)


extractor_registry.register(PipixiaExtractor())
