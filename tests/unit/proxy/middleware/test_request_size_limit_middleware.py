from collections.abc import AsyncIterator
from typing import Final

import httpx
import pytest
from fastapi import Depends, FastAPI, File, Request, UploadFile
from starlette.responses import JSONResponse
from starlette.testclient import TestClient
from starlette.types import Message, Receive, Scope, Send

from litellm.proxy.middleware.request_size_limit_middleware import (
    RequestSizeLimitMiddleware,
)


def test_request_size_limit_middleware_rejects_content_length_before_body_read():
    downstream_called = False

    async def app(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True
        response = JSONResponse({"ok": True})
        await response(scope, receive, send)

    client = TestClient(
        RequestSizeLimitMiddleware(
            app,
            get_max_request_size_mb=lambda: 1,
            is_request_size_limit_enabled=lambda: True,
        )
    )

    response = client.post(
        "/chat/completions",
        content=b"x" * (1024 * 1024 + 1),
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 413
    assert response.json() == {"error": "Request size is too large. Max size is 1 MB"}
    assert response.headers["content-length"] == str(len(response.content))
    assert downstream_called is False


def test_request_size_limit_middleware_zero_limit_disables_guard():
    downstream_called = False

    async def app(scope, receive, send):
        nonlocal downstream_called
        downstream_called = True
        response = JSONResponse({"ok": True})
        await response(scope, receive, send)

    client = TestClient(
        RequestSizeLimitMiddleware(
            app,
            get_max_request_size_mb=lambda: 0,
            is_request_size_limit_enabled=lambda: True,
        )
    )

    response = client.post(
        "/chat/completions",
        content=b"x",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert downstream_called is True


@pytest.mark.asyncio
async def test_request_size_limit_middleware_rejects_streamed_body_without_content_length():
    received_body_bytes = 0

    async def app(scope, receive, send):
        nonlocal received_body_bytes
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                break
            received_body_bytes += len(message.get("body", b""))
            if not message.get("more_body", False):
                break

        response = JSONResponse({"ok": True})
        await response(scope, receive, send)

    middleware = RequestSizeLimitMiddleware(
        app,
        get_max_request_size_mb=lambda: 1,
        is_request_size_limit_enabled=lambda: True,
    )
    sent_messages: list[Message] = []
    receive_messages: list[Message] = [
        {
            "type": "http.request",
            "body": b"x" * (1024 * 1024),
            "more_body": True,
        },
        {
            "type": "http.request",
            "body": b"y",
            "more_body": False,
        },
    ]

    async def receive():
        return receive_messages.pop(0)

    async def send(message):
        sent_messages.append(message)

    await middleware(
        {
            "type": "http",
            "method": "POST",
            "path": "/chat/completions",
            "headers": [(b"content-type", b"application/json")],
        },
        receive,
        send,
    )

    expected_body = b'{"error":"Request size is too large. Max size is 1 MB"}'
    assert sent_messages[0] == {
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(expected_body)).encode("latin-1")),
        ],
    }
    assert sent_messages[1] == {
        "type": "http.response.body",
        "body": expected_body,
        "more_body": False,
    }
    assert received_body_bytes == 1024 * 1024


def test_an_oversized_messages_request_gets_the_anthropic_request_too_large_error() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    client: Final = TestClient(
        RequestSizeLimitMiddleware(app, get_max_request_size_mb=lambda: 1, is_request_size_limit_enabled=lambda: True)
    )

    response: Final = client.post(
        "/v1/messages", content=b"x" * (1024 * 1024 + 1), headers={"content-type": "application/json"}
    )

    assert response.status_code == 413
    assert response.json() == {
        "type": "error",
        "error": {"type": "request_too_large", "message": "Request size is too large. Max size is 1 MB"},
    }


