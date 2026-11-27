# Plano técnico de inventário e personalização

A Fase 7 dá à criança um espaço para ver seus itens, experimentar combinações
e escolher o que aparece no personagem. Títulos, roupas e outros cosméticos
já concedidos por nível ou comprados devem aparecer na primeira visita. A
criança pode equipar, trocar e desequipar sem aprovação e sem custo.

## Propriedade e catálogo

- Usar `UnlockGrant` como fonte de propriedade. O par criança e desbloqueio
  já é único. `purchase_entry` identifica a compra e `required_level` guarda
  o nível exigido quando a concessão veio da progressão. O inventário lê
  as concessões do perfil em sessão e apresenta a origem disponível.
- Usar `LevelUnlock` para os metadados de apresentação. Acrescentar um slot
  opcional e uma chave de recurso visual do aplicativo. A categoria de
  `VirtualOffer` organiza a vitrine. O slot do item permanece disponível
  se a oferta for arquivada. Traduzir nomes e rótulos pelo catálogo atual.
- Manter visíveis e equipáveis as concessões existentes quando uma oferta
  for arquivada ou um desbloqueio deixar de ser concedido. A propriedade
  também independe do saldo, do bloqueio de resgates por tarefas e da
  disponibilidade da loja real.
- Proposta para a raridade cosmética: usar uma classificação fixa no
  catálogo, com padrão **Comum** e opção **Raro**. Exibir em texto nos
  detalhes. A classificação é editorial e não altera preço, atributos
  ou regras de concessão.

[Catálogo e concessões](../economy/models.py) · [Progressão RPG](PROGRESSION_PLAN.md) · [Loja de recompensas](REWARD_SHOPS_PLAN.md)

## Slots e migração

| Slot | Itens iniciais |
| --- | --- |
| Título | Aprendiz, Aventureiro, Exploradora e Guardião |
| Cabeça | Chapéu estrelado |
| Corpo | Túnica de viagem |
| Mão principal | Cajado de cristal |
| Mão secundária | Escudo de madeira |
| Capa | Capa de aventura e Capa da floresta |
| Acessório | Pingente de bússola |
| Decoração | Lanterna de acampamento |
| Tema do personagem | Tema céu estrelado |
| Mascote | Raposa companheira |

Preencher o mapa por códigos estáveis em uma migração após
`0041_reward_shops`, sem depender do nome traduzido. Entradas sem slot
conhecido aparecem na coleção com o estado **Sem encaixe** até que recebam
um mapeamento explícito. Cada perfil começa com os slots vazios, incluindo
o de título. A migração conserva os identificadores e as origens das
concessões, os perfis e o histórico da economia.

Persistir apenas escolhas equipadas em um modelo proposto
`EquippedCosmetic`, com chaves para `ChildProfile` e `UnlockGrant` e um
slot. Garantir no banco a unicidade por perfil e slot e por concessão
equipada. Validar no serviço que a concessão pertence ao perfil e que o
slot corresponde ao catálogo. A ausência de registro representa um slot
vazio. Ao remover um encaixe do catálogo em manutenção futura, limpar
sua seleção de forma explícita e preservar a concessão.

## Tela do personagem

1. Dar acesso a **Meu personagem** pelo painel infantil. Usar uma prévia
   com o título ativo e os cosméticos equipados, junto das opções de
   classe e aparência. Reaproveitar o seletor de classe e sua persistência
   em `ChildProfile.character_class`. Proposta de aparência inicial com
   algumas bases visuais do próprio aplicativo e uma base padrão,
   persistida em um campo próprio do perfil com opções validadas.
2. Agrupar a coleção por slot com rótulos curtos e estado **Equipado** em
   texto. Oferecer **Experimentar**, **Equipar** e **Desequipar**. A prévia
   só altera a composição da tela. Ao confirmar uma troca, mostrar qual
   item entrou. Se o slot ficar vazio, voltar à apresentação padrão.
3. Mostrar o título equipado no painel infantil e incluir um atalho para
   a coleção após uma compra virtual. Usar recursos locais do aplicativo
   e fallback por texto ou ícone se faltar uma imagem. O tema equipado
   controla o fundo da prévia e a decoração aparece nesse fundo. A
   preferência de tema do aplicativo, inclusive sua alternância diária,
   e a foto do perfil continuam pelos fluxos existentes.
4. Usar a raposa como companhia visual estática. A Fase 10 poderá evoluir
   suas interações. O inventário aceitará concessões futuras por
   conquistas. A Fase 11 definirá os critérios, a origem registrada e
   a concessão desses itens.

Manter a interface em português brasileiro e usar cartões com nomes
legíveis, foco visível e alvos de toque confortáveis. Mostrar o que mudou
por texto e permitir o uso por teclado e leitor de tela. Ações de
equipar e desequipar devem funcionar com formulários Django mesmo com
JavaScript desativado. O fluxo dispensa sons, animações obrigatórias,
cronômetros e convites de compra dentro da coleção.

[Painel infantil](../templates/economy/child_dashboard.html) · [Ações do perfil](../economy/views/child.py)

## Gravação e sincronização

- Usar a sessão infantil existente com `child_required`. Obter a criança
  de `request.child` e consultar a concessão pelo par perfil e ID.
  Responder com 404 para uma concessão de outro perfil ou inexistente.
  Aplicar POST com CSRF para equipar e desequipar e redirecionar para a
  coleção com feedback traduzido.
