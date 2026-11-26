# Auditoria da Fase 1 — Português brasileiro e fuso familiar

Base auditada no commit `fa04585` da `translation/pt-br`. A revisão usou
uma cópia temporária com dados sintéticos, o cliente HTTP de testes do Django,
captura de payloads de push e uma caixa de e-mails em memória. O catálogo
existente em [`locale/pt_BR/messages.json`](../locale/pt_BR/messages.json)
foi compilado com o script do projeto. Nenhum código, teste ou catálogo da
aplicação foi alterado.

## O que foi validado

| Área | Resultado |
| --- | --- |
| Telas | Configuração inicial, login de responsável, seleção da criança e painéis do responsável e da criança renderizaram em `pt-br`. A tela de recuperação também abriu em português com disponibilidade de SMTP simulada. O seletor de fuso ofereceu `America/Sao_Paulo`. |
| Idioma e catálogo | A seleção de idioma usa a preferência da família e permite escolha por navegador. A compilação processou 1.376 entradas no catálogo brasileiro. Uma extração estática de chamadas literais simples em Python e tags de tradução dos templates identificou 1.260 chaves distintas. Destas, 1.259 tinham entrada preenchida e 21 entradas coincidiam com o texto de origem, incluindo nomes próprios e siglas. Essa contagem não cobre texto dinâmico, literais sem marcação, JavaScript nem todas as formas de gettext. |
| Validação e e-mail | A recuperação com endereço inválido exibiu “Informe um endereço de email válido.”. A recuperação válida gerou uma mensagem na caixa em memória com o assunto “Família – reset de senha”. |
| Push | Uma aprovação no contexto `pt-br` produziu “Sua tarefa foi aprovada” e “Organizar a mochila: +5 pontos”. A entrega ao dispositivo não foi exercitada. |
| Data e hora | Um evento de `10/08/2026 02:59 UTC` apareceu às `23:59` do dia 9 nos históricos dos dois painéis. O painel infantil mostrou `08-09 23:59` e o parental mostrou `2026-08-09 23:59`. O fuso foi aplicado e os formatos continuaram fixos. |
| Recorrência | Com São Paulo configurado na família, o agendador criou um lote diário às `02:59 UTC` de 10/08/2026, ainda domingo local. Às `03:00 UTC`, já segunda-feira local, criou um novo lote diário e um semanal. Às `03:01 UTC`, a repetição manteve os dois lotes da segunda-feira. O endpoint de estado da criança mudou de assinatura na virada. |

## O que falta

| Achado | Trabalho a fazer |
| --- | --- |
| O painel infantil exibe “Requested birthday change…” em inglês para uma alteração de aniversário pendente. O catálogo não tem a chave com as quebras e os espaços emitidos pelo bloco. | Corrigir a extração ou normalização desse bloco e revisar os termos parcialmente traduzidos, como “reset de senha”. Preservar textos inseridos pela família. |
| Os pushes agendados de atribuição saíram em inglês quando o processo estava em inglês, com a família em `pt-br`. Os pushes disparados por requisições usam o idioma ativo de quem executa a ação. A inscrição de push não guarda idioma. | Definir o idioma das notificações por destinatário ou usar o padrão da família como regra explícita. Aplicá-lo ao construir o payload, inclusive em processos agendados. Conferir convites e feedback, que também geram mensagens no contexto da requisição. |
| Os históricos usam formatos fixos e o JSON do status de backup devolve timestamps formatados sem converter ao fuso familiar. Na simulação, `02:59 UTC` continuou `02:59` no status. | Padronizar formatos localizados para leitura e converter timestamps de backup ao fuso familiar. Preservar ISO nos valores de formulário, atributos de máquina e APIs que dependam desse contrato. |
| A manutenção diária usa o fuso global para aniversários e troca de temas. O crédito de aniversário foi reproduzido às `02:59 UTC` do dia 10, quando em São Paulo ainda era dia 9. | Ativar o fuso familiar na manutenção e cobrir a virada do dia e a execução em instalações atualizadas. A rotina de atribuições já ativa o fuso familiar. |
| O Compose local inicia com `pt-br`. O Django usa inglês como fallback de idioma e `Europe/Vilnius` como fallback de fuso. O assistente permite escolher São Paulo, mas o valor inicialmente selecionado é Vilnius. O formulário familiar atual não oferece edição de fuso ou idioma padrão após o setup. | Definir os padrões das novas instalações do derivado e um caminho para mudar as preferências familiares depois da instalação, preservando as escolhas existentes. |
| A revisão abrangeu HTML renderizado e notificações simuladas. | Conferir visualmente celular e tablet, incluindo diálogos, textos longos, datas e troca de idioma. Validar Web Push e SMTP com uma instalação de teste e dispositivos reais. |

A execução de `run_maintenance` também falhou depois de processar o
aniversário, ao chamar `Session.objects.clear_expired()` no Django 5.2.17.
Isso é um defeito da base encontrado durante a auditoria. A correção fica
fora desta etapa de documentação.

O teste de virada cobre atribuições diárias e semanais. Os testes existentes
também exercitam dias selecionados e fim de semana. Recorrência mensal
pertence à evolução das missões na Fase 3.

## Resultado dos testes

A suíte completa passou com 497 testes no host, usando Python 3.13 e Django
5.2.17. Os 16 testes de push também passaram isoladamente. Ao executar
`test_language_service_worker` antes de `test_push`, cinco verificações de
texto falharam porque receberam lituano quando esperavam inglês. A reprodução
indica dependência do idioma ativo entre os módulos. Isolar o idioma nos testes
de push e verificar a restauração do contexto ao fim das requisições.

## Correções implementadas na Fase 1

- O assistente e o comando de configuração usam `pt-br` e `America/Sao_Paulo` em novas instalações. O idioma ainda pode ser definido por `KINKUDOS_DEFAULT_LANGUAGE`. Os fallbacks do Django foram preservados para instalações antigas sem preferências gravadas.
- As preferências no painel parental permitem trocar o idioma padrão e o fuso da família. Uma opção explícita do navegador continua tendo precedência para a interface.
- O histórico e o status de backup exibem datas no locale ativo e horários no fuso familiar. Datas de calendário, como aniversários, permanecem datas civis.
- Push, convite de cuidador e e-mail de feedback usam o idioma da família quando configurado. O e-mail de recuperação usa o idioma da solicitação. O aviso de alteração de nascimento e os textos de redefinição de senha foram corrigidos no catálogo existente.
- O agendador e a manutenção diária ativam o idioma e o fuso da família. A limpeza de sessões agora usa o comando `clearsessions` do Django. O middleware restaura o idioma e o fuso ao fim da requisição.

A validação em base descartável confirmou o crédito de aniversário após a
meia-noite de São Paulo, os lotes diários e semanais sem repetição, o histórico
e o status de backup em `09/08/2026 23:59` e o push agendado em português com
o processo iniciado em inglês. A inspeção em Firefox usou HTML renderizado e
larguras de 390 e 810 px para as configurações parentais, além de 390 px para
o painel da criança. A entrega real por Web Push e SMTP em dispositivos
continua pendente. A suíte completa passou com 502 testes e a verificação de
migrações não apontou alterações.
A execução direcionada que antes reproduzia a dependência de ordem passou
com 29 testes, rodando o módulo de idioma antes do módulo de push.
