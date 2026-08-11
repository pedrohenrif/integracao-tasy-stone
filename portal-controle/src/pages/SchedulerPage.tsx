import { useCallback, useEffect, useState } from "react";
import {
  schedulerCartaoApi,
  schedulerPixApi,
  setSchedulerCartaoApi,
  setSchedulerPixApi,
  type SchedulerCartaoStatus,
  type SchedulerStatus,
} from "../api/client";

function CronCard({
  title,
  hint,
  status,
  busy,
  onToggle,
}: {
  title: string;
  hint: string;
  status: SchedulerCartaoStatus | SchedulerStatus | null;
  busy: boolean;
  onToggle: (enabled: boolean) => void;
}) {
  return (
    <div className="form-card">
      <h2>{title}</h2>
      {!status && <p className="muted">Carregando...</p>}
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
              <b>
                {status.next_run_time
                  ? status.next_run_time.replace("T", " ").slice(0, 19)
                  : "—"}
              </b>
            </div>
          </div>
          <p className="muted small">{hint}</p>
          <div className="reprocess-group" style={{ marginTop: "0.75rem" }}>
            <button
              type="button"
              className="btn btn-accent"
              disabled={busy || status.enabled}
              onClick={() => onToggle(true)}
            >
              Ativar
            </button>
            <button
              type="button"
              className="btn ghost"
              disabled={busy || !status.enabled}
              onClick={() => onToggle(false)}
            >
              Desativar
            </button>
          </div>
        </>
      )}
    </div>
  );
}

export function SchedulerPage() {
  const [cartao, setCartao] = useState<SchedulerCartaoStatus | null>(null);
  const [pix, setPix] = useState<SchedulerStatus | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    setError("");
    try {
      const [c, p] = await Promise.all([schedulerCartaoApi(), schedulerPixApi()]);
      setCartao(c);
      setPix(p);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar scheduler");
      setCartao(null);
      setPix(null);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function toggleCartao(enabled: boolean) {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      setCartao(await setSchedulerCartaoApi(enabled));
      setMsg(enabled ? "Scheduler cartão ativado." : "Scheduler cartão desativado.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao alterar scheduler cartão");
    } finally {
      setBusy(false);
    }
  }

  async function togglePix(enabled: boolean) {
    setBusy(true);
    setError("");
    setMsg("");
    try {
      setPix(await setSchedulerPixApi(enabled));
      setMsg(enabled ? "Scheduler PIX ativado." : "Scheduler PIX desativado.");
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao alterar scheduler PIX");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Scheduler</h1>
        <p className="muted">Crons D-1 de cartão e PIX (stone-extracao).</p>
        <button type="button" className="btn ghost" onClick={() => void load()} disabled={busy}>
          Atualizar
        </button>
      </header>

      {error && <p className="error">{error}</p>}
      {msg && <p className="ok-msg">{msg}</p>}

      <CronCard
        title="Cartão — conciliação diária (D-1)"
        hint="Quando ativo, busca o extrato de ontem (D-1) na Stone e publica na fila. Horários no .env: principal (CARTAO_CRON_*) e retry (CARTAO_CRON_RETRY_*), padrão 01:00 e 04:00."
        status={cartao}
        busy={busy}
        onToggle={(v) => void toggleCartao(v)}
      />

      <CronCard
        title="PIX — solicitação diária (D-1)"
        hint="Quando ativo, solicita o extrato PIX de ontem; a Stone envia o CSV no webhook. Horários: PIX_CRON_* e PIX_CRON_RETRY_* (padrão 01:05 e 04:05)."
        status={pix}
        busy={busy}
        onToggle={(v) => void togglePix(v)}
      />

      <div className="callout">
        O <code>stone-extracao</code> precisa estar no ar (:8000) e o webhook PIX público cadastrado.
        O estado de cada cron fica salvo e sobrevive a restart do serviço.
      </div>
    </div>
  );
}
