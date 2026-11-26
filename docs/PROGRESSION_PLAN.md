# Plano técnico da progressão RPG

A Fase 5 usa o XP que cada criança já acumulou para calcular seu nível e
conceder títulos e itens cosméticos. O cálculo parte do histórico existente
em `OccurrenceCredit`, o mesmo que alimenta o total de XP mostrado no
painel infantil. A atualização conserva esse histórico, inclusive créditos
obtidos quando o limite de moedas reduziu o pagamento a zero.
[Serviço de crédito](../economy/services.py) · [Modelo de dados](DATABASE.md)

## Curva e cálculo do nível

A curva inicial exige `B × nível atual` de XP para subir um nível, com
`B = 100`. O XP acumulado necessário para chegar ao nível `L` é
`B × L × (L − 1) / 2`. O nível atual é o maior `L` cujo limiar cabe
no total de XP. Usar aritmética inteira, com raiz inteira ou busca
binária, para respeitar os limiares exatos mesmo em níveis altos.
O nível começa em 1 e a curva continua além dos níveis com recompensas.

O painel mostra o nível, o XP obtido desde seu limiar e o XP faltante
até o próximo. Com 140 XP na curva inicial, a criança está no nível 2,
com 40 de 200 XP no nível atual e 160 XP faltando para o nível 3.
Uma missão pode atravessar vários limiares numa única conclusão.

Proposta para configuração: guardar um fator positivo por família e
permitir que o responsável o ajuste enquanto todos os perfis ainda
estiverem no nível 1 e sem desbloqueios acima dele. Essa regra evita
reduzir níveis ou distribuir recompensas antecipadas por uma mudança
de curva no meio da progressão. Se for preciso alterar curvas após
esse ponto, primeiro definir como versioná-las e preservar os níveis
já alcançados.

## Títulos e itens

- Criar um catálogo de desbloqueios com identificador estável, tipo
  (título ou item), nome traduzível, nível mínimo e estado ativo.
  Arquivar uma entrada interrompe novas concessões e mantém as que
  já ocorreram.
- Gravar cada concessão com criança, item ou título, nível exigido e
  data da concessão. Uma restrição única por criança e desbloqueio
  impede duplicação. Desbloquear todos os itens elegíveis, inclusive
  os de níveis intermediários atravessados de uma vez.
- Mostrar os desbloqueios no perfil infantil. A Fase 5 pode entregar
  um catálogo inicial simples, como o título Aprendiz no nível 1, o
  título Aventureiro no nível 3 e uma capa cosmética no nível 5.
  Compra fica para a Fase 6. Editor, inventário e equipar itens ficam
  para a Fase 7. Concessões precisam poder ser consultadas por essas
  fases sem consultar o extrato de moedas.
- Classes terão efeito visual e narrativo. Habilidades podem ser
  marcadas no catálogo de missões e copiadas para a ocorrência, com
  contagem por atividade concluída e habilidade. Elas representam
  atividades praticadas, sem bônus de moeda, XP extra ou notas de
  comportamento. Um crédito repetido também não repete a contagem.

## Integração e atualização

1. Implementar uma função de cálculo reutilizável e uma operação de
   concessão a partir do XP acumulado. Usar os créditos existentes
   como fonte de verdade. O nível pode ser calculado na leitura,
   sem uma segunda coluna de saldo nesta fase.
2. Na atualização, avaliar todas as crianças com a curva inicial,
   inclusive perfis com XP zero, e conceder os desbloqueios já
   alcançados. O catálogo inicial e as concessões devem suportar
   repetição da atualização. Atribuir a data da concessão no
   momento do processamento e preservar as datas dos créditos de XP.
   A reconciliação inicial fica silenciosa.
3. Quando uma ocorrência recebe seu primeiro crédito, calcular nível
   anterior e atual, conceder os desbloqueios em uma transação e
   registrar um evento de avanço vinculado ao crédito. Após o commit,
   emitir uma notificação resumida de avanço e novos desbloqueios,
   mesmo se a criança subir vários níveis. Repetições de requisição
   e reconciliação de catálogo não emitem outro evento.
4. Usar a unicidade e as transações existentes no SQLite para impedir
   concessões concorrentes. Falha de gravação desfaz a operação
   transacional. Falha na notificação mantém XP e concessões
   persistidos, com o resultado disponível no painel.

Consequências e estornos movimentam apenas moedas quando aplicável.
O cálculo do nível e as concessões usam o XP e não sofrem redução nesses
fluxos. Dias sem tarefas mantêm o progresso.

## Critérios de aceite

- Conferir XP zero, primeiro limiar, um ponto abaixo e acima de um
  limiar e valores muito altos. Comparar com os níveis 2, 3, 5, 10 e
  20 da tabela do roadmap.
- Atualizar uma instalação com XP acumulado, rerodar a reconciliação
  e verificar que saldos, extrato e créditos permanecem iguais e
  que os desbloqueios aparecem uma única vez.
- Simular crédito simultâneo, aprovação repetida, avanço de vários
  níveis, crédito com zero moedas, estorno e consequências. Conferir
  que a criança mantém o nível e os cosméticos adquiridos.
- Verificar alterações permitidas e bloqueadas da curva, a visibilidade
  por criança e a leitura do painel em celular e tablet. Permitir
  acompanhar o progresso sem depender de sons ou animações.


## Entrega da Fase 5

A migração `0040_rpg_progression` concede os desbloqueios dos níveis já
alcançados com o fator inicial 100. Os perfis novos recebem os
desbloqueios ativos de nível 1. A reconciliação pode ser repetida com
`python manage.py reconcile_progression` e não envia avisos de avanço.

O painel infantil mostra o nível, o XP até o próximo nível, os títulos e
cosméticos, a classe selecionada e as habilidades praticadas. O catálogo
inicial concede Aprendiz no nível 1, Aventureiro no nível 3, Capa de aventura
no nível 5, Exploradora no nível 10 e Guardião no nível 20. Classes têm
símbolo e descrição e não alteram a economia. A contagem de habilidades
parte do momento em que as missões passaram a registrar suas marcações.
O histórico anterior fica intacto, sem inferir habilidades pelo nome da tarefa.

Em **Configurações → Progressão do personagem**, responsáveis podem editar
o fator enquanto todos os perfis permanecerem no nível 1 e arquivar ou
restaurar entradas do catálogo. Restaurar reconcilia concessões elegíveis
sem reenviar avisos. O cosmético concedido pode ser consultado, e equipá-lo
permanece na Fase 7.

A suíte completa passou com 535 testes. A atualização de `0039` para
`0040` preservou saldos, extrato e XP. A reconciliação repetida manteve uma
única concessão por item. Duas requisições SQLite concorrentes produziram
um único crédito e um único avanço do nível 1 ao 5. O conteúdo do push
foi conferido em português brasileiro sem enviar a um dispositivo real.
As seções de progressão foram conferidas no Firefox a 390 e 810 pixels.
