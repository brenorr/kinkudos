# Banco de dados

A instalação atual usa SQLite. `kinkudos/settings.py` configura transações de
escrita `IMMEDIATE` e timeout de 20 segundos. A arquitetura atual usa WAL.
O volume local do Compose persiste banco, mídia e segredos de execução. O
backup e o teste de migração devem usar instâncias isoladas dos dados familiares.

## Modelos e relações

| Domínio | Modelos e vínculos |
| --- | --- |
| Família e acesso | `FamilySettings` é singleton. `ChildProfile` mantém identidade, PIN, saldo e piso. Responsáveis usam Django `User`. `CaregiverProfile` liga um usuário a crianças autorizadas e `CaregiverInvite` gerencia o convite temporário. |
| Dispositivos e segurança | `DeviceToken`, `DevicePairingLink`, `AttemptCounter` e `SecurityAuditEvent` guardam pareamento, tentativas e auditoria. |
| Catálogos | `Task`, `PenaltyTemplate` e `Reward` compartilham campos do catálogo abstrato e guardam valores inteiros de pontos. |
| Pedidos de tarefa | `TaskClaim` liga criança, tarefa e adulto decisor. Mantém uma cópia do título, do valor e do bônus de foto. Há restrição de um pedido em espera ou em revisão por criança e tarefa. |
| Atribuições | `AssignedTaskBatch` identifica criança e dia. `AssignedTask` pertence ao lote, pode referenciar uma tarefa e liga-se ao lançamento de crédito. `AssignmentPreset` e `AssignmentPresetItem` descrevem os lotes agendados. |
| Registro diário | `TaskCompletion` registra a conclusão de uma tarefa de catálogo por criança e dia. Essa identidade diária é mais restrita que uma ocorrência genérica de missão. |
| Resgates e poupança | `RewardRequest` liga criança e recompensa, guarda custo e decisão e limita pedidos simultâneos para o mesmo par. `Proposal`, `SavingsGoal`, `SavingsContribution`, `SavingsGoalEvent` e `GoalCompletionRequest` dão suporte a propostas, poupança e conclusão de metas. |
| Extrato | `LedgerEntry` pertence à criança e registra delta, saldo posterior, tipo, descrição, ator opcional, origem numérica e instante. O par entre tipo e origem não tem uma restrição geral de unicidade. |
| Raspadinhas | `LotteryTicket` pertence à criança e referencia lançamentos de compra e prêmio. `LotteryReminder` acompanha os lembretes semanais. |
| Outros | `PointGift`, `BirthdayAward`, `BirthDateChangeRequest`, `PushSubscription`, `FeedbackReport` e `BackupAuditEvent` registram os fluxos correspondentes. `Theme` é uma enumeração. |

A migração `0037_economy_foundation` adiciona metadados de operação,
data local e reversão ao extrato, três limites opcionais em `FamilySettings`
e `OccurrenceCredit` como registro único de XP por ocorrência. Os
lançamentos antigos ficam com os metadados novos vazios, e as solicitações
e atribuições antigas conservam os valores prometidos.
A migração `0038_mission_occurrences` introduz `MissionOccurrence`. Ela
registra estado, data local, checklist, valores e regra de aprovação da
execução. Pedidos e itens novos a referenciam. Lotes automáticos têm
unicidade por preset e data. O crédito permanece em `OccurrenceCredit`,
com a chave derivada do ID da ocorrência.

A migração `0039_consequence_episodes` adiciona `BehaviorCategory`,
`ConsequenceEpisode`, `RepairAction` e `GuardianMessage`. O episódio tem
um identificador de criação único por criança e um vínculo opcional com
um único débito do extrato. O estorno é obtido pelo vínculo de reversão
do próprio débito. Advertências, reparações e mensagens não dependem do
extrato nem de `OccurrenceCredit`.

A migração `0040_rpg_progression` adiciona o catálogo `LevelUnlock`,
a concessão única por perfil em `UnlockGrant` e o evento `LevelAdvance`,
vinculado ao primeiro crédito que atingiu o nível. `SkillPractice`
registra uma prática por habilidade e crédito. O nível é derivado do
XP de `OccurrenceCredit`, com fator configurável por família.

O histórico de moedas deve continuar conciliável com o saldo armazenado. As
instalações existentes podem conter saldos abaixo de zero e pedidos em estados
intermediários.

## Invariantes para o desenho futuro

- A identidade de uma ocorrência deve servir aos dois fluxos de entrada e impedir créditos repetidos mesmo com requisições concorrentes.
- A conclusão aprovada ou dispensada de aprovação deve gravar o estado, o XP e o crédito aplicável de moedas em uma transação. Registrar o valor configurado e o efetivamente creditado.
- O XP precisa de um histórico próprio. Qualquer início de XP para dados antigos exige uma decisão explícita sobre retroatividade.
- Estornos devem adicionar lançamentos compensatórios vinculados à origem. Para bilhetes legados sem lançamento de compra íntegro, definir tratamento administrativo antes de executar a migração.
- Preservar registros históricos, saldos, pisos configurados, pedidos em revisão e referências dos resgates legados. Validar cada migração tanto em uma base nova quanto em uma cópia anonimizada ou representativa de uma base existente.
