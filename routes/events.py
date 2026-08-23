import asyncio
import json

from fastapi import APIRouter, Depends
from sse_starlette.sse import EventSourceResponse

from dependency.auth import get_current_user_from_query_token  
from sse.connection_manager import connection_manager

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/stream")
async def stream(current_user=Depends(get_current_user_from_query_token)):
    queue = connection_manager.register(current_user.id)

    async def event_generator():
        try:
            while True:
                ticket = await queue.get()
                yield {"event": "ticket", "data": json.dumps(ticket)}
        except asyncio.CancelledError:
            pass
        finally:
            connection_manager.unregister(current_user.id, queue)

    return EventSourceResponse(event_generator())