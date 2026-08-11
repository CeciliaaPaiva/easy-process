# S12-01 — Investigação com casos reais

**Método:** 6 transcrições reais e variadas, já existentes no banco de dev (processos gerados anteriormente por usuárias reais testando a plataforma, não fixtures sintéticas de teste automatizado), rodadas de novo — chamada real ao Gemini, modelo atual (`gemini-3.1-flash-lite`) — contra o `BpmnGeneratorService` **sem nenhuma mudança de código**, pra ter uma baseline real antes de qualquer alteração desta sprint. Custo: 6 chamadas ao modelo "lite", frações de centavo.

## Casos usados

| Caso | Domínio | Atores na transcrição |
|---|---|---|
| Processo de compra Unika | E-commerce de semijoias | 1 (Empreendedora) |
| pedido pelo app | Delivery (iFood) | 3 (Cozinha, Entregador, Sistema iFood) |
| Pedidos pelo iFood | Delivery (iFood, variação) | 3 (Cozinheiro, Atendente, Entregador) |
| Produção sob encomenda | Manufatura (amplificadores) | 2 (Cliente, Equipe de Produção) |
| marketing e vendas | Varejo/marketing | 2 (Designer Gráfico, Vendedor) |
| Gravação de áudio | Delivery de comida (Coxinha da Elisa) | 2 (Cliente, Aplicativo) |

## Resultado bruto

| Caso | Gateways usados | Tipos de atividade usados | Pool/raia | Anotação |
|---|---|---|---|---|
| Processo de compra Unika | nenhum | userTask×4, serviceTask×1, receiveTask×1 | não | não |
| pedido pelo app | exclusive×1, parallel×2 | manualTask×3, userTask×1, serviceTask×1, sendTask×1 | **não** | não |
| Pedidos pelo iFood | exclusive×1, parallel×1 | manualTask×2, userTask×1, serviceTask×2 | **não** | não |
| Produção sob encomenda | nenhum | manualTask×1, userTask×1, businessRuleTask×1 | **não** | sim (1) |
| marketing e vendas | exclusive×1 | manualTask×1, userTask×2 | **sim** (laneSet, 2 lanes) | não |
| Gravação de áudio | exclusive×1 | manualTask×1, userTask×2, serviceTask×1 | **não** | não |

## Achados catalogados

### 1. Tipagem de atividade — funcionando bem (não é prioridade)
Todos os 6 casos usam tipos específicos (`userTask`/`manualTask`/`serviceTask`/`businessRuleTask`/`sendTask`), nunca caem no `bpmn:task` genérico. As melhorias de prompt da S9 parecem ter resolvido esta parte — **não é o gargalo atual**, ao contrário do que o relato original sugeria. Vale confirmar semanticamente (o tipo escolhido bate com a descrição?) antes de descartar de vez, mas não é prioridade de esforço agora.

### 2. Pools/raias — "IA nunca tenta", confirmado com exemplo concreto
Só 1 de 6 casos usa `laneSet`/`lane` (marketing e vendas — 2 atores da mesma organização, corretamente modelados como raias). **Nenhum dos casos usa `bpmn:participant` como pool "caixa preta"** para atores externos, mesmo quando a transcrição descreve claramente um ator externo:

- **"pedido pelo app"**: a própria IA identificou corretamente 4 atores na lista (`actors: [Cliente, Equipe da Cozinha, Sistema iFood, Entregador]`) — mas o XML gerado achata tudo em um processo único, sem `participant`/`laneSet` nenhum. `Cliente` (claramente externo, do lado de fora do restaurante) e `Sistema iFood` (sistema de terceiros) deveriam no mínimo ser um pool externo trocando mensagem com o processo interno da cozinha.
- Mesmo padrão em "Pedidos pelo iFood", "Produção sob encomenda" e "Gravação de áudio" — todos têm um ator claramente externo (Cliente, ou sistema de terceiros) nunca modelado como pool separado.

**Isso é o achado de maior prioridade** — confirma exatamente o que a stakeholder relatou ("nunca cria pools caixa-preta para atores externos"), com reprodução concreta. A informação (lista de atores) já está correta na saída da IA — o problema é estrutural, na tradução pra XML, o que reforça a tese da decomposição análise→modelagem: a "análise" já sabe quem são os atores e provavelmente já consegue classificar interno/externo se perguntada diretamente; o problema é a modelagem em XML não usar essa informação.

### 3. Gateways — parcialmente correto, com um bug de nuance encontrado
3 de 6 casos usam gateway; os 2 casos sem gateway foram inspecionados manualmente e a ausência é **correta** (transcrições sem decisão condicional explícita — "Processo de compra Unika" é um fluxo linear, "Produção sob encomenda" é mais uma narrativa estratégica do que um processo operacional passo a passo). Sem falso positivo aqui.

Porém, no XML de "pedido pelo app", achado um erro de nuance: `Gateway_SplitEntrega` é um `bpmn:parallelGateway` (divisão paralela) com **uma única saída** (`Task_AguardarEntregador`). Um gateway paralelo de divisão só faz sentido com 2+ saídas simultâneas — com uma saída só, ele não deveria existir (o fluxo deveria seguir direto, sem gateway). É um padrão estrutural detectável e validável (mesmo estilo do `_find_combined_gateway` já existente para o bug da S10).

### 4. Anotações — subutilizadas, mas não claramente errado
Só 1 de 6 casos tem anotação. A regra pede uso "com moderação", então não dá pra afirmar que é erro sem mais casos — fica como observação, não prioridade.

## Conclusão — prioridade pra S12-02/03/04

1. **Maior prioridade, categoria "nunca tenta":** pool/raia para atores externos. Vira checagem estrutural em S12-03 (ex: se a análise identificar um ator com características de "externo" e o XML não tiver `participant` correspondente, reprovar e pedir retry) — não dá pra resolver só com regra de prompt melhor, porque a regra de prompt **já existe** e já está sendo ignorada.
2. **Segunda prioridade, categoria "erra a nuance":** gateway paralelo/inclusivo com menos de 2 saídas de divisão (ou menos de 2 entradas de junção). Vira checagem estrutural nova em `bpmn_validator.py`, mesmo padrão do gateway combinado.
3. **Baixa prioridade agora:** tipagem de atividade (já parece funcionar) e anotações (amostra pequena demais pra concluir).

Isso confirma a decomposição de S12-02 (separar análise de modelagem) como o passo estrutural certo: a análise já identifica os atores corretamente (a informação existe), o problema está na tradução para XML — exatamente o tipo de erro que uma etapa de modelagem dedicada, validada estruturalmente, resolve melhor do que ajustar o prompt único de hoje.
