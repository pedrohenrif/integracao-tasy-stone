import { useCallback, useEffect, useState } from "react";
import {
  schedulerCartaoApi,
  setSchedulerCartaoApi,
  type SchedulerCartaoStatus,
} from "../api/client";

export function SchedulerPage() {
  const [status, setStatus] = useState<SchedulerCartaoStatus | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      setStatus(await schedulerCartaoApi());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar scheduler");
      setStatus(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggle(enabled: boolean) {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const next = await setSchedulerCartaoApi(enabled);
      setStatus(next);
      setMsg(enabled ? "Scheduler ativado." : "Scheduler desativado (pausado).");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao alterar scheduler");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Scheduler</h1>
        <p className="muted">Controle do cron de extração cartão D-1 (stone-extracao).</p>
        <button type="button" className="btn ghost" onClick={() => void load()} disabled={busy}>
          Atualizar
        </button>
      </header>

      {error && <p className="error">{error}</p>}
      {msg && <p className="ok-msg">{msg}</p>}

      <div className="form-card">
        <h2>Cartão — conciliação diária (D-1)</h2>
        {!status && !error && <p className="muted">Carregando...</p>}
        {status && (
          <>
            <div className="cards compact">
              <div className={`card ${status.enabled ? "ok" : "dlq"}`}>
                <span>Estado</span>
                <b>{status.enabled ? "Ativo" : "Desligado"}</b>
              </div>
              <div className="card">
                <span>Horário</span>
                <b>{status.schedule || `${status.hour}:${status.minute}`}</b>
              </div>
              <div className="card">
                <span>Fuso</span>
                <b>{status.timezone}</b>
              </div>
              <div className="card">
                <span>Próxima data (D-1)</span>
                <b>{status.next_date_preview || "—"}</b>
              </div>
              <div className="card">
                <span>Próxima execução</span>
                <b>{status.next_run_time ? status.next_run_time.replace("T", " ").slice(0, 19) : "—"}</b>
              </div>
            </div>
            <p className="muted small">
              Quando ativo, todo dia no horário configurado busca o extrato de <strong>ontem</strong> na
              Stone e publica na fila. Horário vem do .env (`CARTAO_CRON_HOUR` / `MINUTE`); o painel só
              liga/desliga.
            </p>
            <div className="reprocess-group" style={{ marginTop: "0.75rem" }}>
              <button
                type="button"
                className="btn btn-accent"
                disabled={busy || status.enabled}
                onClick={() => void toggle(true)}
              >
                Ativar
              </button>
              <button
                type="button"
                className="btn ghost"
                disabled={busy || !status.enabled}
                onClick={() => void toggle(false)}
              >
                Desativar
              </button>
            </div>
          </>
        )}
      </div>

      <div className="callout">
        O <code>stone-extracao</code> precisa estar no ar (:8000). O estado fica salvo e sobrevive a
        restart do serviço.
      </div>
    </div>
  );
}
