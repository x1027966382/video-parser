"""统一数据模型 — 所有平台解析器都返回这个结构"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional


class MediaType(str, Enum):
    """媒体类型"""
    VIDEO = "video"
    IMAGE = "image"
    AUDIO = "audio"
    MIXED = "mixed"  # 图文混合


@dataclass
class MediaMeta:
    """统一的媒体元数据 — 所有平台抽取器的输出格式

    字段说明：
    - platform: 平台标识（douyin/kuaishou/bilibili/...）
    - type: 媒体类型
    - video: 视频直链（无水印）
    - images: 图集列表
    - music: 音频/背景音乐直链
    - title/author/avatar/cover: 基础元数据
    - duration: 时长（秒）
    - publish_time: 发布时间（字符串）
    - like/comment/share/view: 统计
    - watermark: 是否有水印
    - fingerprint: 去重指纹（基于 platform+id+author）
    - source_url: 原始 URL
    - extra: 平台特定扩展字段
    """
    success: bool = True
    platform: str = ""
    type: MediaType = MediaType.VIDEO
    title: str = ""
    author: str = ""
    avatar: str = ""
    cover: str = ""
    video: str = ""
    music: str = ""
    images: List[str] = field(default_factory=list)
    duration: int = 0
    publish_time: str = ""
    like: int = 0
    comment: int = 0
    share: int = 0
    view: int = 0
    watermark: bool = False
    fingerprint: str = ""
    source_url: str = ""
    extra: dict = field(default_factory=dict)

    def is_valid(self) -> bool:
        """有效结果：必须有视频或图片"""
        return bool(self.video) or bool(self.images)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["type"] = self.type.value
        # 去掉空壳字段
        if not self.images:
            d.pop("images", None)
        return d


@dataclass
class BatchResult:
    """批量解析结果"""
    total: int = 0
    success: int = 0
    failed: int = 0
    items: List[dict] = field(default_factory=list)
    errors: List[dict] = field(default_factory=list)
