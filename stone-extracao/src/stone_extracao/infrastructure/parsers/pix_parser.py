from __future__ import annotations

from stone_extracao.domain.pix.models import TransacaoPix
from stone_extracao.infrastructure.parsers.pix_csv import parse_pix_csv


class PixCsvParser:
    def parse(self, content: bytes | str) -> list[TransacaoPix]:
        return parse_pix_csv(content)
