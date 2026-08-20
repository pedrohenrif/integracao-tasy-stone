import { useEffect, useState, type FormEvent } from "react";
import { maquininhasApi, saveMaquininhaApi, type Maquininha } from "../api/client";

const empty = {
  nr_serie_maquininha: "",
  cd_caixa: "",
  cd_transacao_financeira: "",
  ds_maquininha: "",
  ie_status: "A",
};

export function MaquininhasPage() {
  const [items, setItems] = useState<Maquininha[]>([]);
  const [pendentes, setPendentes] = useState<string[]>([]);
  const [caixas, setCaixas] = useState<Array<{ cd_caixa: number; ds_caixa: string }>>([]);
  const [form, setForm] = useState(empty);
  const [editing, setEditing] = useState(false);
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const data = await maquininhasApi();
    setItems(data.items || []);
    setPendentes(data.seriais_pendentes || []);
    setCaixas(data.caixas || []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  function edit(row: Maquininha) {
    setEditing(true);
    setForm({
      nr_serie_maquininha: row.nr_serie_maquininha,
      cd_caixa: String(row.cd_caixa),
      cd_transacao_financeira: String(row.cd_transacao_financeira),
      ds_maquininha: row.ds_maquininha || "",
      ie_status: row.ie_status || "A",
    });
    setMsg("");
    setError("");
  }

  function novoComSerial(serial: string) {
    setEditing(false);
    setForm({ ...empty, nr_serie_maquininha: serial, ie_status: "A" });
    setMsg(`Preencha caixa e transação financeira para ${serial}`);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    try {
      await saveMaquininhaApi({
        nr_serie_maquininha: form.nr_serie_maquininha.trim(),
        cd_caixa: Number(form.cd_caixa),
        cd_transacao_financeira: Number(form.cd_transacao_financeira),
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
        <p className="muted">Incluir / editar terminais (resolve erro “não cadastrada”)</p>
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
              onChange={(e) => setForm({ ...form, nr_serie_maquininha: e.target.value })}
              disabled={editing}
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
                </option>
              ))}
            </select>
          </label>
          <label>
            Transação financeira (Tasy)
            <input
              required
              type="number"
              value={form.cd_transacao_financeira}
              onChange={(e) => setForm({ ...form, cd_transacao_financeira: e.target.value })}
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
        <div className="filters-actions">
          <button type="submit" className="btn">
            Salvar
          </button>
          {editing && (
            <button
              type="button"
              className="btn ghost"
              onClick={() => {
                setEditing(false);
                setForm(empty);
              }}
            >
              Cancelar
            </button>
          )}
        </div>
        {msg && <p className="ok-msg">{msg}</p>}
        {error && <p className="error">{error}</p>}
      </form>

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
            {items.map((m) => (
              <tr key={m.nr_serie_maquininha}>
                <td>
                  <code>{m.nr_serie_maquininha}</code>
                </td>
                <td>
                  {m.cd_caixa}
                  <div className="muted small">{m.ds_caixa}</div>
                </td>
                <td>{m.cd_transacao_financeira}</td>
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
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
