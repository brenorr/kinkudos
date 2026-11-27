# Plano técnico de participação dos guardiões

O guardião é a identidade narrativa do responsável que a criança já
conhece. Ela aparece ao assinar um elogio, enviar uma missão especial ou
responder a um pedido de ajuda. A criança continua conduzindo a aventura
e recebe XP e moedas pelas regras das missões. A participação do adulto
é opcional e dispensa missões próprias, pontuação e ranking.

## Perfil e acesso

- Vincular uma apresentação opcional de guardião à conta Django
  existente por relação um para um. Guardar nome de exibição, título
  narrativo e avatar. Cada responsável edita o próprio perfil.
  Usar o nome de apresentação existente quando configurado, com
  fallback para um rótulo neutro se a conta tiver apenas nome de login.
  A opção inicial do avatar pode usar a inicial do nome exibido.
- Reaproveitar o processamento atual de fotos. Servir o avatar por
  uma rota autenticada, com acesso infantil apenas quando aquele
  guardião tiver uma participação visível para o perfil em sessão.
  Evitar expor e-mail, login, PIN ou dados de acesso no mural.
- Manter `CaregiverProfile` e seus vínculos de criança, validade e
  bloqueios como fonte de autorização dos convidados. Na primeira
  entrega, só responsáveis com conta completa editam a apresentação e
  usam as novas ações de mural e narrativa. Cuidadores mantêm as ações
  já autorizadas, como atribuir tarefas e decidir solicitações das
  crianças vinculadas. Conferir as permissões no servidor a cada ação.

[Autorização](../economy/auth.py) · [Perfis atuais](../economy/models.py) · [Processamento de imagens](../economy/images.py)

## Mural e elogios

- Usar `GuardianMessage` como registro do mural individual da criança.
  Hoje ele guarda destinatário, autor, texto, data e token, e o painel
  infantil mostra as cinco mensagens mais recentes. Manter a prévia e
  oferecer histórico paginado em **Mural dos guardiões**. Levar a
  composição para uma área própria do painel parental, com um atalho
  na tela atual de consequências.
- Evoluir `send_guardian_message` para distinguir tipos simples, como
  elogio, mensagem de aventura e resposta de ajuda. Usar o tipo
  **Incentivo** para os registros atuais, sem inferir assunto ou
  relação com uma missão pelo conteúdo. Permitir vínculo opcional com
  `MissionOccurrence`, validado para a mesma criança. Manter o texto
  curto e usar o mesmo token para garantir um envio por ação. Rejeitar
  a reutilização do token com autor, texto, tipo ou missão diferentes.
- Na aprovação de uma missão, oferecer um elogio opcional junto do
  resultado. A aprovação continua no serviço atual. Se houver elogio,
  validar o texto antes de decidir e gravá-lo na mesma transação da
  aprovação com identidade estável por ocorrência para essa ação.
  Um reenvio de aprovação não repete crédito, elogio nem aviso. Para
  enviar uma mensagem posterior, usar a composição do mural.
- Mostrar o nome de exibição, o título narrativo quando preenchido e,
  se houver, um link para a missão acessível pela criança. O incentivo
  pode reconhecer esforço, estratégia ou pedido de ajuda, mesmo sem uma
  conclusão. As mensagens não geram moedas, XP ou penalidades.
  Orientações de reparação continuam no fluxo próprio de consequências.

[Mensagens atuais](../economy/consequences.py) · [Painel infantil](../templates/economy/child_dashboard.html)

## Missões e atividades em conjunto

Reaproveitar a atribuição avulsa de `AssignedTaskBatch` e
`AssignedTask`, a autoria em `assigned_by` e a execução em
`MissionOccurrence`. O catálogo `Task` já tem tipos especial e
cooperativo. Acrescentar o tipo à ocorrência para registrar o contexto
na criação, inclusive para atribuições avulsas que não têm uma tarefa
de catálogo. Proposta de manter as ocorrências anteriores sem nova
classificação e aplicar as distinções às novas missões.

