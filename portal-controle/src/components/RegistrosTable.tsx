import type { Registro } from "../types";

const STATUS: Record<number, string> = {
  1: "Pendente",
  2: "Processando",
  5: "Integrado",
  6: "Retry",
  7: "DLQ",
  8: "Sem Tesouraria",
  9: "Reintegrar",
};

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

type Props = {
  rows: Registro[];
  selectable?: boolean;
  selected?: Set<number>;
  onToggle?: (nr: number) => void;
  onToggleAll?: (ids: number[]) => void;
  onReprocessRow?: (row: Registro) => void;
};

export function RegistrosTable({
  rows,
  selectable = false,
  selected,
  onToggle,
  onToggleAll,
  onReprocessRow,
}: Props) {
  if (!rows.length) return <p className="muted">Nenhum registro.</p>;

  const allIds = rows.map((r) => r.nr_sequencia);
  const allSelected = selectable && selected != null && allIds.every((id) => selected.has(id));
  const showActions = Boolean(onReprocessRow);

  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            {selectable && (
              <th className="check-col">
                <input
                  type="checkbox"
                  checked={allSelected}
                  onChange={() => onToggleAll?.(allIds)}
                  title="Selecionar todos da página"
                />
              </th>
            )}
            <th>Status</th>
            <th>ID Stone</th>
            <th>Caixa</th>
            <th>Serial</th>
            <th>Tipo</th>
            <th>Bandeira</th>
            <th>Internac.</th>
            <th>Valor</th>
            <th>Dt mov.</th>
            <th>Obs</th>
            {showActions && <th>Ações</th>}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const canReprocess =
              r.cd_status === 6 || r.cd_status === 7 || r.cd_status === 8 || r.cd_status === 9;
            return (
              <tr
                key={r.nr_sequencia}
                className={selected?.has(r.nr_sequencia) ? "row-selected" : undefined}
              >
                {selectable && (
                  <td className="check-col">
                    <input
                      type="checkbox"
                      checked={selected?.has(r.nr_sequencia) ?? false}
                      onChange={() => onToggle?.(r.nr_sequencia)}
                      disabled={r.cd_status === 5}
                      title={r.cd_status === 5 ? "Já integrado" : "Selecionar"}
                    />
                  </td>
                )}
                <td>
                  <span className={`badge s${r.cd_status}`}>
                    {STATUS[r.cd_status] || r.cd_status} ({r.cd_status})
                  </span>
                </td>
                <td>
                  <code>{r.id_stone}</code>
                </td>
                <td>
                  {r.cd_caixa ?? "-"}
                  <div className="muted small">{r.ds_caixa}</div>
                </td>
                <td>{r.nr_serie_maquininha}</td>
                <td>{r.cd_tipo_transacao || "-"}</td>
                <td>{r.cd_bandeira || "-"}</td>
                <td>
                  {r.ie_internacional === "S"
                    ? "Sim"
                    : r.ie_internacional === "N"
                      ? "Não"
                      : "-"}
                </td>
                <td className="num">{money(Number(r.vl_transacao || 0))}</td>
                <td>{r.dt_movimentacao}</td>
                <td className="obs">{r.ds_obs_processo || ""}</td>
                {showActions && (
                  <td>
                    <button
                      type="button"
                      className="btn btn-accent btn-sm"
                      disabled={!canReprocess}
                      title={
                        canReprocess
                          ? "Editar serial/caixa e reprocessar"
                          : "Só status 6, 7, 8 ou 9"
                      }
                      onClick={() => onReprocessRow?.(r)}
                    >
                      Reprocessar
                    </button>
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