- Aplicar a troca em uma transação. Equipar novamente a mesma concessão
  mantém uma única escolha. Trocas simultâneas no mesmo slot resultam
  na última gravação válida. Ao desequipar, remover apenas a concessão
  indicada se ela ainda estiver no slot. Um formulário antigo não deve
  retirar um item que outro dispositivo equipou depois.
- Incluir os pares slot e concessão e a base visual selecionada no
  estado de atualização do painel infantil (`child_state`). A prévia local
  não entra nesse estado. Uma navegação ou atualização deve mostrar a
  seleção persistida, inclusive em outro dispositivo do mesmo perfil.

[Sessão infantil](../economy/auth.py) · [Banco de dados](DATABASE.md)

## Critérios de aceite

- Migrar uma base representativa da Fase 6 com título e capa por nível
  e um item comprado. Conferir a propriedade e a origem, os slots vazios
  iniciais, a foto, a classe, o saldo, o XP e o extrato.
- Equipar título e capa por nível, trocar a capa por outra comprada e
  desequipá-la. Conferir a prévia sem gravação, a persistência após
  recarregar e a atualização do painel em outro dispositivo.
- Arquivar uma oferta e um desbloqueio e conferir que a criança ainda
  pode equipar o que adquiriu. Repetir com saldo negativo, resgates
  bloqueados por tarefas e loja real desativada. Conferir que cada ação
  altera apenas o estado visual, sem lançamentos ou mudanças de XP.
- Testar perfil vizinho, sessão expirada, slot incompatível, item sem
  mapeamento, POST repetido e trocas concorrentes. Verificar que um
  desequipamento atrasado preserva a escolha mais recente.
- Conferir em celular e tablet com pt-BR, teclado e leitor de tela,
  incluindo coleção vazia, nomes longos e recurso visual ausente.

## Entrega da Fase 7

O painel infantil abre **Meu personagem** e exibe o título equipado.
Após a compra virtual, a criança vai diretamente para a coleção. A
prévia usa uma leitura autenticada e permite confirmar a escolha ou
encerrar a experiência. Os formulários de equipamento funcionam sem
JavaScript. Classe e aparência são gravadas no perfil. A aparência tem
três opções de cor e usa Violeta como padrão. O tema e a decoração
equipados aparecem no cenário da prévia, junto à raposa estática.

A migração `0042_character_inventory` usa o catálogo existente. A
verificação de atualização de uma base SQLite da Fase 6 preservou
concessões, referências de compra, foto, classe, saldo, piso, XP e
extrato. Duas transações concorrentes produziram uma única escolha
no slot da capa. Uma remoção atrasada preservou a capa selecionada.

A suíte completa passou com 553 testes. Os 45 testes focados passaram
após os ajustes finais de navegação. O fluxo em pt-BR foi conferido
no Chromium com JavaScript desativado, navegação por teclado e
inspeção da árvore de acessibilidade a 390 e 810 pixels.

## Ilustrações dos cosméticos

O conjunto tem nove ilustrações transparentes e um cenário em WebP.
Cada imagem usa a chave visual já gravada no catálogo. A coleção
usa as mesmas imagens que a prévia, onde os itens aparecem em
camadas no personagem ou no cenário. A raposa permanece estática.
[Arquivos WebP](../static/character/cosmetics/)

<details>
<summary>Prompts usados na ferramenta integrada de geração de imagens</summary>

**Folha de sprites**

> Use case: illustration-story. Create one production sprite atlas for KinKudos, a cozy children's fantasy RPG paper-doll character. Precisely 3 columns by 3 rows, nine distinct isolated transparent game sprites on one square image. Each sprite is centered within its own equal square cell, has clearance from all its cell edges, and occupies roughly 60–73% of its cell. From left to right, top to bottom: 1 midnight indigo floppy wizard hat with a small bright gold star pin, viewed straight from front with wide flat lower brim; 2 upright dark wooden magic staff with luminous violet crystal at top and small brass binding, tall slender, tip to toe fully visible, slight tilt only; 3 raspberry-burgundy short adventurer cape with golden shoulder clasps, front view as if viewed without wearer, broad flowing fabric with open neck; 4 deep forest green short cloak with leaf clasp, front view, distinct flared draped silhouette fitting the shoulders; 5 teal travel tunic with light stitching and leather belt, front view, arms very short, clean square torso fit; 6 oval walnut shield with copper rim and central gold stud, three-quarter view; 7 antique golden compass pendant with a small loop and blue needle; 8 warmly lit amber camp lantern standing on its own, copper handle; 9 sitting orange fox companion, white chest and big curled tail, facing slightly left. Style: cohesive hand-painted vector-like game illustrations with crisp silhouettes, dark plum outlines, restrained highlights, minimal texture and readable at 45 pixels. Front-lit, no drop shadows outside silhouettes, same visual scales within cell. True fully transparent negative space and gutters, no gridlines, no scene, no labels, text, characters, frames, tiles, or extra objects. Keep all nine real cell boundaries perfectly regular.

**Tema céu estrelado**

> Use case: illustration-story. Create one original wide horizontal game backdrop for a cozy children's fantasy RPG paper-doll preview, an open grassy clearing under a starry lavender-blue night sky, small warm crescent moon high at the right, softly layered indigo hills, sparse pine silhouettes mainly near edges. Keep the middle of the frame calm and the center bottom clear so a separate character, lantern and fox sprites can be overlaid. Crisp broad illustrated shapes with a children's storybook palette of plum, lilac and midnight teal, restrained contrast in the center, sparse small gold stars. Edge-to-edge landscape, no framing, no character, no lantern, no fox, no text, no logo.

</details>
