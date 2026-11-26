# Plano técnico de missões e rotinas

A Fase 3 pode reaproveitar o catálogo, as atribuições, os agendamentos e a
revisão parental do KinKudos. A mudança central é introduzir uma ocorrência
com identidade própria e fazer do serviço de crédito da Fase 2 a única
origem de XP e moedas das novas missões.

## Onde os fluxos se encontram hoje

| Entrada atual | Comportamento | Destino proposto |
| --- | --- | --- |
| Pedido da criança | `TaskClaim` guarda tarefa, nota, evidência e valor. Créditos usam `task-claim:<id>` quando aprovados. | Usar o pedido para evidência e revisão, vinculado à ocorrência canônica. |
| Atribuição manual ou agendada | `AssignedTaskBatch` agrupa itens e `AssignedTask` guarda valores da atribuição. A conclusão usa `assigned-task:<id>` e credita na hora. | Manter lotes e agendamentos. Encaminhar o item vinculado para conclusão ou aprovação conforme a configuração da ocorrência. |
| Lançamento direto | O responsável credita pelo catálogo e o serviço registra criança, tarefa e dia. | O adulto autorizado seleciona a ocorrência e registra a conclusão com aprovação explícita na mesma ação. |
| Registro diário | `TaskCompletion` indica que uma tarefa de catálogo foi feita no dia. | Preservar para histórico e compatibilidade. Usar a identidade da ocorrência para decidir o crédito. |

O código atual permite aprovar um pedido após uma atribuição já ter recebido
moedas para a mesma tarefa. Um teste documenta esse comportamento. As chaves
existentes deduplicam dentro de cada fluxo, e dois fluxos diferentes podem
representar o mesmo trabalho. A nova regra vale para ocorrências da Fase 3.
[Serviços atuais](../economy/services.py) · [Testes de atribuição](../economy/tests/test_assigned_tasks.py)

## Modelo e identidade

- **Modelo da missão.** Estender `Task` com XP, exigência de aprovação
  marcada por padrão, descrição da atividade e configuração de rotina.
  Reutilizar o valor de recompensa como moedas e preservar nome, ícone e
  estado de ativação. Missões atribuídas avulsas continuam possíveis.
- **Ocorrência.** Uma linha por criança e execução, com identificador gerado
  pelo servidor, estado e data local de referência. Guardar uma cópia de
  título, instrução, checklist, XP, moedas e regra de aprovação quando a
  ocorrência ficar disponível. O bônus de evidência é definido no envio
  quando aplicável e registrado como parte do valor solicitado em moedas.
- **Rotina.** Reusar `AssignmentPreset` e seus itens para materializar
  ocorrências. A execução agendada deve ter unicidade no banco por preset e
  janela local. Cada item da rotina tem uma ocorrência por execução.
- **Seleção.** Envio, atribuição e lançamento direto devem localizar a mesma
  ocorrência quando representam a mesma atividade. A tela pode enviar seu
  identificador, mas o servidor resolve a origem e valida a criança.
  Para rotas que recebem apenas a tarefa, usar a ocorrência padrão do dia.
  Atribuições de catálogo normalmente se ligam a ela. Repetições explícitas
  usam o link específico no painel infantil ou o pedido correspondente na
  fila de aprovação.
- **Trabalho repetido.** Para tarefas espontâneas, oferecer uma ocorrência
  padrão por criança, tarefa e dia local. Uma repetição legítima no mesmo
  dia deve ser uma nova ocorrência criada explicitamente, com identidade
  própria. Cliques repetidos, revisões e reenvios conservam o mesmo ID.
  A opção **Adicionar outra ocorrência** fica no diálogo de tarefas do
  responsável, depois que a primeira ocorrência existir. Ela usa um token
  próprio e abre uma entrada separada no painel infantil.

## Aprovação e liquidação

| Ação | Transição |
| --- | --- |
| Começar | De disponível para em andamento. |
| Concluir com aprovação exigida | De disponível ou em andamento para aguardando aprovação. Preservar o checklist e exibir o estado imediatamente. |
| Concluir sem aprovação | De disponível ou em andamento para concluída, com crédito. |
| Aprovar | De aguardando aprovação para concluída, com crédito. |
| Pedir revisão e reenviar | De aguardando aprovação para em revisão. Exibir o que falta, manter o progresso e reenviar a mesma ocorrência para aprovação. |
| Recusar, cancelar ou pular | Encerrar sem crédito nem penalidade automática. Estados terminais exigem uma nova ocorrência para um trabalho efetivamente novo. |

O serviço de transição deve validar estado, criança, prazo e autorização do
ator no servidor. A criança pode atualizar as próprias etapas, concluir
uma missão e pedir ajuda. Responsáveis podem configurar e aprovar. Cuidadores
mantêm somente as ações já autorizadas para as crianças vinculadas.

