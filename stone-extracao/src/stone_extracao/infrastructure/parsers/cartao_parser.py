from stone_extracao.domain.cartao.models import TransacaoCartao
from stone_extracao.infrastructure.parsers.cartao_xml import (
    ParseCartaoResult,
    parse_cartao_xml,
    parse_cartao_xml_with_stats,
)


class CartaoXmlParser:
    def parse(self, content: bytes | str) -> list[TransacaoCartao]:
        return parse_cartao_xml(content)

    def parse_with_stats(self, content: bytes | str) -> ParseCartaoResult:
        return parse_cartao_xml_with_stats(content)
