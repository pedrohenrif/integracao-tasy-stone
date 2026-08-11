export type User = {
  id: number;
  login: string;
  nome: string;
  admin: boolean;
};

export type PortalUsuario = {
  id: number;
  login: string;
  nome: string;
  admin: boolean;
  ativo: boolean;
  dt_inclusao?: string | null;
  dt_ultimo_login?: string | null;
};

export type ResumoTotais = {
  total?: number;
  ok?: number;
  retry?: number;
  dlq?: number;
  sem_tesouraria?: number;
  pendente?: number;
  soma_valor?: number;
  soma_ok?: number;
};

export type Registro = {
  nr_sequencia: number;
  id_stone: string;
  nr_serie_maquininha: string;
  cd_caixa: number | null;
  ds_caixa: string | null;
  dt_movimentacao: string;
  cd_autorizacao: string | null;
  vl_transacao: number;
  cd_tipo_transacao: string | null;
  cd_bandeira: string | null;
  qt_parcelas: number;
  ie_internacional?: string | null;
  cd_status: number;
  ds_obs_processo: string | null;
  dt_atualizacao: string;
};

export type FilaInfo = {
  name: string;
  exists?: boolean;
  messages?: number | null;
  messages_ready?: number | null;
  messages_unacknowledged?: number | null;
  consumers?: number | null;
  state?: string;
  error?: string;
};

export type Filtros = {
  data_de?: string;
  data_ate?: string;
  cd_caixa?: string;
  cd_status?: string;
  tipo?: string;
  id_stone?: string;
  nr_serie?: string;
  autorizacao?: string;
  bandeira?: string;
  ie_internacional?: string;
  vl_min?: string;
  vl_max?: string;
  obs?: string;
  limit?: string;
  offset?: string;
};
