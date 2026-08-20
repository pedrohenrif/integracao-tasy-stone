from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from stone_extracao.domain.cartao.models import TransacaoCartao


@dataclass
class UltimaExtracaoCartao:
    reference_date: str
    source: str
    extracted_at: datetime
    published_count: int
    transactions: list[TransacaoCartao] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        total = len(self.transactions)
        soma = sum((t.vl_transacao for t in self.transactions), Decimal("0"))
        por_tipo: dict[str, int] = {}
        por_terminal: dict[str, int] = {}
        for t in self.transactions:
            tipo = t.cd_tipo_transacao.value
            por_tipo[tipo] = por_tipo.get(tipo, 0) + 1
            por_terminal[t.nr_serie_maquininha] = por_terminal.get(t.nr_serie_maquininha, 0) + 1
        ticket = (soma / total) if total else Decimal("0")
        return {
            "reference_date": self.reference_date,
            "source": self.source,
            "extracted_at": self.extracted_at.isoformat(),
            "total_vendas": total,
            "total_vendido": float(soma),
            "ticket_medio": float(ticket.quantize(Decimal("0.01"))),
            "por_tipo": por_tipo,
            "por_terminal": por_terminal,
            "published_count": self.published_count,
        }


_ultima: UltimaExtracaoCartao | None = None


def salvar_extracao(
    *,
    reference_date: str,
    source: str,
    published_count: int,
    transactions: list[TransacaoCartao],
) -> UltimaExtracaoCartao:
    global _ultima
    _ultima = UltimaExtracaoCartao(
        reference_date=reference_date,
        source=source,
        extracted_at=datetime.now(timezone.utc),
        published_count=published_count,
        transactions=list(transactions),
    )
    return _ultima


def obter_ultima() -> UltimaExtracaoCartao | None:
    return _ultima
