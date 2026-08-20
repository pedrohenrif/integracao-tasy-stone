from __future__ import annotations

import base64
import gzip
from typing import Mapping

from stone_extracao.infrastructure.config.settings import settings


def build_client_auth_headers(api_token: str | None = None) -> dict[str, str]:
    """
    Auth de Cliente Stone (lojista) — Portal Stone chave sk_...

    Docs: https://conciliacao.stone.com.br/reference/overview-da-api-cliente-stone
      Authorization: Basic base64("{chave}:")
      x-user-type: client
      Accept-Encoding: gzip
    """
    token = (api_token if api_token is not None else settings.STONE_API_TOKEN).strip()
    # User = chave, Password = vazio → "chave:"
    basic = base64.b64encode(f"{token}:".encode("ascii")).decode("ascii")
    return {
        "Authorization": f"Basic {basic}",
        "x-user-type": "client",
        "Accept-Encoding": "gzip",
    }


def decode_stone_body(content: bytes, headers: Mapping[str, str] | None = None) -> bytes:
    """Descompacta gzip se a Stone devolver o arquivo zipado."""
    if not content:
        return content

    encoding = ""
    if headers:
        encoding = (headers.get("content-encoding") or headers.get("Content-Encoding") or "").lower()

    is_gzip_magic = len(content) >= 2 and content[0] == 0x1F and content[1] == 0x8B
    if "gzip" in encoding or is_gzip_magic:
        try:
            return gzip.decompress(content)
        except OSError:
            return content
    return content
