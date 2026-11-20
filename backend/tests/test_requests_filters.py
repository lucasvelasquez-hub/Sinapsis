"""Filtros de la cola de solicitudes: tipo de servicio y búsqueda por ID."""

from fastapi.testclient import TestClient


def test_filter_by_service_type(client: TestClient) -> None:
    body = client.get("/api/v1/requests?service_type=EVENTO_ESPECIAL&limit=50").json()

    assert body
    assert {r["service_type"] for r in body} == {"EVENTO_ESPECIAL"}


def test_search_by_id_is_case_insensitive_contains(client: TestClient) -> None:
    body = client.get("/api/v1/requests?q=srv-0999&limit=50").json()

    assert body
    assert all("SRV-0999" in r["service_id"] for r in body)


def test_search_treats_wildcards_literally(client: TestClient) -> None:
    assert client.get("/api/v1/requests?q=%25").json() == []
    assert client.get("/api/v1/requests?q=_").json() == []


def test_search_is_bounded(client: TestClient) -> None:
    assert client.get("/api/v1/requests?q=" + "x" * 33).status_code == 422
