import { useEffect, useState, type FormEvent } from "react";
import {
  createMapeamentoApi,
  mapeamentosApi,
  saveBandeiraApi,
  updateMapeamentoApi,
  type Mapeamento,
} from "../api/client";

const emptyMap = {
  nr_sequencia: 0,
  cd_cartao_bandeira_tasy: "",
  cd_tipo_transacao: "1",
  cd_bandeira: "",
};

export function MapeamentosPage() {
  const [items, setItems] = useState<Mapeamento[]>([]);
  const [tipos, setTipos] = useState<Array<{ cd_tipo_transacao: number; ds_tipo_transacao: string }>>([]);
  const [bandeiras, setBandeiras] = useState<Array<{ cd_bandeira: number; ds_bandeira: string }>>([]);
  const [form, setForm] = useState(emptyMap);
  const [editing, setEditing] = useState(false);
  const [bandForm, setBandForm] = useState({ cd_bandeira: "7", ds_bandeira: "Ticket" });
  const [msg, setMsg] = useState("");
  const [error, setError] = useState("");

  async function load() {
    const data = await mapeamentosApi();
    setItems(data.items || []);
    setTipos(data.tipos || []);
    setBandeiras(data.bandeiras || []);
  }

  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, []);

  function edit(row: Mapeamento) {
    setEditing(true);
    setForm({
      nr_sequencia: row.nr_sequencia,
      cd_cartao_bandeira_tasy: String(row.cd_cartao_bandeira_tasy),
      cd_tipo_transacao: String(row.cd_tipo_transacao),
      cd_bandeira: row.cd_bandeira == null ? "" : String(row.cd_bandeira),
    });
    setMsg("");
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError("");
    setMsg("");
    const body = {
      cd_cartao_bandeira_tasy: Number(form.cd_cartao_bandeira_tasy),
      cd_tipo_transacao: Number(form.cd_tipo_transacao),
      cd_bandeira: form.cd_bandeira === "" ? null : Number(form.cd_bandeira),
    };
    try {
      if (editing) {
        await updateMapeamentoApi(form.nr_sequencia, body);
        setMsg("Mapeamento atualizado.");
      } else {
        await createMapeamentoApi(body);
        setMsg("Mapeamento criado.");
      }
      setForm(emptyMap);
      setEditing(false);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao salvar");
    }
  }

  async function onBandeira(e: FormEvent) {
    e.preventDefault();
    setError("");
    try {
      await saveBandeiraApi({
        cd_bandeira: Number(bandForm.cd_bandeira),
        ds_bandeira: bandForm.ds_bandeira,
      });
      setMsg("Bandeira salva. Agora cadastre o mapeamento (ex.: Crédito + Ticket → id Tasy).");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro bandeira");
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Cadastro — Mapeamentos</h1>
        <p className="muted">
          Tipo + bandeira → id Tasy. Use <strong>Pre_pago (6)</strong> para pré-pago — não use Débito.
        </p>
      </header>

      <form className="form-card" onSubmit={onBandeira}>
        <h2>Bandeira local (se faltar)</h2>
        <p className="muted small">
          Ex.: Ticket = código 7 (já mapeado no consumer). Depois crie o mapeamento com id Tasy real.
        </p>
        <div className="form-grid">
          <label>
            Código
            <input
              type="number"
              required
              value={bandForm.cd_bandeira}
              onChange={(e) => setBandForm({ ...bandForm, cd_bandeira: e.target.value })}
            />
          </label>
          <label>
            Nome
            <input
              required
              value={bandForm.ds_bandeira}
              onChange={(e) => setBandForm({ ...bandForm, ds_bandeira: e.target.value })}
            />
          </label>
        </div>
        <button type="submit" className="btn">
          Salvar bandeira
        </button>
      </form>

      <form className="form-card" onSubmit={onSubmit}>
        <h2>{editing ? "Editar mapeamento" : "Novo mapeamento"}</h2>
        <div className="form-grid">
          <label>
            Tipo
            <select
              required
              value={form.cd_tipo_transacao}
              onChange={(e) => setForm({ ...form, cd_tipo_transacao: e.target.value })}
            >
              {tipos.map((t) => (
                <option key={t.cd_tipo_transacao} value={t.cd_tipo_transacao}>
                  {t.cd_tipo_transacao} — {t.ds_tipo_transacao}
                </option>
              ))}
            </select>
          </label>
          <label>
            Bandeira
            <select
              value={form.cd_bandeira}
              onChange={(e) => setForm({ ...form, cd_bandeira: e.target.value })}
            >
              <option value="">(sem bandeira / PIX)</option>
              {bandeiras.map((b) => (
                <option key={b.cd_bandeira} value={b.cd_bandeira}>
                  {b.cd_bandeira} — {b.ds_bandeira}
                </option>
              ))}
            </select>
          </label>
          <label>
            ID bandeira no Tasy
            <input
              type="number"
              required
              value={form.cd_cartao_bandeira_tasy}
              onChange={(e) => setForm({ ...form, cd_cartao_bandeira_tasy: e.target.value })}
              placeholder="nr_sequencia Tasy"
            />
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
                setForm(emptyMap);
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
              <th>#</th>
              <th>Tipo</th>
              <th>Bandeira</th>
              <th>ID Tasy</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {items.map((m) => (
              <tr key={m.nr_sequencia}>
                <td>{m.nr_sequencia}</td>
                <td>
                  {m.cd_tipo_transacao} — {m.ds_tipo_transacao}
                </td>
                <td>
                  {m.cd_bandeira == null ? "(null)" : `${m.cd_bandeira} — ${m.ds_bandeira || ""}`}
                </td>
                <td>{m.cd_cartao_bandeira_tasy}</td>
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