Para liquidar, abrir uma transação SQLite de escrita, efetuar a transição
condicional e chamar `credit_occurrence` com uma chave derivada do ID
canônico, como `mission:<id>`. Gravar XP e moedas usando os valores da
ocorrência. A restrição única em `OccurrenceCredit` e a chave do extrato
protegem o crédito mesmo quando outra entrada tenta concluir o mesmo
trabalho. Uma falha desfaz estado e lançamentos. Repetições retornam o
resultado persistido. Notificações e efeitos visuais devem ocorrer após
o commit e somente quando houver uma transição nova.

A data da ocorrência determina disponibilidade e recorrência. A data local
do crédito, inclusive quando o responsável aprova no dia seguinte, determina
a cota diária de moedas. Se houver limite, o recibo mostra o valor efetivamente
creditado e conserva o XP integral. [Plano da economia](ECONOMY_PLAN.md)

## Rotinas e experiência infantil

1. Entregar primeiro o fluxo completo com tarefa do catálogo ou avulsa,
   aprovação exigida ou dispensada, revisão, checklist e recibo.
2. Migrar os presets existentes de recorrência diária, semanal, por dias
   selecionados e de fim de semana. Usar um único instante de referência
   convertido ao fuso familiar por execução do agendador. Retentativas e
   reinícios não podem criar outro lote para a mesma janela. Manter revisão
   parental disponível após o prazo quando a criança enviou no horário.
3. Acrescentar recorrência mensal e por evento, grupos de rotina, horário
   sugerido, prazo e pausa de férias. Proposta mensal para dias 29 a 31 em
   meses curtos: usar o último dia, com prévia no formulário. Pausar a
   geração durante férias e retomar sem gerar dívida nem ocorrências
   retroativas.
4. Acrescentar modo de foco com uma etapa visível por vez, ajuda sem mudar
   o estado, temporizador e estímulos opcionais. Separar cadência de
   classificação narrativa. Categoria, dificuldade e etiquetas principal,
   secundária e especial podem evoluir sem alterar a chave de crédito.
   Dependências exigem rejeição de ciclos. Missões cooperativas precisam de
   uma ocorrência por criança ou uma regra explícita de crédito individual.

## Compatibilidade e aceite

- Adicionar esquema e vínculos compatíveis. Preservar IDs, extrato, registros
  de conclusão, evidências, atribuições, presets e rotas legadas. Evitar uma
  migração que infira equivalência entre pedido e atribuição pelo título.
- Manter os pedidos e itens já pendentes no fluxo anterior, com o valor
  prometido, as regras aplicáveis e sem XP retroativo. Enquanto uma pendência
  antiga do mesmo trabalho estiver ativa, as entradas novas devem encaminhar
  ao registro existente ou pedir ao responsável para encerrá-lo. A proteção
  precisa valer para as três entradas, inclusive em concorrência.
- Testar atualização de base com pedido em revisão e atribuição pendente.
  Exercitar envio repetido, cruzamento entre as três rotas, aprovação
  concorrente com cancelamento, falha entre gravações e reenvio depois de
  revisão. Confirmar um único crédito com zero moeda, e dois créditos
  quando forem duas ocorrências legítimas.
- Em `America/Sao_Paulo`, verificar a virada do dia, a troca de semana e a
  aprovação após a meia-noite. Testar também pausa, retorno e meses curtos.
- Conferir permissão de criança, responsável e cuidador, IDs de outra
  criança e estados vencidos. Conferir em celular e tablet as etapas, o
  pedido de ajuda, o aviso de aprovação pendente e o recibo.


## Entrega da Fase 3

A migração `0038_mission_occurrences` adiciona a ocorrência, estende o
catálogo e conserva os vínculos antigos vazios. Solicitações pendentes ou em
revisão e atribuições pendentes continuam com o crédito integral prometido,
inclusive se a instalação já tinha limites ativos na Fase 2. Esses registros
preservam o fluxo legado e não geram XP. Um registro legado já pendente
bloqueia a criação de uma missão nova para o mesmo trabalho.

O catálogo configura descrição, XP, moedas, aprovação, dificuldade,
categoria, rotina, horários, dependência e checklist. Missões cooperativas
usam atribuições individuais por criança. Rotinas mensais usam o último dia
em meses curtos, rotinas sob demanda são acionadas pelo responsável e férias
pausam as atribuições automáticas. Cada execução tem um lote único por
rotina e data. Rotinas sobrepostas reaproveitam a regra diária de
disponibilidade do catálogo. Trabalho adicional usa a ação explícita de
criação de outra ocorrência.

No painel infantil, a missão tem uma página em português brasileiro, etapas
recolhíveis, temporizador opcional, pedido de ajuda e recibo de XP e moedas.
A revisão conserva o checklist e exibe a orientação recebida. Um pedido de
ajuda aparece no painel parental e pode gerar push para os responsáveis.
O temporizador é visual, funciona enquanto a página está aberta e não
interfere na recompensa.

A verificação em uma base atualizada de `0037` para `0038` preservou o
extrato, uma atribuição pendente e um pedido em revisão. Dois processos
SQLite, um aprovando e o outro lançando diretamente, registraram um único
crédito. As rotinas mensais, férias e aprovação após a meia-noite foram
verificadas em `America/Sao_Paulo`. O layout da missão foi conferido no
Firefox a 390 e 810 pixels.