@pytest.mark.parametrize(
    ("method", "path", "root_path", "global_enabled", "global_limit", "expected_status"),
    (
        ("POST", "/claude-code/plugins/upload", "", False, None, 413),
        ("POST", "/gateway/claude-code/plugins/upload", "/gateway", False, None, 413),
        ("PUT", "/claude-code/plugins/upload", "", False, None, 200),
        ("POST", "/claude-code/plugins/upload-other", "", False, None, 200),
        ("POST", "/claude-code/plugins", "", False, 1, 200),
        ("POST", "/claude-code/plugins", "", True, 1, 413),
        ("POST", "/claude-code/plugins/upload", "", True, 10, 413),
    ),
)
def test_route_upload_limit_is_scoped_and_keeps_the_global_limit(
    method: str,
    path: str,
    root_path: str,
    global_enabled: bool,
    global_limit: float | None,
    expected_status: int,
) -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    client: Final = TestClient(
        RequestSizeLimitMiddleware(
            app,
            get_max_request_size_mb=lambda: global_limit,
            is_request_size_limit_enabled=lambda: global_enabled,
            route_max_request_size_mb={("POST", "/claude-code/plugins/upload"): 2},
        ),
        root_path=root_path,
    )

    response: Final = client.request(method, path, content=b"x" * (2 * 1024 * 1024 + 1))

    assert response.status_code == expected_status


def test_a_smaller_operator_limit_also_bounds_skill_uploads() -> None:
    async def app(scope: Scope, receive: Receive, send: Send) -> None:
        await JSONResponse({"ok": True})(scope, receive, send)

    client: Final = TestClient(
        RequestSizeLimitMiddleware(
            app,
            get_max_request_size_mb=lambda: 1,
            is_request_size_limit_enabled=lambda: True,
            route_max_request_size_mb={("POST", "/claude-code/plugins/upload"): 2},
        )
    )

    response: Final = client.post("/claude-code/plugins/upload", content=b"x" * (1024 * 1024 + 1))

    assert response.status_code == 413
    assert response.json() == {"error": "Request size is too large. Max size is 1 MB"}


def test_proxy_bounds_skill_uploads_before_authentication_or_body_parsing() -> None:
    from litellm.proxy.proxy_server import app

    response: Final = TestClient(app).post(
        "/claude-code/plugins/upload", content=b"", headers={"content-length": str(11 * 1024 * 1024 + 1)}
    )

    assert response.status_code == 413
    assert response.json() == {"error": "Request size is too large. Max size is 11 MB"}


@pytest.mark.asyncio
@pytest.mark.parametrize("body_parsed_before_auth", (True, False))
async def test_chunked_upload_overflow_stops_fastapi_and_auth_multipart_parsing(
    body_parsed_before_auth: bool,
) -> None:
    from litellm.proxy.auth.user_api_key_auth import user_api_key_auth

    app: Final = FastAPI()

    async def upload(file: UploadFile = File(...)) -> dict[str, int]:
        return {"bytes": len(await file.read())}

    async def auth_first(request: Request) -> dict[str, int]:
        return {"fields": len(await request.form())}

    app.add_api_route(
        "/claude-code/plugins/upload",
        upload if body_parsed_before_auth else auth_first,
        methods=["POST"],
        dependencies=[Depends(user_api_key_auth)],
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        get_max_request_size_mb=lambda: None,
        is_request_size_limit_enabled=lambda: False,
        route_max_request_size_mb={("POST", "/claude-code/plugins/upload"): 1 / 1024},
    )

    async def chunks() -> AsyncIterator[bytes]:
        yield b'--skill\r\nContent-Disposition: form-data; name="file"; filename="skill.zip"\r\n\r\n'
        yield b"x" * 1024
        pytest.fail("The server consumed more of the upload after its byte limit")

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        response: Final = await client.post(
            "/claude-code/plugins/upload",
            content=chunks(),
            headers={"content-type": "multipart/form-data; boundary=skill"},
        )

    assert response.status_code == 413
    assert response.json() == {"detail": "Request size is too large. Max size is 0.0009765625 MB"}
