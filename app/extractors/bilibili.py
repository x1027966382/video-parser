"""B站解析器 — 视频（BV 号），支持 dash 流"""
from __future__ import annotations
import logging
import re
import time

from app.core.extractor import BaseExtractor, extractor_registry
from app.core.models import MediaMeta, MediaType
from app.core.fetcher import unified_fetcher

logger = logging.getLogger(__name__)

_BV_RE = re.compile(r"BV[0-9A-Za-z]+")
_CV_RE = re.compile(r"/read/cv(\d+)", re.IGNORECASE)
_VIEW_API = "https://api.bilibili.com/x/web-interface/view?bvid={bv}"
_PLAY_API = "https://api.bilibili.com/x/player/playurl?bvid={bv}&cid={cid}&qn=80&fnval=16"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.bilibili.com/",
}


class BilibiliExtractor(BaseExtractor):
    name = "bilibili"
    url_patterns = [r"bilibili\.com", r"b23\.tv", r"bilibili\.tv"]

    async def resolve(self, raw: str) -> str:
        url = raw.strip().rstrip("，。；！？,.!?;")
        if "b23.tv" in url or "b23.wtf" in url:
            url = await unified_fetcher.fetch_redirect_url(url)
        return url

    async def extract(self, url: str) -> MediaMeta:
        try:
            url = await self.resolve(url)
            bv = self._extract_bv(url)
            if not bv:
                if _CV_RE.search(url):
                    return self.reject("暂不支持 B站专栏(cv)")
                return self.reject("无法提取 BV 号")

            # 1. view API — 元数据 + cid
            view = await unified_fetcher.fetch_json(_VIEW_API.format(bv=bv), headers=_HEADERS)
            if not view or view.get("code") != 0:
                msg = (view or {}).get("message") or "空响应"
                return self.reject(f"B站 view API 错误: {msg}")
            data = view.get("data") or {}
            cid = data.get("cid") or ""
            if not cid:
                return self.reject("未获取到 cid")

            # 2. playurl API — 视频/音频直链
            play = await unified_fetcher.fetch_json(
                _PLAY_API.format(bv=bv, cid=cid), headers=_HEADERS)
            video, audio = self._extract_streams(play)
            if not video:
                return self.reject("未提取到视频直链")
            return self._build(data, video, audio, url)
        except Exception as e:
            logger.warning("bilibili error: %s", e)
            return self.reject(str(e))

    def _extract_bv(self, url: str):
        m = _BV_RE.search(url)
        return m.group(0) if m else None

    @staticmethod
    def _extract_streams(play: dict):
        """从 playurl 响应中提取视频/音频直链（兼容 durl 和 dash）"""
        play_data = play.get("data") or {}
        video = ""
        audio = ""
        # 1. durl（老接口）
        durl = play_data.get("durl") or []
        if durl and isinstance(durl[0], dict):
            video = durl[0].get("url") or ""
            if not video:
                video = (durl[0].get("backup_url") or [""])[0]
        # 2. dash
        dash = play_data.get("dash") or {}
        if dash:
            vlist = dash.get("video") or []
            alist = dash.get("audio") or []
            if vlist:
                best = max(vlist, key=lambda x: x.get("bandwidth") or 0)
                video = best.get("baseUrl") or (best.get("backupUrl") or [""])[0]
            if alist:
                best = max(alist, key=lambda x: x.get("bandwidth") or 0)
                audio = best.get("baseUrl") or (best.get("backupUrl") or [""])[0]
        return video, audio

    def _build(self, data: dict, video: str, audio: str, source_url: str) -> MediaMeta:
        owner = data.get("owner") or {}
        stat = data.get("stat") or {}
        publish_time = ""
        if data.get("pubdate"):
            publish_time = time.strftime("%Y-%m-%d", time.localtime(data["pubdate"]))

        return MediaMeta(
            success=True, platform=self.name, type=MediaType.VIDEO,
            title=data.get("title") or "",
            author=owner.get("name") or "",
            avatar=owner.get("face") or "",
            cover=data.get("pic") or "",
            duration=int(data.get("duration") or 0),
            publish_time=publish_time,
            video=video,
            music=audio or "",
            like=stat.get("like") or 0,
            comment=stat.get("reply") or 0,
            view=stat.get("view") or 0,
            share=stat.get("share") or 0,
            source_url=source_url,
        )


extractor_registry.register(BilibiliExtractor())