"""Etapa de MODELAGEM do pipeline de geração de BPMN (Sprint 12, S12-02).

Responsabilidade única: traduzir o grafo já analisado por `bpmn_analysis.py`
para XML BPMN 2.0 válido. Toda decisão semântica (tipo de gateway, tipo de
atividade, ator interno/externo, pontos de anotação) já foi tomada na etapa
de análise — esta etapa não reinterpreta o processo, só formata.

Antes da Sprint 12 este serviço recebia a transcrição bruta e fazia análise
e tradução na mesma chamada — ver `docs/sprints/SPRINT-12-plano.md` para o
raciocínio da separação."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.services.bpmn_analysis import ProcessAnalysisResult
from app.services.bpmn_layout import LayoutError, apply_layout
from app.services.bpmn_validator import (
    validate_bpmn_xml,
    validate_external_actors_have_pools,
)
from app.services.llm_usage import record_usage

_SYSTEM_INSTRUCTION = """\
Você é uma tradutora de um grafo de processo já analisado para BPMN 2.0 XML.
Toda decisão semântica (tipo de gateway, tipo de atividade, quem é ator
interno/externo, pontos de anotação) já foi tomada na etapa de análise —
sua única tarefa é TRADUZIR o grafo abaixo para XML válido, sem
reinterpretar o processo.

FORMATO DO GRAFO DE ENTRADA:
- `activities`: cada uma vira um elemento bpmn:<activity_type>Task (ex:
  activity_type="manual" → bpmn:manualTask; "generic" → bpmn:task), com o
  `id` do grafo como id do elemento e `name` como o label.
- `gateways`: cada um vira bpmn:exclusiveGateway / bpmn:parallelGateway /
  bpmn:inclusiveGateway conforme `gateway_type`, com o `id` do grafo como id
  do elemento. Se tiver `question`, essa pergunta vira o rótulo do gateway
  ou uma anotação associada a ele.
- `flows`: cada um vira um bpmn:sequenceFlow ligando os ids correspondentes;
  `source_id`/`target_id` "start"/"end"/"end:<motivo>" indicam onde criar
  bpmn:startEvent/bpmn:endEvent (um endEvent por motivo distinto de
  término, usando o texto após "end:" como name quando presente); `label`,
  se houver, vira o atributo `name` do sequenceFlow.
- `actors`: atores com `is_external=false` (quando houver 2 ou mais) viram
  raias — UM ÚNICO bpmn:participant principal com bpmn:laneSet contendo uma
  bpmn:lane por ator, cada lane com bpmn:flowNodeRef listando os ids das
  atividades daquele responsible. Com 0 ou 1 ator interno, NÃO crie
  participant/laneSet. Atores com `is_external=true` viram um
  bpmn:participant adicional, um por ator, SEM laneSet e SEM elementos
  internos (pool "caixa preta").
- `annotations`: cada uma vira um bpmn:textAnnotation associado ao
  `step_id` via bpmn:association.
- `business_rules`: se ainda não estiverem cobertas por uma anotação,
  considere adicionar uma bpmn:textAnnotation resumindo a regra no ponto do
  processo onde ela se aplica.

IMPORTANTE sobre o XML: gere APENAS os elementos semânticos do processo —
startEvent, endEvent, tasks, gateways, sequenceFlows,
participant/laneSet/lane, textAnnotation/association — cada um usando o id
indicado no grafo quando existir (crie um id novo só para elementos que o
grafo não tem, como o participant principal). NÃO inclua
bpmndi:BPMNDiagram nem qualquer elemento de diagrama/layout (BPMNShape,
BPMNEdge, Bounds, waypoint) — o layout visual é calculado automaticamente
depois, fora do seu XML. NÃO adicione atributos de cor/estilo nem
namespaces além de bpmn.

Responda respeitando estritamente o schema JSON fornecido."""

_RETRY_PROMPT = """\
O XML retornado a seguir é inválido: {error}

