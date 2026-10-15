import { useCallback, useEffect, useState } from "react";
import { espelharPixBackupApi, movimentosStoneApi, pixBackupApi, type MovimentoStone } from "../api/client";
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
  const [msg, setMsg] = useState("");
  const [loading, setLoading] = useState(false);
  const [busyEspelho, setBusyEspelho] = useState(false);
  const [pixBackup, setPixBackup] = useState<{
    has_csv: boolean;
    conferencia?: {
      publicados?: number;
      fora_piloto?: number;
      ok?: boolean;
      alerta?: string | null;
      source?: string;
      at?: string;
    } | null;
  } | null>(null);

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
      try {
        const backup = await pixBackupApi(dataDe);
        setPixBackup(backup);
      } catch {
        setPixBackup(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, [dataDe, dataAte, origem, publicado, serie, idStone]);

  async function onCarregarCsvVm() {
    setBusyEspelho(true);
    setError("");
    setMsg("");
    try {
      const res = await espelharPixBackupApi(dataDe);
      setMsg(res.mensagem || `Carregadas ${res.upserted} linha(s) do CSV.`);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar CSV da VM");
    } finally {
      setBusyEspelho(false);
    }
  }

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
      {msg && <p className="ok-msg">{msg}</p>}
      {pixBackup?.has_csv && (
        <p className="muted">
          CSV PIX de {dataDe} está na VM
          {pixBackup.conferencia
            ? ` · publicados ${pixBackup.conferencia.publicados ?? "—"} · fora do cadastro ${pixBackup.conferencia.fora_piloto ?? "—"}`
            : ""}
          .{" "}
          <button
            type="button"
            className={`btn${busyEspelho ? " btn-busy" : ""}`}
            disabled={busyEspelho}
            onClick={() => void onCarregarCsvVm()}
          >
            {busyEspelho ? "Carregando…" : "Carregar relação do CSV"}
          </button>
        </p>
      )}
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
            {pixBackup?.has_csv
              ? "O arquivo está na VM. Clique em Carregar relação do CSV — não integra de novo no Tasy."
              : "Ainda não há CSV PIX deste dia na VM (webhook ~04:50 do dia seguinte). Cartão aparece após extrair no Dashboard."}
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
