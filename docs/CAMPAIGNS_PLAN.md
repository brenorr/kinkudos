# Plano técnico de campanhas e mapa de aventuras

Campanhas organizam a aventura em capítulos. Cada capítulo pode propor
uma missão, uma sessão narrada pelo guardião ou uma combinação das duas.
Essa estrutura usa as conclusões já registradas pelas Fases 3 e 8. O
mapa mostra o próximo passo e permite voltar à história já percorrida.

## O que reaproveitar

| Recurso atual | Uso no capítulo |
| --- | --- |
| `Task`, `AssignedTask` e `MissionOccurrence` | Selecionar uma tarefa do catálogo ou criar uma atribuição especial, surpresa ou cooperativa pelo fluxo atual. Vincular a ocorrência específica da criança ao requisito. Preservar instruções, recompensas e regra de aprovação da ocorrência. |
| `StorySession` | Abrir uma sessão com cena pronta ou em modo livre. O vínculo aponta para a sessão da criança e reaproveita o narrador, os trechos, as escolhas e a pausa. Uma sessão em andamento pode receber o vínculo e continuar do mesmo ponto. |
| `GuardianProfile` e mural | Exibir a identidade do guardião quando ele participar da narrativa. Usar o mural para elogios e mensagens opcionais. |
| `LevelUnlock` e `UnlockGrant` | Cadastrar cosméticos da campanha e concedê-los pela mesma propriedade que a coleção já consulta. |

[Missões](../economy/missions.py) · [Sessões narradas](../economy/guardians.py) · [Inventário](INVENTORY_PLAN.md)

Se a criança já tiver uma sessão aberta, oferecer **Retomar sessão**
ou permitir que o responsável a vincule explicitamente ao capítulo.
Reaproveitar a regra atual de uma sessão ativa ou pausada por criança.

## Catálogo e progresso

- Proposta de ter um catálogo de regiões com código estável, nome,
  posição no mapa e ordem de leitura. Usar as seis regiões do roadmap.
  A **Vila dos Aprendizes** é o ponto de entrada. Cada capítulo tem
  região, posição na campanha, título, texto de abertura, diálogos
  curtos de personagens e requisitos obrigatórios. Um desafio pode usar
  uma missão especial ou cooperativa que já existe no produto.
- O responsável escolhe a campanha e ativa uma edição para a criança.
  Pode adaptar a abertura, os diálogos e os requisitos aos interesses
  dela. Guardar a edição usada por cada partida. Progresso existente
  conserva seus requisitos e histórico quando o responsável publica uma
  nova edição. Antes de iniciar, validar a ordem dos capítulos, seus
  requisitos e as recompensas configuradas.
- Manter edição, capítulos e requisitos no catálogo. Na partida,
  registrar um vínculo por requisito e permitir que ele aponte para
  uma ocorrência de missão ou para uma sessão, de acordo com seu tipo.
  Usar a referência da execução como evidência. Registros legados sem
  ocorrência equivalente continuam no histórico original.
- Guardar o progresso por criança e campanha, com o capítulo atual,
  capítulos concluídos, estado da partida e datas. Começar com capítulos
  em ordem linear. Concluir um capítulo libera o próximo e, se ele
  estiver em outra região, abre essa região no mapa da criança.
  Voltar a uma região visitada permite reler sua história.
- O responsável pode vincular uma execução já existente, inclusive
  uma missão concluída ou uma sessão encerrada, por escolha explícita.
  Validar o tipo de atividade, a criança e o capítulo no servidor.
  Proposta de usar cada ocorrência ou sessão como evidência de um único
  requisito. A revisão de um requisito em andamento pode trocar uma
  execução recusada, cancelada ou expirada por outra elegível. Um
  requisito concluído conserva a referência que comprovou seu avanço.

### Exemplo de campanha inicial

Na **Vila dos Aprendizes**, o guardião apresenta um pedido para preparar
uma mochila de exploração. O capítulo usa uma missão existente. Assim
que a ocorrência estiver concluída, abre **A ponte da floresta**, na
**Floresta Encantada**. O guardião reaproveita a cena pronta da Fase 8
ou conta sua própria versão no modo livre. Encerrar a sessão vinculada
completa o requisito narrativo. O capítulo final pode entregar um
cosmético fixo e guardar a lembrança no histórico de aventuras.

## Conclusão, pausa e recompensas

1. Uma missão vinculada conta quando a `MissionOccurrence` chega a
   concluída pelo fluxo atual, com aprovação quando exigida. Pedidos
   pendentes e revisões mostram seu estado no capítulo. O XP e as moedas
   continuam usando a chave única de `OccurrenceCredit`. Uma missão
   com crédito de zero moedas por limite ainda pode concluir o requisito.
2. Uma sessão vinculada conta quando o guardião a encerra. Uma sessão
   em andamento ou pausada guarda suas escolhas para retomada. A sessão
   continua sem movimentar XP ou moedas. A campanha consulta o estado
   persistido e os resumos existentes da sessão.
