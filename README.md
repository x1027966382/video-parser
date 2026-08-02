# Video Parser v2 — 多平台视频/图集解析服务

基于 FastAPI 的多平台短视频/图集解析服务，采用**统一三层架构**（输入归一化 → 元数据提取 → 媒体获取），支持 **14 个平台**、批量解析、元数据缓存、去重指纹、SSE 进度、流反代、Emby NFO 生成、Web UI。

## ✨ 特性

### 🏗️ 统一架构
- **Layer 1 输入归一化**：任何形态输入（URL / 分享口令 / 短链）→ 标准 URL
- **Layer 2 元数据提取**：所有平台实现 `BaseExtractor`，返回统一的 `MediaMeta`
- **Layer 3 媒体获取**：统一下载（Referer 轮询 / Range / 代理）

新增一个平台只需写一个文件（`resolve` + `extract`），其余全部复用。

### 🌐 支持平台（14 个）
| 平台 | 类型 | 说明 |
|------|------|------|
| 抖音 | 视频 / 图集 | 分享口令、短链、主页链接 |
| 快手 | 视频 / 图集 | 短链跳转 |
| 小红书 | 图文 / 视频 | xhslink 短链 |
| 微博 | 视频 / 图文 | 官方 ajax 接口 |
| YouTube | 视频 | yt-dlp，支持字幕提取 |
| Instagram | Reels / Posts | JSON-LD 解析 |
| **B站** | 视频 | 官方 API + dash 流（视频/音频分离） |
| **TikTok** | 视频 / 图集 | SIGI_STATE + yt-dlp 降级 |
| **Twitter/X** | 视频 / 图文 | yt-dlp 兜底 |
| **皮皮虾** | 视频 / 图集 | 字节系 |
| **西瓜视频** | 视频 / 图集 | 字节系 |
| **微视** | 视频 | 腾讯系 |
| **Pinterest** | 图片 / 视频 | Pin 详情 |
| **百度贴吧** | 图文 / 视频 | 帖子解析 |

### 🆕 功能
- ✅ **批量解析** `/api/batch` — 一次最多 50 个 URL，并发解析（Semaphore 5）
- ✅ **元数据缓存** — LRU 500 条 / 10 分钟 TTL
- ✅ **去重指纹** — 基于 platform+author+title+video 计算 SHA1
- ✅ **SSE 进度** `/api/progress/{task_id}` — 批量任务实时进度
- ✅ **流反代** `/api/proxy` — 解决前端跨域 / CDN 防盗链
- ✅ **Emby NFO 生成** — 每个解析结果附带 `movie.nfo` XML
- ✅ **Cookie 池** `/api/cookie` — 多账号 Cookie 轮询 + 失效标记
- ✅ **字幕提取** — YouTube 字幕（yt-dlp）
- ✅ **Web UI** — 原生 JS 单页（零依赖），支持多链接批量解析
- ✅ **批量下载** — `/api/download` 直接返回文件流

## 🚀 快速开始

### Docker 部署

```bash
cp .env.example .env   # 按需填写代理
docker compose up -d --build
# 访问 http://localhost:8000
```

### 本地运行

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## 📡 API 使用

### 1. 健康检查
```bash
curl http://localhost:8000/api/health
```

### 2. 解析（自动识别平台）
```bash
curl -X POST http://localhost:8000/api/parse \
  -H "Content-Type: application/json" \
  -d '{"url": "https://v.douyin.com/xxxxx/"}'
```

### 3. 指定平台解析
```bash
curl -X POST http://localhost:8000/api/parse/bilibili \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bilibili.com/video/BV1GJ411x7h7"}'
```

### 4. 批量解析
```bash
curl -X POST http://localhost:8000/api/batch \
  -H "Content-Type: application/json" \
  -d '{"urls": ["https://v.douyin.com/xxx/", "https://b23.tv/xxx"]}'
```

### 5. 下载
```bash
curl -X POST http://localhost:8000/api/download \
  -H "Content-Type: application/json" \
  -d '{"url": "https://v.douyin.com/xxx/"}' -o video.mp4
```

### 6. 列出平台
```bash
curl http://localhost:8000/api/platforms
```

### 7. Cookie 管理
```bash
# 添加
curl -X POST http://localhost:8000/api/cookie \
  -H "Content-Type: application/json" \
  -d '{"platform": "douyin", "cookie": "..."}'
# 状态
curl http://localhost:8000/api/cookie
```

### 8. 流反代
```bash
curl "http://localhost:8000/api/proxy?url=https://xxx.com/video.mp4" -o video.mp4
```

## 📦 项目结构

```
video-parser/
├── app/
│   ├── main.py                    # FastAPI 入口
│   ├── api.py                     # 全部 API 端点
│   ├── config.py                  # Pydantic Settings
│   ├── models.py                  # API 请求/响应模型
│   ├── core/                      # 统一架构核心
│   │   ├── input_normalizer.py    # Layer 1 输入归一化 + 平台识别
│   │   ├── extractor.py           # BaseExtractor + 注册表
│   │   ├── fetcher.py             # Layer 3 统一下载
│   │   ├── models.py              # MediaMeta 统一数据模型
│   │   ├── cache.py               # LRU 缓存
│   │   ├── dedup.py               # 去重指纹
│   │   ├── cookie_pool.py         # Cookie 池
│   │   ├── progress.py            # SSE 进度
│   │   └── nfo.py                 # Emby NFO 生成
│   ├── extractors/                # 14 个平台实现
│   │   ├── douyin.py kuaishou.py xiaohongshu.py weibo.py
│   │   ├── youtube.py instagram.py bilibili.py tiktok.py
│   │   ├── twitter.py pipixia.py xigua.py weishi.py
│   │   └── pinterest.py tieba.py
│   └── static/                    # Web UI（原生 JS）
├── tests/                         # 单元测试
├── Dockerfile
├── docker-compose.yml
└── .github/workflows/docker-build.yml  # GHCR 自动构建
```

## ⚙️ 配置说明（.env）

| 变量 | 说明 |
|------|------|
| `PORT` | 服务端口，默认 8000 |
| `HTTP_PROXY` / `HTTPS_PROXY` | HTTP 代理（YouTube/Twitter/IG 需要） |
| `SOCKS_PROXY` | SOCKS5 代理，如 `socks5://127.0.0.1:1080` |
| `REQUEST_TIMEOUT` | 请求超时（秒） |
| `MAX_RETRY` | 失败重试次数 |
| `LOG_LEVEL` | 日志级别 |
| `CACHE_TTL` | 缓存有效期（秒） |

## 🧪 单元测试

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

## 免责声明

本服务仅用于个人学习与技术研究，请遵守各平台服务条款与相关法律法规。请勿用于商业用途或侵犯他人版权。
