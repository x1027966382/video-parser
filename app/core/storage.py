"""本地存储模块 — 视频保存到文件夹"""
from __future__ import annotations
import os, json, time
from app.core.models import MediaMeta, _ensure_name
from app.core.fetcher import unified_fetcher
from app.core.nfo import generate_nfo
from app.config import settings


async def mkdir(path: str):
    os.makedirs(path, exist_ok=True)


async def save_media(meta: MediaMeta, output_dir: str | None = None) -> dict:
    """视频解析完成后自动保存到本地文件夹。"""
    base = output_dir or settings.storage_dir
    plat = meta.platform or "unknown"
    author = _ensure_name(meta.author) or "unknown"
    title = _ensure_name(meta.title) or f"untitled_{int(time.time())}"
    target = os.path.join(base, plat, author, title)
    await mkdir(target)
    result = {"dir": target, "files": []}

    if meta.video:
        ext = ".mp4" if ".mp4" not in meta.video.lower() else ""
        path = os.path.join(target, f"video{ext}")
        if await unified_fetcher.download_to(meta.video, path):
            result["files"].append("video")
    elif meta.images:
        for i, url in enumerate(meta.images):
            ext = ".jpg"
            for suf in [".jpg", ".jpeg", ".png", ".webp"]:
                if suf in url.lower():
                    ext = suf
                    break
            prefix = "image" if len(meta.images) == 1 else f"image_{i+1}"
            path = os.path.join(target, f"{prefix}{ext}")
            if await unified_fetcher.download_to(url, path):
                result["files"].append(f"image_{i+1}")

    if meta.cover:
        ok = await unified_fetcher.download_to(meta.cover, os.path.join(target, "poster.jpg"))
        if ok:
            result["files"].append("poster")

    meta_path = os.path.join(target, "meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta.to_dict(), f, ensure_ascii=False, indent=2)
    result["files"].append("meta.json")

    nfo_path = os.path.join(target, "movie.nfo")
    with open(nfo_path, "w") as f:
        f.write(generate_nfo(meta))
    result["files"].append("movie.nfo")

    return result