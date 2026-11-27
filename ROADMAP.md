# ROADMAP — KinKudos RPG Evolution

## 1. Visão do projeto

Evoluir o KinKudos para uma plataforma gamificada de desenvolvimento de hábitos, autonomia e responsabilidade infantil, utilizando elementos de RPG.

A evolução é candidata a um produto derivado do KinKudos. O primeiro uso previsto é familiar. A identidade, o nome e a distribuição do produto serão decididos depois da validação do MVP.

A aplicação deve incentivar a realização de atividades do cotidiano por meio de missões, experiência, níveis, moedas, equipamentos, conquistas e aventuras.

### Premissas

- Preservar as funcionalidades existentes.
- Evitar reescritas desnecessárias.
- Manter compatibilidade com instalações existentes.
- Utilizar português brasileiro como idioma principal da instalação.
- Priorizar dispositivos móveis e tablets.
- Permitir configuração das regras pelos responsáveis.
- Manter a criança como protagonista da aventura, com instruções curtas, etapas claras, pedido de ajuda e estímulos opcionais. Validar essas escolhas no uso familiar, respeitando preferências individuais.
- Permitir participação dos pais sem exigir tarefas próprias.
- Preservar os avisos de copyright e licenças originais.

---

## 2. Papéis dos usuários

### Responsável — Guardião

Os responsáveis participam como administradores e mentores da aventura.

Permissões:

- Criar, editar e remover missões.
- Aprovar a conclusão de missões.
- Configurar recompensas.
- Aprovar resgates.
- Aplicar consequências.
- Criar desafios especiais.
- Enviar mensagens de incentivo.
- Acompanhar o desenvolvimento da criança.
- Configurar a economia do jogo.
- Personalizar seu avatar e título de guardião.

Os responsáveis não possuem obrigatoriamente missões, níveis, moedas ou metas de produtividade.

### Criança — Aventureiro

- Possui personagem personalizável.
- Realiza missões.
- Recebe XP e moedas.
- Evolui de nível.
- Desbloqueia conquistas.
- Equipa itens cosméticos.
- Solicita recompensas.
- Participa de campanhas.
- Interage com seu mascote.
- Recebe mensagens dos guardiões.

---

# Fase 0 — Auditoria técnica

**Prioridade: P0**

Antes de implementar novas funcionalidades, analisar a arquitetura atual do KinKudos.

- [x] Identificar arquitetura do frontend.
- [x] Identificar arquitetura do backend.
- [x] Mapear modelos e relacionamentos do banco.
- [x] Mapear endpoints existentes.
- [x] Identificar sistema de autenticação e autorização.
- [x] Identificar fluxo de tarefas e aprovações.
- [x] Identificar implementação atual de pontos.
- [x] Identificar implementação de penalidades.
- [x] Identificar implementação de recompensas.
- [x] Verificar internacionalização.
- [ ] Confirmar a procedência dos ícones próprios e das capturas antes de distribuir o derivado. A licença do código e o aviso do Font Awesome já foram identificados.
- [x] Identificar cobertura de testes.
- [x] Documentar arquitetura existente.
- [x] Validar execução via Docker.

### Entregáveis

- [Arquitetura atual](docs/ARCHITECTURE.md)
- [Funcionalidades atuais](docs/CURRENT_FEATURES.md)
- [Dívida técnica e verificação](docs/TECHNICAL_DEBT.md)
- [Banco de dados](docs/DATABASE.md)

### Critérios de aceite

- Aplicação original executando corretamente.
- Fluxos existentes documentados.
- Nenhuma funcionalidade removida.
- Estratégia de evolução definida com base no código real.

---

# Fase 1 — Internacionalização

**Prioridade: P0**

- [ ] Reaproveitar o catálogo `locale/pt_BR/` e a infraestrutura de tradução da branch `translation/pt-br`, que serve de base para este derivado. Validar a cobertura existente e traduzir os textos faltantes ou novos.
- [ ] Centralizar textos traduzíveis.
- [ ] Traduzir painel infantil.
- [ ] Traduzir painel dos responsáveis.
- [ ] Traduzir notificações.
- [ ] Traduzir mensagens de validação.
- [ ] Traduzir categorias e configurações padrão.
- [x] Permitir seleção de idioma na interface.
- [x] Formatar datas conforme locale.
- [x] Permitir editar o idioma padrão e o fuso da família após a configuração inicial.
- [x] Disponibilizar America/Sao_Paulo na configuração inicial.
- [x] Aplicar o fuso familiar também na manutenção diária e na exibição do status de backup.