| Fluxo | Proposta |
| --- | --- |
| Missão especial | Criar uma ocorrência avulsa assinada pelo guardião, com instrução, XP, moedas e aprovação exigida por padrão. A criança acompanha e conclui pelo fluxo atual. |
| Missão surpresa | Revelar a apresentação da missão quando ela ficar disponível. Definir XP e moedas na criação e mostrar os valores ao revelar a atividade, antes de a criança decidir começar. Usar a data local da atribuição e a mesma ocorrência em cliques repetidos. |
| Atividade em conjunto | Usar uma missão cooperativa e permitir que o responsável registre quem participou. A autoria da atribuição não comprova participação. A conclusão aparece no histórico da criança, com as moedas e o XP configurados para a própria ocorrência. |

Usar a fila atual de aprovação e a regra de um único crédito por
ocorrência. A criança pode pular a atividade pelas regras atuais.
As novas opções de narrativa não bloqueiam a loja nem geram punição.
Para não duplicar os recursos das fases seguintes, os capítulos,
diálogos e vinculação ao mapa serão definidos na Fase 9. O pedido
e a aprovação de uma conquista especial serão definidos na Fase 11.
O perfil do guardião e o mural poderão apresentar esses eventos
quando os fluxos correspondentes estiverem disponíveis.

[Atribuições atuais](../economy/services.py) · [Plano de missões](MISSIONS_PLAN.md)

## Sessão de RPG narrada no app

No painel adulto, **Guardiões → Iniciar sessão de RPG** abre a seleção
da criança e do modo. No painel infantil, **Entrar na sessão** abre
a cena atual com o personagem e os itens equipados. O guardião pode
ouvir a escolha e registrá-la quando estiverem juntos em uma tela.
Em dispositivos separados, a criança pode selecionar uma opção da cena
no próprio perfil. O guardião conduz o desfecho e avança a narrativa.

| Modo | Experiência inicial |
| --- | --- |
| Cena pronta | Incluir **A ponte da floresta**. A introdução apresenta a ponte e quem a vigia. A criança pode atravessar, procurar outro caminho, conversar com quem vigia ou sugerir outra ação em voz alta. O guardião narra a consequência e pode registrar a escolha ou um breve resumo. |
| Modo livre | O guardião informa um título e escreve a situação inicial. Durante a sessão, pode publicar trechos curtos e, se quiser, sugerir opções. A história também pode seguir com as respostas faladas da criança. |

- Proposta de persistir a sessão com criança, conta do guardião
  narrador, modo, cena inicial, trecho atual, última escolha registrada
  e estado. Começar com uma sessão ativa ou pausada por criança.
  A criança acessa apenas a própria sessão. O guardião que a iniciou
  controla a publicação de trechos, a pausa, a retomada e o encerramento,
  com validação em cada requisição.
- **Pausar** salva o ponto atual e mantém a cena visível com o estado
  **Sessão pausada**. **Retomar** restaura a mesma cena, as opções e
  a escolha registrada. A pausa suspende novas escolhas e avanços.
  **Encerrar** finaliza a sessão e permite salvar um resumo. O
  guardião pode enviar um elogio opcional pelo mural existente.
- Gravar mudanças de estado e escolhas em transação. Validar a
  versão do trecho ao aceitar uma escolha, para que um envio atrasado
  não substitua a resposta de uma cena posterior. Permitir recarregar
  a cena manualmente e reaproveitar a consulta de estado do painel para
  atualizar a sessão em dois dispositivos. O fluxo dispensa cronômetro.
- Vincular escolhas e resumos à sessão narrativa. Iniciar, jogar,
  pausar, retomar e encerrar não criam uma missão, não concedem XP
  e não movimentam moedas. A cena funciona na Fase 8. A Fase 9
  poderá vincular sessões a capítulos do mapa.

## Ajuda e notificações

- Manter **Pedir ajuda** na página da missão, que já registra
  `help_requested_at` e aparece no painel adulto. Proposta de guardar
  cada abertura em um registro ligado à ocorrência, com no máximo um
  pedido em aberto por vez. Migrar os pedidos ativos que já aparecem no
  painel sem reenviar avisos e preservar as datas anteriores. O
  responsável pode responder pelo mural e fechar o pedido na mesma
  transação, registrando quem respondeu e quando. A missão segue no
  estado em que estava. Enquanto aceitar pedidos de ajuda, a criança
  pode abrir outro de forma explícita, com uma nova identidade para o
  aviso. O histórico mantém a resposta anterior.
