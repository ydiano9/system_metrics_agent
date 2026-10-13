from unittest.mock import patch

import pytest

from app import agent
from app.config import Settings


def test_settings_from_env(monkeypatch):
    monkeypatch.setenv("METRICS_ENDPOINT", "http://api:8000/metrics")
    monkeypatch.setenv("COLLECTION_INTERVAL", "2")
    monkeypatch.setenv("REQUEST_TIMEOUT", "3")

    settings = Settings.from_env()

    assert settings.metrics_endpoint == "http://api:8000/metrics"
    assert settings.collection_interval == 2.0
    assert settings.request_timeout == 3.0


@pytest.mark.parametrize("value", ["abc", "0", "-1"])
def test_settings_rejects_invalid_interval(monkeypatch, value):
    monkeypatch.setenv("COLLECTION_INTERVAL", value)

    with pytest.raises(ValueError):
        Settings.from_env()


@patch("app.agent.send_metrics")
@patch("app.agent.collect_system_metrics")
def test_run_once(mock_collect, mock_send):
    mock_collect.return_value = {
        "timestamp": "t",
        "hostname": "h",
        "cpu": {},
        "memory": {},
        "system": {},
    }
    mock_send.return_value = {"status_code": 201, "response": {}}
    settings = Settings("http://api:8000/metrics", 5, 2)

    result = agent.run_once(settings)

    assert result["status_code"] == 201
    kwargs = mock_send.call_args.kwargs
    assert kwargs["endpoint"] == "http://api:8000/metrics"
    assert kwargs["timeout"] == 2
    assert kwargs["payload"]["event_type"] == "system_metrics"
