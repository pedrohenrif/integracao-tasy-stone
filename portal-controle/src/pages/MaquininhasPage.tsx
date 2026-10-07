import { useEffect, useMemo, useState, type FormEvent } from "react";
import {
  maquininhasApi,
  saveCaixaApi,
  saveMaquininhaApi,
  type CaixaOpt,
  type Maquininha,
} from "../api/client";

const empty = {
  nr_serie_maquininha: "",
  cd_caixa: "",
  cd_transacao_financeira: "",
  ds_maquininha: "",
  ie_status: "A",
};

function normSerial(s: string) {
  return s.trim().toUpperCase();
}

export function MaquininhasPage() {
  const [items, setItems] = useState<Maquininha[]>([]);
  const [pendentes, setPendentes] = useState<string[]>([]);
  const [caixas, setCaixas] = useState<CaixaOpt[]>([]);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");
  const [busca, setBusca] = useState("");
  const [filtroCaixa, setFiltroCaixa] = useState("");
  const [filtroStatus, setFiltroStatus] = useState("");

  async function load() {
    const data = await maquininhasApi();
    setItems(data.items || []);
    setPendentes(data.seriais_pendentes || []);
    setCaixas(data.caixas || []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  const existentePeloSerial = useMemo(() => {
    const serial = normSerial(form.nr_serie_maquininha);
    if (!serial) return null;
    return items.find((m) => normSerial(m.nr_serie_maquininha) === serial) ?? null;
  }, [form.nr_serie_maquininha, items]);

  const caixaSel = useMemo(
    () => caixas.find((c) => String(c.cd_caixa) === form.cd_caixa) ?? null,
    [caixas, form.cd_caixa],
  );
  const somenteMovto = (caixaSel?.ie_somente_movto || "").toUpperCase() === "S";

  const filtradas = useMemo(() => {
    const q = busca.trim().toLowerCase();
    return items.filter((m) => {
      if (filtroCaixa && String(m.cd_caixa) !== filtroCaixa) return false;
      if (filtroStatus && (m.ie_status || "") !== filtroStatus) return false;
      if (!q) return true;
      const blob = [
        m.nr_serie_maquininha,
        m.ds_maquininha,
        String(m.cd_caixa),
        m.ds_caixa,
        String(m.cd_transacao_financeira),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();
      return blob.includes(q);
    });
  }, [items, busca, filtroCaixa, filtroStatus]);

  function edit(row: Maquininha) {
    setEditing(true);
    setForm({
      nr_serie_maquininha: row.nr_serie_maquininha,
      cd_caixa: String(row.cd_caixa),
      cd_transacao_financeira:
        row.cd_transacao_financeira == null ? "" : String(row.cd_transacao_financeira),
      ds_maquininha: row.ds_maquininha || "",
      ie_status: row.ie_status || "A",
    });
    setMsg("");
    setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function novoComSerial(serial: string) {
    const ja = items.find((m) => normSerial(m.nr_serie_maquininha) === normSerial(serial));
    if (ja) {
      edit(ja);
      setError(
        `Serial ${serial} já está cadastrado (caixa ${ja.cd_caixa}). Abrimos a edição — não cadastre de novo.`,
      );
      return;
    }
    setEditing(false);
    setForm({ ...empty, nr_serie_maquininha: serial, ie_status: "A" });
    setMsg(`Preencha caixa e transação financeira para ${serial}`);
    setError("");
  }

  function onSerialChange(value: string) {
    setForm({ ...form, nr_serie_maquininha: value });
    if (editing) return;
    const ja = items.find((m) => normSerial(m.nr_serie_maquininha) === normSerial(value));
    if (ja) {
      setError(
        `Este serial já existe no caixa ${ja.cd_caixa} (${ja.ds_caixa || "—"}${
          ja.ds_maquininha ? ` · ${ja.ds_maquininha}` : ""
        }). Não cadastre de novo — use Editar.`,
      );
    } else if (error.startsWith("Este serial") || error.startsWith("Serial ")) {
      setError("");
    }
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    const serial = form.nr_serie_maquininha.trim();
    const ja = items.find((m) => normSerial(m.nr_serie_maquininha) === normSerial(serial));
    if (!editing && ja) {
      const ok = window.confirm(
        `A maquininha ${ja.nr_serie_maquininha} já está cadastrada no caixa ${ja.cd_caixa}` +
          `${ja.ds_caixa ? ` (${ja.ds_caixa})` : ""}.\n\n` +
          `Não é possível cadastrar o mesmo serial duas vezes.\n` +
          `OK = abrir o cadastro existente para editar.\nCancelar = não salvar.`,
      );
      if (ok) edit(ja);
      else
        setError(
          `Serial já cadastrado no caixa ${ja.cd_caixa}. Use Editar em vez de cadastrar de novo.`,
        );
      return;
    }
    const caixaSel = caixas.find((c) => String(c.cd_caixa) === form.cd_caixa);
    const somenteMovto = (caixaSel?.ie_somente_movto || "").toUpperCase() === "S";
    try {
      await saveMaquininhaApi({
        nr_serie_maquininha: serial,
        cd_caixa: Number(form.cd_caixa),
        cd_transacao_financeira: somenteMovto
          ? form.cd_transacao_financeira
            ? Number(form.cd_transacao_financeira)
            : null
          : Number(form.cd_transacao_financeira),
        ds_maquininha: form.ds_maquininha || undefined,
        ie_status: form.ie_status,
      });
      setMsg(editing ? "Maquininha atualizada." : "Maquininha cadastrada.");
      setForm(empty);
      setEditing(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Cadastro — Maquininhas</h1>
        <p className="muted">
          Só as ativas entram na extração e na integração. Inative para parar de importar — sem lista no
          .env.
        </p>
      </header>

      {pendentes.length > 0 && (
        <div className="callout">
          <strong>Seriais em DLQ sem cadastro:</strong>
          <div className="chip-row">
            {pendentes.map((s) => (
              <button key={s} type="button" className="chip" onClick={() => novoComSerial(s)}>
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      <form className="form-card" onSubmit={onSubmit}>
        <h2>{editing ? "Editar maquininha" : "Nova maquininha"}</h2>
        <div className="form-grid">
          <label>
            Serial
            <input
              required
              value={form.nr_serie_maquininha}
              onChange={(e) => onSerialChange(e.target.value)}
              disabled={editing}
              placeholder="Ex.: PB09231X75906"
            />
          </label>
          <label>
            Caixa
            <select
              required
              value={form.cd_caixa}
              onChange={(e) => setForm({ ...form, cd_caixa: e.target.value })}
            >
              <option value="">Selecione</option>
              {caixas.map((c) => (
                <option key={c.cd_caixa} value={c.cd_caixa}>
                  {c.cd_caixa} — {c.ds_caixa}
                  {(c.ie_somente_movto || "").toUpperCase() === "S" ? " (só movto)" : ""}
                </option>
              ))}
            </select>
          </label>
          {form.cd_caixa && (
            <label className="check-inline">
              <input
                type="checkbox"
                checked={somenteMovto}
                onChange={async (e) => {
                  const flag = e.target.checked ? "S" : "N";
                  try {
                    const row = await saveCaixaApi(Number(form.cd_caixa), flag);
                    setCaixas((prev) =>
                      prev.map((c) =>
                        c.cd_caixa === row.cd_caixa ? { ...c, ie_somente_movto: row.ie_somente_movto } : c,
                      ),
                    );
                    setMsg(
                      flag === "S"
                        ? "Caixa marcado: só movimento no Tasy (sem caixa diário)."
                        : "Caixa voltou ao fluxo normal (caixa diário + TF).",
                    );
                  } catch (err) {
                    setError(err instanceof Error ? err.message : "Erro ao atualizar caixa");
                  }
                }}
              />
              Só movimento (sem caixa diário) — use quando o caixa tem várias transações financeiras, como Telemarketing
            </label>
          )}
          <label>
            Transação financeira (Tasy)
            <input
              required={!somenteMovto}
              type="number"
              value={form.cd_transacao_financeira}
              onChange={(e) => setForm({ ...form, cd_transacao_financeira: e.target.value })}
              placeholder={somenteMovto ? "Opcional neste caixa" : ""}
            />
          </label>
          <label>
            Nome / observação
            <input
              value={form.ds_maquininha}
              onChange={(e) => setForm({ ...form, ds_maquininha: e.target.value })}
            />
          </label>
          <label>
            Status
            <select value={form.ie_status} onChange={(e) => setForm({ ...form, ie_status: e.target.value })}>
              <option value="A">A — Ativa</option>
              <option value="I">I — Inativa</option>
            </select>
          </label>
        </div>
        {!editing && existentePeloSerial && (
          <p className="warn-msg">
            Serial já cadastrado no caixa {existentePeloSerial.cd_caixa}
            {existentePeloSerial.ds_caixa ? ` (${existentePeloSerial.ds_caixa})` : ""}.{" "}
            <button type="button" className="linkish" onClick={() => edit(existentePeloSerial)}>
              Abrir cadastro existente
            </button>
          </p>
        )}
        <div className="filters-actions">
          <button type="submit" className="btn">
            {editing ? "Salvar alteração" : "Cadastrar"}
          </button>
          {editing && (
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setEditing(false);
                setForm(empty);
                setError("");
              }}
            >
              Cancelar
            </button>
          )}
        </div>
        {msg && <p className="ok-msg">{msg}</p>}
        {error && <p className="error">{error}</p>}
      </form>

      <div className="maq-toolbar">
        <label>
          Buscar
          <input
            value={busca}
            onChange={(e) => setBusca(e.target.value)}
            placeholder="Serial, nome ou transação…"
          />
        </label>
        <label>
          Caixa
          <select value={filtroCaixa} onChange={(e) => setFiltroCaixa(e.target.value)}>
            <option value="">Todos</option>
            {caixas.map((c) => (
              <option key={c.cd_caixa} value={c.cd_caixa}>
                {c.cd_caixa} — {c.ds_caixa}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select value={filtroStatus} onChange={(e) => setFiltroStatus(e.target.value)}>
            <option value="">Todos</option>
            <option value="A">Ativas</option>
            <option value="I">Inativas</option>
          </select>
        </label>
        <span className="muted small maq-count">
          {filtradas.length} de {items.length}
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Serial</th>
              <th>Caixa</th>
              <th>Trans fin</th>
              <th>Nome</th>
              <th>Status</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {filtradas.length === 0 ? (
              <tr>
                <td colSpan={6} className="muted">
                  Nenhuma maquininha neste filtro. Limpe a busca/caixa ou cadastre uma nova.
                </td>
              </tr>
            ) : (
              filtradas.map((m) => (
                <tr
                  key={m.nr_serie_maquininha}
                  className={
                    existentePeloSerial?.nr_serie_maquininha === m.nr_serie_maquininha
                      ? "row-selected"
                      : undefined
                  }
                >
                  <td>
                    <code>{m.nr_serie_maquininha}</code>
                  </td>
                  <td>
                    {m.cd_caixa}
                    <div className="muted small">{m.ds_caixa}</div>
                  </td>
                  <td>{m.cd_transacao_financeira ?? "—"}</td>
                  <td>{m.ds_maquininha || "-"}</td>
                  <td>
                    <span className={`badge ${m.ie_status === "A" ? "s5" : "s7"}`}>{m.ie_status}</span>
                  </td>
                  <td>
                    <button type="button" className="btn ghost" onClick={() => edit(m)}>
                      Editar
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
