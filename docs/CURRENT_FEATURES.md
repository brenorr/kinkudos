# Funcionalidades atuais

Auditoria da Fase 0 sobre o KinKudos no commit `fa04585`.

| Fluxo | Comportamento verificado no código |
| --- | --- |
| Configuração inicial | O assistente cria a família e o primeiro administrador. Idioma e fuso são selecionáveis. SMTP é opcional. |
| Autenticação | Responsáveis usam conta Django. Crianças usam PIN Argon2, normalmente em navegador ou PWA pareada. Cuidadores entram por convite temporário e atuam apenas sobre crianças autorizadas. |
| Tarefa solicitada pela criança | A criança envia uma tarefa do catálogo, com nota e evidência conforme o fluxo. O responsável pode aprovar, recusar ou pedir correções. O reenvio conserva o pedido. A aprovação credita os pontos e eventual bônus de foto. |
| Tarefa atribuída | O responsável ou cuidador autorizado cria um lote diário. A tarefa guarda título, nota e valor da atribuição. A conclusão no dia credita pontos imediatamente. Há cancelamento, expiração e lembretes. |
| Recorrência | Presets configuram execução diária, dias selecionados, fim de semana ou dia semanal. O agendador materializa os lotes usando o horário local da família. |
| Pontos | Há saldo por criança, piso configurável, lançamentos históricos, ajustes, presentes e bônus. O serviço atualiza saldo e extrato na mesma transação. |
| Penalidades | O adulto autorizado pode lançar penalidade por modelo ou pelo fluxo individual, com débito no extrato. Regras futuras de advertência, reparação, limites e estorno precisam de desenho próprio. |
| Resgates e metas | A criança solicita uma recompensa do catálogo. O custo é registrado na solicitação e debitado após aprovação. Recusa e cancelamento encerram um pedido sem débito prévio. A aplicação também possui propostas e metas de poupança. |
| Raspadinhas | Compra e revelação são operações distintas. O preço é debitado na compra, e eventual prêmio é creditado na revelação. Há configuração por família e criança e lembretes agendados. |
| PWA e localização | Manifesto, service worker, Web Push, temas e seleção de idioma já existem. O fork inclui catálogo brasileiro e o Compose local inicia em português. O fuso configurado é ativado nas requisições e nas rotinas agendadas. |
| Operação | Verificação de saúde, migrações, backup e restauração, auditoria administrativa e fluxo de atualização já fazem parte da base. |

Os testes de configuração e troca de idioma incluem casos com `pt-br` e
`America/Sao_Paulo`. A revisão integral de textos, e-mails, push, formatos de
data e recorrências na virada do dia pertence à Fase 1.

## Recorte do MVP derivado

- Evoluir os fluxos atuais de tarefas para missões com aprovação configurável por tarefa, exigida por padrão.
- Creditar XP e moedas após aprovação, ou na conclusão de uma tarefa dispensada de aprovação.
- Reaproveitar os pontos como moedas e preservar saldos, pisos configurados e histórico.
- Retirar as raspadinhas com tratamento de bilhetes ainda não revelados.
- Manter o resgate legado por compatibilidade e adiar as novas funções da loja real.
- Priorizar uma etapa clara por vez, pedido de ajuda e estímulos opcionais na experiência infantil.
