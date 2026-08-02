"""SSE 进度追踪 — 批量下载任务推送进度"""
from __future__ import annotations
import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ProgressTask:
    task_id: str
    total: int = 0
    done: int = 0
    status: str = "pending"  # pending / running / done / failed
    errors: list[dict] = field(default_factory=list)

    @property
    def percent(self) -> float:
        return (self.done / self.total * 100) if self.total else 0.0

    def to_event(self) -> str:
        import json
        return f"data: {json.dumps({'task_id': self.task_id, 'done': self.done, 'total': self.total, 'status': self.status, 'percent': round(self.percent, 1)})}\n\n"


class ProgressTracker:
    """SSE 进度中心"""

    def __init__(self):
        self._tasks: dict[str, ProgressTask] = {}
        self._queues: dict[str, asyncio.Queue] = {}

    def create(self, total: int, task_id: str | None = None) -> str:
        """新建任务，返回 task_id"""
        tid = task_id or uuid.uuid4().hex[:8]
        self._tasks[tid] = ProgressTask(task_id=tid, total=total, status="running")
        self._queues[tid] = asyncio.Queue(maxsize=100)
        return tid

    def update(self, task_id: str, done: int, status: str = "running") -> None:
        task = self._tasks.get(task_id)
        if not task:
            return
        task.done = done
        task.status = status
        q = self._queues.get(task_id)
        if q is not None:
            try:
                q.put_nowait(task.to_event())
            except asyncio.QueueFull:
                pass

    def add_error(self, task_id: str, url: str, msg: str) -> None:
        task = self._tasks.get(task_id)
        if task:
            task.errors.append({"url": url, "msg": msg})

    async def subscribe(self, task_id: str):
        """SSE 订阅 — async generator"""
        task = self._tasks.get(task_id)
        if not task:
            yield "data: {\"error\": \"task not found\"}\n\n"
            return
        # 先发当前快照
        yield task.to_event()
        q = self._queues.get(task_id)
        if q is None:
            return
        # 持续推送直到完成
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield event
                if task.status in ("done", "failed"):
                    break
            except asyncio.TimeoutError:
                # 30 秒没新事件，发心跳
                yield f": heartbeat\n\n"


# 全局唯一实例
progress_tracker = ProgressTracker()