XML INVÁLIDO:
{invalid_xml}

Corrija o problema apontado — lembre-se de gerar apenas os elementos
semânticos do processo, sem bpmndi:BPMNDiagram — e retorne o JSON completo
novamente."""


class _BpmnXmlSchema(BaseModel):
    bpmn_xml: str


@dataclass
class BpmnGenerationResult:
    bpmn_xml: str
    summary: str
    actors: list[str] = field(default_factory=list)
    tasks: list[dict[str, str]] = field(default_factory=list)


def _serialize_graph(analysis: ProcessAnalysisResult) -> str:
    """Serializa o grafo já analisado no formato compacto que o prompt de
    tradução espera — sem os campos que a modelagem não usa (summary,
    business_rules já viram texto/anotação tratados à parte)."""
    graph = {
        "actors": [
            {"name": a.name, "is_external": a.is_external} for a in analysis.actors
        ],
        "activities": [
            {
                "id": a.id,
                "name": a.name,
                "responsible": a.responsible,
                "activity_type": a.activity_type,
            }
            for a in analysis.activities
        ],
        "gateways": [
            {
                "id": g.id,
                "role": g.role,
                "gateway_type": g.gateway_type,
                "question": g.question,
            }
            for g in analysis.gateways
        ],
        "flows": [
            {"source_id": f.source_id, "target_id": f.target_id, "label": f.label}
            for f in analysis.flows
        ],
        "annotations": [
            {"step_id": a.step_id, "text": a.text} for a in analysis.annotations
        ],
        "business_rules": analysis.business_rules,
    }
    return json.dumps(graph, ensure_ascii=False)


class BpmnGeneratorService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.gemini_model_generation

    async def generate(
        self,
        analysis: ProcessAnalysisResult,
        max_retries: int = 3,
        process_id: str | None = None,
        tenant_id: str | None = None,
    ) -> BpmnGenerationResult:
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_BpmnXmlSchema,
            temperature=0.1,
        )

        last_error = "formato inválido"
        prompt = f"GRAFO DO PROCESSO (JSON):\n{_serialize_graph(analysis)}"

        summary = analysis.summary
        actors = [a.name for a in analysis.actors]
        external_actors = [a.name for a in analysis.actors if a.is_external]
        tasks = [
            {"name": a.name, "responsible": a.responsible} for a in analysis.activities
        ]

        for attempt in range(1, max_retries + 1):
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
            await record_usage(
                "bpmn_modeling",
                tenant_id,
                process_id,
                response,
                self._model_name,
                attempt,
            )

            data = response.parsed
            if data is not None:
                try:
                    bpmn_with_layout = apply_layout(data.bpmn_xml)
                except LayoutError as exc:
                    last_error = str(exc)
                    prompt = _RETRY_PROMPT.format(
                        error=last_error, invalid_xml=data.bpmn_xml
                    )
                    continue

                valid, err = validate_bpmn_xml(bpmn_with_layout)
                if valid:
                    err = validate_external_actors_have_pools(
                        bpmn_with_layout, external_actors
                    )
                    valid = not err

                if valid:
                    return BpmnGenerationResult(
                        bpmn_xml=bpmn_with_layout,
                        summary=summary,
                        actors=actors,
                        tasks=tasks,
                    )
                last_error = err
                prompt = _RETRY_PROMPT.format(error=err, invalid_xml=data.bpmn_xml)
            else:
                last_error = "JSON inválido na resposta"
                prompt = (
                    f"GRAFO DO PROCESSO (JSON):\n{_serialize_graph(analysis)}\n\n"
                    "A resposta anterior não seguiu o schema JSON esperado. "
                    "Retorne novamente respeitando o schema."
                )

        raise RuntimeError(
            f"Não foi possível gerar BPMN válido após {max_retries} tentativas. "
            f"Último erro: {last_error}"
        )


bpmn_generator_service = BpmnGeneratorService()
