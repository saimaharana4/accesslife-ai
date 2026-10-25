"""Bound mutation bodies before parsing, including requests without Content-Length."""

from uuid import uuid4

from starlette.responses import JSONResponse


class BoundedBodyMiddleware:
    def __init__(self, app, max_bytes: int = 16_384):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] not in {"POST", "PUT", "PATCH", "DELETE"}:
            return await self.app(scope, receive, send)
        messages, size = [], 0
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            size += len(message.get("body", b""))
            if size > self.max_bytes:
                request_id = str(uuid4())
                response = JSONResponse(
                    {
                        "error": {
                            "code": "REQUEST_TOO_LARGE",
                            "message": "This request is too large.",
                            "retryable": False,
                            "request_id": request_id,
                            "field_errors": [],
                            "retry_after_seconds": None,
                        }
                    },
                    status_code=413,
                    headers={"Cache-Control": "no-store", "X-Request-ID": request_id},
                )
                return await response(scope, receive, send)
            messages.append(message)
            if not message.get("more_body", False):
                break

        async def buffered_receive():
            return messages.pop(0) if messages else await receive()

        await self.app(scope, buffered_receive, send)
