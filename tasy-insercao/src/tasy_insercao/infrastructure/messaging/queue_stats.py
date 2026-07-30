from __future__ import annotations

from typing import Any

import httpx

from tasy_insercao.infrastructure.config.settings import settings


def _queue_names() -> list[str]:
    return [
        settings.RABBITMQ_QUEUE_CARTAO,
        settings.RABBITMQ_QUEUE_RETRY,
        settings.RABBITMQ_QUEUE_DLQ,
        settings.RABBITMQ_QUEUE_PIX,
        settings.RABBITMQ_QUEUE_PIX_RETRY,
        settings.RABBITMQ_QUEUE_PIX_DLQ,
    ]


def listar_filas() -> list[dict[str, Any]]:
    """Consulta RabbitMQ Management API (porta 15673)."""
    base = settings.RABBITMQ_MGMT_URL.rstrip("/")
    auth = (settings.RABBITMQ_MGMT_USER, settings.RABBITMQ_MGMT_PASS)
    resultado: list[dict[str, Any]] = []

    with httpx.Client(timeout=8.0, auth=auth) as client:
        for name in _queue_names():
            url = f"{base}/api/queues/%2F/{name}"
            try:
                resp = client.get(url)
                if resp.status_code == 404:
                    resultado.append(
                        {
                            "name": name,
                            "exists": False,
                            "messages": 0,
                            "messages_ready": 0,
                            "messages_unacknowledged": 0,
                            "consumers": 0,
                        }
                    )
                    continue
                resp.raise_for_status()
                data = resp.json()
                resultado.append(
                    {
                        "name": name,
                        "exists": True,
                        "messages": data.get("messages", 0),
                        "messages_ready": data.get("messages_ready", 0),
                        "messages_unacknowledged": data.get("messages_unacknowledged", 0),
                        "consumers": data.get("consumers", 0),
                        "state": data.get("state"),
                    }
                )
            except Exception as exc:
                resultado.append(
                    {
                        "name": name,
                        "exists": False,
                        "error": str(exc),
                        "messages": None,
                        "messages_ready": None,
                        "messages_unacknowledged": None,
                        "consumers": None,
                    }
                )
    return resultado
