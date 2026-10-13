import pytest
from fastapi.testclient import TestClient

from app import api

client = TestClient(api.app)

PAYLOAD = {
    "agent": "test-agent",
    "event_type": "system_metrics",
    "data": {
        "timestamp": "2026-10-13T00:00:00+00:00",
        "hostname": "host-test",
        "cpu": {"percent": 12.5, "logical_cores": 4},
        "memory": {
            "total_bytes": 1000,
            "available_bytes": 400,
            "used_bytes": 600,
            "percent": 60.0,
        },
        "system": {"load_1m": 0.1, "load_5m": 0.2, "load_15m": 0.3},
    },
}


@pytest.fixture(autouse=True)
def reset_storage():
    api.received_metrics.clear()
    yield
    api.received_metrics.clear()


def test_health():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_latest_without_metrics_returns_404():
    response = client.get("/metrics/latest")

    assert response.status_code == 404


def test_post_then_latest():
    post = client.post("/metrics", json=PAYLOAD)
    latest = client.get("/metrics/latest")

    assert post.status_code == 201
    assert post.json()["total_received"] == 1
    assert latest.status_code == 200
    assert latest.json()["data"]["cpu"]["percent"] == 12.5
    assert "received_at" in latest.json()


def test_get_all_metrics():
    client.post("/metrics", json=PAYLOAD)
    client.post("/metrics", json=PAYLOAD)

    response = client.get("/metrics")

    assert response.json()["total"] == 2


def test_invalid_payload_is_rejected():
    response = client.post("/metrics", json={"agent": "", "data": {}})

    assert response.status_code == 422


def test_prometheus_endpoint_exposes_received_metrics():
    client.post("/metrics", json=PAYLOAD)

    response = client.get("/prometheus")
    body = response.text

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert 'sma_cpu_percent{agent="test-agent",hostname="host-test"} 12.5' in body
    assert (
        'sma_load_average{agent="test-agent",hostname="host-test",period="5m"} 0.2'
        in body
    )
    assert "sma_payloads_received_total" in body


def test_prometheus_ignores_non_numeric_values():
    payload = {
        "agent": "test-agent",
        "event_type": "system_metrics",
        "data": {"hostname": "host-nan", "system": {"load_1m": None}},
    }

    response = client.post("/metrics", json=payload)
    body = client.get("/prometheus").text

    assert response.status_code == 201
    assert 'hostname="host-nan",period="1m"' not in body
