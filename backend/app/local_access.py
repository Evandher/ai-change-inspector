"""Browser-origin defenses for a loopback-only, single-user service (not authentication)."""

import ipaddress
from urllib.parse import urlsplit

from starlette.datastructures import Headers
from starlette.responses import JSONResponse

from app.local_settings import api_url, web_url

MAX_BODY_BYTES = 8 * 1024 * 1024


class LocalAccessMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        original_send = send

        async def secured_send(message):
            if message["type"] == "http.response.start":
                message = {
                    **message,
                    "headers": list(message.get("headers", []))
                    + [
                        (b"cache-control", b"no-store"),
                        (b"x-content-type-options", b"nosniff"),
                        (b"x-frame-options", b"DENY"),
                    ],
                }
            await original_send(message)

        send = secured_send
        origins = {api_url(), web_url()}
        hosts = {urlsplit(origin).netloc for origin in origins}

        async def reject(code: str, message: str, status: int = 403):
            await JSONResponse(
                status_code=status,
                content={
                    "error": {"code": code, "message": message, "line": None},
                },
            )(scope, receive, send)

        try:
            local_peer = ipaddress.ip_address(scope.get("client", ("", 0))[0]).is_loopback
        except (ValueError, TypeError):
            local_peer = False
        if (
            not local_peer
            or headers.get("host", "").lower() not in hosts
            or (headers.get("origin") is not None and headers["origin"] not in origins)
            or headers.get("sec-fetch-site") == "cross-site"
        ):
            return await reject("local_access_denied", "Origen o Host no permitido.")
        if scope["method"] in ("POST", "PUT", "PATCH", "DELETE"):
            if headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
                return await reject("json_required", "Se requiere application/json.", 415)
            if (
                scope["path"].startswith("/api/reviews")
                and headers.get("x-inspector-request") != "1"
            ):
                return await reject(
                    "request_marker_required", "Falta el marcador de solicitud local."
                )
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > MAX_BODY_BYTES:
                    return await reject("request_too_large", "Cuerpo HTTP demasiado grande.", 413)
                if not message.get("more_body", False):
                    break
            delivered = False

            async def replay():
                nonlocal delivered
                if not delivered:
                    delivered = True
                    return {"type": "http.request", "body": bytes(body), "more_body": False}
                return await receive()

            return await self.app(scope, replay, send)
        return await self.app(scope, receive, send)
