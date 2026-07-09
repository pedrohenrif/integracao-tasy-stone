from __future__ import annotations

from pathlib import Path

import httpx

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class CartaoFetchError(Exception):
    pass


async def fetch_conciliation_xml(
    reference_date: str,
    *,
    use_sample: bool = False,
    sample_path: str | None = None,
) -> bytes:
    """
    Busca o arquivo de conciliação de cartão da Stone.

    Em desenvolvimento, use_sample=True (ou STONE_CARTAO_SAMPLE_PATH) evita a API.
    reference_date: YYYYMMDD
    """
    if use_sample or not settings.STONE_API_TOKEN:
        path = Path(sample_path or settings.STONE_CARTAO_SAMPLE_PATH)
        if not path.is_file():
            # tenta relativo à pasta do projeto
            alt = Path(__file__).resolve().parents[2] / path
            if alt.is_file():
                path = alt
            else:
                workspace_root = Path(__file__).resolve().parents[3]
                alt2 = workspace_root / path.name
                if alt2.is_file():
                    path = alt2
                else:
                    raise CartaoFetchError(f"Sample XML não encontrado: {path}")
        logger.info("Recebido | fonte=sample | path=%s | date=%s", path, reference_date)
        return path.read_bytes()

    url = (
        f"{settings.STONE_CONCILIATION_BASE_URL.rstrip('/')}"
        f"/merchant/{settings.STONE_MERCHANT_ID}"
        f"/conciliation-file/{reference_date}"
    )
    headers = {"Authorization": f"Bearer {settings.STONE_API_TOKEN}"}
    logger.info("Recebido | fonte=stone_api | url=%s", url)
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, headers=headers)
        if response.status_code != 200:
            raise CartaoFetchError(
                f"Stone API retornou {response.status_code}: {response.text[:300]}"
            )
        return response.content
