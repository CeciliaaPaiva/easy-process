from __future__ import annotations

from dataclasses import dataclass, field

from google import genai
from google.genai import types
from pydantic import BaseModel

from app.core.config import settings
from app.services.bpmn_layout import LayoutError, apply_layout
from app.services.bpmn_validator import validate_bpmn_xml
from app.services.llm_usage import log_usage

_SYSTEM_INSTRUCTION = """\
Você é um especialista em modelagem de processos BPMN 2.0.

Analise a transcrição de uma entrevista fornecida pelo usuário e gere:
1. Um diagrama BPMN 2.0 em XML válido com startEvent, endEvent, Tasks e SequenceFlows
2. Um resumo do processo (máx 200 palavras)
3. Lista de atores/participantes identificados
4. Lista de tarefas com responsável

IMPORTANTE sobre o XML: gere APENAS os elementos semânticos do processo dentro
de bpmn:definitions/bpmn:process — startEvent, endEvent, tasks, gateways e
sequenceFlows, cada um com um id único. NÃO inclua bpmndi:BPMNDiagram nem
qualquer elemento de diagrama/layout (BPMNShape, BPMNEdge, Bounds, waypoint) —
o layout visual é calculado automaticamente depois, fora do seu XML. NÃO
adicione atributos de cor/estilo nem namespaces além de bpmn.

Responda respeitando estritamente o schema JSON fornecido."""

_RETRY_PROMPT = """\
O XML retornado a seguir é inválido: {error}

XML INVÁLIDO:
{invalid_xml}

Corrija o problema apontado — lembre-se de gerar apenas os elementos
semânticos do processo, sem bpmndi:BPMNDiagram — e retorne o JSON completo
novamente."""


class _BpmnTask(BaseModel):
    name: str
    responsible: str


class _BpmnGenerationSchema(BaseModel):
    bpmn_xml: str
    summary: str
    actors: list[str]
    tasks: list[_BpmnTask]


@dataclass
class BpmnGenerationResult:
    bpmn_xml: str
    summary: str
    actors: list[str] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)


class BpmnGeneratorService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.gemini_model_generation

    async def generate(
        self,
        transcription: str,
        max_retries: int = 3,
        process_id: str | None = None,
    ) -> BpmnGenerationResult:
        if not transcription or len(transcription.strip()) < 50:
            raise ValueError("Transcrição muito curta ou vazia (mínimo 50 caracteres)")

        transcription = transcription[:50_000]
        config = types.GenerateContentConfig(
            system_instruction=_SYSTEM_INSTRUCTION,
            response_mime_type="application/json",
            response_schema=_BpmnGenerationSchema,
            temperature=0.1,
        )

        last_error = "formato inválido"
        prompt = f"TRANSCRIÇÃO:\n{transcription}"

        for attempt in range(1, max_retries + 1):
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=prompt,
                config=config,
            )
            log_usage(
                "bpmn_generation", process_id, response, self._model_name, attempt
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
                    return BpmnGenerationResult(
                        bpmn_xml=bpmn_with_layout,
                        summary=data.summary,
                        actors=data.actors,
                        tasks=[t.model_dump() for t in data.tasks],
                    )
                last_error = err
                prompt = _RETRY_PROMPT.format(error=err, invalid_xml=data.bpmn_xml)
            else:
                last_error = "JSON inválido na resposta"
                prompt = (
                    f"TRANSCRIÇÃO:\n{transcription}\n\n"
                    "A resposta anterior não seguiu o schema JSON esperado. "
                    "Retorne novamente respeitando o schema."
                )

        raise RuntimeError(
            f"Não foi possível gerar BPMN válido após {max_retries} tentativas. "
            f"Último erro: {last_error}"
        )


bpmn_generator_service = BpmnGeneratorService()
