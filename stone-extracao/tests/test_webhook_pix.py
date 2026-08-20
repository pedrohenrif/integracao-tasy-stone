from __future__ import annotations

import asyncio
import json
from decimal import Decimal
from pathlib import Path

from stone_extracao.application.use_cases.receber_webhook_pix import (
    ReceberWebhookPix,
    extract_download_url,
    parse_webhook_payload,
)
from stone_extracao.infrastructure.parsers.pix_parser import PixCsvParser

SAMPLE = Path(__file__).resolve().parents[2] / "stone_movimento_20260708_pix.xml"


class _FakePublisher:
    def __init__(self) -> None:
        self.items: list = []

    async def publish_pix(self, evento) -> None:
        self.items.append(evento)


class _FakeDownloader:
    def __init__(self, content: bytes) -> None:
        self.content = content
        self.called_with: list[str] = []

    async def download_file(self, url: str) -> bytes:
        self.called_with.append(url)
        return self.content


def test_parse_validation_payload():
    raw = json.dumps({"type": "validation_notification"}).encode()
    payload = parse_webhook_payload(raw)
    assert payload is not None
    assert payload["type"] == "validation_notification"


def test_extract_download_url_variants():
    assert extract_download_url({"downloadUrl": "https://a/x.csv"}) == "https://a/x.csv"
    assert extract_download_url({"url": "https://b/y.csv"}) == "https://b/y.csv"
    assert extract_download_url({"type": "pix"}) is None


def test_webhook_validation_ack():
    publisher = _FakePublisher()
    use_case = ReceberWebhookPix(parser=PixCsvParser(), publisher=publisher)
    result = asyncio.run(
        use_case.execute(
            json.dumps({"type": "validation_notification"}),
            source="webhook",
        )
    )
    assert result.event_type == "validation_notification"
    assert result.status == "ok"
    assert result.published_count == 0
    assert publisher.items == []


def test_webhook_download_url_publishes_csv():
    assert SAMPLE.is_file()
    csv = SAMPLE.read_bytes()
    publisher = _FakePublisher()
    downloader = _FakeDownloader(csv)
    use_case = ReceberWebhookPix(
        parser=PixCsvParser(),
        publisher=publisher,
        downloader=downloader,
    )
    body = json.dumps(
        {
            "type": "pix",
            "downloadUrl": "https://signed.example/file.csv",
            "referenceDate": "2026-07-08",
            "document": "76610690000162",
        }
    )
    result = asyncio.run(use_case.execute(body, source="webhook", limit=3))
    assert downloader.called_with == ["https://signed.example/file.csv"]
    assert result.event_type == "pix"
    assert result.reference_date == "2026-07-08"
    assert result.published_count == 3
    assert len(publisher.items) == 3
    assert publisher.items[0].transaction.vl_transacao >= Decimal("0")


def test_webhook_url_field_alias():
    csv = SAMPLE.read_bytes()
    publisher = _FakePublisher()
    downloader = _FakeDownloader(csv)
    use_case = ReceberWebhookPix(
        parser=PixCsvParser(),
        publisher=publisher,
        downloader=downloader,
    )
    body = json.dumps({"type": "pix", "url": "https://signed.example/alt.csv"})
    result = asyncio.run(use_case.execute(body, source="webhook", limit=1))
    assert result.published_count == 1
    assert downloader.called_with == ["https://signed.example/alt.csv"]


def test_webhook_raw_csv_still_works():
    csv = SAMPLE.read_bytes()
    publisher = _FakePublisher()
    use_case = ReceberWebhookPix(parser=PixCsvParser(), publisher=publisher)
    result = asyncio.run(use_case.execute(csv, source="sample", limit=2))
    assert result.published_count == 2
    assert result.event_type == "pix"
