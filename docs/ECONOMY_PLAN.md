# Plano técnico da economia

Proposta para a Fase 2, com integração das missões na Fase 3. A unidade de
saldo passa a ser apresentada como moeda na proporção de **1 ponto para 1
moeda**. O XP começa em zero e possui histórico próprio. A progressão por
níveis, a loja real e as mudanças no ciclo de vida das missões seguem nos seus
respectivos marcos.

## Saldo e extrato existentes

- Continuar usando `ChildProfile.balance` como saldo disponível, `min_balance`
  como piso individual e `LedgerEntry` como extrato. Preservar valores,
  identificadores, datas, descrições, tipos e referências históricas. O valor
  de um custo, bônus ou recompensa legado continua valendo o mesmo em moedas.
- Usar migrações aditivas para metadados de lançamentos novos. Registrar saldo
  anterior e posterior, origem tipada, ator, justificativa quando aplicável e
  uma chave única da operação. No histórico antigo, o saldo anterior inferido
  é `balance_after - delta`. Exibir um campo histórico desconhecido como tal.
- Manter os tipos de lançamento legados. `source_id` sozinho não identifica
  uma operação. O catálogo pode aparecer mais de uma vez no extrato, um
  presente tem duas pontas e uma raspadinha pode ter compra e prêmio. A chave
  nova deve incorporar o tipo de evento e o identificador estável da origem.
- Reaproveitar `post_ledger_entry` como ponto de atualização do saldo e
  do extrato. Incluir o fluxo de presentes na revisão, pois hoje ele grava
  as duas pontas diretamente. Resgates legados, valores reservados em metas e
  custos em solicitações pendentes mantêm suas regras e referências.

## XP e crédito de uma ocorrência

O histórico de XP deve ter um registro por ocorrência premiada, com criança,
origem estável, quantidade concedida, instante e ator quando aplicável. O saldo
acumulado pode ser calculado a partir desse histórico no MVP. Preservar o
histórico de moedas integralmente e iniciar o XP em zero para todos, inclusive
perfis legados, é a proposta de migração. As conclusões antigas não registram
XP configurado e o extrato contém créditos de várias origens.

Na Fase 2, preparar o serviço transacional de crédito e seus invariantes.
Na Fase 3, ligar ao serviço as entradas de solicitação, atribuição e
lançamento direto. A ocorrência recebe sua identidade uma vez. Em uma
atribuição recorrente, a identidade distingue o dia ou execução da série.
Revisões e reenvios conservam a mesma identidade. O registro legado
`TaskCompletion` pode continuar indicando que uma tarefa foi feita no dia.
Hoje, uma atribuição e uma aprovação de pedido podem gerar créditos separados
mesmo quando compartilham o mesmo registro diário.

1. Fixar na ocorrência a exigência de aprovação e os valores configurados de XP
   e moedas. Ao migrar um pedido ou uma atribuição já pendente, preservar o
   valor em pontos que foi registrado. A proposta é concluir esses registros
   pelo fluxo legado, com o crédito integral previsto e sem XP retroativo.
2. Em uma única transação, reivindicar a mudança de estado, conferir o vínculo
   com a criança e a permissão do ator, aplicar os limites e gravar o resultado.
   Com aprovação exigida, o crédito ocorre na aprovação. Com dispensa, na
   conclusão. Recusa, revisão e cancelamento não geram lançamentos.
3. Persistir o valor configurado, o valor creditado e a razão de qualquer
   redução. Se o limite de moedas se esgotar, concluir a ocorrência e entregar
   o XP integral. Gravar o resultado da ocorrência mesmo quando não houver
   lançamento de moedas. A chave única do crédito e a transição condicional devem
   impedir duplicação mesmo quando o valor em moedas for zero. A repetição
   devolve o resultado persistido. Efeitos externos ocorrem após o commit.

## Limites e estornos

