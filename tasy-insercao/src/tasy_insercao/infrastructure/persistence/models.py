from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CHAR,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Bandeira(Base):
    __tablename__ = "bandeiras"

    cd_bandeira: Mapped[int] = mapped_column(Integer, primary_key=True)
    ds_bandeira: Mapped[str] = mapped_column(String(50), nullable=False)


class TipoTransacao(Base):
    __tablename__ = "tipos_transacoes"

    cd_tipo_transacao: Mapped[int] = mapped_column(Integer, primary_key=True)
    ds_tipo_transacao: Mapped[str] = mapped_column(String(50), nullable=False)


class CaixaTasy(Base):
    __tablename__ = "caixas_tasy"

    cd_caixa: Mapped[int] = mapped_column(Integer, primary_key=True)
    ds_caixa: Mapped[str] = mapped_column(String(120), nullable=False)
    ie_ativo: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="S")
    dt_atualizacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MaquininhaStone(Base):
    __tablename__ = "maquininha_stone"

    nr_sequencia: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nr_serie_maquininha: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    cd_caixa: Mapped[int] = mapped_column(
        Integer, ForeignKey("caixas_tasy.cd_caixa"), nullable=False
    )
    ds_maquininha: Mapped[str | None] = mapped_column(String(120))
    ie_status: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="A")
    dt_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    cd_transacao_financeira: Mapped[int] = mapped_column(Integer, nullable=False)


class MapeamentoTransacaoTasy(Base):
    """Schema Cotolengo: FK numérico tipo/bandeira → id bandeira no Tasy."""

    __tablename__ = "mapeamento_transacoes_tasy"

    nr_sequencia: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    cd_cartao_bandeira_tasy: Mapped[int] = mapped_column(Integer, nullable=False)
    cd_tipo_transacao: Mapped[int] = mapped_column(
        Integer, ForeignKey("tipos_transacoes.cd_tipo_transacao"), nullable=False
    )
    cd_bandeira: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("bandeiras.cd_bandeira")
    )


class RegistroMaquininha(Base):
    __tablename__ = "registro_maquininha"

    nr_sequencia: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nr_serie_maquininha: Mapped[str] = mapped_column(String(64), nullable=False)
    cd_caixa: Mapped[int | None] = mapped_column(Integer)
    dt_movimentacao: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cd_autorizacao: Mapped[str | None] = mapped_column(String(80))
    vl_transacao: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    id_stone: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    cd_tipo_transacao: Mapped[str | None] = mapped_column(String(40))
    cd_bandeira: Mapped[str | None] = mapped_column(String(40))
    qt_parcelas: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ie_transacao_parcelada: Mapped[str] = mapped_column(CHAR(1), nullable=False, default="N")
    cd_status: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    ds_obs_processo: Mapped[str | None] = mapped_column(String(500))
    dt_inclusao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    dt_atualizacao: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
