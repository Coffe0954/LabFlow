"""Рассылка обновлений очереди всем подписчикам по WebSocket."""

import logging
from collections import defaultdict
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class QueueHub:
    def __init__(self) -> None:
        self._subs: dict[int, set[WebSocket]] = defaultdict(set)

    def add(self, queue_id: int, ws: WebSocket) -> None:
        self._subs[queue_id].add(ws)

    def remove(self, queue_id: int, ws: WebSocket) -> None:
        subs = self._subs.get(queue_id)
        if subs is not None:
            subs.discard(ws)
            if not subs:
                del self._subs[queue_id]

    def active_queue_ids(self) -> list[int]:
        return list(self._subs)

    def subscribers(self, queue_id: int) -> int:
        return len(self._subs.get(queue_id, ()))

    async def broadcast(self, queue_id: int, message: dict[str, Any]) -> None:
        for ws in list(self._subs.get(queue_id, ())):
            try:
                await ws.send_json(message)
            except Exception:  # клиент отвалился — просто убираем его
                logger.debug("WebSocket отключён при рассылке", exc_info=True)
                self.remove(queue_id, ws)


hub = QueueHub()
