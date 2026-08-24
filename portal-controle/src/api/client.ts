import type { FilaInfo, Filtros, PortalUsuario, Registro, ResumoTotais, User } from "../types";

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

export async function usuariosApi() {
  return request<{ items: PortalUsuario[] }>("/api/auth/usuarios");
}

export async function criarUsuarioApi(body: {
  login: string;
  nome: string;
  password: string;
  admin?: boolean;
}) {
  return request<PortalUsuario>("/api/auth/usuarios", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function atualizarUsuarioApi(
  id: number,
  body: {
    nome?: string;
    password?: string;
    admin?: boolean;
    ativo?: boolean;
  },
) {
  return request<PortalUsuario>(`/api/auth/usuarios/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export async function desativarUsuarioApi(id: number) {
  return request<PortalUsuario>(`/api/auth/usuarios/${id}`, {
    method: "DELETE",
  });
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
    stone_message?: string | null;
    raw_bytes?: number | null;
    parse_stats?: Record<string, unknown>;
    totais_avisos?: string[];
    pix?: {
      reference_date?: string;
      status?: string | null;
      message?: string | null;
      error?: string | null;
      published_from_body?: number;
    };
  }>("/api/reprocessar/dia", {
    method: "POST",
    body: JSON.stringify({ date }),
  });
}

export async function fecharRecebimentosAbertosApi(date: string) {
  const q = new URLSearchParams({ date });
  return request<{
    ok: boolean;
    date: string;
    encontrados: number;
    fechados: number;
    falhas: number;
    itens?: Array<{
      nr_seq_caixa_rec: number;
      nr_seq_caixa?: number | null;
      ok: boolean;
      vl_troco?: number;
      erro?: string;
    }>;
  }>(`/api/tesouraria/fechar-recebimentos-abertos?${q}`, {
    method: "POST",
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
  return request<{
    items: AcaoLog[];
    total?: number;
    limit?: number;
    offset?: number;
  }>(`/api/audit/logs?limit=${limit}`);
}

export type AuditoriaFiltros = {
  limit?: number;
  offset?: number;
  acao?: string;
  login?: string;
  id_stone?: string;
  data_de?: string;
  data_ate?: string;
};

export async function auditoriaLogsApi(filtros: AuditoriaFiltros = {}) {
  const q = new URLSearchParams();
  q.set("limit", String(filtros.limit ?? 50));
  q.set("offset", String(filtros.offset ?? 0));
  if (filtros.acao) q.set("acao", filtros.acao);
  if (filtros.login) q.set("login", filtros.login);
  if (filtros.id_stone) q.set("id_stone", filtros.id_stone);
  if (filtros.data_de) q.set("data_de", filtros.data_de);
  if (filtros.data_ate) q.set("data_ate", filtros.data_ate);
  return request<{
    items: AcaoLog[];
    total: number;
    limit: number;
    offset: number;
  }>(`/api/audit/logs?${q.toString()}`);
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
  last_run_at?: string | null;
  last_ok?: boolean | null;
  last_ok_at?: string | null;
  last_error_at?: string | null;
  last_error?: string | null;
  last_reference_date?: string | null;
  last_published?: number | null;
  last_slot?: string | null;
  last_status?: string | null;
};

export type SchedulerStatus = SchedulerCartaoStatus & {
  flow?: string;
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

export async function schedulerPixApi() {
  return request<SchedulerStatus>("/api/scheduler/pix");
}

export async function setSchedulerPixApi(enabled: boolean) {
  return request<SchedulerStatus>("/api/scheduler/pix", {
    method: "POST",
    body: JSON.stringify({ enabled }),
  });
}

export type PurgePreviewItem = {
  nr_sequencia: number;
  id_stone: string;
  cd_caixa: number | null;
  cd_status: number;
  vl_transacao: number;
  dt_movimentacao: string;
  oracle: {
    nr_seq_movto: number;
    nr_seq_caixa_rec: number | null;
    vl_transacao: number;
    dt_transacao: string | null;
    ja_fechado: boolean;
    qtd_docs: number;
    qtd_parcelas: number;
  } | null;
  can_purge: boolean;
  blocked_reason: string | null;
};

export type PurgePreviewResponse = {
  confirm_token: string;
  confirm_phrase_required: string;
  expires_in_seconds: number;
  nm_usuario: string;
  allow_fechado: boolean;
  totais: {
    total: number;
    elegiveis: number;
    bloqueados: number;
    sem_oracle: number;
  };
  items: PurgePreviewItem[];
  avisos: string[];
};

export type PurgeResultItem = {
  nr_sequencia: number;
  id_stone: string;
  ok: boolean;
  deleted?: Record<string, number>;
  blocked_reason?: string | null;
  staging_status?: number;
};

export type PurgeBody = {
  nm_usuario: string;
  nr_sequencias?: number[];
  id_stones?: string[];
  cd_caixa?: number | null;
  data_de?: string | null;
  data_ate?: string | null;
  id_stone?: string | null;
  allow_fechado?: boolean;
};

export async function purgePreviewApi(body: PurgeBody) {
  return request<PurgePreviewResponse>("/api/purge/preview", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export async function purgeConfirmApi(
  body: PurgeBody & { confirm_token: string; confirm_phrase: string },
) {
  return request<{
    nm_usuario: string;
    allow_fechado: boolean;
    ok: number;
    falhas: number;
    resultados: PurgeResultItem[];
  }>("/api/purge/confirm", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
