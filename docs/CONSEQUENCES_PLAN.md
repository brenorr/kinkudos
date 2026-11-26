# Plano técnico de consequências e reforço positivo

A Fase 4 propõe registrar consequências por episódio e reaproveitar o extrato
de moedas para os débitos manuais. Advertências, ações de reparação e elogios
têm registro próprio. O XP e as recompensas de progressão ficam fora desses
fluxos.

## Base existente

O catálogo `PenaltyTemplate` já guarda modelos com valor negativo. Há
três entradas parentais para aplicar penalidades. Duas já exigem
justificativa, enquanto a aplicação em lote ainda aceita texto vazio.
O token do formulário em lote evita repetir o mesmo envio para cada modelo,
mas uma nova solicitação pode cobrar o mesmo episódio de novo.

O serviço `post_ledger_entry` já calcula o limite diário por criança e data
local, respeita o piso individual e rejeita débitos que ultrapassem o valor
disponível. `reverse_ledger_entry` registra uma compensação única vinculada
ao lançamento original e exige um responsável administrador. O XP está
registrado separadamente em `OccurrenceCredit`. [Serviços e regras atuais](../economy/services.py) · [Entradas parentais](../economy/views/parent_actions.py)

## Modelo proposto

| Registro | Dados e regras |
| --- | --- |
| Categoria | Nome configurável e estado ativo. Desativar conserva a categoria nos episódios existentes. Usar os nomes iniciais do roadmap como sugestões editáveis para descrever fatos observáveis. |
| Episódio | Identificador estável, criança, categoria, relato objetivo obrigatório, autor e data. Um episódio aceita uma única decisão com débito. Uma advertência pode ser evoluída explicitamente para essa decisão no mesmo episódio, preservando sua trilha. |
| Consequência | Advertência sem lançamento ou débito manual de moedas vinculado ao episódio. Registrar o decisor, o valor autorizado e a justificativa. Copiar o nome e o valor do modelo selecionado para preservar o contexto de decisões antigas. |
| Reparação | Ação combinada vinculada ao episódio, com registro de quem a propôs e quando foi realizada. Concluir a reparação pode motivar uma mensagem positiva, sem crédito, débito ou estorno automático. |
| Incentivo | Mensagem positiva independente, com texto, criança destinatária, responsável autor e data. Exibir no painel infantil e permitir elogiar esforço, estratégia, cooperação ou pedido de ajuda. |

Os modelos existentes continuam disponíveis como sugestões de débito. As
três entradas de aplicação devem usar o mesmo serviço e exigir
justificativa. A aplicação em lote deve apresentar uma decisão por episódio,
com um único valor total explícito. Episódios distintos devem ser
registrados separadamente. A interface deve localizar um episódio já
aberto antes de oferecer outro registro. A restrição no banco protege o
mesmo ID e o token de criação protege reenvios. Episódios recriados
manualmente com IDs diferentes exigem revisão humana, pois data e texto
iguais também podem corresponder a fatos distintos.

## Débito e estorno

1. Em uma transação, validar a criança, a permissão do decisor, a categoria
   ativa e a justificativa. Registrar a decisão com proteção de unicidade
   por episódio. Repetir com os mesmos dados devolve o resultado persistido.
   Uma tentativa com valor diferente deve ser recusada.
2. Pedir o débito a `post_ledger_entry`, com origem tipada e chave derivada do
   ID do episódio. Se o valor exceder a cota diária ou atravessar o piso,
   recusar a decisão monetária inteira e informar quanto pode ser aplicado.
   O responsável pode voltar e escolher uma advertência. Um saldo já abaixo
   do piso continua intacto e fica indisponível para novos débitos.
3. Estornar pelo serviço da Fase 2, com justificativa e vínculo ao débito
   original. Atualizar a situação da consequência na mesma transação. A
   compensação restitui as moedas e preserva o histórico. O estorno não
   reabre a cota diária nem permite outro débito pelo mesmo episódio.

Usar o fuso familiar no momento do lançamento, independente da data em que o
fato foi registrado. Preservar o limite diário opcional nas instalações
existentes e aplicar sempre o piso individual. Missões puladas, incompletas,
recusadas ou em revisão não chamam o serviço de consequências. Débitos,
advertências e estornos não escrevem no histórico de XP. Níveis e
equipamentos futuros ficam fora dessas operações.

## Permissões e experiência

Responsáveis configuram categorias e modelos. A proposta é manter os
cuidadores com a permissão de aplicação que já possuem, restrita às crianças
vinculadas, e reservar estornos a responsáveis administradores. Mensagens de
incentivo devem começar com responsáveis como autores. A criança consulta
seus próprios registros e as orientações que o responsável decidiu mostrar.

O formulário deve pedir uma descrição concreta do que aconteceu e oferecer
advertência ou reparação sem cobrança. Deve deixar explícito que emoções e
dificuldades involuntárias ficam fora das penalidades. O painel infantil
deve mostrar o próximo passo combinado em linguagem curta, sem rótulos de
personalidade, rankings ou vínculo com necessidades básicas.

## Migração e aceite

- Adicionar as estruturas sem reclassificar débitos históricos em episódios
  inferidos. Preservar modelos, saldos, extrato, estornos e XP. Os débitos
  antigos continuam identificados como lançamentos legados e podem ser
  estornados pelo fluxo atual.
- Testar as três entradas, justificativa obrigatória, advertência e reparação
  sem lançamentos, elogio e isolamento entre crianças e cuidadores.
- Testar duas solicitações concorrentes para um episódio, repetição com
  valor diferente, estorno concorrente e falha parcial de transação.
- Testar limite configurado e desativado, piso zero e negativo, saldo antigo
  abaixo do piso e virada do dia em `America/Sao_Paulo`. Conferir que XP e
  registros de ocorrência permanecem iguais em todos esses cenários.

## Entrega da Fase 4

O painel do responsável oferece **Mais ações → Consequências e incentivos**.
É possível registrar um episódio ou advertência, combinar uma reparação,
enviar um incentivo e aplicar um débito quando houver uma justificativa.
Os cuidadores mantêm acesso apenas às crianças vinculadas e não configuram
categorias nem enviam incentivos. O painel infantil exibe incentivos e
orientações compartilhadas. A justificativa privada do responsável não
aparece no extrato infantil dos episódios novos.

A migração `0039` semeia as categorias iniciais e conserva o histórico
existente. As rotas anteriores continuam disponíveis, com um ID de
episódio existente ou um token de criação obrigatório para o débito.
Uma seleção em lote registra um lançamento com o total e guarda os
modelos usados. A situação de estorno do episódio segue o vínculo de
reversão do extrato. A proteção contra repetição cobre o mesmo episódio
e o mesmo token de criação. Episódios registrados separadamente conservam
identidades distintas.

A suíte completa passou com 527 testes. A atualização de `0038` para
`0039` preservou saldos, modelos, extrato e XP de uma base de teste. Dois
processos SQLite concorrentes produziram um único débito e um único
estorno para o episódio. As telas foram conferidas em Firefox a 390 px
para o responsável e 810 px no painel infantil.

[Plano da economia](ECONOMY_PLAN.md) · [Roadmap](../ROADMAP.md#fase-4--consequências-e-reforço-positivo)
