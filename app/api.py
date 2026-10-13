"""API FastAPI de réception des métriques."""

from __future__ import annotations

import logging
import os
from collections import deque
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel, Field

from app import monitoring

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Historique borné : évite que la mémoire de l'API grossisse indéfiniment.
MAX_STORED_METRICS = int(os.getenv("MAX_STORED_METRICS", "1000"))

app = FastAPI(
    title="System Metrics API",
    description="API de réception des métriques envoyées par les agents.",
    version="1.1.0",
)

received_metrics: deque[dict[str, Any]] = deque(maxlen=MAX_STORED_METRICS)


class MetricsPayload(BaseModel):
    """Payload reçu depuis l'agent."""

    agent: str = Field(..., min_length=1)
    event_type: str
    data: dict[str, Any]


@app.get("/metrics")
def get_metrics() -> dict[str, Any]:
    """Retourne toutes les métriques reçues."""
    return {
        "total": len(received_metrics),
        "metrics": list(received_metrics),
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Vérifie l'état de l'API."""
    return {"status": "ok"}


@app.post("/metrics", status_code=status.HTTP_201_CREATED)
def receive_metrics(payload: MetricsPayload) -> dict[str, Any]:
    """Reçoit et stocke temporairement les métriques."""
    item = {
        "received_at": datetime.now(timezone.utc).isoformat(),
        **payload.model_dump(),
    }
    received_metrics.append(item)
    monitoring.record(payload.agent, payload.data)

    logger.info(
        "Métriques reçues de %s. Total=%s",
        payload.agent,
        len(received_metrics),
    )

    return {
        "status": "received",
        "message": "Métriques enregistrées avec succès.",
        "total_received": len(received_metrics),
    }


@app.get("/metrics/latest")
def latest_metrics() -> dict[str, Any]:
    """Retourne la dernière métrique reçue."""
    if not received_metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Aucune métrique disponible.",
        )

    return received_metrics[-1]


@app.get("/prometheus", include_in_schema=False)
def prometheus_metrics() -> Response:
    """Expose les métriques au format texte Prometheus.

    Le chemin `/metrics` étant déjà utilisé par l'API métier,
    Prometheus scrape cet endpoint dédié.
    """
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
