import { useCallback, useEffect, useState } from "react";
import {
  caixasApi,
  espelharPixBackupApi,
  movimentosStoneApi,
  pixBackupApi,
  type MovimentoStone,
} from "../api/client";
import {
  BANDEIRAS,
  ChipGroup,
  STATUS,
  TIPOS,
} from "../components/FiltersBar";
import { dataOntemISO } from "../utils/dates";

function csvToggle(csv: string, id: string): string {
  const set = new Set(
    csv
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean),
  );
  if (set.has(id)) set.delete(id);
  else set.add(id);
  return [...set].join(",");
}

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function statusCasou(r: MovimentoStone) {
  if (!r.nr_seq_registro) return "sem lançamento";
  const map: Record<number, string> = {
    5: "Integrado",
    11: "Só movto",
    8: "Sem tesouraria",
    10: "Ignorado",
    7: "DLQ",
    6: "Retry",
    9: "Reintegrar",
  };
  return map[Number(r.cd_status)] || `status ${r.cd_status ?? "—"}`;
}

export function MovimentosStonePage() {
  const ontem = dataOntemISO();
  const [dataDe, setDataDe] = useState(ontem);
  const [dataAte, setDataAte] = useState(ontem);
  const [origem, setOrigem] = useState("");
  const [publicado, setPublicado] = useState("");
  const [serie, setSerie] = useState("");
  const [idStone, setIdStone] = useState("");
  const [vlMin, setVlMin] = useState("");
  const [vlMax, setVlMax] = useState("");
  const [casou, setCasou] = useState("");
  const [cdCaixa, setCdCaixa] = useState("");
  const [tipo, setTipo] = useState("");
  const [bandeira, setBandeira] = useState("");
  const [cdStatus, setCdStatus] = useState("");
  const [obs, setObs] = useState("");
  const [caixas, setCaixas] = useState<Array<{ cd_caixa: number; ds_caixa: string }>>([]);
  const [rows, setRows] = useState<MovimentoStone[]>([]);
  const [resumo, setResumo] = useState<{
    total?: number;
    publicados?: number;
    nao_publicados?: number;
    casaram?: number;
    nao_casaram?: number;
    soma_valor?: number;
    soma_casaram?: number;
    soma_nao_casaram?: number;
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

  const load = useCallback(async (f: {
    data_de: string;
    data_ate: string;
    origem: string;
    publicado: string;
    nr_serie: string;
    id_stone: string;
    vl_min: string;
    vl_max: string;
    casou: string;
    cd_caixa: string;
    tipo: string;
    bandeira: string;
    cd_status: string;
    obs: string;
  }) => {
    setError("");
    setLoading(true);
    try {
      const data = await movimentosStoneApi({
        ...f,
        limit: "500",
      });
      setRows(data.items || []);
      setResumo(data.resumo || {});
      try {
        const backup = await pixBackupApi(f.data_de);
        setPixBackup(backup);
      } catch {
        setPixBackup(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar");
    } finally {
      setLoading(false);
    }
  }, []);

  function filtrosAtuais() {
    return {
      data_de: dataDe,
      data_ate: dataAte,
      origem,
      publicado,
      nr_serie: serie,
      id_stone: idStone,
      vl_min: vlMin,
      vl_max: vlMax,
      casou,
      cd_caixa: cdCaixa,
      tipo,
      bandeira,
      cd_status: cdStatus,
      obs,
    };
  }

  function resetOntem() {
    const ontemISO = dataOntemISO();
    setDataDe(ontemISO);
    setDataAte(ontemISO);
    setOrigem("");
    setPublicado("");
    setSerie("");
    setIdStone("");
    setVlMin("");
    setVlMax("");
    setCasou("");
    setCdCaixa("");
    setTipo("");
    setBandeira("");
    setCdStatus("");
    setObs("");
    void load({
      data_de: ontemISO,
      data_ate: ontemISO,
      origem: "",
      publicado: "",
      nr_serie: "",
      id_stone: "",
      vl_min: "",
      vl_max: "",
      casou: "",
      cd_caixa: "",
      tipo: "",
      bandeira: "",
      cd_status: "",
      obs: "",
    });
  }

  async function onCarregarCsvVm() {
    setBusyEspelho(true);
    setError("");
    setMsg("");
    try {
      const res = await espelharPixBackupApi(dataDe);
      setMsg(res.mensagem || `Carregadas ${res.upserted} linha(s) do CSV.`);
      await load(filtrosAtuais());
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao carregar CSV da VM");
    } finally {
      setBusyEspelho(false);
    }
  }

  useEffect(() => {
    caixasApi()
      .then((r) => setCaixas(r.items || []))
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    void load({
      data_de: ontem,
      data_ate: ontem,
      origem: "",
      publicado: "",
      nr_serie: "",
      id_stone: "",
      vl_min: "",
      vl_max: "",
      casou: "",
      cd_caixa: "",
      tipo: "",
      bandeira: "",
      cd_status: "",
      obs: "",
    });
  }, [load, ontem]);

  return (
    <div>
      <header className="page-head">
        <h1>Movimentos Stone</h1>
        <p className="muted">
          Arquivo Stone (CSV/XML) comparado com Integrações. “Sem lançamento” = na fila/arquivo e
          sem staging — o furo de 1–2 vendas. Não é a conferência do Tasy.
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
          void load(filtrosAtuais());
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
            Comparação
            <select value={casou} onChange={(e) => setCasou(e.target.value)}>
              <option value="">Todas</option>
              <option value="N">Só o que não casou</option>
              <option value="S">Só o que casou</option>
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
          <label>
            Valor mín
            <input value={vlMin} onChange={(e) => setVlMin(e.target.value)} />
          </label>
          <label>
            Valor máx
            <input value={vlMax} onChange={(e) => setVlMax(e.target.value)} />
          </label>
          <label className="filters-span-2">
            Motivo / obs
            <input value={obs} onChange={(e) => setObs(e.target.value)} />
          </label>
        </div>
        <ChipGroup
          title="Tipo"
          hint="todos os tipos"
          options={TIPOS}
          csv={tipo}
          onToggle={(id) => setTipo((prev) => csvToggle(prev, id))}
        />
        <ChipGroup
          title="Status Integrações"
          hint="todos os status"
          options={STATUS}
          csv={cdStatus}
          onToggle={(id) => setCdStatus((prev) => csvToggle(prev, id))}
        />
        <ChipGroup
          title="Bandeira"
          hint="todas as bandeiras"
          options={BANDEIRAS}
          csv={bandeira}
          onToggle={(id) => setBandeira((prev) => csvToggle(prev, id))}
          collapsible
        />
        <ChipGroup
          title="Caixa"
          hint="todos os caixas"
          options={caixas.map((c) => ({
            id: String(c.cd_caixa),
            label: `${c.cd_caixa} · ${c.ds_caixa}`,
          }))}
          csv={cdCaixa}
          onToggle={(id) => setCdCaixa((prev) => csvToggle(prev, id))}
          collapsible
        />
        <div className="filters-actions">
          <button type="submit" className="btn">
            Filtrar
          </button>
          <button type="button" className="btn ghost" onClick={resetOntem}>
            Só ontem
          </button>
          <span className="muted small">Marque um ou mais. Vazio = todos.</span>
        </div>
      </form>
      <div className="cards compact">
        <div className="card">
          <span>Stone (arquivo)</span>
          <b>
            {resumo.total ?? 0} · {money(Number(resumo.soma_valor || 0))}
          </b>
        </div>
        <div className="card ok">
          <span>Casaram (Integrações)</span>
          <b>
            {resumo.casaram ?? 0} · {money(Number(resumo.soma_casaram || 0))}
          </b>
        </div>
        <div className="card dlq">
          <span>Sem lançamento</span>
          <b>
            {resumo.nao_casaram ?? 0} · {money(Number(resumo.soma_nao_casaram || 0))}
          </b>
        </div>
        <div className="card">
          <span>Fila sim / não</span>
          <b>
            {resumo.publicados ?? 0} / {resumo.nao_publicados ?? 0}
          </b>
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
              ? "PIX: use Carregar relação do CSV (não reintegra no Tasy). Cartão não entra nesse botão — extraia o dia no Dashboard."
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
                <th>Caixa</th>
                <th>Tipo</th>
                <th>Bandeira</th>
                <th>Valor</th>
                <th>Data</th>
                <th>Fila</th>
                <th>Integrações</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr
                  key={`${r.origem}-${r.id_stone}`}
                  className={r.nr_seq_registro ? undefined : "row-gap"}
                >
                  <td>{r.origem}</td>
                  <td>
                    <code>{r.id_stone}</code>
                  </td>
                  <td>
                    <code>{r.nr_serie_maquininha || "—"}</code>
                  </td>
                  <td>
                    {r.cd_caixa != null
                      ? `${r.cd_caixa}${r.ds_caixa ? ` · ${r.ds_caixa}` : ""}`
                      : "—"}
                  </td>
                  <td>{r.cd_tipo_transacao || "—"}</td>
                  <td>{r.cd_bandeira || "—"}</td>
                  <td className="num">
                    {r.vl_transacao != null ? money(Number(r.vl_transacao)) : "—"}
                  </td>
                  <td>{r.dt_movimentacao || r.reference_date || "—"}</td>
                  <td>
                    <span className={`badge ${r.publicado === "S" ? "s5" : "s10"}`}>
                      {r.publicado === "S" ? "Sim" : "Não"}
                    </span>
                  </td>
                  <td>
                    <span className={`badge ${r.nr_seq_registro ? "s5" : "s7"}`}>
                      {statusCasou(r)}
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
