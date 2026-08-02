"""Layer 2: BaseExtractor 抽象基类 + ExtractorRegistry 注册表"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Type

from app.core.input_normalizer import InputNormalizer, detect_platform_by_url
from app.core.models import MediaMeta


class BaseExtractor(ABC):
    """所有平台解析器的统一基类。

    每个平台只需要实现：
    1. name / url_patterns — 平台标识与 URL 匹配规则
    2. resolve(raw_input) → str — 输入归一化（口令/短链 → 真实 URL）
    3. extract(url) → MediaMeta — URL → 标准元数据
    """

    name: str = ""
    url_patterns: list[str] = []
    needs_cookie: bool = False

    @abstractmethod
    async def resolve(self, raw_input: str) -> str:
        """Layer 1 hook: 子类自行做输入归一化（平台特定口令/短链处理）"""
        ...

    @abstractmethod
    async def extract(self, url: str) -> MediaMeta:
        """Layer 2: 从标准 URL 中提取媒体元数据"""
        ...

    # ── 公用工具方法 ──

    async def fetch_html(self, url: str, **kwargs) -> str:
        """快捷：抓取页面 HTML"""
        from app.core.fetcher import unified_fetcher
        return await unified_fetcher.fetch_html(url, **kwargs)

    def reject(self, msg: str = "") -> MediaMeta:
        """快速构建失败 MediaMeta"""
        return MediaMeta(success=False, platform=self.name, title=msg)


class ExtractorRegistry:
    """平台解析器注册表 — 发号施令的中心"""

    def __init__(self):
        self._extractors: dict[str, BaseExtractor] = {}
        self._loaded: bool = False

    # ── 注册 ──

    def register(self, ext: BaseExtractor) -> None:
        self._extractors[ext.name] = ext

    def register_many(self, extractors: list[BaseExtractor]) -> None:
        for e in extractors:
            self.register(e)

    def unregister(self, name: str) -> None:
        self._extractors.pop(name, None)

    # ── 查询 ──

    def get(self, name: str) -> Optional[BaseExtractor]:
        return self._extractors.get(name)

    def list_platforms(self) -> list[str]:
        return sorted(self._extractors.keys())

    def list_platforms_info(self) -> list[dict]:
        return [
            {"name": e.name, "needs_cookie": e.needs_cookie}
            for e in self._extractors.values()
        ]

    def detect_platform(self, url: str) -> Optional[str]:
        """根据 URL 自动识别平台"""
        return detect_platform_by_url(url)

    # ── 统一入口 ──

    async def parse(self, url: str) -> MediaMeta:
        """自动识别平台 → 解析 → 返回完整 MediaMeta"""
        platform = self.detect_platform(url)
        if not platform:
            return MediaMeta(
                success=False, platform="", title="无法识别平台", source_url=url,
            )
        ext = self.get(platform)
        if not ext:
            return MediaMeta(
                success=False, platform=platform,
                title=f"平台 {platform} 的解析器未注册", source_url=url,
            )
        return await ext.extract(url)

    async def parse_platform(self, platform: str, url: str) -> Optional[MediaMeta]:
        """指定平台解析"""
        ext = self.get(platform)
        if not ext:
            return MediaMeta(
                success=False, platform=platform,
                title=f"不支持的平台: {platform}", source_url=url,
            )
        return await ext.extract(url)

    # ── 自动加载 ──

    def ensure_loaded(self):
        """延迟加载所有内置解析器（避免循环导入）"""
        if self._loaded:
            return
        from app.extractors import douyin, kuaishou, xiaohongshu, weibo
        from app.extractors import youtube, instagram, bilibili, tiktok
        from app.extractors import twitter, pipixia, xigua, weishi, pinterest, tieba
        _ = (douyin, kuaishou, xiaohongshu, weibo, youtube, instagram,
             bilibili, tiktok, twitter, pipixia, xigua, weishi, pinterest, tieba)
        self._loaded = True


# 全局唯一实例
extractor_registry = ExtractorRegistry()