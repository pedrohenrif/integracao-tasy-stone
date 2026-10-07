import { useCallback, useEffect, useState } from "react";
import { movimentosStoneApi, type MovimentoStone } from "../api/client";
import { dataOntemISO } from "../utils/dates";

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function MovimentosStonePage() {
  const ontem = dataOntemISO();
  const [dataDe, setDataDe] = useState(ontem);
  const [dataAte, setDataAte] = useState(ontem);
  const [origem, setOrigem] = useState("");
  const [publicado, setPublicado] = useState("");
  const [serie, setSerie] = useState("");
  const [idStone, setIdStone] = useState("");
  const [rows, setRows] = useState<MovimentoStone[]>([]);
  const [resumo, setResumo] = useState<{
    total?: number;
    publicados?: number;
    nao_publicados?: number;
    soma_valor?: number;
  }>({});
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setError("");
    setLoading(true);
    try {
      const data = await movimentosStoneApi({
        data_de: dataDe,
        data_ate: dataAte,
        origem,
        publicado,
        nr_serie: serie,
        id_stone: idStone,
        limit: "500",
      });
      setRows(data.items || []);
      setResumo(data.resumo || {});
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, [dataDe, dataAte, origem, publicado, serie, idStone]);

  useEffect(() => {
    load().catch(() => undefined);
  }, [load]);

  return (
    <div>
      <header className="page-head">
        <h1>Movimentos Stone</h1>
        <p className="muted">
          Tudo que veio no CSV PIX e no XML de cartão, inclusive o que não foi publicado na fila
          (máquina inativa/não cadastrada, status diferente de paid, etc.). Não é o staging de integração.
        </p>
      </header>
      <form
        className="filters"
        onSubmit={(e) => {
          e.preventDefault();
          void load();
        }}
      >
        <div className="filters-row">
          <label>
            De
            <input type="date" value={dataDe} onChange={(e) => setDataDe(e.target.value)} />
          </label>
          <label>
            Até
            <input type="date" value={dataAte} onChange={(e) => setDataAte(e.target.value)} />
          </label>
          <label>
            Origem
            <select value={origem} onChange={(e) => setOrigem(e.target.value)}>
              <option value="">Todas</option>
              <option value="pix">PIX</option>
              <option value="cartao">Cartão</option>
            </select>
          </label>
          <label>
            Publicado
            <select value={publicado} onChange={(e) => setPublicado(e.target.value)}>
              <option value="">Todos</option>
              <option value="S">Sim (foi para a fila)</option>
              <option value="N">Não</option>
            </select>
          </label>
          <label>
            Serial
            <input value={serie} onChange={(e) => setSerie(e.target.value)} placeholder="PB09…" />
          </label>
          <label>
            ID Stone
            <input value={idStone} onChange={(e) => setIdStone(e.target.value)} />
          </label>
        </div>
        <div className="filters-actions">
          <button type="submit" className="btn">
            Filtrar
          </button>
        </div>
      </form>
      <div className="cards compact">
        <div className="card">
          <span>Total</span>
          <b>{resumo.total ?? 0}</b>
        </div>
        <div className="card ok">
          <span>Publicados</span>
          <b>{resumo.publicados ?? 0}</b>
        </div>
        <div className="card">
          <span>Não publicados</span>
          <b>{resumo.nao_publicados ?? 0}</b>
        </div>
        <div className="card">
          <span>Soma</span>
          <b>{money(Number(resumo.soma_valor || 0))}</b>
        </div>
      </div>
      {error && <p className="error">{error}</p>}
      {loading ? (
        <p className="muted">Carregando...</p>
      ) : rows.length === 0 ? (
        <div className="empty-state">
          <strong>Nenhum movimento neste filtro</strong>
          <p className="muted">
            Aparece após o webhook PIX ou a extração de cartão (exige PORTAL_INTERNAL_TOKEN nos dois
            .env).
          </p>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Origem</th>
                <th>ID Stone</th>
                <th>Serial</th>
                <th>Valor</th>
                <th>Data</th>
                <th>Status CSV</th>
                <th>Fila</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={`${r.origem}-${r.id_stone}`}>
                  <td>{r.origem}</td>
                  <td>
                    <code>{r.id_stone}</code>
                  </td>
                  <td>
                    <code>{r.nr_serie_maquininha || "—"}</code>
                  </td>
                  <td className="num">
                    {r.vl_transacao != null ? money(Number(r.vl_transacao)) : "—"}
                  </td>
                  <td>{r.dt_movimentacao || r.reference_date || "—"}</td>
                  <td>{r.status_origem || "—"}</td>
                  <td>
                    <span className={`badge ${r.publicado === "S" ? "s5" : "s10"}`}>
                      {r.publicado === "S" ? "Sim" : "Não"}
                    </span>
                  </td>
                  <td className="obs">{r.ds_motivo || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
