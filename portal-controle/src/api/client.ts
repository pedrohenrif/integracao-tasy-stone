import type { FilaInfo, Filtros, Registro, ResumoTotais, User } from "../types";

const API_BASE = import.meta.env.VITE_API_URL ?? "";

function authHeaders(): HeadersInit {
  const token = localStorage.getItem("portal_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (res.status === 401) {
    localStorage.removeItem("portal_token");
    localStorage.removeItem("portal_user");
    if (!path.includes("/api/auth/login")) {
      window.location.href = "/login";
    }
  }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data.detail;
    const msg =
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join("; ")
          : data.error || `HTTP ${res.status}`;
    throw new Error(msg || `HTTP ${res.status}`);
  }
  return data as T;
}

export async function loginApi(login: string, password: string) {
  return request<{ access_token: string; user: User }>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ login, password }),
  });
}

export async function meApi() {
  return request<User>("/api/auth/me");
}

export async function loginLogsApi(limit = 100) {
  return request<{ items: Array<Record<string, unknown>> }>(
    `/api/auth/login-logs?limit=${limit}`,
  );
}

export async function caixasApi() {
  return request<{ items: Array<{ cd_caixa: number; ds_caixa: string }> }>("/api/caixas");
}

function toQuery(f: Filtros): string {
  const p = new URLSearchParams();
  Object.entries(f).forEach(([k, v]) => {
    if (v !== undefined && v !== "") p.set(k, v);
  });
  return p.toString();
}

export async function registrosApi(filtros: Filtros) {
  const q = toQuery(filtros);
  return request<{
    resumo: {
      totais: ResumoTotais;
      por_status: Array<{ cd_status: number; qtd: number }>;
      por_caixa: Array<{ cd_caixa: number; ds_caixa: string; qtd: number; total: number }>;
    };
    registros: Registro[];
  }>(`/api/registros?${q}`);
}

export async function filasApi() {
  return request<{ items: FilaInfo[] }>("/api/filas");
}

export type Maquininha = {
  nr_sequencia: number;
  nr_serie_maquininha: string;
  cd_caixa: number;
  ds_caixa?: string;
  ds_maquininha?: string;
  ie_status: string;
  cd_transacao_financeira: number;
};

export type Mapeamento = {
  nr_sequencia: number;
  cd_cartao_bandeira_tasy: number;
  cd_tipo_transacao: number;
  ds_tipo_transacao?: string;
  cd_bandeira: number | null;
  ds_bandeira?: string | null;
};

export async function maquininhasApi() {
  return request<{
    items: Maquininha[];
    seriais_pendentes: string[];
    caixas: Array<{ cd_caixa: number; ds_caixa: string }>;
  }>("/api/cadastros/maquininhas");
}

export async function saveMaquininhaApi(body: {
  nr_serie_maquininha: string;
  cd_caixa: number;
  cd_transacao_financeira: number;
  ds_maquininha?: string;
  ie_status: string;
}) {
  return request<Maquininha>("/api/cadastros/maquininhas", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function mapeamentosApi() {
  return request<{
    items: Mapeamento[];
    tipos: Array<{ cd_tipo_transacao: number; ds_tipo_transacao: string }>;
    bandeiras: Array<{ cd_bandeira: number; ds_bandeira: string }>;
  }>("/api/cadastros/mapeamentos");
}

export async function createMapeamentoApi(body: {
  cd_cartao_bandeira_tasy: number;
  cd_tipo_transacao: number;
  cd_bandeira: number | null;
}) {
  return request<Mapeamento>("/api/cadastros/mapeamentos", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function updateMapeamentoApi(
  id: number,
  body: {
    cd_cartao_bandeira_tasy: number;
    cd_tipo_transacao: number;
    cd_bandeira: number | null;
  },
) {
  return request<Mapeamento>(`/api/cadastros/mapeamentos/${id}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function saveBandeiraApi(body: { cd_bandeira: number; ds_bandeira: string }) {
  return request<{ cd_bandeira: number; ds_bandeira: string }>("/api/cadastros/bandeiras", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function reprocessarSelecionadosApi(nr_sequencias: number[]) {
  return request<{
    enfileirados: number;
    ids_stone: string[];
    ignorados: Array<{ nr_sequencia: number; id_stone?: string; motivo: string }>;
    erros: Array<{ nr_sequencia: number; id_stone?: string; erro: string }>;
  }>("/api/reprocessar/selecionados", {
    method: "POST",
    body: JSON.stringify({ nr_sequencias }),
  });
}

export async function reprocessarDiaApi(date: string) {
  return request<{
    reference_date: string;
    parsed_count?: number;
    published_count?: number;
    queue?: string;
    mensagem?: string;
  }>("/api/reprocessar/dia", {
    method: "POST",
    body: JSON.stringify({ date }),
  });
}

export async function reprocessarRegistroApi(body: {
  nr_sequencia: number;
  nr_serie_maquininha?: string;
  cd_caixa?: number | null;
  obs?: string;
}) {
  return request<{
    enfileirado: boolean;
    fluxo: string;
    nr_sequencia: number;
    id_stone: string;
    mensagem: string;
    antes: Record<string, unknown>;
    depois: Record<string, unknown>;
  }>("/api/reprocessar/registro", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export type AcaoLog = {
  nr_sequencia: number;
  nr_seq_usuario: number | null;
  ds_login: string;
  ds_nome?: string | null;
  ds_acao: string;
  nr_seq_registro: number | null;
  id_stone: string | null;
  ds_antes: Record<string, unknown> | null;
  ds_depois: Record<string, unknown> | null;
  ds_obs: string | null;
  dt_evento: string;
};

export async function reprocessarLogsApi(limit = 100) {
  return request<{ items: AcaoLog[] }>(`/api/reprocessar/logs?limit=${limit}`);
}

export type SchedulerCartaoStatus = {
  enabled: boolean;
  running?: boolean;
  paused?: boolean;
  hour: number;
  minute: number;
  timezone: string;
  job_id?: string;
  mode?: string;
  next_run_time?: string | null;
  next_date_preview?: string;
  schedule?: string;
};

export async function schedulerCartaoApi() {
  return request<SchedulerCartaoStatus>("/api/scheduler/cartao");
}

export async function setSchedulerCartaoApi(enabled: boolean) {
  return request<SchedulerCartaoStatus>("/api/scheduler/cartao", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}
