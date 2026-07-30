from __future__ import annotations

from pathlib import Path

import httpx

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.stone.auth import build_client_auth_headers, decode_stone_body

logger = get_logger(__name__)


class StoneFetchError(Exception):
    pass


class StoneConciliationClient:
    """Adapter HTTP da API de Conciliação Stone (Cartão) — Cliente Stone."""

    async def fetch(self, reference_date: str) -> bytes:
        if settings.STONE_USE_SAMPLE:
            return self._read_sample(reference_date)

        if not settings.STONE_API_TOKEN:
            raise StoneFetchError(
                "STONE_API_TOKEN não configurado. "
                "Preencha no .env para homologação ou use STONE_USE_SAMPLE=true."
            )

        url = (
            f"{settings.STONE_CONCILIATION_BASE_URL.rstrip('/')}"
            f"/merchant/{settings.STONE_MERCHANT_ID}"
            f"/conciliation-file/{reference_date}"
        )
        headers = build_client_auth_headers()
        logger.info("Recebido | fonte=stone_api | url=%s | auth=Basic+x-user-type", url)

        # Stone pode responder 307 (ex.: arquivo em storage). Seguir redirect.
        async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise StoneFetchError(
                    f"Stone API {response.status_code}: {response.text[:400]}"
                )
            logger.info(
                "Stone OK | status=%s | bytes=%s | final_url=%s",
                response.status_code,
                len(response.content),
                response.url,
            )
            return decode_stone_body(response.content, response.headers)

    def _read_sample(self, reference_date: str) -> bytes:
        path = Path(settings.STONE_CARTAO_SAMPLE_PATH)
        candidates = [
            path,
            Path(__file__).resolve().parents[4] / path,
            Path(__file__).resolve().parents[5] / path.name,
        ]
        for candidate in candidates:
            if candidate.is_file():
                logger.info(
                    "Recebido | fonte=sample | path=%s | date=%s",
                    candidate,
                    reference_date,
                )
                return candidate.read_bytes()
        raise StoneFetchError(f"Sample XML não encontrado: {path}")
