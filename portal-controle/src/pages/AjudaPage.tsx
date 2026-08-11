import { useAuth } from "../auth/AuthContext";

type HelpBlock = {
  id: string;
  title: string;
  body: string[];
  adminOnly?: boolean;
};

const BLOCKS: HelpBlock[] = [
  {
    id: "geral",
    title: "O que este portal faz?",
    body: [
      "Ele acompanha as vendas da Stone (cartão e PIX) que são enviadas para o Tasy.",
      "O fluxo automático busca o dia anterior (D-1). Você usa o portal para consultar, corrigir cadastros e tratar erros.",
      "Não é necessário extrair manualmente no dia a dia — isso fica com o administrador, se precisar.",
    ],
  },
  {
    id: "dashboard",
    title: "Dashboard",
    body: [
      "Mostra totais do staging: quantos registros estão integrados, em retry, DLQ ou sem tesouraria.",
      "Também resume quantas mensagens estão nas filas do RabbitMQ.",
      "Perfil Financeiro: consulta e cadastros (maquininhas/mapeamentos). O botão de extrair o dia é só admin.",
    ],
  },
  {
    id: "integracoes",
    title: "Integrações",
    body: [
      "Lista os registros gravados no Postgres (staging).",
      "Ao abrir, carrega só o dia de ontem (paginado). Amplie as datas nos filtros para ver mais.",
      "Use os filtros: data, caixa, status, tipo (crédito/débito/PIX), bandeira, ID Stone, etc.",
      "Status comuns: Integrado (ok), Retry, DLQ, Sem Tesouraria.",
      "Serve para conferir se um movimento do dia entrou e com qual valor/caixa.",
    ],
  },
  {
    id: "erros",
    title: "Erros / Sem Tesouraria",
    body: [
      "Foco nos registros que falharam ou ficaram sem vínculo de tesouraria.",
      "Causas frequentes: maquininha (serial) não cadastrada, caixa incorreto, mapeamento de bandeira/tipo faltando.",
      "Você pode editar serial/caixa e reprocessar o registro (ou vários selecionados).",
      "Isso republica só aquele registro na fila — não dispara nova busca na Stone.",
    ],
  },
  {
    id: "maquininhas",
    title: "Maquininhas",
    body: [
      "Cadastro do serial da máquina Stone ligado a um caixa do Tasy e à transação financeira.",
      "Se o serial não existir aqui, a integração costuma cair em erro ou Sem Tesouraria.",
      "Quando uma máquina nova entrar em uso, cadastre o serial assim que possível.",
    ],
  },
  {
    id: "mapeamentos",
    title: "Mapeamentos",
    body: [
      "Relaciona tipo/bandeira da Stone com o código de cartão/bandeira no Tasy.",
      "PIX e alguns débitos podem usar mapeamento sem bandeira (conforme regras do hospital).",
      "Só altere se souber o código correto no Tasy — mapeamento errado gera lançamento incorreto.",
    ],
  },
  {
    id: "filas",
    title: "Filas",
    body: [
      "Mostra o estado das filas RabbitMQ (cartão e PIX, inclusive retry e DLQ).",
      "Ready alto por muito tempo pode indicar consumer parado ou erro em massa.",
      "Normalmente o consumer processa sozinho; use esta tela para monitoramento.",
    ],
  },
  {
    id: "usuarios",
    title: "Usuários (somente admin)",
    adminOnly: true,
    body: [
      "Crie usuários do perfil Financeiro (login, nome e senha).",
      "Financeiro vê Dashboard, Integrações, Erros, Maquininhas, Mapeamentos, Filas e Ajuda.",
      "Financeiro não vê Scheduler, Auditoria, Logs nem o botão de extrair o dia.",
      "Para remover acesso, desative o usuário (soft-delete) — não apaga o histórico.",
    ],
  },
  {
    id: "scheduler",
    title: "Scheduler (somente admin)",
    adminOnly: true,
    body: [
      "Liga/desliga a rotina automática D-1 de cartão e de PIX.",
      "Cartão: baixa o extrato de ontem e publica na fila.",
      "PIX: solicita o extrato de ontem; a Stone envia o arquivo no webhook.",
      "Horários vêm do .env na VM (CARTAO_CRON_* e PIX_CRON_*).",
    ],
  },
  {
    id: "fluxo",
    title: "Passo a passo do dia a dia (Financeiro)",
    body: [
      "1) Abra Integrações e filtre o dia / caixa / PIX ou cartão.",
      "2) Se faltar movimento, confira Erros / Sem Tesouraria.",
      "3) Se o erro for serial ou caixa, ajuste em Maquininhas (ou edite no erro) e reprocesse o registro.",
      "4) Se for tipo/bandeira, revise Mapeamentos com apoio do admin/TI.",
      "5) Confira no Tasy o lançamento quando o status estiver Integrado.",
    ],
  },
];

export function AjudaPage() {
  const { user } = useAuth();
  const visible = BLOCKS.filter((b) => !b.adminOnly || user?.admin);

  return (
    <div>
      <header className="page-head">
        <h1>Ajuda</h1>
        <p className="muted">
          Tutorial rápido do portal Stone → Tasy
          {user?.admin ? " (visão admin)" : " (perfil Financeiro)"}
        </p>
      </header>

      <div className="callout">
        Dúvida no dia a dia: comece por <strong>Integrações</strong> e{" "}
        <strong>Erros / Sem Tesouraria</strong>. Extração manual e Scheduler ficam com o admin.
      </div>

      <div className="help-list">
        {visible.map((block) => (
          <details key={block.id} className="help-item" open={block.id === "geral" || block.id === "fluxo"}>
            <summary>{block.title}</summary>
            <ul>
              {block.body.map((line) => (
                <li key={line}>{line}</li>
              ))}
            </ul>
          </details>
        ))}
      </div>
    </div>
  );
}
