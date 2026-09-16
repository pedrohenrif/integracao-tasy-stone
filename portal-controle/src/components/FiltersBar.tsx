import type { Filtros } from "../types";

type Props = {
  value: Filtros;
  caixas: Array<{ cd_caixa: number; ds_caixa: string }>;
  onChange: (next: Filtros) => void;
  onSubmit: () => void;
  showStatus?: boolean;
};

const TIPOS = [
  { id: "credit_card", label: "Crédito" },
  { id: "debit_card", label: "Débito" },
  { id: "prepaid_debit", label: "Pré-pago débito" },
  { id: "prepaid_credit", label: "Pré-pago crédito" },
  { id: "pix", label: "PIX" },
];

const STATUS = [
  { id: "5", label: "Integrado" },
  { id: "6", label: "Retry" },
  { id: "7", label: "DLQ" },
  { id: "8", label: "Sem Tesouraria" },
  { id: "9", label: "Reintegrar" },
  { id: "10", label: "Ignorado" },
  { id: "1", label: "Pendente" },
  { id: "2", label: "Processando" },
];

const BANDEIRAS = [
  { id: "visa", label: "Visa" },
  { id: "mastercard", label: "Mastercard" },
  { id: "elo", label: "Elo" },
  { id: "amex", label: "Amex" },
  { id: "hipercard", label: "Hipercard" },
  { id: "ticket", label: "Ticket" },
  { id: "cabal", label: "Cabal" },
  { id: "unionpay", label: "UnionPay" },
  { id: "alelo", label: "Alelo" },
];

function tokens(csv: string | undefined): string[] {
  return (csv || "")
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);
}

function hasToken(csv: string | undefined, id: string): boolean {
  return tokens(csv).includes(id);
}

function toggleToken(csv: string | undefined, id: string): string {
  const set = new Set(tokens(csv));
  if (set.has(id)) set.delete(id);
  else set.add(id);
  return [...set].join(",");
}

function ChipGroup({
  title,
  hint,
  options,
  csv,
  onToggle,
}: {
  title: string;
  hint?: string;
  options: Array<{ id: string; label: string }>;
  csv: string | undefined;
  onToggle: (id: string) => void;
}) {
  const n = tokens(csv).length;
  return (
    <div className="filters-group">
      <div className="filters-group-head">
        <strong>{title}</strong>
        <span className="muted small">{n ? `${n} selecionado(s)` : hint || "todos"}</span>
      </div>
      <div className="filters-chips">
        {options.map((opt) => {
          const on = hasToken(csv, opt.id);
          return (
            <label key={opt.id} className={`chip-check${on ? " on" : ""}`}>
              <input
                type="checkbox"
                checked={on}
                onChange={() => onToggle(opt.id)}
              />
              <span>{opt.label}</span>
            </label>
          );
        })}
      </div>
    </div>
  );
}

export function FiltersBar({ value, caixas, onChange, onSubmit, showStatus = true }: Props) {
  const set = (key: keyof Filtros, v: string) => onChange({ ...value, [key]: v });
  const toggle = (key: keyof Filtros, id: string) => set(key, toggleToken(value[key], id));

  return (
    <form
      className="filters"
      onSubmit={(e) => {
        e.preventDefault();
        onSubmit();
      }}
    >
      <div className="filters-row">
        <label>
          Data de
          <input type="date" value={value.data_de || ""} onChange={(e) => set("data_de", e.target.value)} />
        </label>
        <label>
          Data até
          <input type="date" value={value.data_ate || ""} onChange={(e) => set("data_ate", e.target.value)} />
        </label>
        <label>
          ID Stone
          <input
            value={value.id_stone || ""}
            onChange={(e) => set("id_stone", e.target.value)}
            placeholder="ex.: 310633…"
            autoComplete="off"
          />
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
        <label className="filters-span-2">
          Obs / erro
          <input value={value.obs || ""} onChange={(e) => set("obs", e.target.value)} />
        </label>
        <label>
          Internacional
          <select
            value={value.ie_internacional || ""}
            onChange={(e) => set("ie_internacional", e.target.value)}
          >
            <option value="">Todos</option>
            <option value="S">Sim</option>
            <option value="N">Não</option>
          </select>
        </label>
      </div>

      <ChipGroup
        title="Tipo"
        hint="todos os tipos"
        options={TIPOS}
        csv={value.tipo}
        onToggle={(id) => toggle("tipo", id)}
      />

      {showStatus && (
        <ChipGroup
          title="Status"
          hint="todos os status"
          options={STATUS}
          csv={value.cd_status}
          onToggle={(id) => toggle("cd_status", id)}
        />
      )}

      <ChipGroup
        title="Bandeira"
        hint="todas as bandeiras"
        options={BANDEIRAS}
        csv={value.bandeira}
        onToggle={(id) => toggle("bandeira", id)}
      />

      <ChipGroup
        title="Caixa"
        hint="todos os caixas"
        options={caixas.map((c) => ({
          id: String(c.cd_caixa),
          label: `${c.cd_caixa} · ${c.ds_caixa}`,
        }))}
        csv={value.cd_caixa}
        onToggle={(id) => toggle("cd_caixa", id)}
      />

      <div className="filters-actions">
        <button type="submit" className="btn">
          Filtrar
        </button>
        <span className="muted small">Marque um ou mais. Vazio = todos.</span>
      </div>
    </form>
  );
}
