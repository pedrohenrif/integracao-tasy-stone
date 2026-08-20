from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from stone_extracao.domain.cartao.models import EventoFilaCartao, TransacaoCartao


class ConciliationFilePort(Protocol):
    async def fetch(self, reference_date: str) -> bytes: ...


class CartaoParserPort(Protocol):
    def parse(self, content: bytes | str) -> list[TransacaoCartao]: ...


class MessagePublisherPort(Protocol):
    async def publish_cartao(self, evento: EventoFilaCartao) -> None: ...


class UnitOfWork(ABC):
    @abstractmethod
    async def __aenter__(self): ...

    @abstractmethod
    async def __aexit__(self, *args): ...
