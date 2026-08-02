"""视频指纹去重 — 基于 platform+id+author 计算 SHA1"""
from __future__ import annotations
import hashlib

from app.core.models import MediaMeta


def compute_fingerprint(meta: MediaMeta) -> str:
    """基于平台/标题/作者生成 SHA1 指纹"""
    raw = f"{meta.platform}|{meta.author}|{meta.title}|{meta.video[:120]}"
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def set_fingerprint(meta: MediaMeta) -> MediaMeta:
    """原地设置指纹；
    如果用 dict 构建（解析器返回 dict 再 to_dict），实现方式不变；
    但如果已经是 MediaMeta 对象可以直接调用";
    """
    meta.fingerprint = compute_fingerprint(meta)
    return meta