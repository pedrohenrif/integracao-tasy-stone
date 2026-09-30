from __future__ import annotations

from stone_extracao.domain.pix.models import TransacaoPix
from stone_extracao.infrastructure.parsers.pix_csv import (
    ParsePixResult,
    parse_pix_csv,
    parse_pix_csv_with_stats,
)


class PixCsvParser:
    def parse(self, content: bytes | str) -> list[TransacaoPix]:
        return parse_pix_csv(content)

    def parse_with_stats(self, content: bytes | str) -> ParsePixResult:
        return parse_pix_csv_with_stats(content)
