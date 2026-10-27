"""Bound mutation bodies before parsing, including requests without Content-Length."""

from uuid import uuid4
import asyncio

from starlette.responses import JSONResponse


class BoundedBodyMiddleware:
    def __init__(self, app, max_bytes: int = 16_384):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, send)
        messages, size = [], 0
        failure = None
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    size += len(message.get("body", b""))
                    if size > self.max_bytes or len(messages) >= 256:
                        failure = (413, "REQUEST_TOO_LARGE", "This request is too large.")
                        break
                    messages.append(message)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            failure = (408, "REQUEST_TIMEOUT", "The request body took too long. Retry the request.")
        if failure:
            status, code, message = failure
            request_id = str(uuid4())
            response = JSONResponse(
                {
                    "error": {
                        "code": code,
                        "message": message,
                        "retryable": status == 408,
                        "request_id": request_id,
                        "field_errors": [],
                        "retry_after_seconds": None,
                    }
                },
                status_code=status,
                headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
            )
            return await response(scope, receive, send)

        async def buffered_receive():
            return messages.pop(0) if messages else await receive()

        await self.app(scope, buffered_receive, send)