Os resultados da auditoria e das correções estão em [Português brasileiro e fuso familiar](docs/LOCALIZATION_AUDIT.md). As novas instalações começam em português brasileiro e no fuso de São Paulo. A validação de entrega real de Web Push e SMTP segue pendente.

### Critérios de aceite

- Nenhum texto estático relevante permanece sem tradução.
- Idioma pode ser alterado sem modificar o código.
- Traduções não quebram layouts.
- Datas e recorrências respeitam o fuso horário configurado.

---

# Fase 2 — Economia do jogo

**Prioridade: P0**

Separar a progressão do personagem da economia de recompensas.

O [plano técnico da economia](docs/ECONOMY_PLAN.md) detalha o reaproveitamento dos pontos, o crédito de XP e os critérios de migração.

## 2.1 Experiência — XP

- [x] Criar saldo acumulativo de experiência.
- [x] Ligar a configuração de XP às missões na Fase 3.
- [x] Registrar experiência em histórico.
- [x] Garantir crédito único por ocorrência no serviço de XP.
- [x] Preservar experiência em dias sem atividades.
- [x] Impedir perda de XP por penalidades.

XP representa progresso e aprendizado, não poder de compra.

## 2.2 Moedas

A moeda existente deverá ser reaproveitada sempre que possível.

- [x] Reutilizar a recompensa em pontos por tarefa como valor em moedas.
- [x] Ligar o crédito único de moedas e XP ao fluxo de missões na Fase 3.
- [x] Configurar limite diário de ganhos.
- [x] Configurar limite máximo de saldo opcional.
- [x] Configurar limite diário de penalidades.
- [x] Permitir saldo negativo até o piso configurado por criança. Usar zero em novas instalações e preservar pisos e saldos existentes.
- [x] Registrar os metadados financeiros dos novos lançamentos e preservar o extrato legado.
- [x] Permitir estorno administrativo.
- [x] Garantir consistência transacional.
- [x] Implementar idempotência nas operações.

## 2.3 Configurações iniciais

Valores iniciais para instalações novas. Os limites ficam desativados em instalações existentes até o responsável configurá-los.

| Parâmetro | Valor inicial |
|---|---:|
| Limite diário de moedas | 50 |
| Limite máximo de saldo | 500 |
| Limite diário de penalidades | 10 |
| Piso de saldo por criança | 0 em novas instalações, configurável |
| Expiração de moedas | Desabilitada |
| Perda de XP | Desabilitada |

## 2.4 Histórico econômico

Cada movimentação deverá possuir:

- Identificador.
- Usuário.
- Tipo de movimentação.
- Quantidade.
- Saldo anterior.
- Saldo posterior.
- Origem.
- Justificativa.
- Responsável pela operação, quando aplicável.
- Data e horário.
- Chave de idempotência.

Tipos sugeridos:

- `QUEST_REWARD`
- `BONUS_REWARD`
- `REWARD_REDEMPTION`
- `COSMETIC_PURCHASE`
- `PENALTY`
- `REFUND`
- `ADMIN_ADJUSTMENT`

---

# Fase 3 — Missões e rotinas

**Prioridade: P0**

Evoluir o sistema atual de tarefas para um sistema de missões.

O [plano técnico de missões e rotinas](docs/MISSIONS_PLAN.md) descreve o reaproveitamento das tarefas, a aprovação e o crédito único por ocorrência.

## Tipos de missão

- Diária.
- Semanal.
- Mensal.
- Eventual.
- Principal.
- Secundária.
- Especial.
- Cooperativa.

## Funcionalidades

- [x] Nome temático da missão.
- [x] Descrição objetiva da atividade real.
- [x] Categoria.
- [x] Ícone.
- [x] Dificuldade.
- [x] Horário sugerido.
- [x] Prazo opcional.
- [x] Recompensa em XP.
- [x] Recompensa em moedas.
- [x] Checklist de subtarefas.
- [x] Temporizador visual opcional.
- [x] Modo de foco com uma etapa visível por vez e feedback de revisão que indica o que falta.
- [x] Recorrência.
- [x] Aprovação parental configurável por tarefa e exigida por padrão.
- [x] Dependências entre missões.
- [x] Agrupamento por rotina.
- [x] Modo férias.
- [x] Possibilidade de solicitar ajuda.

