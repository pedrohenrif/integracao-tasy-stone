import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { filasApi, registrosApi, reprocessarDiaApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { FilaInfo, ResumoTotais } from "../types";

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function DashboardPage() {
  const { user } = useAuth();
  const [totais, setTotais] = useState<ResumoTotais>({});
  const [filas, setFilas] = useState<FilaInfo[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [dia, setDia] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    Promise.all([registrosApi({ limit: "1" }), filasApi()])
      .then(([reg, fq]) => {
        setTotais(reg.resumo.totais || {});
        setFilas(fq.items || []);
      })
      .catch((e) => setError(e.message));
  }, []);

  const ready = filas.reduce((acc, f) => acc + (f.messages_ready || 0), 0);

  async function onExecutarDia() {
    if (!dia) return;
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await reprocessarDiaApi(dia);
      const pub = res.published_count ?? "?";
      const parsed = res.parsed_count ?? "?";
      const stats = res.parse_stats?.summary
        ? String(res.parse_stats.summary)
        : "";
      const pixPart = res.pix?.error
        ? ` PIX: falha — ${res.pix.error}`
        : res.pix?.message
          ? ` PIX: ${res.pix.message}`
          : res.pix?.status
            ? ` PIX: ${res.pix.status}`
            : "";
      const extra = res.stone_message || "";
      setMsg(
        `Dia ${dia}: cartão parseados ${parsed}, publicados ${pub}.` +
          (stats ? ` [${stats}]` : "") +
          (extra ? ` ${extra}` : "") +
          pixPart,
      );
      if (Number(pub) === 0 && !pixPart) {
        setError(extra || stats || "Stone não retornou transações para esta data.");
      } else if (res.pix?.error) {
        setError(`Cartão ok; PIX falhou: ${res.pix.error}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao executar dia");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Dashboard</h1>
        <p className="muted">Visão geral do staging e das filas</p>
      </header>
      {error && <p className="error">{error}</p>}
      {msg && <p className="ok-msg">{msg}</p>}
      <div className="cards">
        <div className="card">
          <span>Total</span>
          <b>{totais.total ?? 0}</b>
        </div>
        <div className="card ok">
          <span>Integrado</span>
          <b>{totais.ok ?? 0}</b>
        </div>
        <div className="card retry">
          <span>Retry</span>
          <b>{totais.retry ?? 0}</b>
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
          <span>Reintegrar (9)</span>
          <b>{totais.confirmacao_pendente ?? 0}</b>
        </div>
        <div className="card">
          <span>Soma OK</span>
          <b>{money(Number(totais.soma_ok || 0))}</b>
        </div>
        <div className="card">
          <span>Msgs nas filas</span>
          <b>{ready}</b>
        </div>
      </div>

      {user?.admin && (
        <div className="reprocess-bar">
          <div className="reprocess-group">
            <strong>Admin — executar integração do dia</strong>
            <label className="reprocess-date">
              Dia
              <input type="date" value={dia} onChange={(e) => setDia(e.target.value)} />
            </label>
            <button
              type="button"
              className="btn btn-accent"
              disabled={busy || !dia}
              onClick={() => void onExecutarDia()}
            >
              Extrair cartão + PIX do dia
            </button>
            <span className="muted small">
              Cartão → fila; PIX solicita extrato (webhook assíncrono)
            </span>
          </div>
        </div>
      )}

      <div className="quick-links">
        <Link to="/integracoes">Ver integrações</Link>
        <Link to="/erros">Ver erros / Sem Tesouraria</Link>
        <Link to="/filas">Ver filas</Link>
      </div>
      <h2>Filas (resumo)</h2>
      <ul className="fila-list">
        {filas.map((f) => (
          <li key={f.name}>
            <code>{f.name}</code> — ready: {f.messages_ready ?? "-"} · consumers: {f.consumers ?? "-"}
            {f.error ? <span className="error"> ({f.error})</span> : null}
          </li>
        ))}
      </ul>
    </div>
  );
}
