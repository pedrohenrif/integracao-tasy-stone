from decimal import Decimal
from pathlib import Path

from stone_extracao.infrastructure.parsers.pix_csv import parse_pix_file

SAMPLE = Path(__file__).resolve().parents[2] / "stone_movimento_20260708_pix.xml"


def test_parse_pix_sample():
    assert SAMPLE.is_file()
    txs = parse_pix_file(SAMPLE)
    assert len(txs) > 0
    first = next(t for t in txs if t.id_stone == "A2896o6HJEvEhX3g3cUL1pMhCHx")
    assert first.vl_transacao == Decimal("7.00")
    assert first.nr_serie_maquininha == "PB09231S72079"
    assert first.e2e_id.startswith("E00360305")
    assert first.payment_method == "pix"
    assert first.stone_code == "116852622"


def test_pix_only_paid_pay():
    txs = parse_pix_file(SAMPLE)
    assert all(t.status == "paid" for t in txs)
    assert all((t.operation or "pay") == "pay" for t in txs)
