from pathlib import Path
import asyncio

from stone_extracao.application.use_cases.receber_webhook_pix import ReceberWebhookPix
from stone_extracao.infrastructure.parsers.pix_parser import PixCsvParser


SAMPLE = Path(__file__).resolve().parents[2] / "stone_movimento_20260708_pix.xml"


class _FakePublisher:
    def __init__(self) -> None:
        self.items: list = []

    async def publish_pix(self, evento) -> None:
        self.items.append(evento)


def test_csv_cru_publica_pix():
    assert SAMPLE.is_file()
    publisher = _FakePublisher()
    use_case = ReceberWebhookPix(parser=PixCsvParser(), publisher=publisher)
    result = asyncio.run(
        use_case.execute(SAMPLE.read_bytes(), source="csv_manual", limit=2)
    )
    assert result.published_count == 2
    assert result.source == "csv_manual"
    assert len(publisher.items) == 2
