import { useCallback, useEffect, useState } from "react";
import { auditoriaLogsApi, type AcaoLog } from "../api/client";

const PAGE_SIZE = 50;

type Applied = {
  acao: string;
  login: string;
  id_stone: string;
  data_de: string;
  data_ate: string;
};

function summarizeDiff(antes: Record<string, unknown> | null, depois: Record<string, unknown> | null) {
  if (!antes && !depois) return "—";
  const keys = [
    "nr_serie_maquininha",
    "cd_caixa",
    "cd_status",
    "published_count",
    "published",
    "reference_date",
    "enabled",
    "path",
    "method",
    "status_code",
    "error",
    "slot",
    "flow",
  ];
  const parts: string[] = [];
  for (const k of keys) {
    const a = antes?.[k];
    const d = depois?.[k];
    if (a !== d && (a !== undefined || d !== undefined)) {
      parts.push(`${k}: ${a ?? "∅"} → ${d ?? "∅"}`);
    }
  }
  if (parts.length) return parts.join(" · ");
  if (depois && Object.keys(depois).length) {
    return Object.entries(depois)
      .slice(0, 4)
      .map(([k, v]) => `${k}=${v}`)
      .join(" · ");
  }
  return "—";
}

export function AuditoriaPage() {
  const [items, setItems] = useState<AcaoLog[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [acao, setAcao] = useState("");
  const [login, setLogin] = useState("");
  const [idStone, setIdStone] = useState("");
  const [dataDe, setDataDe] = useState("");
  const [dataAte, setDataAte] = useState("");
  const [applied, setApplied] = useState<Applied>({
    acao: "",
    login: "",
    id_stone: "",
    data_de: "",
    data_ate: "",
  });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await auditoriaLogsApi({
        limit: PAGE_SIZE,
        offset: (page - 1) * PAGE_SIZE,
        acao: applied.acao || undefined,
        login: applied.login || undefined,
        id_stone: applied.id_stone || undefined,
        data_de: applied.data_de || undefined,
        data_ate: applied.data_ate || undefined,
      });
      setItems(data.items || []);
      setTotal(data.total ?? 0);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, applied]);

  useEffect(() => {
    void load();
  }, [load]);

  function applyFilters(e: React.FormEvent) {
    e.preventDefault();
    setPage(1);
    setApplied({
      acao: acao.trim(),
      login: login.trim(),
      id_stone: idStone.trim(),
      data_de: dataDe,
      data_ate: dataAte,
    });
  }

  return (
    <div>
      <header className="page-head">
        <h1>Auditoria</h1>
        <p className="muted">
          Histórico de ações do portal e do sistema (scheduler, reprocesso, cadastros, APIs).
        </p>
      </header>

      <form className="form-card filters" onSubmit={applyFilters}>
        <label>
          Ação
          <input
            value={acao}
            onChange={(e) => setAcao(e.target.value)}
            placeholder="ex.: scheduler, reprocessar, api_post"
          />
        </label>
        <label>
          Login
          <input
            value={login}
            onChange={(e) => setLogin(e.target.value)}
            placeholder="usuário ou sistema"
          />
        </label>
        <label>
          ID Stone
          <input value={idStone} onChange={(e) => setIdStone(e.target.value)} />
        </label>
        <label>
          De
          <input type="date" value={dataDe} onChange={(e) => setDataDe(e.target.value)} />
        </label>
        <label>
          Até
          <input type="date" value={dataAte} onChange={(e) => setDataAte(e.target.value)} />
        </label>
        <div className="reprocess-group" style={{ alignItems: "end" }}>
          <button type="submit" className="btn btn-accent" disabled={loading}>
            Filtrar
          </button>
          <button
            type="button"
            className="btn ghost"
            disabled={loading}
            onClick={() => void load()}
          >
            Atualizar
          </button>
        </div>
      </form>

      <div className="pager-bar">
        <span className="muted small">
          {total} registro(s) · página {page}/{totalPages}
        </span>
        <div className="pager-nav">
          <button
            type="button"
            className="btn ghost btn-sm"
            disabled={loading || page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            Anterior
          </button>
          <button
            type="button"
            className="btn ghost btn-sm"
            disabled={loading || page >= totalPages}
            onClick={() => setPage((p) => p + 1)}
          >
            Próxima
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Carregando...</p>}
      {!loading && !items.length && <p className="muted">Nenhuma ação no filtro atual.</p>}
      {items.length > 0 && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Quando</th>
                <th>Usuário</th>
                <th>Ação</th>
                <th>ID Stone</th>
                <th>Registro</th>
                <th>Detalhes</th>
                <th>Obs</th>
              </tr>
            </thead>
            <tbody>
              {items.map((l) => (
                <tr key={l.nr_sequencia}>
                  <td className="nowrap">{l.dt_evento}</td>
                  <td>
                    <strong>{l.ds_login}</strong>
                    {l.ds_nome ? <div className="muted small">{l.ds_nome}</div> : null}
                  </td>
                  <td>
                    <code>{l.ds_acao}</code>
                  </td>
                  <td>
                    <code>{l.id_stone || "—"}</code>
                  </td>
                  <td>{l.nr_seq_registro ?? "—"}</td>
                  <td className="obs">{summarizeDiff(l.ds_antes, l.ds_depois)}</td>
                  <td className="obs">{l.ds_obs || ""}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
