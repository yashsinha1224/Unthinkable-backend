# realtime/connection_manager.py
import asyncio
from collections import defaultdict
from typing import Dict, Set

_main_loop: asyncio.AbstractEventLoop | None = None


def bind_loop(loop: asyncio.AbstractEventLoop) -> None:
    global _main_loop
    _main_loop = loop


class ConnectionManager:
    def __init__(self):
        self._connections: Dict[int, Set[asyncio.Queue]] = defaultdict(set)

    def register(self, user_id: int) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._connections[user_id].add(queue)
        return queue

    def unregister(self, user_id: int, queue: asyncio.Queue) -> None:
        self._connections[user_id].discard(queue)
        if not self._connections[user_id]:
            del self._connections[user_id]

    def _dispatch(self, user_id: int, ticket: dict) -> None:
        for queue in self._connections.get(user_id, ()):
            try:
                queue.put_nowait(ticket)
            except asyncio.QueueFull:
                pass  
    def send_to_user(self, user_id: int, ticket: dict) -> None:
        """Safe to call from either sync (threadpool) or async route handlers."""
        if _main_loop is None:
            return
        _main_loop.call_soon_threadsafe(self._dispatch, user_id, ticket)

    def broadcast(self, user_ids: list[int], ticket: dict) -> None:
        for uid in user_ids:
            self.send_to_user(uid, ticket)


connection_manager = ConnectionManager()