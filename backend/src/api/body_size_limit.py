"""Request body size limit middleware.

Rejects requests whose Content-Length exceeds a configured maximum
before the body is read into memory, preventing memory-DoS from
oversized uploads.  Also wraps the ASGI ``receive`` callable to track
actual received bytes, catching chunked transfers that have no
Content-Length header.

Uses a raw ASGI middleware (not BaseHTTPMiddleware) so that streaming
responses such as SSE are not buffered.
"""

from __future__ import annotations

from starlette.types import ASGIApp, Receive, Scope, Send


class BodySizeLimitMiddleware:
    """Reject HTTP requests whose body exceeds *max_bytes*.

    Checks ``Content-Length`` first (fast reject).  For chunked requests
    that lack the header, wraps ``receive`` to accumulate actual bytes
    and abort once the limit is exceeded.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = 100 * 1024 * 1024) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length = headers.get(b"content-length")
        if content_length:
            try:
                size = int(content_length.decode())
            except ValueError:
                await self._send_error(send, 400, b'{"detail":"Invalid Content-Length header"}')
                return
            if size > self.max_bytes:
                max_mb = self.max_bytes // (1024 * 1024)
                body = f'{{"detail":"Request body too large. Maximum size: {max_mb}MB"}}'.encode()
                await self._send_error(send, 413, body)
                return

        # Wrap receive to track actual bytes for chunked transfers.
        # When the limit is exceeded, send 413 directly and drain remaining
        # messages.  Also wrap send so that the downstream app's response
        # is silently dropped (the 413 has already been sent).
        total_received = 0
        limit_exceeded = False

        async def wrapped_receive() -> dict:
            nonlocal total_received, limit_exceeded
            message = await receive()

            if message["type"] == "http.request":
                chunk = message.get("body", b"")
                total_received += len(chunk)
                if total_received > self.max_bytes and not limit_exceeded:
                    limit_exceeded = True
                    max_mb = self.max_bytes // (1024 * 1024)
                    body = f'{{"detail":"Request body too large. Maximum size: {max_mb}MB"}}'.encode()
                    await self._send_error(send, 413, body)
                    # Drain remaining receive messages to avoid blocking the client
                    while message.get("more_body", False):
                        message = await receive()

            return message

        async def wrapped_send(message: dict) -> None:
            # Suppress any response the app tries to send after we already
            # responded with 413.
            if limit_exceeded:
                return
            await send(message)

        await self.app(scope, wrapped_receive, wrapped_send)

    @staticmethod
    async def _send_error(send: Send, status: int, body: bytes) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [[b"content-type", b"application/json"]],
            }
        )
        await send(
            {
                "type": "http.response.body",
                "body": body,
            }
        )