3. O capítulo termina quando todos os requisitos obrigatórios estiverem
   concluídos. Proposta de registrar uma única conclusão por partida e
   capítulo, com o desbloqueio da próxima região e a concessão do
   cosmético na mesma transação. Sinalizar a atualização depois do
   commit da missão ou sessão. Reconciliar também na ação **Continuar
   aventura** ou ao retomar a campanha. Assim uma atualização perdida
   pode ser refeita pelo estado persistido.
4. Registrar a origem de campanha nas novas concessões de cosméticos.
   Preparar o catálogo para distinguir itens concedidos por campanha
   dos que são vendidos ou ganhos por nível. A coleção mostra a origem
   correta e reaproveita o encaixe existente. Se a criança já tem o
   cosmético, a campanha registra a conclusão e mantém a concessão
   original. O catálogo fica com recompensas fixas, exibidas no capítulo.
5. A pausa da campanha guarda o próximo passo e conserva as regiões
   abertas. Uma missão avulsa ou sessão pode continuar pelo próprio
   fluxo. Ao retomar, reconciliar as conclusões registradas durante a
   pausa. Faltas, dias sem jogar, consequências e estornos de moedas
   não desfazem capítulos ou itens adquiridos.

[Crédito atual](../economy/services.py) · [Catálogo e propriedade](../economy/models.py)

## Mapa e histórico

- Abrir **Mapa de aventuras** no painel infantil. O mapa e uma lista
  acessível de regiões usam os mesmos dados e indicam por texto o
  capítulo atual, as regiões abertas e o motivo do bloqueio.
  Priorizar o botão **Continuar aventura**, que abre o próximo passo
  disponível. Mostrar quando a etapa está aguardando aprovação do
  responsável ou retomada da sessão.
- No painel dos guardiões, listar capítulos, vínculos e progresso da
  criança. Só responsáveis com conta completa configuram e ativam
  campanhas. O controle da sessão continua com o narrador original.
  As permissões atuais de cuidadores nas missões continuam valendo.
- Exibir no histórico os capítulos concluídos, as missões vinculadas e
  o resumo publicado pelo guardião. Respeitar a criança em sessão em
  todas as leituras e ações. Reaproveitar a atualização do painel
  infantil para refletir novas conclusões em outro dispositivo.
- Apresentar textos curtos e estados previsíveis em pt-BR. O mapa deve
  funcionar em celular e tablet, com teclado e leitor de tela pela
  lista de regiões. A criança pode retomar sem contagem regressiva,
  sequência diária ou animação obrigatória.

## Ordem de entrega e aceite

1. Criar catálogo e progresso com migração aditiva. Uma instalação
   atualizada começa sem partidas ativas e preserva missões, sessões,
   créditos, extrato e inventário. Conferir vínculos explícitos com
   atividades anteriores, inclusive uma sessão pausada.
2. Entregar a campanha de exemplo. Testar missão aprovada e com
   aprovação dispensada, revisão e reenvio, sessão em modo livre,
   pausa e retomada, tentativa de vínculo entre irmãos e permissões
   de guardião e cuidador.
3. Validar reenvios e concorrência em SQLite, incluindo a aprovação
   da última missão junto do encerramento da sessão. Conferir um
   único registro de capítulo, um único desbloqueio e uma única
   concessão. Simular a perda da atualização após o commit e
   conferir a reconciliação ao continuar a aventura.
4. Conferir viradas de dia em `America/Sao_Paulo`, edição de campanha
   em uso, saldo negativo, estorno e dias sem jogar. Comparar XP,
   saldo e extrato antes e depois de sessões e concessões cosméticas
   da campanha. Conferir mapa, lista acessível e histórico em
   celular e tablet.

## Entrega da Fase 9

No painel adulto, **Guardiões → Campanhas de aventura** organiza a
publicação de edições, a escolha da criança e os vínculos do capítulo
atual. É possível vincular uma atividade existente, atribuir uma
tarefa do catálogo ou iniciar uma sessão pelo próprio capítulo.
Missões especiais e cooperativas podem vir do mural do guardião.

Em **Mapa de aventuras**, a criança acompanha o progresso e pode
pausar, retomar e abrir o próximo passo. A campanha pronta visita
a Vila dos Aprendizes e a Floresta Encantada. As outras quatro
regiões ficam disponíveis no editor. O Broche da trilha é o
cosmético inicial de campanha e reaproveita a arte do pingente
de bússola na coleção.

A migração de uma base da Fase 8 preservou a cena pausada, a
missão existente, o extrato, o XP e o equipamento. Uma aprovação
concorrente com o encerramento da sessão produziu um crédito, uma
conclusão e uma concessão. O estorno de moedas preservou o capítulo,
o XP e o cosmético. O fluxo em pt-BR foi testado no Chromium sem
JavaScript a 390 e 810 pixels, incluindo a edição de campanha.

A suíte completa passou com 564 testes. Os 44 testes focados
passaram após os ajustes finais, incluindo o limite de moedas e
a virada do dia em `America/Sao_Paulo`.
