from datetime import date
from decimal import Decimal
from pathlib import Path

from stone_extracao.infrastructure.parsers.pix_csv import (
    parse_pix_csv_with_stats,
    parse_pix_file,
)

SAMPLE = Path(__file__).resolve().parents[2] / "stone_movimento_20260708_pix.xml"

CSV_STATS = """id,status,pix_transaction__detail__operation,amount,pix_transaction__detail__provider_datetime,pix_transaction__terminal__serial_number
ok1,paid,pay,1000,2026-09-15T10:00:00-03:00,PB09231S72079
skip_status,cancelled,pay,1000,2026-09-15T10:00:00-03:00,PB09231S72079
skip_op,paid,refund,500,2026-09-15T10:00:00-03:00,PB09231S72079
,paid,pay,3000,2026-09-15T10:00:00-03:00,PB09231S72079
ok2,paid,pay,2000,2026-09-15T11:00:00-03:00,OUTROSERIAL
"""


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


def test_parse_pix_stats_conta_descartes():
    parsed = parse_pix_csv_with_stats(CSV_STATS)
    assert parsed.stats.rows_total == 5
    assert parsed.stats.accepted == 2
    assert parsed.stats.skipped_status == 1
    assert parsed.stats.skipped_operation == 1
    assert parsed.stats.skipped_no_id == 1
    assert {t.id_stone for t in parsed.transactions} == {"ok1", "ok2"}
    reasons = {s["reason"] for s in parsed.stats.skipped_samples}
    assert {"status", "operation", "no_id"} <= reasons


CSV_PIX_DEPOIS_21H = """id,status,pix_transaction__detail__operation,amount,pix_transaction__detail__provider_datetime,pix_transaction__terminal__serial_number,created_at
naive_utc,paid,pay,400,2026-10-21T00:37:00.000,PB09243M78791,
aware_utc,paid,pay,400,2026-10-21T00:37:00+00:00,PB09243M78791,
zulu,paid,pay,400,2026-10-21T00:37:00Z,PB09243M78791,
brt_offset,paid,pay,400,2026-10-20T21:37:00-03:00,PB09243M78791,
created_utc,paid,pay,400,,PB09243M78791,2026-10-21T00:37:00.000000+00:00
"""


def test_pix_depois_das_21h_fica_no_dia_brt():
    """21:37 BRT = 00:37 UTC D+1 — o caixa tem que permanecer no dia da venda."""
    parsed = parse_pix_csv_with_stats(CSV_PIX_DEPOIS_21H)
    assert parsed.stats.accepted == 5
    for tx in parsed.transactions:
        assert tx.reference_date == "2026-10-20", tx.id_stone
        assert tx.dt_movimentacao.date() == date(2026, 10, 20), tx.id_stone
        assert tx.dt_movimentacao.hour == 21, tx.id_stone
        assert tx.dt_movimentacao.minute == 37, tx.id_stone
    assert {r["reference_date"] for r in parsed.portal_rows} == {"2026-10-20"}
