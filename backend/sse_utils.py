import asyncio
import json
import threading

from fastapi import Request


def sse_event(data: dict) -> str:
    """Formats one Server-Sent-Events frame. Was hand-rolled as
    f"data: {json.dumps(data)}\\n\\n" independently in every streaming route."""
    return f"data: {json.dumps(data)}\n\n"


async def poll_for_cancel(request: Request, task: "asyncio.Task", cancel_event: threading.Event) -> bool:
    """Polls `task` for completion while watching for client disconnect. If the client
    disconnects first, sets cancel_event, cancels the task, and returns True (the caller
    should stop and return, doing whatever cleanup is specific to that route). Returns
    False once the task completes normally, so the caller can read its result."""
    while not task.done():
        await asyncio.sleep(0.5)
        if await request.is_disconnected():
            cancel_event.set()
            task.cancel()
            return True
    return False