## Rotinas

- Manhã.
- Escola.
- Tarde.
- Noite.
- Final de semana.

### Exemplo

**Missão: Preparar o inventário**

Atividade real: organizar a mochila escolar.

Subtarefas:

- Conferir cadernos.
- Guardar estojo.
- Conferir atividades escolares.
- Separar garrafa de água.

Recompensa:

- 20 XP.
- 5 moedas.

## Ciclo de vida

`AVAILABLE → IN_PROGRESS → PENDING_APPROVAL → COMPLETED`

Estados adicionais:

- `IN_REVIEW`
- `REJECTED`
- `CANCELLED`
- `SKIPPED`

### Regras

- A tarefa que exige aprovação credita o XP e as moedas configurados após a aprovação. A tarefa dispensada de aprovação credita na conclusão.
- Enquanto aguarda aprovação ou revisão, a criança vê o estado da missão e mantém o progresso do checklist.
- Cada ocorrência credita XP e moedas uma única vez. Os limites de moedas podem reduzir o crédito em moedas, preservando o XP configurado e mostrando o valor efetivamente creditado.
- Tarefas não concluídas não geram automaticamente penalidades.
- Missões futuras não podem ser concluídas antecipadamente sem autorização.
- Falhas e esquecimentos não removem experiência acumulada.

---

# Fase 4 — Consequências e reforço positivo

**Prioridade: P0**

Aprimorar o sistema existente de penalidades, evitando uma experiência predominantemente punitiva.

O [plano técnico de consequências e reforço positivo](docs/CONSEQUENCES_PLAN.md) detalha o registro por episódio, o uso dos limites de moedas e a proteção do XP.

- [x] Criar categorias configuráveis de comportamento.
- [x] Exigir justificativa.
- [x] Permitir advertência sem perda de moedas.
- [x] Permitir penalidade limitada em moedas.
- [x] Permitir registrar uma ação de reparação.
- [x] Permitir estornar penalidades.
- [x] Registrar o responsável pela decisão.
- [x] Impedir penalidades automáticas.
- [x] Impedir mais de um débito manual por episódio, inclusive após estorno.
- [x] Impedir perda de XP, níveis e equipamentos adquiridos.
- [x] Permitir mensagens positivas dos guardiões.

## Categorias iniciais

- Descumprimento de combinado.
- Falta de respeito.
- Mentira deliberada.
- Dano intencional.
- Outro comportamento.

As categorias não devem ser utilizadas para classificar a personalidade da criança.

## Restrições

- Não penalizar emoções.
- Não penalizar dificuldades involuntárias.
- Missões incompletas, puladas ou devolvidas para revisão não geram débitos automáticos. Consequências manuais respeitam o piso configurado e o limite diário.
- Não utilizar ranking de comportamento.
- Não condicionar necessidades básicas, carinho ou atenção ao desempenho.
- Não aplicar punição automática por missão incompleta.

---

# Fase 5 — Progressão RPG

**Prioridade: P1**

O [plano técnico da progressão RPG](docs/PROGRESSION_PLAN.md) descreve o cálculo com XP acumulado, as concessões por nível e a atualização de perfis existentes.

## 5.1 Níveis

- [x] Implementar progressão baseada em XP acumulado.
- [x] Configurar curva de experiência.
- [x] Exibir progresso até o próximo nível.
- [x] Notificar subida de nível.
- [x] Desbloquear títulos.
- [x] Desbloquear itens cosméticos.
- [x] Permitir evolução indefinida.

Curva inicial sugerida:

`XP necessário para avançar = 100 × nível atual`

| Nível | XP acumulado necessário |
|---|---:|
| 1 | 0 |
| 2 | 100 |
| 3 | 300 |
| 4 | 600 |
| 5 | 1.000 |
| 10 | 4.500 |
| 20 | 19.000 |

## 5.2 Classes

- [x] Maga.
- [x] Guerreira.
- [x] Druida.
- [x] Alquimista.
- [x] Exploradora.
- [x] Arqueira.

Classes possuem finalidade exclusivamente cosmética e narrativa.

