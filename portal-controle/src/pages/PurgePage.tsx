import { useState } from "react";
import {
  purgeConfirmApi,
  purgePreviewApi,
  type PurgePreviewResponse,
  type PurgeResultItem,
} from "../api/client";

function money(v: number) {
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

export function PurgePage() {
  const [nmUsuario, setNmUsuario] = useState("stone");
  const [cdCaixa, setCdCaixa] = useState("");
  const [dataDe, setDataDe] = useState("");
  const [dataAte, setDataAte] = useState("");
  const [idStone, setIdStone] = useState("");
  const [idStonesText, setIdStonesText] = useState("");
  const [allowFechado, setAllowFechado] = useState(false);
  const [phrase, setPhrase] = useState("");
  const [preview, setPreview] = useState<PurgePreviewResponse | null>(null);
  const [resultados, setResultados] = useState<PurgeResultItem[] | null>(null);
  const [error, setError] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);

  function buildBody() {
    const id_stones = idStonesText
      .split(/[\s,;]+/)
      .map((s) => s.trim())
      .filter(Boolean);
    return {
      nm_usuario: nmUsuario.trim() || "stone",
      cd_caixa: cdCaixa.trim() ? Number(cdCaixa) : null,
      data_de: dataDe || null,
      data_ate: dataAte || null,
      id_stone: idStone.trim() || null,
      id_stones,
      allow_fechado: allowFechado,
    };
  }

  async function onPreview() {
    setBusy(true);
    setError("");
    setMsg("");
    setResultados(null);
    try {
      const data = await purgePreviewApi(buildBody());
      setPreview(data);
      setPhrase("");
      setMsg(
        `Preview: ${data.totais.elegiveis} elegíveis · ${data.totais.bloqueados} bloqueados · ${data.totais.sem_oracle} sem Oracle`,
      );
    } catch (e) {
      setPreview(null);
      setError(e instanceof Error ? e.message : "Erro no preview");
    } finally {
      setBusy(false);
    }
  }

  async function onConfirm() {
    if (!preview?.confirm_token) {
      setError("Faça o preview antes de confirmar.");
      return;
    }
    setBusy(true);
    setError("");
    setMsg("");
    try {
      const data = await purgeConfirmApi({
        ...buildBody(),
        confirm_token: preview.confirm_token,
        confirm_phrase: phrase,
      });
      setResultados(data.resultados);
      setPreview(null);
      setPhrase("");
      setMsg(`Purge concluído: ${data.ok} ok · ${data.falhas} falhas`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Erro ao confirmar");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <header className="page-head">
        <h1>Purge Stone (admin)</h1>
        <p className="muted">
          Remove no Tasy apenas recebimentos/cartões/documentos criados pela integração (usuário + ID
          stone). Caixa e saldo diário não são apagados.
        </p>
      </header>

      <div className="callout">
        Fluxo obrigatório: <strong>Preview</strong> → revisar → digitar <code>EXCLUIR</code> →{" "}
        <strong>Confirmar</strong>. Lançamentos manuais (outro usuário) não entram.
      </div>

      <div className="form-card">
        <h2>Filtros</h2>
        <div className="filters">
          <label>
            Usuário Oracle (nm_usuario)
            <input
              value={nmUsuario}
              onChange={(e) => setNmUsuario(e.target.value)}
              placeholder="stone"
            />
          </label>
          <label>
            Caixa
            <input
              value={cdCaixa}
              onChange={(e) => setCdCaixa(e.target.value)}
              placeholder="ex.: 48"
            />
          </label>
          <label>
            Data de
            <input type="date" value={dataDe} onChange={(e) => setDataDe(e.target.value)} />
          </label>
          <label>
            Data até
            <input type="date" value={dataAte} onChange={(e) => setDataAte(e.target.value)} />
          </label>
          <label>
            ID Stone (parcial)
            <input
              value={idStone}
              onChange={(e) => setIdStone(e.target.value)}
              placeholder="filtro staging"
            />
          </label>
        </div>
        <label className="block-label">
          IDs Stone exatos (um por linha ou separados por vírgula)
          <textarea
            rows={3}
            value={idStonesText}
            onChange={(e) => setIdStonesText(e.target.value)}
            placeholder="28963791511463"
          />
        </label>
        <label className="check-inline">
          <input
            type="checkbox"
            checked={allowFechado}
            onChange={(e) => setAllowFechado(e.target.checked)}
          />
          Permitir recebimentos já confirmados (dt_fechamento)
        </label>
        <div className="reprocess-group" style={{ marginTop: "0.75rem" }}>
          <button type="button" className="btn btn-accent" disabled={busy} onClick={() => void onPreview()}>
            Preview
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {msg && <p className="ok-msg">{msg}</p>}

      {preview && (
        <div className="form-card" style={{ marginTop: "1rem" }}>
          <h2>Preview</h2>
          <div className="cards compact">
            <div className="card">
              <span>Total</span>
              <b>{preview.totais.total}</b>
            </div>
            <div className="card ok">
              <span>Elegíveis</span>
              <b>{preview.totais.elegiveis}</b>
            </div>
            <div className="card dlq">
              <span>Bloqueados</span>
              <b>{preview.totais.bloqueados}</b>
            </div>
            <div className="card">
              <span>Sem Oracle</span>
              <b>{preview.totais.sem_oracle}</b>
            </div>
          </div>
          <ul className="muted small">
            {preview.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Pode?</th>
                  <th>ID Stone</th>
                  <th>Caixa</th>
                  <th>Status</th>
                  <th>Valor</th>
                  <th>Oracle</th>
                  <th>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {preview.items.map((it) => (
                  <tr key={it.nr_sequencia}>
                    <td>{it.can_purge ? "Sim" : "Não"}</td>
                    <td>
                      <code>{it.id_stone}</code>
                    </td>
                    <td>{it.cd_caixa ?? "-"}</td>
                    <td>{it.cd_status}</td>
                    <td className="num">{money(it.vl_transacao)}</td>
                    <td className="small">
                      {it.oracle
                        ? `movto=${it.oracle.nr_seq_movto} · docs=${it.oracle.qtd_docs} · parc=${it.oracle.qtd_parcelas}${
                            it.oracle.ja_fechado ? " · FECHADO" : ""
                          }`
                        : "—"}
                    </td>
                    <td className="obs">{it.blocked_reason || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {preview.totais.elegiveis > 0 && (
            <div className="reprocess-group" style={{ marginTop: "1rem" }}>
              <label>
                Digite <code>{preview.confirm_phrase_required}</code> para confirmar
                <input
                  value={phrase}
                  onChange={(e) => setPhrase(e.target.value)}
                  placeholder={preview.confirm_phrase_required}
                  autoComplete="off"
                />
              </label>
              <button
                type="button"
                className="btn"
                disabled={busy || phrase.trim() !== preview.confirm_phrase_required}
                onClick={() => void onConfirm()}
              >
                Confirmar exclusão
              </button>
            </div>
          )}
        </div>
      )}

      {resultados && (
        <div className="form-card" style={{ marginTop: "1rem" }}>
          <h2>Resultado</h2>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>OK</th>
                  <th>ID Stone</th>
                  <th>Deleted</th>
                  <th>Motivo</th>
                </tr>
              </thead>
              <tbody>
                {resultados.map((r) => (
                  <tr key={`${r.nr_sequencia}-${r.id_stone}`}>
                    <td>{r.ok ? "Sim" : "Não"}</td>
                    <td>
                      <code>{r.id_stone}</code>
                    </td>
                    <td className="small">{JSON.stringify(r.deleted || {})}</td>
                    <td className="obs">{r.blocked_reason || ""}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
