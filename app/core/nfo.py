"""Emby / Jellyfin NFO 生成器"""
from __future__ import annotations
from app.core.models import MediaMeta


def generate_nfo(meta: MediaMeta) -> str:
    """把 MediaMeta 转成 Emby/Jellyfin 可识别的 movie.nfo XML 字符串"""
    lines = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        "<movie>",
        f"  <title>{_xml_escape(meta.title or 'unknown')}</title>",
        f"  <originaltitle>{_xml_escape(meta.title or 'unknown')}</originaltitle>",
        f"  <plot>{_xml_escape(meta.title or '')}</plot>",
    ]
    if meta.author:
        lines.append(f"  <director>{_xml_escape(meta.author)}</director>")
    if meta.publish_time:
        lines.append(f"  <premiered>{meta.publish_time[:10]}</premiered>")
    if meta.duration:
        lines.append(f"  <runtime>{meta.duration // 60}</runtime>")
    lines.append(f"  <genre>{meta.platform}</genre>")
    lines.append(f"  <tag>{meta.platform}</tag>")
    lines.append(f"  <source>{meta.platform}</source>")
    lines.append("</movie>")
    return "\n".join(lines)


def _xml_escape(s: str) -> str:
    """最小 XML 转义"""
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")