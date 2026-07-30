import { useCallback, useEffect, useState } from "react";
import { reprocessarLogsApi, type AcaoLog } from "../api/client";

function summarizeDiff(antes: Record<string, unknown> | null, depois: Record<string, unknown> | null) {
  if (!antes && !depois) return "—";
  const keys = ["nr_serie_maquininha", "cd_caixa", "cd_status", "published_count", "reference_date"];
  const parts: string[] = [];
  for (const k of keys) {
    const a = antes?.[k];
    const d = depois?.[k];
    if (a !== d && (a !== undefined || d !== undefined)) {
      parts.push(`${k}: ${a ?? "∅"} → ${d ?? "∅"}`);
    }
  }
  return parts.length ? parts.join(" · ") : "sem alteração de serial/caixa/status";
}

export function AuditoriaPage() {
  const [items, setItems] = useState<AcaoLog[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await reprocessarLogsApi(200);
      setItems(data.items || []);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <div>
      <header className="page-head">
        <h1>Auditoria</h1>
        <p className="muted">Quem reprocessou ou alterou registros no portal.</p>
        <button type="button" className="btn ghost" onClick={() => void load()} disabled={loading}>
          Atualizar
        </button>
      </header>
      {error && <p className="error">{error}</p>}
      {loading && <p className="muted">Carregando...</p>}
      {!loading && !items.length && <p className="muted">Nenhuma ação registrada ainda.</p>}
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
                <th>Alterações</th>
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
