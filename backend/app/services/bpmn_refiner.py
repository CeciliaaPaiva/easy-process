from __future__ import annotations

from dataclasses import dataclass

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.services.bpmn_prompts import SEMANTIC_MODELING_RULES
from app.services.bpmn_validator import validate_bpmn_xml
from app.services.llm_usage import record_usage

_REFINER_SYSTEM = f"""\
Você é um especialista em modelagem de processos BPMN 2.0.
Recebe um diagrama BPMN em XML e uma instrução do usuário para alterá-lo.

IMPORTANTE sobre IDs: cada elemento no XML deve ter um id único. Os elementos de
diagrama (bpmndi:BPMNShape e bpmndi:BPMNEdge) NUNCA podem reutilizar o id do
elemento semântico que representam — use um id diferente, ex: BPMNEdge
id="Edge_SequenceFlow_1" bpmnElement="SequenceFlow_1" (não id="SequenceFlow_1").

{SEMANTIC_MODELING_RULES}

REGRAS DE LAYOUT (BPMNDI) — siga exatamente para as setas nunca cruzarem por
cima das formas, mesmo ao alterar o BPMN existente:
- Fluxo principal em uma ÚNICA linha horizontal (mesmo y para todos os
  elementos do caminho principal); só use uma segunda linha (offset vertical
  de pelo menos 150px) para ramos alternativos de gateways.
- Tamanhos fixos: startEvent/endEvent = 36x36; task/userTask/manualTask/
  serviceTask/businessRuleTask/sendTask/receiveTask = 100x80; qualquer tipo de
  gateway = 50x50; bpmn:textAnnotation = 100x60.
- Espaçamento horizontal fixo de 150px entre o fim de uma forma e o início da
  próxima.
- Alinhe verticalmente pelo centro: todas as formas da mesma linha devem ter
  o centro vertical (y + altura/2) idêntico.
- Waypoints de bpmndi:BPMNEdge devem sair do centro da borda DIREITA da forma
  de origem e entrar no centro da borda ESQUERDA da forma de destino — uma
  linha reta horizontal, sem desvios, quando ambas estão na mesma linha.
- Se houver bpmn:participant (pool): a forma do pool DEVE conter (sobrepor
  visualmente) todas as formas dos elementos dentro dele — isso é esperado,
  não é erro. Se houver bpmn:lane (raia), cada raia é uma faixa horizontal
  dentro do pool, com a mesma largura do pool, empilhadas sem sobrepor umas
  às outras; cada elemento fica dentro dos limites verticais da sua raia. Um
  pool "caixa preta" (sem laneSet, sem elementos internos, representando um
  ator externo) é só um retângulo com nome, sem nada dentro.
- NUNCA posicione uma forma cujo retângulo (x, y, largura, altura) sobreponha
  o retângulo de outra forma-irmã (não containers) ou o caminho de uma
  aresta. Se precisar adicionar/remover elementos, recalcule as posições x de
  TODOS os elementos seguintes para manter o espaçamento.
- NÃO adicione atributos de cor/estilo (ex: bioc:stroke, bioc:fill, cor de
  destaque) nem qualquer namespace que não esteja declarado no elemento raiz
  bpmn:definitions. Use apenas os namespaces bpmn, bpmndi, dc e di.

Responda respeitando estritamente o schema JSON fornecido."""

_REFINER_PROMPT = """\
BPMN ATUAL:
{bpmn_xml}

INSTRUÇÃO DO USUÁRIO: {instruction}"""

_RETRY_PROMPT = """\
O XML retornado a seguir é inválido: {error}

XML INVÁLIDO:
{invalid_xml}

Corrija o problema apontado, respeitando as mesmas regras de IDs e layout, e
retorne o JSON completo novamente."""


class _BpmnRefinementSchema(BaseModel):
    bpmn_xml: str
    change_description: str


@dataclass
class BpmnRefinementResult:
    bpmn_xml: str
    change_description: str


class BpmnRefinerService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.gemini_model_refinement

    async def refine(
        self,
        bpmn_xml: str,
        instruction: str,
        history: list[dict[str, str]],
        max_retries: int = 3,
        process_id: str | None = None,
        tenant_id: str | None = None,
    ) -> BpmnRefinementResult:
        if not bpmn_xml or not instruction.strip():
            raise ValueError("BPMN e instrução são obrigatórios")

        # Histórico de chat é curto (mensagens do usuário + change_description das
        # respostas anteriores) — não contém XML, então é seguro reenviar inteiro.
        base_contents: list[types.Content] = [
            types.Content(
                role="model" if msg["role"] == "assistant" else "user",
                parts=[types.Part(text=msg["content"])],
            )
            for msg in history
        ]

        config = types.GenerateContentConfig(
            system_instruction=_REFINER_SYSTEM,
            response_mime_type="application/json",
            response_schema=_BpmnRefinementSchema,
            temperature=0.1,
        )

        last_error = "formato inválido"
        prompt = _REFINER_PROMPT.format(bpmn_xml=bpmn_xml, instruction=instruction)

        for attempt in range(1, max_retries + 1):
            contents = [
                *base_contents,
                types.Content(role="user", parts=[types.Part(text=prompt)]),
            ]

            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=contents,
                config=config,
            )
            await record_usage(
                "bpmn_refinement",
                tenant_id,
                process_id,
                response,
                self._model_name,
                attempt,
            )

            data = response.parsed
            if data is not None:
                valid, err = validate_bpmn_xml(data.bpmn_xml)
                if valid:
                    return BpmnRefinementResult(
                        bpmn_xml=data.bpmn_xml,
                        change_description=data.change_description,
                    )
                last_error = err
                prompt = _RETRY_PROMPT.format(error=err, invalid_xml=data.bpmn_xml)
            else:
                last_error = "JSON inválido na resposta"
                prompt = (
                    _REFINER_PROMPT.format(bpmn_xml=bpmn_xml, instruction=instruction)
                    + "\n\nA resposta anterior não seguiu o schema JSON esperado. "
                    "Retorne novamente respeitando o schema."
                )

        raise RuntimeError(
            f"Não foi possível refinar BPMN após {max_retries} tentativas. "
            f"Último erro: {last_error}"
        )


bpmn_refiner_service = BpmnRefinerService()
