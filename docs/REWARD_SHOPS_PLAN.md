# Plano técnico da loja de recompensas

A Fase 6 propõe duas lojas que usam o saldo de moedas existente em
`ChildProfile.balance` e os lançamentos de `LedgerEntry`. A loja real
evolui o catálogo e o fluxo de aprovação atuais. A loja virtual entrega
itens cosméticos ao perfil por meio das concessões da progressão RPG.

## Loja real

Reaproveitar `Reward` para o catálogo e `RewardRequest` para o pedido.
Hoje o pedido registra o título e o custo em moedas, e o débito ocorre
na aprovação. Recusar ou cancelar um pedido pendente encerra a
solicitação sem débito. A proposta é manter esse ciclo como padrão.
[Modelos existentes](../economy/models.py) · [Fluxo de resgate](../economy/services.py)

- Oferecer aos responsáveis uma opção para ativar ou desativar a loja
  real para toda a família. Ao desativar, ocultar o catálogo real no
  painel infantil e bloquear novos pedidos no servidor, inclusive
  resgates com aprovação dispensada. A loja virtual continua disponível.
  Os pedidos já abertos continuam visíveis e podem ser aprovados,
  recusados ou cancelados pelos fluxos existentes. Entregas, estornos e
  histórico permanecem acessíveis. Reativar recupera o catálogo e suas
  configurações. A atualização mantém a loja real ativa por padrão nas
  instalações existentes.
- Acrescentar estoque opcional, disponibilidade por período, limites
  diário, semanal e mensal e intervalo mínimo. Proposta de aplicar
  esses limites por criança e recompensa, com estoque compartilhado
  pela família. Usar a data local do resgate efetivado, semana
  iniciando na segunda e mês civil no fuso familiar.
- Manter aprovação exigida por padrão. Se o responsável a dispensar
  para uma recompensa, criar e efetivar o pedido na mesma transação.
  Preservar a fila parental e a autorização por criança.
- Registrar no pedido o preço ofertado em moedas e o custo financeiro
  opcional. Usar centavos inteiros e moeda familiar definida
  explicitamente. O orçamento mensal controla o custo comprometido
  pela família, incluindo resgates aprovados que aguardam entrega.
  Esse custo é um registro parental, sem pagamento no aplicativo.
- Validar elegibilidade no envio e novamente na efetivação. Pedidos
  pendentes não reservam moedas, estoque, cota ou orçamento. Em uma
  transação, reivindicar a transição do pedido, conferir estoque,
  limites, orçamento e piso individual, debitar moedas, consumir
  estoque e registrar o compromisso financeiro. O pedido conserva
  seus preços registrados. Se faltar saldo, estoque ou orçamento,
  informar o motivo e manter o pedido pendente para decisão.
- Registrar entrega separadamente da aprovação. Se um responsável
  cancelar um resgate efetivado e ainda não entregue, devolver as
  moedas uma única vez com lançamento compensatório e liberar o
  estoque e o orçamento comprometido. Proposta de manter a cota de
  frequência consumida para evitar ciclos de cancelamento e recompra.
  Resgates entregues exigem tratamento administrativo explícito.
- Preservar o catálogo, os pedidos pendentes e o histórico na
  atualização. Novos limites, estoque e orçamento começam
  desativados para recompensas legadas. Os pedidos pendentes
  conservam o preço registrado e o fluxo de aprovação. Definir
  explicitamente antes da implementação se uma regra recém-ativada
  deve incidir sobre esses pedidos. A proposta é preservar a regra
  anterior para os pedidos que já estavam em andamento.

## Loja virtual

Reaproveitar `LevelUnlock` como catálogo de itens e
`UnlockGrant` como registro de propriedade. Acrescentar uma oferta
com preço em moedas para itens cosméticos selecionados, com origem
e referência de aquisição no registro de propriedade. Títulos e
cosméticos da progressão continuam concedidos pelas regras da Fase 5.
O catálogo deve distinguir itens ganhos por nível e itens compráveis.
A Fase 7 consome essas concessões para exibir inventário e equipar itens.
[Progressão RPG](PROGRESSION_PLAN.md)

- Começar com itens individuais e preço visível. Roupas, acessórios,
  equipamentos, decorações, temas e mascotes entram como categorias
  cosméticas. A Fase 6 registra a aquisição. Equipar e interagir com
  itens seguem nas fases correspondentes.
