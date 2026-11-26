# Dívida técnica e verificação da Fase 0

## Decisões para as próximas fases

| Prioridade | Achado na base | Próximo passo |
| --- | --- | --- |
| P0 | Tarefas solicitadas, atribuídas e lançamentos diretos do responsável têm fluxos distintos de conclusão. | Definir a identidade da ocorrência, o instante em que a configuração de aprovação e o prêmio são fixados e como tratar atribuições já pendentes. Preservar revisão, reenvio e permissões dos cuidadores. |
| P0 | O extrato tem transações e proteções específicas por fluxo. O par tipo e origem não é, por si só, uma chave de idempotência global. | Projetar deduplicação por operação e concorrência em SQLite. Definir o corte diário no fuso familiar, fontes sujeitas aos limites de moedas e o efeito de estornos sobre os limites. |
| P0 | Os dois pisos de saldo atuais têm default de `-100`. Algumas rotas legadas usam o crédito disponível para autorizar resgates. | Aplicar o padrão zero apenas a instalações novas, conservar valores existentes e testar débitos, ajustes e resgates que cruzem o piso. |
| P0 | Os lançamentos manuais de penalidade não aplicam o piso pelo serviço de extrato, e a operação em lote aceita justificativa vazia. | Especificar o comportamento ao atingir o piso ou o limite diário e exigir justificativa nos fluxos de penalidade. |
| P0 | Os lembretes, as telas e os endpoints dependem do fluxo ativo de raspadinhas. | Remover as ações de compra e revelação, encerrar lembretes e devolver o preço pago de bilhetes em aberto uma vez, com lançamento compensatório. Preservar bilhetes já resolvidos e o histórico. |
| P0 | Localização brasileira, seleção de idioma e fuso já existem. O fallback e a seleção inicial de fuso ainda apontam para `Europe/Vilnius`. | Confirmar padrões para instalações novas e conferir os catálogos, e-mails, push, formatos, layouts e recorrências no fuso da família. |
| P1 | O PWA e as telas atuais já têm comportamento responsivo e temas. | Verificar em celular e tablet os fluxos infantis de leitura, foco, ajuda, checklist e feedback. Deixar som e movimento configuráveis. |
| Condicional | O singleton `FamilySettings` representa um único domicílio por instalação. | Manter esse modelo no MVP. Caso a distribuição do derivado passe a compartilhar uma instância entre famílias, desenhar isolamento antes de admitir esse cenário. |

## Licenças e autoria

- O código está sob a licença MIT de [`LICENSE`](../LICENSE). O aviso de copyright de KinKudos contributors deve acompanhar o derivado.
- [O template base](../templates/economy/base.html) credita Font Awesome Free 7.3.1. Segundo o aviso existente, ícones usam CC BY 4.0, fontes usam SIL OFL 1.1 e código usa MIT.
- Os PNGs em [`static/icons/`](../static/icons/) entraram no histórico local na importação inicial (`92bf4fa`). A revisão não encontrou atribuição individual que confirme a origem desses arquivos ou das capturas em [`docs/screenshots/`](screenshots/). Confirmar a procedência dos recursos e a autorização de uso da marca antes de publicar o derivado.

## Cobertura atual

[A suíte Django](../economy/tests/README.md) cobre modelos e serviços, autenticação, cuidadores, pareamento, permissões entre crianças, configuração, localização, PWA, fluxos infantis e parentais, evidências, raspadinhas, notificações, backups, implantação e execução em SQLite. Essa auditoria mapeia os cenários existentes. Ainda falta uma medição percentual de cobertura, e não houve verificação de interface em dispositivos reais.

As novas fases precisam de casos de corrida entre aprovações, repetição de requisições, aplicação dos limites na virada local do dia e atualização com dados legados. Para missões, testar também revisão e reenvio, conclusão sem aprovação, aprovação com recompensa zerada pelo limite diário de moedas e persistência do checklist.

## Validação da base

| Verificação | Resultado |
| --- | --- |
| Compose local | Configuração válida. Imagem construída com Python 3.12.13, migrações verificadas no build, traduções compiladas e arquivos estáticos coletados. A instância isolada iniciou e ficou saudável. `GET /health/` retornou a versão 26.8.4 e `GET /setup/` abriu em `pt-br`. |
| Verificação do Django | `manage.py check` passou na cópia de trabalho temporária. |
| Suíte na imagem de aplicação | 496 de 497 testes passaram com Python 3.12.13. O teste do instalador público precisa de `curl` e a imagem de aplicação não inclui esse comando. O instalador é executado no host. |
| Suíte no host | 497 de 497 testes passaram em cópia temporária com Python 3.13 e dependências compatíveis. A verificação de migrações também passou. |

O fluxo de validação das próximas fases deve começar com migrações e testes
na base atual, seguir para os cenários de upgrade com dados legados e, por
fim, verificar a interface em celular e tablet. O MVP pode usar a mesma
arquitetura de instalação, sem novos serviços obrigatórios.
