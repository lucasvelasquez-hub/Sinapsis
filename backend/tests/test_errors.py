"""Errores inesperados: mismo sobre de error, identificador de request y log."""

import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app

BOOM_PATH = "/api/v1/__test_boom"


@pytest.fixture
def boom_client() -> Iterator[TestClient]:
    def boom() -> None:
        raise RuntimeError("secreto interno")

    app.add_api_route(BOOM_PATH, boom, methods=["GET"])
    try:
        yield TestClient(app, raise_server_exceptions=False)
    finally:
        app.router.routes = [r for r in app.router.routes if getattr(r, "path", "") != BOOM_PATH]


def test_unhandled_error_returns_envelope_with_request_id(
    boom_client: TestClient, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.ERROR):
        resp = boom_client.get(BOOM_PATH, headers={"X-Request-ID": "req-123"})

    assert resp.status_code == 500
    body = resp.json()["error"]
    assert body["code"] == "INTERNAL_ERROR"
    assert body["request_id"] == "req-123"
    assert "secreto interno" not in resp.text  # no se filtran detalles internos
    assert any("req-123" in r.getMessage() and r.exc_info for r in caplog.records)


def test_request_id_is_generated_and_echoed(client: TestClient) -> None:
    resp = client.get("/api/v1/health")

    assert resp.headers.get("X-Request-ID")


def test_request_id_from_client_is_echoed(client: TestClient) -> None:
    resp = client.get("/api/v1/health", headers={"X-Request-ID": "abc-1"})

    assert resp.headers.get("X-Request-ID") == "abc-1"


def test_domain_error_includes_request_id(client: TestClient) -> None:
    resp = client.get("/api/v1/requests/NOPE", headers={"X-Request-ID": "abc-2"})

    assert resp.status_code == 404
    assert resp.json()["error"]["request_id"] == "abc-2"