Nenhuma classe deverá gerar vantagem na economia de recompensas reais.

## 5.3 Habilidades

Cada missão poderá contribuir para uma ou mais categorias de habilidades.

- Organização.
- Aprendizado.
- Autonomia.
- Cooperação.
- Criatividade.
- Cuidado.

As habilidades representam atividades praticadas, não notas de caráter ou personalidade.

## 5.4 Títulos

Exemplos:

- Aprendiz.
- Aventureiro.
- Explorador.
- Guardião.
- Mestre da Academia.
- Herói do Reino.

---

# Fase 6 — Loja de recompensas

**Prioridade: P1**

O [plano técnico da loja de recompensas](docs/REWARD_SHOPS_PLAN.md) detalha o reaproveitamento dos resgates, as compras cosméticas e o uso do saldo de moedas.

Separar recompensas reais de recompensas virtuais. As novas funcionalidades da loja real ficam para depois do MVP. O catálogo e os resgates existentes continuam disponíveis por compatibilidade.

## 6.1 Loja real

- [x] Catálogo administrado pelos responsáveis.
- [x] Permitir que os responsáveis ativem ou desativem a loja real para toda a família.
- [x] Custo em moedas.
- [x] Estoque opcional.
- [x] Limite diário de resgates.
- [x] Limite semanal de resgates.
- [x] Limite mensal de resgates.
- [x] Intervalo mínimo entre resgates.
- [x] Disponibilidade por período.
- [x] Aprovação obrigatória configurável.
- [x] Recusa sem débito e estorno de resgate efetivado ainda sem entrega.
- [x] Custo financeiro opcional.
- [x] Orçamento mensal familiar.

Exemplos:

- Tempo adicional de tablet.
- Escolher um filme.
- Escolher uma atividade especial.
- Escolher uma sobremesa.
- Brinquedo dentro de orçamento definido.

## 6.2 Loja virtual

- [x] Roupas.
- [x] Chapéus.
- [x] Capas.
- [x] Cajados.
- [x] Equipamentos.
- [x] Acessórios.
- [x] Decorações.
- [x] Temas.
- [x] Mascotes.

Itens exclusivamente cosméticos.

## 6.3 Restrições

- Não implementar loot boxes pagas.
- Não implementar apostas.
- Não utilizar escassez artificial para pressionar compras.
- Não permitir compras com dinheiro real pela criança.
- Raspadinhas e mecânicas equivalentes ficam fora do produto derivado. A retirada das raspadinhas existentes integra o MVP e inclui bloquear novas compras, encerrar bilhetes ainda não revelados com devolução única do valor pago e preservar o histórico.
- Não remover itens adquiridos como punição.

---

# Fase 7 — Personagem e inventário

**Prioridade: P1**

A tela **Meu personagem** usa as concessões por nível e por compra.
As regras de conquistas entram na Fase 11 e as interações dos mascotes
na Fase 10. [Plano técnico e entrega](docs/INVENTORY_PLAN.md)

