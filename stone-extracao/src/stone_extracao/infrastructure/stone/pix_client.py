from __future__ import annotations

from pathlib import Path

import httpx

from stone_extracao.infrastructure.config.logging import get_logger
from stone_extracao.infrastructure.config.settings import settings
from stone_extracao.infrastructure.stone.auth import build_client_auth_headers, decode_stone_body

logger = get_logger(__name__)


class PixFetchError(Exception):
    pass


class StonePixClient:
    """
    Adapter PIX Stone (Cliente Stone).

    Fluxo oficial (diferente do cartão):
      1) Cadastrar webhook HTTPS: POST /v2/webhook {"url": "..."}
      2) Solicitar extrato: POST /v2/merchant/{cnpj}/conciliation-file/pix/{date}
      3) Stone notifica o webhook com {"type":"pix","downloadUrl"|"url":"..."}
      4) Baixar o CSV na URL assinada e publicar na fila
    """

    async def request_extract(self, reference_date: str) -> dict:
        """
        reference_date: YYYY-MM-DD
        Endpoint oficial: POST /merchant/{cnpj}/conciliation-file/pix/{date}
        """
        if settings.STONE_USE_SAMPLE:
            raw = self.read_sample()
            logger.info(
                "PIX request | fonte=sample | date=%s | bytes=%s (publica no body)",
                reference_date,
                len(raw),
            )
            return {
                "status": "ok",
                "source": "sample",
                "reference_date": reference_date,
                "has_body": True,
                "raw_bytes": raw,
                "message": (
                    "Modo sample: CSV local no body — SolicitarExtratoPix publica na fila. "
                    "Alternativa: POST /pix/conciliation/dev"
                ),
            }

        if not settings.STONE_API_TOKEN:
            raise PixFetchError("STONE_API_TOKEN não configurado")

        merchant = "".join(ch for ch in (settings.STONE_PIX_MERCHANT_ID or "") if ch.isdigit())
        if not merchant:
            raise PixFetchError(
                "STONE_PIX_MERCHANT_ID vazio ou inválido. "
                "Use o CNPJ do merchant PIX (14 dígitos), não o StoneCode do cartão. "
                "Sem isso a Stone responde 400 ClientIdentifier/ClientId or AccountId."
            )
        if len(merchant) != 14:
            logger.warning(
                "PIX request | STONE_PIX_MERCHANT_ID=%s tem %s dígitos "
                "(esperado CNPJ 14). StoneCode do cartão costuma falhar com ClientIdentifier.",
                merchant,
                len(merchant),
            )
        url = (
            f"{settings.STONE_CONCILIATION_BASE_URL.rstrip('/')}"
            f"/merchant/{merchant}"
            f"/conciliation-file/pix/{reference_date}"
        )
        headers = {
            **build_client_auth_headers(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        logger.info(
            "PIX request | início | date=%s | merchant=%s | method=POST | url=%s",
            reference_date,
            merchant,
            url,
        )

        async with httpx.AsyncClient(timeout=90.0, follow_redirects=True) as client:
            response = await client.post(url, headers=headers)
            if response.status_code not in (200, 202, 204):
                body = (response.text or "")[:500]
                logger.error(
                    "PIX request | falha Stone | date=%s | http=%s | body=%s",
                    reference_date,
                    response.status_code,
                    body,
                )
                hint = ""
                if "ClientIdentifier" in body or "ClientId" in body or "AccountId" in body:
                    hint = (
                        " | Dica: confira STONE_PIX_MERCHANT_ID (CNPJ 14 dígitos do merchant PIX) "
                        "e se STONE_API_TOKEN é a chave de Cliente Stone (x-user-type: client)."
                    )
                raise PixFetchError(
                    f"Stone PIX API {response.status_code}: {body[:350]}{hint}"
                )

            raw = decode_stone_body(response.content, response.headers) if response.content else b""
            content_type = (response.headers.get("content-type") or "").lower()
            body_preview = ""
            if raw:
                try:
                    body_preview = raw[:200].decode("utf-8", errors="replace")
                except Exception:
                    body_preview = "<binary>"

            logger.info(
                "PIX request | aceito | date=%s | http=%s | content_type=%s | "
                "has_body=%s | body_bytes=%s | preview=%s",
                reference_date,
                response.status_code,
                content_type or "-",
                bool(raw),
                len(raw),
                body_preview[:160].replace("\n", " "),
            )
            return {
                "status": "accepted" if response.status_code in (202, 204) else "ok",
                "http_status": response.status_code,
                "source": "stone_api",
                "reference_date": reference_date,
                "content_type": content_type,
                "has_body": bool(raw),
                "body_preview": body_preview,
                "message": (
                    "Extrato solicitado (assíncrono). Aguarde notificação em POST /pix/webhook "
                    "com downloadUrl/url e o download do CSV."
                ),
                "raw_bytes": raw,
            }

    async def register_webhook(self, webhook_url: str) -> dict:
        """POST /v2/webhook — cadastra URL HTTPS (Stone envia validation_notification)."""
        return await self._upsert_webhook(webhook_url, method="POST", ok_statuses=(201,))

    async def update_webhook(self, webhook_url: str) -> dict:
        """PUT /v2/webhook — atualiza URL HTTPS já cadastrada."""
        return await self._upsert_webhook(webhook_url, method="PUT", ok_statuses=(200, 204))

    async def _upsert_webhook(
        self,
        webhook_url: str,
        *,
        method: str,
        ok_statuses: tuple[int, ...],
    ) -> dict:
        if not settings.STONE_API_TOKEN:
            raise PixFetchError("STONE_API_TOKEN não configurado")

        url = webhook_url.strip()
        if not url.lower().startswith("https://"):
            raise PixFetchError("Webhook Stone exige URL HTTPS pública")

        endpoint = f"{settings.STONE_CONCILIATION_BASE_URL.rstrip('/')}/webhook"
        headers = {
            **build_client_auth_headers(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {"url": url}
        logger.info("PIX webhook %s | url=%s | target=%s", method, endpoint, url)

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.request(method, endpoint, headers=headers, json=payload)
            if response.status_code not in ok_statuses:
                raise PixFetchError(
                    f"Stone webhook {method} {response.status_code}: {response.text[:400]}"
                )
            return {
                "status": "ok",
                "http_status": response.status_code,
                "webhook_url": url,
                "message": (
                    "Webhook cadastrado."
                    if method == "POST"
                    else "Webhook atualizado."
                ),
            }

    async def download_file(self, url: str) -> bytes:
        """Baixa CSV na URL pré-assinada do webhook (sem Basic Auth)."""
        if not url or not url.strip():
            raise PixFetchError("downloadUrl vazia")

        logger.info("PIX download | url=%s", url[:120])
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            response = await client.get(url.strip())
            if response.status_code != 200:
                raise PixFetchError(
                    f"Download PIX {response.status_code}: {response.text[:300]}"
                )
            raw = decode_stone_body(response.content, response.headers)
            if not raw:
                raise PixFetchError("Download PIX retornou body vazio")
            logger.info("PIX download | bytes=%s", len(raw))
            return raw

    def read_sample(self) -> bytes:
        path = Path(settings.STONE_PIX_SAMPLE_PATH)
        candidates = [
            path,
            Path(__file__).resolve().parents[4] / path,
            Path(__file__).resolve().parents[5] / path.name,
        ]
        for candidate in candidates:
            if candidate.is_file():
                logger.info("PIX sample | path=%s", candidate)
                return candidate.read_bytes()
        raise PixFetchError(f"Sample PIX não encontrado: {path}")
