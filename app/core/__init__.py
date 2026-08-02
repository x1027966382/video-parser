"""video-parser 核心抽象层"""
from app.core.models import MediaMeta, MediaType, BatchResult
from app.core.input_normalizer import InputNormalizer
from app.core.extractor import BaseExtractor, ExtractorRegistry, extractor_registry
from app.core.fetcher import unified_fetcher
from app.core.cache import metadata_cache
from app.core.dedup import compute_fingerprint, set_fingerprint
from app.core.cookie_pool import cookie_pool
from app.core.progress import progress_tracker
from app.core.nfo import generate_nfo

__all__ = [
    "MediaMeta",
    "MediaType",
    "BatchResult",
    "InputNormalizer",
    "BaseExtractor",
    "ExtractorRegistry",
    "extractor_registry",
    "unified_fetcher",
    "metadata_cache",
    "compute_fingerprint",
    "set_fingerprint",
    "cookie_pool",
    "progress_tracker",
    "generate_nfo",
]
