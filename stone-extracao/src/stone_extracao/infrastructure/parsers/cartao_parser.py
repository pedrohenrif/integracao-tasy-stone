from __future__ import annotations

from stone_extracao.domain.cartao.models import TransacaoCartao
from stone_extracao.infrastructure.parsers.cartao_xml import parse_cartao_xml


class CartaoXmlParser:
    def parse(self, content: bytes | str) -> list[TransacaoCartao]:
        return parse_cartao_xml(content)
