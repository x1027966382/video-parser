"""视频解析器 — 所有平台实现"""
from app.extractors.douyin import DouyinExtractor
from app.extractors.kuaishou import KuaishouExtractor
from app.extractors.xiaohongshu import XiaohongshuExtractor
from app.extractors.weibo import WeiboExtractor
from app.extractors.youtube import YouTubeExtractor
from app.extractors.instagram import InstagramExtractor
from app.extractors.bilibili import BilibiliExtractor
from app.extractors.tiktok import TiktokExtractor
from app.extractors.twitter import TwitterExtractor
from app.extractors.pipixia import PipixiaExtractor
from app.extractors.xigua import XiguaExtractor
from app.extractors.weishi import WeishiExtractor
from app.extractors.pinterest import PinterestExtractor
from app.extractors.tieba import TiebaExtractor

__all__ = [
    "DouyinExtractor", "KuaishouExtractor", "XiaohongshuExtractor",
    "WeiboExtractor", "YouTubeExtractor", "InstagramExtractor",
    "BilibiliExtractor", "TiktokExtractor", "TwitterExtractor",
    "PipixiaExtractor", "XiguaExtractor", "WeishiExtractor",
    "PinterestExtractor", "TiebaExtractor",
]