- Reaproveitar `notify_task_claim` e a fila atual para aprovações
  pendentes, inclusive nas atribuições. O push adulto hoje alcança
  contas completas ativas. Preservar esse alcance e ancorar o aviso no
  pedido de aprovação ou de ajuda. Enviar após o commit e apenas em
  uma transição nova. O painel continua sendo a fonte do estado
  quando push estiver desativado. Novos avisos podem usar texto
  genérico na tela bloqueada e deixar o conteúdo na área autenticada.
- Atualizar a assinatura de estado infantil com o mural e com o
  estado do pedido associado à missão. Mostrar explicitamente
  **Ajuda solicitada** e **Resposta do guardião**. Usar pt-BR,
  datas no fuso familiar e rótulos legíveis em celular e tablet,
  sem exigir sons ou animações.

[Fluxo de ajuda](../economy/missions.py) · [Notificações atuais](../economy/push.py)

## Migração e critérios de aceite

1. Adicionar perfil opcional e metadados de mensagem. Conferir a
   atualização com responsáveis, cuidadores e elogios antigos.
   Preservar autores, textos, datas, destinatários e histórico.
2. Entregar o mural, a composição e a resposta de ajuda. Testar
   isolamento entre crianças, acesso por URL direta, edição do próprio
   perfil e expiração dos convidados. Conferir histórico paginado e
   a atualização após receber mensagem em outro dispositivo.
3. Integrar os tipos de atribuição e o elogio na aprovação. Testar
   atribuição repetida, aprovação concorrente, aprovação sem elogio,
   surpresa com recompensa fixa, atividade cooperativa e pedido de
   ajuda que não altera o saldo ou XP. Confirmar que a aprovação
   protege crédito, mensagem e aviso contra duplicação.
4. Conferir o fluxo de notificações com e sem push, incluindo envio
   próximo à meia-noite em `America/Sao_Paulo`, revisão seguida de
   reenvio e links que respeitam a criança e o papel em sessão.
5. Iniciar a cena pronta e o modo livre, jogar em uma tela e em dois
   dispositivos, pausar, recarregar e retomar no mesmo trecho. Testar
   acesso de outra criança, tentativa de escolha atrasada e
   encerramento com resumo ou elogio. Comparar XP, saldo, créditos e
   extrato antes e depois da sessão.

## Entrega da Fase 8

Em **Guardiões**, o responsável pode personalizar o perfil, escolher
uma criança, enviar mensagens e missões, responder a pedidos de ajuda
e iniciar uma sessão. A criança acompanha as respostas e pode rever o
resumo de sessões encerradas no mural. A aprovação de uma missão pode
incluir um elogio. Convidados mantêm as permissões de aprovação e
atribuição das crianças vinculadas.

Uma sessão pronta inicia com **A ponte da floresta**. O modo livre
aceita uma abertura escrita pelo guardião. A cena e o personagem
equipado aparecem no painel infantil. O guardião narra, pausa, retoma
e encerra. As duas telas atualizam quando o outro perfil age e
permitem recarregar manualmente. Um trecho digitado permanece
disponível se a cena mudar antes de o guardião enviá-lo.

A atualização de uma base SQLite da Fase 7 preservou texto, autor,
destinatário, data e saldo. O pedido de ajuda em aberto manteve a
data original. No Chromium, duas sessões de navegador em pt-BR
confirmaram a atualização, a pausa e a retomada, a aparência
equipada da criança, o resumo e o elogio do mural. O modo livre
foi conferido com registro de uma escolha falada.

Em uma base SQLite em disco, disputas concorrentes por criação de
sessão, escolha de cena e abertura do pedido de ajuda produziram
um único registro ou transição em cada caso.

A suíte completa passou com 559 testes. A comparação do Ruff com o
commit da Fase 7 confirmou que as 11 pendências restantes de lint
já existiam.
