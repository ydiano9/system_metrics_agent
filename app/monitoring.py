"""Exposition des métriques reçues au format Prometheus.

Chaque payload reçu par l'API met à jour des jauges étiquetées par
agent et par hostname. Prometheus les scrape sur `GET /prometheus`
et Grafana les affiche.
"""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import Counter, Gauge

LABELS = ("agent", "hostname")

PAYLOADS_RECEIVED = Counter(
    "sma_payloads_received_total",
    "Nombre de payloads de métriques reçus par l'API.",
    LABELS,
)
LAST_SEEN = Gauge(
    "sma_agent_last_seen_timestamp_seconds",
    "Horodatage Unix du dernier payload reçu d'un agent.",
    LABELS,
)
CPU_PERCENT = Gauge("sma_cpu_percent", "Utilisation CPU en pourcentage.", LABELS)
CPU_CORES = Gauge("sma_cpu_logical_cores", "Nombre de coeurs logiques.", LABELS)
MEMORY_PERCENT = Gauge(
    "sma_memory_percent", "Utilisation mémoire en pourcentage.", LABELS
)
MEMORY_USED = Gauge("sma_memory_used_bytes", "Mémoire utilisée en octets.", LABELS)
MEMORY_TOTAL = Gauge("sma_memory_total_bytes", "Mémoire totale en octets.", LABELS)
LOAD = Gauge(
    "sma_load_average",
    "Charge système moyenne (sortie de la commande uptime).",
    (*LABELS, "period"),
)


def _set_if_number(gauge: Gauge, value: Any, **labels: str) -> None:
    """Met à jour une jauge seulement si la valeur est numérique."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        gauge.labels(**labels).set(value)


def record(agent: str, data: dict[str, Any]) -> None:
    """Met à jour les métriques Prometheus à partir d'un payload."""
    labels = {"agent": agent, "hostname": str(data.get("hostname", "unknown"))}

    PAYLOADS_RECEIVED.labels(**labels).inc()
    LAST_SEEN.labels(**labels).set(time.time())

    cpu = data.get("cpu") or {}
    _set_if_number(CPU_PERCENT, cpu.get("percent"), **labels)
    _set_if_number(CPU_CORES, cpu.get("logical_cores"), **labels)

    memory = data.get("memory") or {}
    _set_if_number(MEMORY_PERCENT, memory.get("percent"), **labels)
    _set_if_number(MEMORY_USED, memory.get("used_bytes"), **labels)
    _set_if_number(MEMORY_TOTAL, memory.get("total_bytes"), **labels)

    system = data.get("system") or {}
    for period in ("1m", "5m", "15m"):
        _set_if_number(LOAD, system.get(f"load_{period}"), period=period, **labels)
