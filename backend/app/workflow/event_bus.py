"""In-process workflow event broker used by the SSE endpoint.

The broker removes fixed-interval database polling. Each state mutation publishes a
lightweight signal, and connected SSE clients query the latest snapshot only when a
workflow actually changes. A production multi-worker deployment should replace this
with Redis/NATS/PostgreSQL LISTEN-NOTIFY.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict


_subscribers: dict[str, set[asyncio.Queue[None]]] = defaultdict(set)
_lock = asyncio.Lock()


async def subscribe(workflow_id: str) -> asyncio.Queue[None]:
    queue: asyncio.Queue[None] = asyncio.Queue(maxsize=1)
    async with _lock:
        _subscribers[workflow_id].add(queue)
    return queue


async def unsubscribe(workflow_id: str, queue: asyncio.Queue[None]) -> None:
    async with _lock:
        queues = _subscribers.get(workflow_id)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            _subscribers.pop(workflow_id, None)


async def publish_workflow_event(workflow_id: str) -> None:
    async with _lock:
        queues = tuple(_subscribers.get(workflow_id, ()))
    for queue in queues:
        if queue.full():
            continue
        queue.put_nowait(None)
