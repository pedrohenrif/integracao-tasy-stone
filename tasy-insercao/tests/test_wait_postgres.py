import asyncio

from tasy_insercao.infrastructure.persistence import postgres as pg_mod


def test_wait_postgres_pronto_na_primeira(monkeypatch):
    calls = {"n": 0}

    def ping() -> None:
        calls["n"] += 1

    monkeypatch.setattr(pg_mod, "ping_postgres", ping)
    monkeypatch.setattr(pg_mod.settings, "CONSUMER_RECONNECT_DELAY_SECONDS", 1)

    asyncio.run(pg_mod.wait_postgres_ready())
    assert calls["n"] == 1


def test_wait_postgres_retenta_depois_falha(monkeypatch):
    calls = {"n": 0}

    def ping() -> None:
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("ainda não está aceitando conexões")

    monkeypatch.setattr(pg_mod, "ping_postgres", ping)
    monkeypatch.setattr(pg_mod.settings, "CONSUMER_RECONNECT_DELAY_SECONDS", 1)

    asyncio.run(pg_mod.wait_postgres_ready())
    assert calls["n"] == 3


def test_wait_postgres_para_se_stop(monkeypatch):
    monkeypatch.setattr(
        pg_mod,
        "ping_postgres",
        lambda: (_ for _ in ()).throw(RuntimeError("down")),
    )
    monkeypatch.setattr(pg_mod.settings, "CONSUMER_RECONNECT_DELAY_SECONDS", 1)

    async def _run() -> None:
        stop = asyncio.Event()
        stop.set()
        try:
            await pg_mod.wait_postgres_ready(stop)
        except RuntimeError as exc:
            assert "parado" in str(exc)
            return
        raise AssertionError("esperava RuntimeError")

    asyncio.run(_run())
