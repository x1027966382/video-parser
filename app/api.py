"""API 路由 — 统一入口点"""
from __future__ import annotations
import asyncio
import urllib.parse
from typing import AsyncIterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core import (
    extractor_registry,
    metadata_cache,
    unified_fetcher,
    compute_fingerprint,
    set_fingerprint,
    cookie_pool,
    progress_tracker,
    generate_nfo,
)
from app.core.input_normalizer import InputNormalizer
from app.core.models import MediaMeta, MediaType
from app.models import (
    ParseRequest, BatchRequest, ParseResponse, BatchResult,
    HealthResponse, CookieAddRequest,
)

import logging
logger = logging.getLogger(__name__)

router = APIRouter()


# ═══════════════════════════════════════════════
# 输入归一化（共享）
# ═══════════════════════════════════════════════

async def _normalize_input(raw: str) -> str:
    """任何输入 → 标准 URL"""
    url = InputNormalizer.extract_url_from_text(raw)
    if not url or not url.startswith("http"):
        raise HTTPException(status_code=400, detail="无效的 URL")
    return url

async def _normalize_and_resolve(raw: str) -> str:
    """归一化 + 短链跳转解析"""
    url = await _normalize_input(raw)
    return await InputNormalizer.resolve_redirect(url)

def _to_response(meta: MediaMeta) -> ParseResponse:
    """MediaMeta → ParseResponse，顺带加 nfo + fingerprint"""
    if meta and meta.success:
        if not meta.fingerprint:
            set_fingerprint(meta)
        r = ParseResponse.from_media_meta(meta)
        r.nfo = generate_nfo(meta)
        r.fingerprint = meta.fingerprint
        return r
    return ParseResponse(
        success=False,
        platform=meta.platform if meta else "",
        title=meta.title if meta else "解析失败",
    )


# ═══════════════════════════════════════════════
# 系统端点
# ═══════════════════════════════════════════════

@router.get("/health", response_model=HealthResponse, tags=["system"])
async def health():
    extractor_registry.ensure_loaded()
    return HealthResponse(
        status="ok",
        platforms=len(extractor_registry.list_platforms()),
        platforms_list=extractor_registry.list_platforms(),
        cache_size=metadata_cache.size,
    )


@router.get("/platforms", tags=["system"])
async def platforms():
    extractor_registry.ensure_loaded()
    return {"platforms": extractor_registry.list_platforms_info()}


# ═══════════════════════════════════════════════
# 解析
# ═══════════════════════════════════════════════

@router.post("/parse", response_model=ParseResponse, tags=["parse"])
async def parse_api(req: ParseRequest):
    url = await _normalize_and_resolve(req.url)

    # 缓存
    cached = metadata_cache.get(url)
    if cached:
        r = _to_response(cached)
        r.cached = True
        return r

    extractor_registry.ensure_loaded()
    meta = await extractor_registry.parse(url)
    metadata_cache.set(url, meta)
    return _to_response(meta)


@router.post("/parse/{platform}", response_model=ParseResponse, tags=["parse"])
async def parse_platform_api(platform: str, req: ParseRequest):
    url = await _normalize_and_resolve(req.url)
    extractor_registry.ensure_loaded()
    meta = await extractor_registry.parse_platform(platform, url)
    metadata_cache.set(url, meta)
    return _to_response(meta)


# ═══════════════════════════════════════════════
# 批量
# ═══════════════════════════════════════════════

@router.post("/batch", response_model=BatchResult, tags=["parse"])
async def batch_api(req: BatchRequest):
    if len(req.urls) > 50:
        raise HTTPException(status_code=400, detail="最多 50 个 URL")
    extractor_registry.ensure_loaded()

    async def parse_one(url: str) -> dict:
        try:
            u = await InputNormalizer.normalize(url)
            if not u.startswith("http"):
                return {"error": "无效 URL", "url": url}
            meta = await extractor_registry.parse(u)
            if meta and meta.success:
                set_fingerprint(meta)
                metadata_cache.set(u, meta)
            return _to_response(meta).model_dump()
        except Exception as e:
            return {"error": str(e), "url": url}

    # 限制并发
    sem = asyncio.Semaphore(5)
    async def bounded(url):
        async with sem:
            return await parse_one(url)
    items = await asyncio.gather(*(bounded(u) for u in req.urls))
    ok = [d for d in items if d.get("success")]
    failed_count = len(items) - len(ok)
    return BatchResult(
        total=len(items),
        success=len(ok),
        failed=failed_count,
        items=ok,
    )


