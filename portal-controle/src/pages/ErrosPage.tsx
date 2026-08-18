import { useCallback, useEffect, useState } from "react";
import {
  caixasApi,
  registrosApi,
  reprocessarDiaApi,
  reprocessarRegistroApi,
  reprocessarSelecionadosApi,
} from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { FiltersBar } from "../components/FiltersBar";
import { RegistrosTable } from "../components/RegistrosTable";
import type { Filtros, Registro } from "../types";

function detailMessage(err: unknown): string {
  if (err instanceof Error) return err.message;
  return "Erro";
}

type CaixaOpt = { cd_caixa: number; ds_caixa: string };

export function ErrosPage() {
  const { user } = useAuth();
  const [filtros, setFiltros] = useState<Filtros>({ cd_status: "7", limit: "200" });
  const [caixas, setCaixas] = useState<CaixaOpt[]>([]);
  const [rows, setRows] = useState<Registro[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [dia, setDia] = useState("");
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  const [editing, setEditing] = useState<Registro | null>(null);
  const [editSerial, setEditSerial] = useState("");
  const [editCaixa, setEditCaixa] = useState("");
  const [editObs, setEditObs] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const data = await registrosApi({ ...filtros });
      setRows(data.registros || []);
      setSelected(new Set());
    } catch (e) {
      setError(detailMessage(e));
    }
  }, [filtros]);

  useEffect(() => {
    caixasApi()
      .then((r) => setCaixas(r.items || []))
      .catch(() => undefined);
    void load();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function toggle(nr: number) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(nr)) next.delete(nr);
      else next.add(nr);
      return next;
    });
  }

  function toggleAll(ids: number[]) {
    const elegiveis = ids.filter((id) => {
      const row = rows.find((r) => r.nr_sequencia === id);
      return row && row.cd_status !== 5;
    });
    setSelected((prev) => {
      const allOn = elegiveis.length > 0 && elegiveis.every((id) => prev.has(id));
      if (allOn) return new Set();
      return new Set(elegiveis);
    });
  }

  function openEdit(row: Registro) {
    setEditing(row);
    setEditSerial(row.nr_serie_maquininha || "");
    setEditCaixa(row.cd_caixa != null ? String(row.cd_caixa) : "");
    setEditObs("");
    setError("");
    setMsg("");
  }

  function closeEdit() {
    setEditing(null);
  }

  async function onConfirmEdit() {
    if (!editing) return;
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await reprocessarRegistroApi({
        nr_sequencia: editing.nr_sequencia,
        nr_serie_maquininha: editSerial.trim() || undefined,
        cd_caixa: editCaixa ? Number(editCaixa) : undefined,
        obs: editObs.trim() || undefined,
      });
      setMsg(`${res.mensagem} · id_stone=${res.id_stone}`);
      closeEdit();
      await load();
    } catch (e) {
      setError(detailMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReprocessSelecionados() {
    if (!selected.size) {
      setError("Selecione ao menos um registro.");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await reprocessarSelecionadosApi([...selected]);
      setMsg(
        `Enfileirados: ${res.enfileirados}` +
          (res.ignorados.length ? ` · Ignorados: ${res.ignorados.length}` : "") +
          (res.erros.length ? ` · Erros: ${res.erros.length}` : ""),
      );
      await load();
    } catch (e) {
      setError(detailMessage(e));
    } finally {
      setBusy(false);
    }
  }

  async function onReprocessDia() {
    if (!dia) {
      setError("Informe a data do dia.");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const res = await reprocessarDiaApi(dia);
      const pub = res.published_count ?? 0;
      const extra = res.stone_message || "";
      const pixPart = res.pix?.error
        ? ` | PIX falha: ${res.pix.error}`
        : res.pix?.message
          ? ` | PIX: ${res.pix.message}`
          : "";
      setMsg(
        `Dia ${res.reference_date}: cartão ${pub} publicadas` +
          (res.parsed_count != null ? ` (${res.parsed_count} lidas)` : "") +
          (extra ? ` — ${extra}` : "") +
          pixPart,
      );
      if (res.pix?.error) {
        setError(`Cartão ok; PIX falhou: ${res.pix.error}`);
      } else if (pub === 0) {
        setError(extra || "Stone não retornou transações para esta data.");
      }
      await load();
    } catch (e) {
      setError(detailMessage(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Erros / DLQ</h1>
        <p className="muted">
          Erros, Sem Tesouraria e Reintegrar (9). Status &quot;Todos&quot; lista qualquer status (respeitando as
          datas). Reprocesse com edição de serial/caixa ou em lote.
        </p>
      </header>

      <div className="reprocess-bar">
        <div className="reprocess-group">
          <button
            type="button"
            className="btn btn-accent"
            disabled={busy || selected.size === 0}
            onClick={() => void onReprocessSelecionados()}
          >
            Reprocessar selecionados ({selected.size})
          </button>
          <span className="muted small">Republica na fila a partir do staging</span>
        </div>
        {user?.admin && (
          <div className="reprocess-group">
            <label className="reprocess-date">
              Dia
              <input type="date" value={dia} onChange={(e) => setDia(e.target.value)} />
            </label>
            <button
              type="button"
              className="btn ghost"
              disabled={busy || !dia}
              onClick={() => void onReprocessDia()}
            >
              Reprocessar dia (cartão + PIX)
            </button>
            <span className="muted small">Cartão na fila + solicitação PIX (webhook)</span>
          </div>
        )}
      </div>

      <FiltersBar value={filtros} caixas={caixas} onChange={setFiltros} onSubmit={() => void load()} />
      {error && <p className="error">{error}</p>}
      {msg && <p className="ok-msg">{msg}</p>}
      <RegistrosTable
        rows={rows}
        selectable
        selected={selected}
        onToggle={toggle}
        onToggleAll={toggleAll}
        onReprocessRow={openEdit}
      />

      {editing && (
        <div className="modal-backdrop" role="presentation" onClick={closeEdit}>
          <div
            className="modal-card"
            role="dialog"
            aria-modal="true"
            aria-labelledby="reprocess-title"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 id="reprocess-title">Reprocessar transação</h2>
            <p className="muted small">
              id_stone <code>{editing.id_stone}</code> · status {editing.cd_status}
            </p>
            <label>
              Serial da maquininha
              <input
                value={editSerial}
                onChange={(e) => setEditSerial(e.target.value)}
                placeholder="Ex.: PB09231S72079"
              />
            </label>
            <label>
              Caixa
              <select value={editCaixa} onChange={(e) => setEditCaixa(e.target.value)}>
                <option value="">— manter / escolher —</option>
                {caixas.map((c) => (
                  <option key={c.cd_caixa} value={c.cd_caixa}>
                    {c.cd_caixa} — {c.ds_caixa}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Observação (opcional)
              <input
                value={editObs}
                onChange={(e) => setEditObs(e.target.value)}
                placeholder="Motivo da correção"
              />
            </label>
            <p className="muted small">
              Altera só este registro no staging e reenfileira. A ação fica no log de auditoria.
            </p>
            <div className="modal-actions">
              <button type="button" className="btn ghost" disabled={busy} onClick={closeEdit}>
                Cancelar
              </button>
              <button type="button" className="btn btn-accent" disabled={busy} onClick={() => void onConfirmEdit()}>
                Salvar e reprocessar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
