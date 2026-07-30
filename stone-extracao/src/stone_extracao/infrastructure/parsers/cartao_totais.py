from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from xml.etree import ElementTree as ET

from stone_extracao.domain.cartao.models import TransacaoCartao
from stone_extracao.infrastructure.parsers.cartao_xml import _local, _parse_decimal


@dataclass
class DivergenciaTotais:
    """Comparação soma das txs parseadas vs totais declarados no XML (se existirem)."""

    tem_totais_arquivo: bool = False
    soma_transacoes: Decimal = Decimal("0")
    total_arquivo: Decimal | None = None
    divergencia: Decimal | None = None
    por_bandeira_tipo: dict[str, Decimal] = field(default_factory=dict)
    avisos: list[str] = field(default_factory=list)

    @property
    def tem_divergencia(self) -> bool:
        if self.divergencia is None:
            return False
        return abs(self.divergencia) >= Decimal("0.01")


def _sum_transactions(transactions: list[TransacaoCartao]) -> tuple[Decimal, dict[str, Decimal]]:
    total = Decimal("0")
    por: dict[str, Decimal] = {}
    for tx in transactions:
        total += tx.vl_transacao
        key = f"{tx.cd_bandeira or '?'}|{tx.cd_tipo_transacao.value}|at={tx.account_type}"
        por[key] = por.get(key, Decimal("0")) + tx.vl_transacao
    return total, por


def _sum_payments_section(root: ET.Element) -> Decimal | None:
    """
    Soma valores em seções de pagamento/liquidação se existirem
    (Payments, Receivables, FinancialEvents, etc.).
    """
    section_names = {
        "Payments",
        "Receivables",
        "FinancialEvents",
        "PaymentEvents",
        "Settlements",
        "Deposits",
        "Summary",
        "Totals",
    }
    total = Decimal("0")
    hit = False
    for child in root:
        if _local(child.tag) not in section_names:
            continue
        for el in child.iter():
            name = _local(el.tag).lower()
            if name in {
                "amount",
                "paymentamount",
                "netamount",
                "grossamount",
                "totalamount",
                "capturedamount",
                "depositamount",
            }:
                val = _parse_decimal((el.text or "").strip())
                if val is not None:
                    total += val
                    hit = True
    return total if hit else None


def analyze_cartao_totais(
    content: str | bytes,
    transactions: list[TransacaoCartao],
) -> DivergenciaTotais:
    """
    Detecta possível divergência de arredondamento / totais do extrato.

    Layout 2.2 tipicamente só traz Header + FinancialTransactions (sem total
    agregado). Nesse caso `tem_totais_arquivo=False` e listamos soma por
    bandeira/tipo para o time Tasy cruzar com a tela de depósitos.
    """
    if isinstance(content, bytes):
        content = content.decode("utf-8")

    root = ET.fromstring(content)
    soma, por = _sum_transactions(transactions)
    result = DivergenciaTotais(soma_transacoes=soma, por_bandeira_tipo=por)

    arquivo_total = _sum_payments_section(root)
    if arquivo_total is not None:
        result.tem_totais_arquivo = True
        result.total_arquivo = arquivo_total
        result.divergencia = (soma - arquivo_total).quantize(Decimal("0.01"))
        if result.tem_divergencia:
            result.avisos.append(
                f"Divergência totais: soma txs={soma} vs arquivo={arquivo_total} "
                f"(delta={result.divergencia})"
            )
    else:
        result.avisos.append(
            "XML sem seção de totais/pagamentos comparável — "
            "use a soma por bandeira/tipo para cruzar com depósitos no Tasy. "
            "Se houver divergência conhecida (ex. Visa crédito), envie o XML "
            "ou print do GA111 para refinarmos a regra."
        )

    # Visa crédito (AccountType=2, BrandId tipicamente Visa) — destaque no log
    visa_credito = Decimal("0")
    for key, val in por.items():
        parts = key.split("|")
        brand, tipo = (parts[0] if parts else ""), (parts[1] if len(parts) > 1 else "")
        if tipo == "credit_card" and brand.lower() in {"1", "visa", "2"}:
            # BrandId Stone varia; mantém agregação credit_card no aviso
            pass
        if tipo == "credit_card":
            visa_credito += val
    if visa_credito:
        result.avisos.append(f"Soma crédito (todas bandeiras) nas txs: {visa_credito}")

    return result
