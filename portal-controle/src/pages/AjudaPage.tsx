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
      "Acompanha as vendas Stone (cartão e PIX) que a integração grava no Tasy.",
      "O job automático busca o dia anterior (D-1): PIX via webhook e cartão via extrato. No dia a dia o Financeiro consulta, corrige cadastro e trata erro — não precisa extrair na mão.",
      "Cartão e PIX nunca se misturam na fila nem no recebimento do Tasy: cada caixa/dia pode ter um recebimento de cartão e outro de PIX.",
      "Só máquina ativa (status A no cadastro) entra na extração e na integração. Inative no portal para parar de importar.",
    ],
  },
  {
    id: "status",
    title: "Status das transações",
    body: [
      "1 Pendente — chegou no staging, ainda não processou.",
      "2 Processando — o consumer está inserindo no Tasy.",
      "5 Integrado — ok no Tasy (ou já existia: a mesma id_stone não duplica).",
      "6 Retry — falha transitória (rede/Oracle); a fila tenta de novo.",
      "7 DLQ — esgotou tentativas. Corrija cadastro/serial/mapeamento e reprocesse.",
      "8 Sem tesouraria — legado: movto no Tasy sem caixa diário (policy insert).",
      "9 Reintegrar — a confirmação no Tasy falhou; o Oracle foi limpo para gravar de novo.",
      "10 Ignorado — máquina inativa ou não cadastrada. Não grava no Tasy.",
      "11 Só movto — caixa marcado como só movimento (ex. Telemarketing): grava MOVTO_CARTAO_CR sem saldo/recebimento do dia. Aparece em Administração de Cartão se IE_LIB_CAIXA = S.",
      "O card “Soma OK” do Dashboard/Integrações soma só o status 5. Só movto (11) pode estar no Tasy e não entrar nessa soma.",
    ],
  },
  {
    id: "dashboard",
    title: "Dashboard",
    body: [
      "Mostra totais do staging (integrado, retry, DLQ, sem tesouraria, só movto) e mensagens prontas nas filas.",
      "Financeiro: consulta e atalho para as telas. O botão de extrair o dia é só admin.",
      "Extrair cartão + PIX do dia: busca de novo o arquivo na Stone e publica na fila. Integrados (5) não são regravados no Tasy.",
      "Isso não é o mesmo que Reprocessar pendentes/erros: extração puxa o arquivo; Reprocessar só reenfileira o que já está no staging com erro.",
      "Retroativo (D-2 ou mais): a Stone em geral não reenvia PIX. Admin importa o CSV do dia, espera a fila PIX drenar, depois extrai só o cartão. Não use o botão amarelo nesses dias.",
      "Hoje a operação não confirma o recebimento no Tasy. Os lançamentos ficam abertos para o time conferir. Se um dia confirmarem, cartão e PIX já vão em recebimentos separados (evita o limite de 4 mil caracteres do comprovante em caixa grande, ex. Churrasco).",
    ],
  },
  {
    id: "integracoes",
    title: "Integrações",
    body: [
      "Lista o que está no Postgres (staging) — o que a integração tentou gravar no Tasy.",
      "Ao abrir, filtra o dia de ontem. Amplie as datas para ver mais; a lista é paginada.",
      "Marque tipos, status, bandeiras e caixas. Sem marca = todos.",
      "Filtros: data, caixa, status, tipo (crédito/débito/PIX), bandeira, serial, ID Stone, valor, observação de erro.",
      "Use para conferir se o movimento do dia entrou, com qual valor e em qual caixa.",
    ],
  },
  {
    id: "movimentos",
    title: "Movimentos Stone",
    body: [
      "Lista o que veio no arquivo da Stone (CSV PIX e XML de cartão), mesmo o que não foi integrado.",
      "Publicado = sim: entrou na fila. Não: máquina inativa/não cadastrada, status diferente de paid, etc.",
      "Se o valor existe aqui e não em Integrações, o arquivo chegou e a integração falhou ou ignorou — vá em Reprocessar ou Maquininhas.",
      "Se não existe nem aqui, a extração não puxou (máquina inativa, dia errado, ou PIX ainda não veio no webhook).",
    ],
  },
  {
    id: "erros",
    title: "Reprocessar",
    body: [
      "Tela para tratar o que falhou: DLQ, retry, pendente, reintegrar, sem tesouraria, ignorado ou só movto.",
      "Causas frequentes: serial não cadastrado ou inativo, caixa/TF errados, mapeamento de bandeira/tipo faltando.",
      "Por linha: edita serial/caixa daquele registro e reenfileira (não busca de novo na Stone).",
      "Selecionados: republica o lote marcado. Integrado (5) é ignorado.",
      "Pendentes/erros do dia: reenfileira só status 1, 2, 6, 7 e 9 da data. Se o filtro Serial estiver preenchido, vale só esse terminal. Não toca em Integrado (5) nem Só movto (11).",
      "Para puxar o arquivo de novo na Stone, o admin usa o Dashboard (Extrair cartão + PIX).",
    ],
  },
  {
    id: "maquininhas",
    title: "Maquininhas",
    body: [
      "Serial Stone ligado a um caixa do Tasy e à transação financeira (TF). Só ativas (A) são extraídas.",
      "Máquina nova: cadastre o serial no caixa certo assim que entrar em uso. Serial já cadastrado não duplica — o portal avisa e abre a edição.",
      "Inative (status I) para parar de importar, sem lista no .env.",
      "Só movimento: marque no caixa (não na máquina). Usado em Telemarketing, quando há várias TF e não se abre caixa diário. O Tasy recebe o movto; a TF da máquina pode ficar em branco.",
      "O serial também grava em MOVTO_CARTAO_CR.DS_COMPROVANTE nos inserts novos (além da observação).",
    ],
  },
  {
    id: "mapeamentos",
    title: "Mapeamentos",
    body: [
      "Liga tipo/bandeira da Stone ao código de cartão no Tasy.",
      "PIX e alguns débitos podem usar mapeamento sem bandeira.",
      "Débito pré-pago da Stone entra no Tasy como débito. Crédito pré-pago continua nas bandeiras 25/27/28.",
      "Mapeamento errado gera lançamento na bandeira/tipo errados. Só altere com o código certo do Tasy.",
    ],
  },
  {
    id: "tasy",
    title: "Onde conferir no Tasy",
    body: [
      "Administração de Cartão: movimentos com IE_LIB_CAIXA = S. Só movto (Telemarketing) também aparece aí.",
      "Tesouraria / caixa do dia: recebimento Stone aberto (nm_usuario stone). Cartão e PIX do mesmo caixa vêm em dois recebimentos (Stone vs Stone PIX).",
      "O ID Stone vai no começo da observação do movimento (o Tasy corta o fim do texto). Serial também está no comprovante, nos inserts novos.",
      "A mesma id_stone não gera segundo movimento. Reprocessar um dia já integrado é seguro.",
    ],
  },
  {
    id: "filas",
    title: "Filas",
    body: [
      "Estado do RabbitMQ: cartão e PIX, inclusive retry e DLQ.",
      "Ready alto por muito tempo: consumer parado, Oracle fora ou erro em massa.",
      "O consumer processa sozinho. Esta tela é monitoramento.",
    ],
  },
  {
    id: "usuarios",
    title: "Usuários (somente admin)",
    adminOnly: true,
    body: [
      "Crie usuários Financeiro (login, nome e senha).",
      "Financeiro vê Dashboard, Integrações, Movimentos Stone, Reprocessar, Maquininhas, Mapeamentos, Filas e Ajuda.",
      "Financeiro não vê Scheduler, Auditoria, Purge, Logs de acesso nem o botão de extrair o dia.",
      "Para remover acesso, desative o usuário — não apaga o histórico.",
    ],
  },
  {
    id: "scheduler",
    title: "Scheduler (somente admin)",
    adminOnly: true,
    body: [
      "Liga/desliga a rotina automática D-1 de cartão e de PIX.",
      "Cartão: baixa o extrato de ontem e publica na fila.",
      "PIX: solicita o extrato de ontem; a Stone envia o arquivo no webhook público.",
      "Horários vêm do .env na VM (CARTAO_CRON_* e PIX_CRON_*).",
      "A tela mostra a última execução (OK/ERRO). Falhas também entram na Auditoria (login sistema), se PORTAL_INTERNAL_TOKEN estiver nos dois .env.",
    ],
  },
  {
    id: "auditoria",
    title: "Auditoria (somente admin)",
    adminOnly: true,
    body: [
      "Ações do portal e do sistema: reprocesso, extração, cadastros, usuários, purge e jobs.",
      "Filtros: ação, login, ID Stone, datas. Login de usuários continua em Logs de acesso.",
    ],
  },
  {
    id: "purge",
    title: "Purge Stone (somente admin)",
    adminOnly: true,
    body: [
      "Apaga no Tasy só o que a integração criou (usuário Oracle + ID Stone), sem tocar no caixa/saldo diário.",
      "Sempre faça Preview. Confirme digitando EXCLUIR.",
      "Recebimentos já confirmados (dt_fechamento) ficam bloqueados salvo o checkbox explícito.",
      "Depois o staging volta para pendente com obs PURGED_BY_ADMIN, para reintegrar se precisar.",
    ],
  },
  {
    id: "fluxo",
    title: "Passo a passo do dia a dia (Financeiro)",
    body: [
      "1) Integrações: filtre o dia e o caixa. Confira quantidade e soma.",
      "2) Se faltar valor, abra Movimentos Stone do mesmo dia/serial. Está no arquivo e não no staging? Vá em Reprocessar.",
      "3) Erro de serial/caixa: ajuste em Maquininhas (ou edite na linha do erro) e reprocesse o registro. Não use “pendentes do dia” achando que o filtro da tabela limita a extração Stone — aquele botão só reenfileira erro.",
      "4) Erro de tipo/bandeira: revise Mapeamentos com o admin.",
      "5) Status Integrado (5): confira Administração de Cartão. Só movto (11): a mesma tela, se o caixa estiver marcado como só movimento.",
      "6) Telemarketing e máquinas sem caixa diário: cadastre no caixa certo e marque só movimento no caixa, não “desligue” a máquina.",
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
          Como usar o portal Stone → Tasy
          {user?.admin ? " (visão admin)" : " (perfil Financeiro)"}
        </p>
      </header>

      <div className="callout">
        Dúvida no dia a dia: <strong>Integrações</strong> (o que gravamos),{" "}
        <strong>Movimentos Stone</strong> (o que veio no arquivo) e{" "}
        <strong>Reprocessar</strong> (corrigir erro). Extração manual e Scheduler ficam
        com o admin.
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
