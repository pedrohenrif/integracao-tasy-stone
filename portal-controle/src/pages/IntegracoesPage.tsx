import { useCallback, useEffect, useState } from "react";
import { caixasApi, registrosApi } from "../api/client";
import { FiltersBar } from "../components/FiltersBar";
import { RegistrosTable } from "../components/RegistrosTable";
import type { Filtros, Registro, ResumoTotais } from "../types";

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function IntegracoesPage() {
  const [filtros, setFiltros] = useState<Filtros>({ limit: "200" });
  const [caixas, setCaixas] = useState<Array<{ cd_caixa: number; ds_caixa: string }>>([]);
  const [rows, setRows] = useState<Registro[]>([]);
  const [totais, setTotais] = useState<ResumoTotais>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await registrosApi(filtros);
      setRows(data.registros || []);
      setTotais(data.resumo?.totais || {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }, [filtros]);

  useEffect(() => {
    caixasApi()
      .then((r) => setCaixas(r.items || []))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- carga inicial

  return (
    <div>
      <header className="page-head">
        <h1>Integrações</h1>
        <p className="muted">Dados de registro_maquininha (Postgres staging)</p>
      </header>
      <FiltersBar value={filtros} caixas={caixas} onChange={setFiltros} onSubmit={() => void load()} />
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
          <span>Soma</span>
          <b>{money(Number(totais.soma_valor || 0))}</b>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {loading ? <p className="muted">Carregando...</p> : <RegistrosTable rows={rows} />}
    </div>
  );
}
