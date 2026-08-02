"""核心层单元测试"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from app.core.input_normalizer import detect_platform_by_url, InputNormalizer
from app.core.models import MediaMeta, MediaType
from app.core.dedup import compute_fingerprint, set_fingerprint
from app.core.cache import MetadataCache
from app.core.nfo import generate_nfo
from app.core.extractor import extractor_registry


def test_platform_detection():
    cases = [
        ("https://v.douyin.com/abc", "douyin"),
        ("https://www.kuaishou.com/short-video/3x", "kuaishou"),
        ("https://www.xiaohongshu.com/explore/abc", "xiaohongshu"),
        ("https://weibo.com/123/detail/abc", "weibo"),
        ("https://youtu.be/abc", "youtube"),
        ("https://www.instagram.com/p/abc", "instagram"),
        ("https://www.bilibili.com/video/BV1xx", "bilibili"),
        ("https://www.tiktok.com/@u/video/123", "tiktok"),
        ("https://twitter.com/u/status/123", "twitter"),
        ("https://h5.pipix.com/item/123", "pipixia"),
        ("https://www.ixigua.com/123", "xigua"),
        ("https://weishi.qq.com/s/abc", "weishi"),
        ("https://www.pinterest.com/pin/abc", "pinterest"),
        ("https://tieba.baidu.com/p/123456", "tieba"),
        ("https://example.com/unknown", None),
    ]
    for url, expected in cases:
        got = detect_platform_by_url(url)
        assert got == expected, f"{url} → {got} (expected {expected})"


def test_share_text_extraction():
    n = InputNormalizer
    # 分享口令
    url = n.extract_url_from_text("8.43 abc:/ 复制打开抖音，看看作品 https://v.douyin.com/xxx/")
    assert url.startswith("https://v.douyin.com/xxx"), url
    # 纯 URL 不去尾标点误伤
    url2 = n.extract_url_from_text("https://v.douyin.com/abc123")
    assert url2 == "https://v.douyin.com/abc123"
    # 尾部标点清理
    url3 = n.extract_url_from_text("https://b23.tv/abcd，")
    assert url3 == "https://b23.tv/abcd"


def test_fingerprint():
    m1 = MediaMeta(platform="douyin", author="A", title="T", video="https://x")
    m2 = MediaMeta(platform="douyin", author="A", title="T", video="https://x")
    f1 = set_fingerprint(m1).fingerprint
    f2 = set_fingerprint(m2).fingerprint
    assert f1 == f2  # 相同内容相同指纹
    assert len(f1) == 12


def test_cache():
    c = MetadataCache(max_size=3, ttl=10)
    meta = MediaMeta(success=True, platform="test", video="x")
    assert c.get("u1") is None
    c.set("u1", meta)
    assert c.get("u1") is not None
    c.set("u2", meta)
    c.set("u3", meta)
    c.set("u4", meta)  # 淘汰 u1
    assert c.get("u1") is None
    assert c.get("u4") is not None


def test_nfo():
    meta = MediaMeta(platform="bilibili", title="测试<视频>", author="UP主",
                     duration=120, publish_time="2026-01-01")
    nfo = generate_nfo(meta)
    assert "<movie>" in nfo
    assert "测试&lt;视频&gt;" in nfo  # XML 转义
    assert "<runtime>2</runtime>" in nfo


def test_registry_loads_all():
    extractor_registry.ensure_loaded()
    platforms = extractor_registry.list_platforms()
    assert len(platforms) >= 14, f"只加载了 {len(platforms)} 个平台"
    expected = {"douyin", "kuaishou", "xiaohongshu", "weibo", "youtube",
                "instagram", "bilibili", "tiktok", "twitter", "pipixia",
                "xigua", "weishi", "pinterest", "tieba"}
    assert expected.issubset(set(platforms))


@pytest.mark.asyncio
async def test_parse_unknown_platform():
    from app.core import extractor_registry as er
    meta = await er.parse("https://example.com/x")
    assert not meta.success


@pytest.mark.asyncio
async def test_douyin_reject_invalid():
    from app.extractors.douyin import DouyinExtractor
    e = DouyinExtractor()
    # 无网络环境下应该安全失败
    meta = await e.extract("https://v.douyin.com/notexist12345")
    assert meta is not None
