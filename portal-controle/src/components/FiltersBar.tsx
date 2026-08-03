import type { Filtros } from "../types";

type Props = {
  value: Filtros;
  caixas: Array<{ cd_caixa: number; ds_caixa: string }>;
  onChange: (next: Filtros) => void;
  onSubmit: () => void;
  showStatus?: boolean;
};

export function FiltersBar({ value, caixas, onChange, onSubmit, showStatus = true }: Props) {
  const set = (key: keyof Filtros, v: string) => onChange({ ...value, [key]: v });

  return (
    <form
      className="filters"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <label>
        Data de
        <input type="date" value={value.data_de || ""} onChange={(e) => set("data_de", e.target.value)} />
      </label>
      <label>
        Data até
        <input type="date" value={value.data_ate || ""} onChange={(e) => set("data_ate", e.target.value)} />
      </label>
      <label>
        Caixa
        <select value={value.cd_caixa || ""} onChange={(e) => set("cd_caixa", e.target.value)}>
          <option value="">Todos</option>
          {caixas.map((c) => (
            <option key={c.cd_caixa} value={c.cd_caixa}>
              {c.cd_caixa} — {c.ds_caixa}
            </option>
          ))}
        </select>
      </label>
      {showStatus && (
        <label>
          Status
          <select value={value.cd_status || ""} onChange={(e) => set("cd_status", e.target.value)}>
            <option value="">Todos</option>
            <option value="5">5 — Integrado</option>
            <option value="6">6 — Retry</option>
            <option value="7">7 — DLQ</option>
            <option value="8">8 — Sem Tesouraria</option>
            <option value="1">1 — Pendente</option>
            <option value="2">2 — Processando</option>
          </select>
        </label>
      )}
      <label>
        Tipo
        <select value={value.tipo || ""} onChange={(e) => set("tipo", e.target.value)}>
          <option value="">Todos</option>
          <option value="credit_card">Crédito</option>
          <option value="debit_card">Débito</option>
          <option value="prepaid_debit">Pré-pago</option>
          <option value="pix">PIX</option>
        </select>
      </label>
      <label>
        Bandeira
        <select value={value.bandeira || ""} onChange={(e) => set("bandeira", e.target.value)}>
          <option value="">Todas</option>
          <option value="visa">Visa</option>
          <option value="mastercard">Mastercard</option>
          <option value="elo">Elo</option>
          <option value="amex">Amex</option>
          <option value="hipercard">Hipercard</option>
          <option value="ticket">Ticket</option>
          <option value="cabal">Cabal</option>
          <option value="unionpay">UnionPay</option>
          <option value="alelo">Alelo</option>
        </select>
      </label>
      <label>
        ID Stone
        <input value={value.id_stone || ""} onChange={(e) => set("id_stone", e.target.value)} placeholder="parcial" />
      </label>
      <label>
        Serial
        <input value={value.nr_serie || ""} onChange={(e) => set("nr_serie", e.target.value)} />
      </label>
      <label>
        Valor mín
        <input value={value.vl_min || ""} onChange={(e) => set("vl_min", e.target.value)} />
      </label>
      <label>
        Valor máx
        <input value={value.vl_max || ""} onChange={(e) => set("vl_max", e.target.value)} />
      </label>
      <label>
        Obs / erro
        <input value={value.obs || ""} onChange={(e) => set("obs", e.target.value)} />
      </label>
      <div className="filters-actions">
        <button type="submit" className="btn">
          Filtrar
        </button>
      </div>
    </form>
  );
}