| Regra proposta | Aplicação |
| --- | --- |
| Ganhos diários | Contar moedas novas de missões, bônus e presentes de aniversário por criança e pela data local do crédito. Transferências entre saldos, devoluções e ajustes administrativos ficam fora dessa soma. |
| Teto de saldo | Limitar os créditos que criam moedas. Uma conta acima do teto conserva o saldo, pode gastar e volta a receber esses créditos quando houver espaço. Um presente entre crianças deve caber integralmente antes do débito. Devoluções e estornos de débitos podem ultrapassar o teto para restaurar valor já existente. |
| Piso individual | Usar zero em novas instalações e preservar os pisos legados. Resgate, penalidade e ajuste a débito precisam consultar o piso na transação. Se um saldo existente já estiver abaixo do piso, aceitar créditos e bloquear novos débitos. |
| Penalidade diária | Somar débitos manuais de penalidade no dia da família. Proposta de recusar um débito que exceda o limite disponível ou atravesse o piso e informar o máximo aplicável. XP permanece intacto. |
| Estorno | Criar lançamento compensatório com ator, motivo e referência ao original. Começar com estorno integral e único. Se a reversão de um crédito atravessar o piso, recusar e conservar os dois saldos. Estornar os dois lados de uma transferência juntos ou recusar toda a operação. Um estorno não reabre a cota diária de ganhos ou penalidades. |

Os limites de 50 moedas por dia, 500 de saldo e 10 em penalidades são os
valores sugeridos no roadmap. Proposta de ativá-los por padrão em novas
instalações e pedir que instalações existentes habilitem cada limite
explicitamente. Persistir a data local do lançamento para os novos limites,
usando o fuso familiar no momento do crédito ou débito. Em
`America/Sao_Paulo`, testar a virada entre 02:59 e 03:00 UTC em uma data com
deslocamento de três horas. Trocar o fuso afeta lançamentos futuros.

## Migração e critérios de aceite

1. Fazer backup e verificar restauração em uma instalação isolada. Na base de
   teste, guardar por criança o saldo, piso, quantidade de lançamentos, último
   saldo registrado e referências de pedidos e metas. Se o saldo e o extrato
   já divergirem, registrar a divergência para revisão do responsável.
2. Aplicar as migrações aditivas. Confirmar que saldos positivos e negativos,
   pisos, extratos e pedidos pendentes permanecem íntegros. Testar uma base
   nova e uma base representativa de uma atualização.
3. Exercitar créditos concorrentes, falha entre gravações, reenvio, saldo
   acima do teto ou abaixo do piso, crédito parcial, crédito zero e estorno
   repetido. Simular aprovação e conclusão concorrentes em conexões SQLite
   distintas. Conferir que cada ocorrência produz no máximo um crédito de
   moeda e um de XP, com estado, saldo e histórico consistentes.
4. Manter a retirada das raspadinhas como operação separada do MVP. Bloquear
   compras e revelações antes de devolver uma vez o valor histórico da compra
   dos bilhetes abertos. Preservar bilhetes resolvidos. Bilhetes sem lançamento
   de compra confiável devem ir para revisão administrativa. Testar repetição
   da operação e concorrência com a última revelação.

## Situação da implementação

A migração `0037` mantém as linhas legadas e deixa os limites nulos nas
instalações existentes. Em novas instalações, o assistente e o comando
de configuração adotam 50, 500 e 10 como valores iniciais e piso zero.
Os limites podem ser alterados ou desativados em **Configurações → Limites
de moedas**. O painel infantil exibe o XP acumulado, inicialmente zero.

O serviço `credit_occurrence` está disponível para a integração das missões
na Fase 3. Ele registra também créditos de zero moeda para manter o resultado
auditável. A Fase 2 mantém as aprovações e recorrências existentes. Os
lançamentos legados recém-processados registram o tipo de origem e os
metadados econômicos. Os novos formulários de presente, ajuste e
penalidades em lote enviam uma chave de operação para deduplicar reenvios.

O histórico permite estorno por um responsável administrador. Movimentações
de poupança permanecem vinculadas ao fluxo de metas. Eventuais devoluções
de raspadinhas pertencem à etapa de retirada da mecânica. O botão de
estorno cobre tarefas, penalidades, resgates legados, ajustes, presentes e
bônus de aniversário.

A suíte passou com 509 testes. A atualização de uma base representativa de
`0036` para `0037` preservou saldos negativos e acima do teto sugerido,
pisos, extrato e recompensas pendentes. Uma verificação com dois processos
SQLite confirmou um único crédito ao repetir a mesma ocorrência.

[Modelos atuais](DATABASE.md) · [Roadmap](../ROADMAP.md#fase-2--economia-do-jogo)
