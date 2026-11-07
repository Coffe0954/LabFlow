"""WS /api/v1/ws/queues/{id}?token=<JWT> — поток обновлений очереди.

Сразу после подключения сервер присылает текущее состояние, затем — после каждого
пересчёта: {"type": "queue_state", "data": QueueState}. Клиент может слать "ping",
сервер ответит "pong" (держит соединение живым через прокси).
"""

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.security import decode_access_token
from app.models import User
from app.services import queue_service as qs
from app.ws.hub import hub

router = APIRouter()


@router.websocket("/ws/queues/{queue_id}")
async def queue_updates(websocket: WebSocket, queue_id: int, token: str = "") -> None:
    factory: async_sessionmaker[AsyncSession] = websocket.app.state.session_factory
    user_id = decode_access_token(token)
    # Короткая сессия только на проверку и первое состояние — не держим соединение с БД.
    async with factory() as db:
        user = await db.get(User, user_id) if user_id is not None else None
        if user is None:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        try:
            queue = await qs.get_queue(db, queue_id)
        except HTTPException:  # очередь не найдена
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        state = await qs.build_state(db, queue)

    await websocket.accept()
    hub.add(queue_id, websocket)
    try:
        await websocket.send_json({"type": "queue_state", "data": state.model_dump(mode="json")})
        while True:
            message = await websocket.receive_text()
            if message == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        pass
    finally:
        hub.remove(queue_id, websocket)
