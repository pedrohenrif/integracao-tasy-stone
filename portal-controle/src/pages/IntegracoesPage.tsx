import { useCallback, useEffect, useMemo, useState } from "react";
import { caixasApi, registrosApi } from "../api/client";
import { FiltersBar } from "../components/FiltersBar";
import { RegistrosTable } from "../components/RegistrosTable";
import type { Filtros, Registro, ResumoTotais } from "../types";
import { dataOntemISO } from "../utils/dates";

const PAGE_SIZE_DEFAULT = 50;
const PAGE_SIZES = [25, 50, 100];

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function filtrosIniciais(): Filtros {
  const ontem = dataOntemISO();
  return {
    data_de: ontem,
    data_ate: ontem,
    limit: String(PAGE_SIZE_DEFAULT),
    offset: "0",
  };
}

export function IntegracoesPage() {
  const [filtros, setFiltros] = useState<Filtros>(() => filtrosIniciais());
  const [caixas, setCaixas] = useState<Array<{ cd_caixa: number; ds_caixa: string }>>([]);
  const [rows, setRows] = useState<Registro[]>([]);
  const [totais, setTotais] = useState<ResumoTotais>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const pageSize = Math.max(1, Number(filtros.limit) || PAGE_SIZE_DEFAULT);
  const offset = Math.max(0, Number(filtros.offset) || 0);
  const page = Math.floor(offset / pageSize) + 1;
  const total = Number(totais.total || 0);
  const totalPages = Math.max(1, Math.ceil(total / pageSize) || 1);

  const load = useCallback(async (f: Filtros) => {
    setLoading(true);
    setError("");
    try {
      const data = await registrosApi(f);
      setRows(data.registros || []);
      setTotais(data.resumo?.totais || {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    caixasApi()
      .then((r) => setCaixas(r.items || []))
      .catch(() => undefined);
    void load(filtrosIniciais());
  }, [load]);

  const rangeLabel = useMemo(() => {
    if (total === 0) return "0 registros";
    const de = offset + 1;
    const ate = Math.min(offset + pageSize, total);
    return `${de}–${ate} de ${total}`;
  }, [offset, pageSize, total]);

  function apply(next: Filtros) {
    setFiltros(next);
    void load(next);
  }

  function onFiltrar() {
    apply({ ...filtros, offset: "0", limit: String(pageSize) });
  }

  function goPage(nextPage: number) {
    const p = Math.min(Math.max(1, nextPage), totalPages);
    apply({
      ...filtros,
      offset: String((p - 1) * pageSize),
      limit: String(pageSize),
    });
  }

  function onPageSize(size: number) {
    apply({
      ...filtros,
      limit: String(size),
      offset: "0",
    });
  }

  function resetOntem() {
    apply(filtrosIniciais());
  }

  return (
    <div>
      <header className="page-head">
        <h1>Integrações</h1>
        <p className="muted">
          Staging Postgres · ao abrir: só ontem · use filtros para ampliar o período
        </p>
      </header>
      <FiltersBar
        value={filtros}
        caixas={caixas}
        onChange={(next) => setFiltros({ ...next, limit: next.limit || String(pageSize) })}
        onSubmit={onFiltrar}
      />
      <div className="pager-bar">
        <button type="button" className="btn ghost btn-sm" onClick={resetOntem}>
          Só ontem
        </button>
        <label className="pager-size">
          Por página
          <select value={pageSize} onChange={(e) => onPageSize(Number(e.target.value))}>
            {PAGE_SIZES.map((n) => (
              <option key={n} value={n}>
                {n}
              </option>
            ))}
          </select>
        </label>
        <span className="muted small">{rangeLabel}</span>
        <div className="pager-nav">
          <button
            type="button"
            className="btn ghost btn-sm"
            disabled={loading || page <= 1}
            onClick={() => goPage(page - 1)}
          >
            Anterior
          </button>
          <span className="muted small">
            Página {page} / {totalPages}
          </span>
          <button
            type="button"
            className="btn ghost btn-sm"
            disabled={loading || page >= totalPages}
            onClick={() => goPage(page + 1)}
          >
            Próxima
          </button>
        </div>
      </div>
      <div className="cards compact">
        <div className="card">
          <span>Total filtro</span>
          <b>{totais.total ?? 0}</b>
        </div>
        <div className="card ok">
          <span>OK</span>
          <b>{totais.ok ?? 0}</b>
        </div>
        <div className="card dlq">
          <span>DLQ</span>
          <b>{totais.dlq ?? 0}</b>
        </div>
        <div className="card">
          <span>Sem Tesouraria</span>
          <b>{totais.sem_tesouraria ?? 0}</b>
        </div>
        <div className="card">
          <span>Ignorado (10)</span>
          <b>{totais.ignorado ?? 0}</b>
        </div>
        <div className="card">
          <span>Reintegrar (9)</span>
          <b>{totais.confirmacao_pendente ?? 0}</b>
        </div>
        <div className="card">
          <span>Soma</span>
          <b>{money(Number(totais.soma_valor || 0))}</b>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {loading ? <p className="muted">Carregando...</p> : <RegistrosTable rows={rows} />}
      {!loading && total > 0 && (
        <div className="pager-bar pager-bar-bottom">
          <span className="muted small">{rangeLabel}</span>
          <div className="pager-nav">
            <button
              type="button"
              className="btn ghost btn-sm"
              disabled={page <= 1}
              onClick={() => goPage(page - 1)}
            >
              Anterior
            </button>
            <span className="muted small">
              Página {page} / {totalPages}
            </span>
            <button
              type="button"
              className="btn ghost btn-sm"
              disabled={page >= totalPages}
              onClick={() => goPage(page + 1)}
            >
              Próxima
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
