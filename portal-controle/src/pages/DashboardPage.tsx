import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { extrairCartaoDiaApi, filasApi, importarPixCsvApi, registrosApi, reprocessarDiaApi } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import type { FilaInfo, ResumoTotais } from "../types";

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function dateFromFilename(name: string): string {
  const m = name.match(/(20\d{2})(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])/);
  if (!m) return "";
  return `${m[1]}-${m[2]}-${m[3]}`;
}

export function DashboardPage() {
  const { user } = useAuth();
  const [totais, setTotais] = useState<ResumoTotais>({});
  const [filas, setFilas] = useState<FilaInfo[]>([]);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [dia, setDia] = useState("");
  const [csvFile, setCsvFile] = useState<File | null>(null);
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
      const pixPart = res.pix?.error
        ? ` PIX: falha — ${res.pix.error}`
        : res.pix?.message
          ? ` PIX: ${res.pix.message}`
          : res.pix?.status
            ? ` PIX: ${res.pix.status}`
            : "";
      setMsg(
        res.mensagem ||
          `Dia ${dia}: PIX solicitado; cartão após webhook.` + pixPart,
      );
      if (res.pix?.error) {
        setError(`PIX falhou: ${res.pix.error}`);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao executar dia");
    } finally {
      setBusy(false);
    }
  }

  async function onImportarPixCsv() {
    if (!dia || !csvFile) return;
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await importarPixCsvApi(dia, csvFile);
      setMsg(
        res.mensagem ||
          `PIX CSV ${dia}: publicados=${res.published_count ?? 0}. Depois extraia o cartão.`,
      );
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao importar CSV PIX");
    } finally {
      setBusy(false);
    }
  }

  async function onExtrairCartao() {
    if (!dia) return;
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await extrairCartaoDiaApi(dia);
      setMsg(res.mensagem || `Cartão ${dia} extraído.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao extrair cartão");
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
          <span>Ignorado (10)</span>
          <b>{totais.ignorado ?? 0}</b>
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
              className={`btn btn-accent${busy ? " btn-busy" : ""}`}
              disabled={busy || !dia}
              title={!dia ? "Selecione o dia" : busy ? "Aguarde…" : ""}
              onClick={() => void onExecutarDia()}
            >
              Extrair cartão + PIX do dia
            </button>
            <span className="muted small">
              PIX → webhook (mesmo vazio) → cartão; 1 recebimento/caixa; confirma ~5 min
              após o lote parar de integrar. Só D-1 via Stone.
            </span>
          </div>
          <div className="reprocess-group">
            <strong>Retroativo — CSV PIX + cartão (um dia por vez)</strong>
            <label className="reprocess-date">
              Dia do CSV
              <input type="date" value={dia} onChange={(e) => setDia(e.target.value)} />
            </label>
            <label className="reprocess-date">
              CSV PIX
              <input
                type="file"
                accept=".csv,text/csv,text/plain,.xml"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  setCsvFile(f);
                  if (f) {
                    const guessed = dateFromFilename(f.name);
                    if (guessed) setDia(guessed);
                  }
                }}
              />
            </label>
            <button
              type="button"
              className={`btn${busy ? " btn-busy" : ""}`}
              disabled={busy || !dia || !csvFile}
              title={
                !csvFile
                  ? "Escolha o arquivo CSV"
                  : !dia
                    ? "Selecione o dia do lote"
                    : busy
                      ? "Aguarde…"
                      : ""
              }
              onClick={() => void onImportarPixCsv()}
            >
              {busy ? "Importando…" : "1) Importar PIX CSV"}
            </button>
            <button
              type="button"
              className={`btn${busy ? " btn-busy" : ""}`}
              disabled={busy || !dia}
              title={!dia ? "Selecione o dia do lote" : busy ? "Aguarde…" : ""}
              onClick={() => void onExtrairCartao()}
            >
              {busy ? "Extraindo…" : "2) Extrair só cartão"}
            </button>
            <span className="muted small">
              Use quando a Stone não reenvia PIX (D-2+). Ordem: CSV do dia → esperar fila PIX
              drenar → extrair cartão do mesmo dia. Não use o botão amarelo nesses dias.
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
