"""Regras semânticas de modelagem BPMN 2.0 compartilhadas entre o gerador
inicial e o refinador via chat — mantidas em um único lugar para não
divergirem entre os dois prompts."""

SEMANTIC_MODELING_RULES = """\
REGRAS SEMÂNTICAS DE MODELAGEM BPMN — siga com precisão, não use sempre os
mesmos elementos genéricos:

1. TIPOS DE GATEWAY — escolha o tipo certo pela lógica da decisão, nunca use
   sempre exclusiveGateway:
   - bpmn:exclusiveGateway (XOR, ◇ com X): UM caminho é seguido, mutuamente
     exclusivo — "se aprovado... senão...".
   - bpmn:parallelGateway (AND, ◇ com +): TODOS os caminhos seguem ao mesmo
     tempo, sem condição — atividades que acontecem em paralelo.
   - bpmn:inclusiveGateway (OR, ◇ com O): UM OU MAIS caminhos são seguidos
     conforme condições independentes entre si.
   Todo gateway de divisão (split) com mais de uma saída condicional deve ter
   um gateway de junção (join) correspondente do MESMO tipo mais adiante,
   salvo quando um dos caminhos termina em endEvent.

2. TIPOS DE ATIVIDADE — escolha pelo modo de execução descrito na
   transcrição/instrução, nunca use apenas bpmn:task genérico quando o modo
   for identificável:
   - bpmn:manualTask: trabalho físico/manual, sem uso de sistema (ex:
     "confere o documento fisicamente", "empacota o produto").
   - bpmn:userTask: uma pessoa realiza a atividade interagindo com um
     sistema/software (ex: "preenche o formulário no sistema", "aprova o
     pedido na tela").
   - bpmn:serviceTask: executada automaticamente por um sistema, sem
     intervenção humana (ex: "o sistema calcula", "envio automático de
     e-mail", integração/API).
   - bpmn:businessRuleTask: aplicação de uma regra de negócio/política
     definida (ex: "aplica a tabela de desconto", motor de regras).
   - bpmn:sendTask / bpmn:receiveTask: envio ou recebimento explícito de uma
     mensagem entre participantes.
   - bpmn:task (genérico): só use quando o modo de execução não estiver claro
     na descrição.

3. POOLS (bpmn:participant) vs RAIAS (bpmn:lane) — não confunda os dois:
   - Uma RAIA (lane) representa um papel/departamento/pessoa DENTRO do MESMO
     processo, na MESMA organização — use quando os atores da transcrição
     colaboram no mesmo fluxo (ex: "Analista", "Gerente", "Financeiro" do
     mesmo processo). Modele como UM ÚNICO bpmn:participant contendo um
     bpmn:laneSet com uma bpmn:lane por ator, cada bpmn:lane com
     bpmn:flowNodeRef listando os ids dos elementos daquele ator.
   - Um POOL (participant) SEPARADO representa uma organização/sistema
     DIFERENTE, externa ao processo modelado, que troca mensagens com ele
     (ex: "Cliente", "Sistema de pagamento externo", "Fornecedor"). Use um
     bpmn:participant adicional SEM laneSet e SEM elementos internos
     detalhados (um pool "caixa preta" — bpmn:participant com processRef
     vazio ou omitido), conectado ao pool principal por bpmn:messageFlow.
   - Se a transcrição descrever só um processo com um único ator ou não
     mencionar atores distintos, NÃO force pools/raias — um processo simples
     sem participant é válido e preferível.

4. ANOTAÇÕES (bpmn:textAnnotation) — adicione para tornar o processo mais
   didático: explique critérios de decisão em gateways (ex: "Valor > R$
   1000?"), regras de negócio aplicadas, exceções, ou pontos que a
   transcrição deixou implícitos. Conecte a anotação ao elemento com
   bpmn:association (sourceRef apontando para o elemento, targetRef para a
   anotação, ou vice-versa). Use com moderação — só onde agrega entendimento,
   não em toda tarefa."""
