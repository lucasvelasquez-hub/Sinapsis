"""Filtros de la cola de solicitudes: tipo de servicio y búsqueda por ID."""

from fastapi.testclient import TestClient


def test_filter_by_service_type(client: TestClient) -> None:
    body = client.get("/api/v1/requests?service_type=Dolor%20tor%C3%A1cico&limit=50").json()

    assert body
    assert {r["service_type"] for r in body} == {"Dolor torácico"}


def test_search_by_id_is_case_insensitive_contains(client: TestClient) -> None:
    body = client.get("/api/v1/requests?q=srv-0099&limit=50").json()

    assert body
    assert all("SRV-0099" in r["service_id"] for r in body)


def test_search_treats_wildcards_literally(client: TestClient) -> None:
    assert client.get("/api/v1/requests?q=%25").json() == []
    assert client.get("/api/v1/requests?q=_").json() == []


def test_search_is_bounded(client: TestClient) -> None:
    assert client.get("/api/v1/requests?q=" + "x" * 33).status_code == 422


def test_pending_queue_orders_by_urgency_then_oldest_first(client: TestClient) -> None:
    created = {}
    for urgency, when in [
        ("06", "2026-05-01T10:00:00"),
        ("01", "2026-05-01T10:05:00"),
        ("02", "2026-05-01T10:01:00"),
        ("01", "2026-05-01T10:02:00"),
        ("03", "2026-05-01T10:00:30"),
    ]:
        resp = client.post(
            "/api/v1/requests/simulate",
            json={
                "urgency_level": urgency,
                "service_type": "Dolor torácico",
                "zone_id": "Z-MED-01-01",
                "request_datetime": when,
            },
        )
        assert resp.status_code == 201, resp.text
        created[resp.json()["service_id"]] = (urgency, when)

    body = client.get("/api/v1/requests?status=PENDING&limit=200").json()
    ours = [created[r["service_id"]] for r in body if r["service_id"] in created]

    assert ours == [
        ("01", "2026-05-01T10:02:00"),
        ("01", "2026-05-01T10:05:00"),
        ("02", "2026-05-01T10:01:00"),
        ("03", "2026-05-01T10:00:30"),
        ("06", "2026-05-01T10:00:00"),
    ]


def test_other_views_keep_newest_first(client: TestClient) -> None:
    body = client.get("/api/v1/requests?status=COMPLETED&limit=5").json()
    times = [r["request_datetime"] for r in body]

    assert times == sorted(times, reverse=True)