# ═══════════════════════════════════════════════
# 批量（SSE 进度）
# ═══════════════════════════════════════════════

@router.post("/batch/progress", tags=["parse"])
async def batch_progress_api(req: BatchRequest):
    """批量解析 SSE 进度（返回 start 事件 + task_id）"""
    if len(req.urls) > 50:
        raise HTTPException(status_code=400, detail="最多 50 个 URL")
    extractor_registry.ensure_loaded()
    tid = progress_tracker.create(total=len(req.urls))
    return {"task_id": tid, "total": len(req.urls)}


# ═══════════════════════════════════════════════
# SSE 进度订阅
# ═══════════════════════════════════════════════

@router.get("/progress/{task_id}", tags=["system"])
async def progress_stream(task_id: str):
    return StreamingResponse(
        progress_tracker.subscribe(task_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ═══════════════════════════════════════════════
# 下载
# ═══════════════════════════════════════════════

def _safe_filename(title: str, ext: str) -> str:
    name = title.strip() or "unnamed"
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in name)
    return safe.strip().replace(" ", "_")[:128] + ext

def _make_cd(filename: str) -> str:
    encoded = urllib.parse.quote(filename)
    return f'attachment; filename*=UTF-8\'\'{encoded}'

def _abort(status: int, msg: str):
    raise HTTPException(status_code=status, detail=msg)

@router.post("/download", tags=["download"])
async def download(req: ParseRequest, as_zip: bool = Query(False)):
    url = await _normalize_and_resolve(req.url)
    extractor_registry.ensure_loaded()
    meta = await extractor_registry.parse(url)
    if not meta or not meta.is_valid():
        _abort(404, "没有可下载的媒体")

    if meta.type == MediaType.IMAGE or meta.images:
        if as_zip:
            _abort(501, "zip 打包暂未实现")
        img = meta.images[0]
        return StreamingResponse(
            unified_fetcher.stream(img),
            status_code=200,
            media_type="image/jpeg",
            headers={"Content-Disposition": _make_cd(_safe_fn(meta.title, ".jpg"))},
        )

    vurl = meta.video
    if not vurl:
        _abort(404, "未找到视频")

    return StreamingResponse(
        unified_fetcher.stream(vurl),
        status_code=200,
        media_type="video/mp4",
        headers={"Content-Disposition": _make_cd(_safe_fn(meta.title, ".mp4"))},
    )


@router.post("/download/{platform}", tags=["download"])
async def download_platform(platform: str, req: ParseRequest):
    return await download(req)


# ═══════════════════════════════════════════════
# 流反代 (proxy)
# ═══════════════════════════════════════════════

@router.get("/proxy", tags=["proxy"])
async def proxy_stream(url: str = Query(...)):
    """反代远端媒体流 URL → 二进制流（解决前端跨域）"""
    if not url.startswith("http"):
        _abort(400, "无效的媒体 URL")
    return StreamingResponse(
        unified_fetcher.stream(url),
        media_type="application/octet-stream",
    )


# ═══════════════════════════════════════════════
# 字幕提取
# ═══════════════════════════════════════════════

@router.get("/subtitle/{platform}", tags=["subtitle"])
async def subtitle(platform: str, url: str = Query(...)):
    """从解析结果中提取字幕（目前 YouTube 支持最佳）"""
    extractor_registry.ensure_loaded()
    meta = await extractor_registry.parse_platform(platform, url)
    if not meta or not meta.success:
        _abort(404, "解析失败")
    subs = meta.extra.get("subtitles") or {}
    return {"subtitles": subs}


# ═══════════════════════════════════════════════
# Cookie 池管理
# ═══════════════════════════════════════════════

@router.post("/cookie", tags=["cookie"])
async def cookie_add(req: CookieAddRequest):
    cookie_pool.add(req.platform, req.cookie)
    return {"ok": True, "platform": req.platform}

@router.get("/cookie", tags=["cookie"])
async def cookie_stats():
    return cookie_pool.stats()

@router.delete("/cookie/{platform}", tags=["cookie"])
async def cookie_clear(platform: str):
    cookie_pool.clear_platform(platform)
    return {"ok": True}


# ── 别名 ──
_safe_fn = _safe_filename
_make_download_cd = _make_cd