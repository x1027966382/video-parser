"""全局配置 — Pydantic Settings + dotenv"""
from __future__ import annotations
from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """服务配置（可通过 .env 或环境变量覆盖）"""
    port: int = 8000
    http_proxy: Optional[str] = None
    https_proxy: Optional[str] = None
    socks_proxy: Optional[str] = None
    request_timeout: int = 20
    max_retry: int = 3
    log_level: str = "INFO"
    cache_ttl: int = 600
    storage_dir: str = "/data/downloads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def proxy(self) -> Optional[str]:
        """统一代理入口：优先 socks，其次 http"""
        return self.socks_proxy or self.http_proxy or self.https_proxy or None


@lru_cache()
def get_config() -> Settings:
    return Settings()


settings = get_config()