import json
import re
from dataclasses import dataclass, field

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.bpmn_validator import validate_bpmn_xml

_GENERATION_PROMPT = """\
Você é um especialista em modelagem de processos BPMN 2.0.

Analise a transcrição de uma entrevista e gere:
1. Um diagrama BPMN 2.0 em XML válido com startEvent, endEvent, Tasks e SequenceFlows
2. Um resumo do processo (máx 200 palavras)
3. Lista de atores/participantes identificados
4. Lista de tarefas com responsável

TRANSCRIÇÃO:
{transcription}

Responda APENAS com JSON válido, sem texto antes ou depois:
{{
  "bpmn_xml": "<?xml version='1.0'?><bpmn:definitions ...>...</bpmn:definitions>",
  "summary": "...",
  "actors": ["Ator 1", "Ator 2"],
  "tasks": [{{"name": "Tarefa", "responsible": "Ator"}}]
}}"""

_RETRY_PROMPT = """\
A resposta anterior estava incorreta ou o BPMN era inválido.
Retorne SOMENTE JSON válido sem texto adicional.
O campo bpmn_xml deve ser XML BPMN 2.0 bem-formado começando com '<?xml'.
Erro: {error}
Tente novamente."""


@dataclass
class BpmnGenerationResult:
    bpmn_xml: str
    summary: str
    actors: list[str] = field(default_factory=list)
    tasks: list[dict] = field(default_factory=list)


class BpmnGeneratorService:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def generate(
        self, transcription: str, max_retries: int = 3
    ) -> BpmnGenerationResult:
        if not transcription or len(transcription.strip()) < 50:
            raise ValueError("Transcrição muito curta ou vazia (mínimo 50 caracteres)")

        initial_prompt = _GENERATION_PROMPT.format(transcription=transcription[:50_000])
        messages: list[dict[str, str]] = [{"role": "user", "content": initial_prompt}]
        last_error = "formato inválido"

        for attempt in range(1, max_retries + 1):
            response = await self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8096,
                messages=messages,
            )

            raw = response.content[0].text
            data = self._parse_json(raw)

            if data is not None:
                bpmn = data.get("bpmn_xml", "")
                valid, err = validate_bpmn_xml(bpmn)
                if valid:
                    return BpmnGenerationResult(
                        bpmn_xml=bpmn,
                        summary=data.get("summary", ""),
                        actors=data.get("actors", []),
                        tasks=data.get("tasks", []),
                    )
                last_error = err
            else:
                last_error = "JSON inválido na resposta"

            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {"role": "user", "content": _RETRY_PROMPT.format(error=last_error)}
                )

        raise RuntimeError(
            f"Não foi possível gerar BPMN válido após {max_retries} tentativas. "
            f"Último erro: {last_error}"
        )

    def _parse_json(self, text: str) -> dict | None:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        return None


bpmn_generator_service = BpmnGeneratorService()