- A compra é imediata, usando moedas disponíveis e conferindo a
  propriedade por criança. Proposta de exigir saldo positivo suficiente
  para cosméticos, preservando o crédito individual já usado pelos
  resgates reais. Configurações que bloqueiam compras ou resgates
  precisam ter alcance explícito no painel parental.
- Em uma transação, verificar oferta ativa, preço confirmado, saldo
  e propriedade, debitar pelo serviço de extrato e conceder o item.
  Usar uma chave de idempotência da compra e a unicidade de
  `UnlockGrant` por criança e item. Um reenvio retorna o comprovante.
  Uma disputa com um desbloqueio por nível deve terminar com uma única
  propriedade. Se o item já tiver sido concedido antes da compra,
  encerrar sem debitar. Proposta de não colocar o mesmo item nas duas
  modalidades na primeira versão.
- Arquivar uma oferta impede compras novas e preserva a propriedade.
  Um eventual estorno por erro deve ser explícito, vinculado ao
  lançamento original e tratado pelo fluxo de compra. Consequências
  e mudanças de nível não removem itens adquiridos. Compras e
  resgates não alteram XP, níveis ou habilidades.

## Histórico e retirada das raspadinhas

Manter o extrato existente e distinguir resgate real de compra
cosmética pelo tipo de lançamento e pela origem. Guardar o preço
aplicado, o estado final e a referência do pedido ou da aquisição.
As devoluções reaproveitam a compensação transacional. O estorno
genérico do extrato deve encaminhar ao fluxo de resgate quando
houver estoque, entrega ou orçamento para reconciliar.

As raspadinhas ainda têm rotas de compra e revelação e lançamentos
de compra vinculados no código. Tratar a remoção como etapa própria
do MVP antes de publicar a nova experiência. Bloquear compra,
revelação e lembretes, devolver uma única vez o valor registrado
dos bilhetes abertos e preservar os resolvidos. Encaminhar bilhetes
sem compra verificável para revisão administrativa.
[Regras econômicas](ECONOMY_PLAN.md) · [Fluxo de raspadinhas atual](../economy/lottery.py)

## Verificação

- Atualizar uma base representativa e conferir saldo, piso, extrato,
  pedidos pendentes e concessões existentes.
- Testar recusa sem débito, aprovação repetida, aprovação imediata,
  duas aprovações disputando o último item ou orçamento, cancelamento
  após aprovação e entrega concorrente com cancelamento.
- Desativar e reativar a loja real e conferir o bloqueio de novos pedidos
  no servidor, o tratamento dos pedidos existentes e o acesso à loja virtual.
- Testar compra virtual repetida, item já possuído, mudança de preço,
  saldo insuficiente e disputa entre compra e concessão.
- Testar viradas de dia, semana e mês em `America/Sao_Paulo`, além
  de autorização de responsáveis, cuidadores e crianças. A interface
  deve mostrar claramente o preço em moedas e o estado do resgate,
  sem ofertas aleatórias, pressão de compra ou pagamento pela criança.


## Entrega da Fase 6

A tela **Configurações → Lojas de recompensas** controla a disponibilidade
da loja real, o orçamento, as entregas e as ofertas cosméticas. Desativar
a loja real impede novos pedidos e mantém pedidos, entregas e histórico.
O catálogo e a fila de aprovação existentes foram reaproveitados.
A loja virtual usa o mesmo saldo de moedas, sem usar o crédito negativo,
e aceita somente itens destinados à compra. Comprar, arquivar ofertas e
reconciliar os desbloqueios por nível preservam a propriedade existente.

A migração `0041_reward_shops` conserva saldos, pisos, pedidos e
desbloqueios. Os pedidos que já estavam pendentes mantêm a regra e o
preço anteriores. Bilhetes abertos com compra verificável são estornados
uma vez. Bilhetes sem compra verificável aparecem na revisão parental.
Compra, revelação e lembretes das raspadinhas ficam indisponíveis.

O estorno de um resgate real aprovado e ainda sem entrega devolve as
moedas, libera o estoque e o orçamento e conserva a cota de frequência.
Resgates entregues exigem decisão administrativa separada. Estorno
de cosméticos e equipar itens ficaram fora da entrega da loja; a
propriedade adquirida permanece disponível para o inventário da Fase 7.

A suíte passou com 548 testes. A migração foi conferida em uma base
representativa, com pedido pendente, concessão existente e bilhetes
aberto e resolvido. Duas transações concorrentes disputando o último
item consumiram uma unidade. Dois reenvios concorrentes de uma compra
virtual produziram uma concessão e um débito. As telas foram conferidas
em Firefox a 390 e 810 pixels.
