# Stage 3 完成汇报

## 新增：自动下载 & NFO 生成

### app/core/storage.py（新建）
解析完自动保存到本地文件夹，完全遵循 Emby 规范：

```
{base}/{platform}/{author}/{title}/
  - video.mp4
  - meta.json
  - movie.nfo
  - poster.jpg
```

### app/core/models.py（更新）
加 `_ensure_name` 工具函数清理文件名。

### app/core/nfo.py（已就绪）
generate_nfo() 生成标准 Kodi/Emby movie.nfo。

## 调用方式

```python
import asyncio
from app.core.storage import save_media
from app.parsers.douyin import DouyinParser

meta = await DouyinParser().parse("https://v.douyin.com/xxx/")
result = await save_media(meta)
print(result["dir"])  # /data/downloads/douyin/作者/标题/
```

## 已全部完成

video-parser v2 完整能力：
- 14 个平台解析器
- 统一三层架构
- GitHub Actions 自动构建
- 自动下载到存储
- Emby / NFO 兼容
- 批量导入 / API 干净

一句话总结：**喂它一个分享链接，给你 Emby 里就能看的完整文件。** 🎬

需要我推送到 GitHub 并触发新的镜像构建吗？