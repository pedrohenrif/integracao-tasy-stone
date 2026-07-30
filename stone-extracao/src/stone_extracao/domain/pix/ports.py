from __future__ import annotations

from typing import Protocol

from stone_extracao.domain.pix.models import EventoFilaPix, TransacaoPix


class PixConciliationPort(Protocol):
    """Solicita geração do extrato PIX na Stone (passo 1 do fluxo)."""

    async def request_extract(self, reference_date: str) -> dict: ...


class PixWebhookAdminPort(Protocol):
    """Cadastro/atualização da URL HTTPS do webhook PIX na Stone."""

    async def register_webhook(self, webhook_url: str) -> dict: ...

    async def update_webhook(self, webhook_url: str) -> dict: ...


class PixDownloadPort(Protocol):
    """Baixa o CSV na URL pré-assinada enviada no webhook."""

    async def download_file(self, url: str) -> bytes: ...


class PixParserPort(Protocol):
    def parse(self, content: bytes | str) -> list[TransacaoPix]: ...


class PixMessagePublisherPort(Protocol):
    async def publish_pix(self, evento: EventoFilaPix) -> None: ...