- [ ] Revisar o visual provisório do personagem e dos cosméticos antes
  de iniciar a [Fase 10 — Mascotes virtuais](#fase-10--mascotes-virtuais).
- [x] Editor de personagem.
- [x] Seleção de classe.
- [x] Seleção de aparência.
- [x] Personalização de roupas.
- [x] Inventário individual.
- [x] Equipar, trocar e desequipar itens.
- [x] Raridade cosmética com classificação fixa no catálogo.
- [x] Reaproveitamento dos desbloqueios por nível.
- [x] Pré-visualização de equipamentos.
- [x] Persistência das configurações.

## Slots

- Cabeça.
- Corpo.
- Mão principal.
- Mão secundária.
- Capa.
- Acessório.
- Mascote.
- Título.
- Decoração do personagem.
- Tema do personagem.

---

# Fase 8 — Participação dos guardiões

**Prioridade: P1**

Transformar a participação parental em uma experiência integrada à narrativa do RPG.

Os responsáveis não precisarão realizar missões individuais.

As contas existentes dão acesso ao perfil narrativo, ao mural e ao
fluxo de missões. A participação em capítulos depende da Fase 9 e a
aprovação de conquistas depende da Fase 11.
[Plano técnico e entrega](docs/GUARDIANS_PLAN.md)

- [x] Criar perfil de guardião.
- [x] Permitir avatar personalizado.
- [x] Permitir título personalizado.
- [x] Criar mural de mensagens.
- [x] Enviar elogios e incentivos.
- [x] Narrar uma sessão de RPG no app, com cena pronta, modo livre e
  opção de pausar e retomar, sem movimentar XP ou moedas.
- [x] Criar missões especiais.
- [x] Criar missões surpresa sem recompensas aleatórias.
- [x] Registrar atividades realizadas em conjunto.
- [x] Permitir que a criança solicite ajuda e receba uma resposta.
- [x] Reaproveitar as notificações da fila de aprovação pendente.

### Exemplos de interação

- O guardião envia uma nova missão.
- A criança conclui a atividade.
- O guardião aprova e envia uma mensagem.
- O personagem recebe XP e moedas.
- A criança desbloqueia uma conquista.
- Os responsáveis recebem uma notificação.

### Restrições

- Sem ranking entre pais e filhos.
- Sem obrigatoriedade de produtividade dos responsáveis.
- Sem tarefas domésticas atribuídas aos guardiões como requisito de participação.

---

# Fase 9 — Campanhas e mapa de aventuras

**Prioridade: P2**

Criar um mundo visual onde o personagem evolui conforme realiza missões.

O mapa usa missões e sessões narradas como requisitos de capítulos e
guarda a edição e o progresso por criança. A campanha inicial percorre
a Vila dos Aprendizes e a Floresta Encantada. As outras regiões ficam
disponíveis para configurar novos capítulos.
[Plano técnico e entrega](docs/CAMPAIGNS_PLAN.md)

## Regiões iniciais

1. Vila dos Aprendizes.
2. Floresta Encantada.
3. Vale dos Cristais.
4. Montanha dos Guardiões.
5. Academia de Magia.
6. Castelo dos Heróis.

## Funcionalidades

- [x] Mapa interativo com lista acessível de regiões.
- [x] Regiões desbloqueáveis.
- [x] Campanhas configuráveis e edições publicadas.
- [x] Capítulos narrativos.
- [x] Personagens NPC e falas nos capítulos.
- [x] Missões e sessões narradas vinculadas a campanhas.
- [x] Desafios especiais pelo fluxo de missões dos guardiões.
- [x] Recompensas cosméticas.
- [x] Histórico de aventuras.

## Regras

- Progresso permanente.
- Não regredir campanhas por penalidades.
- Não exigir sequência perfeita de dias.
- Permitir pausa e retomada.
- Permitir campanhas adaptadas aos interesses da criança.

---

# Fase 10 — Mascotes virtuais

**Prioridade: P2**

- [ ] Adotar mascote.
- [ ] Escolher nome.
- [ ] Evolução por experiência.
- [ ] Desbloquear aparências.
- [ ] Equipar acessórios.
- [ ] Animações de celebração.
- [ ] Participação em aventuras.
- [ ] Interações simples.

Mascotes iniciais:

- Dragão.
- Raposa.
- Gato mágico.
- Coruja.
- Fênix.
- Unicórnio.

### Restrições

- Mascotes não morrem.
- Mascotes não adoecem por ausência.
- Mascotes não perdem evolução por tarefas incompletas.
- Não gerar culpa emocional na criança.
- Não exigir interação constante.

---

# Fase 11 — Conquistas e eventos

**Prioridade: P2**

- [ ] Sistema de medalhas.
- [ ] Conquistas por quantidade de missões.
- [ ] Conquistas por habilidades praticadas.
- [ ] Conquistas por evolução.
- [ ] Conquistas cooperativas.
- [ ] Conquistas personalizadas pelos guardiões.
- [ ] Eventos temáticos.
- [ ] Celebrações opcionais.
- [ ] Histórico de conquistas.

Exemplos:

- Primeira aventura.
- Explorador iniciante.
- 10 missões concluídas.
- Mestre do inventário.
- Amigo dos animais.
- Grande descoberta.
- Aventura em família.

---

# Fase 12 — Dashboard parental

**Prioridade: P1**

- [ ] Resumo diário.
- [ ] Resumo semanal.
- [ ] Missões pendentes de aprovação.
- [ ] Recompensas pendentes.
- [ ] Histórico de XP.
- [ ] Histórico de moedas.
- [ ] Histórico de consequências.
- [ ] Desempenho por rotina.
- [ ] Identificação de tarefas que frequentemente exigem ajuda.
- [ ] Controle de orçamento de recompensas.
- [ ] Configuração centralizada.
- [ ] Exportação de dados.

Os relatórios devem servir para identificar dificuldades e ajustar rotinas, não para rotular a criança.

---

# Fase 13 — Experiência de usuário e acessibilidade

**Prioridade: P1**

- [ ] Layout mobile-first.
- [ ] Interface adaptada para tablets.
- [ ] Botões grandes.
- [ ] Navegação simplificada.
- [ ] Modo de foco em uma missão.
- [ ] Indicadores visuais de progresso.
- [ ] Checklist interativo.
- [ ] Temporizador visual.
- [ ] Leitura opcional de instruções.
- [ ] Sons configuráveis.
- [ ] Controle de animações.
- [ ] Modo de movimento reduzido.
- [ ] Temas claro e escuro.
- [ ] PWA, caso ainda não exista.
- [ ] Notificações configuráveis.
- [ ] Evitar estímulos visuais excessivos.

---

# Fase 14 — Integrações

**Prioridade: P3**

- [ ] API documentada.
- [ ] Webhooks.
- [ ] Integração com Home Assistant.
- [ ] Integração com calendário.
- [ ] Notificações externas.
- [ ] Integração opcional com assistentes de voz.
- [ ] Backup e restauração automatizados.

---

# Fase 15 — Segurança e qualidade

**Prioridade: Contínua**

- [ ] Validação de permissões no backend.
- [ ] Isolamento de dados familiares.
- [ ] Proteção de dados infantis.
- [ ] Minimização de dados pessoais.
- [ ] Ausência de rastreamento publicitário.
- [ ] Auditoria de ações administrativas.
- [ ] Testes unitários.
- [ ] Testes de integração.
- [ ] Testes end-to-end dos fluxos críticos.
- [ ] Testes de concorrência na economia.
- [ ] Migrações compatíveis.
- [ ] Backup antes de migrações destrutivas.
- [ ] Health checks.
- [ ] Logs estruturados.
- [ ] Atualização da documentação.
- [ ] Validação de instalação via Docker.

---

# Marcos de entrega

## MVP — Rotina gamificada

- Auditoria técnica.
- Português brasileiro.
- Missões e rotinas.
- XP independente.
- Economia controlada.
- Consequências configuráveis.
- Retirada das raspadinhas com preservação do histórico.
- Aprovação parental por tarefa, exigida por padrão.

## V0.2 — RPG

- Níveis.
- Classes.
- Habilidades.
- Títulos.
- Inventário.
- Loja virtual.

A loja real fica no backlog pós-MVP, sem versão de entrega definida.

## V0.3 — Guardiões

- Perfis parentais narrativos.
- Mensagens de incentivo.
- Missões especiais.
- Dashboard parental.
- Participação cooperativa opcional.

## V0.4 — Universo de aventuras

- Mapa.
- Campanhas.
- NPCs.
- Mascotes.
- Eventos.
- Conquistas avançadas.

## V1.0 — Plataforma consolidada

- Experiência mobile e tablet refinada.
- Acessibilidade.
- Segurança.
- Testes.
- Documentação.
- Integrações.
- Backup e restauração.

---

# Instruções para o agente de desenvolvimento

1. Não implementar todo o roadmap de uma única vez.
2. Iniciar exclusivamente pela Fase 0.
3. Inspecionar o código antes de propor alterações estruturais.
4. Reutilizar funcionalidades existentes.
5. Não substituir tecnologias sem justificativa técnica.
6. Não realizar alterações destrutivas sem autorização.
7. Priorizar compatibilidade com dados existentes.
8. Elaborar um plano técnico para cada fase.
9. Implementar testes juntamente com novas funcionalidades.
10. Atualizar a documentação ao concluir cada etapa.
11. Utilizar commits pequenos e descritivos.
12. Garantir consistência transacional em XP, moedas e recompensas.
13. Não confiar exclusivamente em validações do frontend.
14. Manter regras de negócio configuráveis.
15. Não introduzir serviços externos obrigatórios.
16. Registrar decisões arquiteturais relevantes em ADRs.
17. Apresentar critérios de aceite e resultados dos testes ao concluir cada fase.
18. Manter este roadmap atualizado conforme o desenvolvimento.
