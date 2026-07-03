import json
import re
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from app.core.config import settings
from app.services.bpmn_validator import validate_bpmn_xml

_GENERATION_PROMPT = """\
Você é um especialista em modelagem de processos BPMN 2.0.

Analise a transcrição de uma entrevista e gere:
1. Um diagrama BPMN 2.0 em XML válido com startEvent, endEvent, Tasks e SequenceFlows
2. Um resumo do processo (máx 200 palavras)
3. Lista de atores/participantes identificados
4. Lista de tarefas com responsável

IMPORTANTE sobre IDs: cada elemento no XML deve ter um id único. Os elementos de
diagrama (bpmndi:BPMNShape e bpmndi:BPMNEdge) NUNCA podem reutilizar o id do
elemento semântico que representam — use um id diferente, ex: BPMNEdge
id="Edge_SequenceFlow_1" bpmnElement="SequenceFlow_1" (não id="SequenceFlow_1").

REGRAS DE LAYOUT (BPMNDI) — siga exatamente para as setas nunca cruzarem por
cima das formas:
- Fluxo principal em uma ÚNICA linha horizontal (mesmo y para todos os
  elementos do caminho principal); só use uma segunda linha (offset vertical
  de pelo menos 150px) para ramos alternativos de gateways.
- Tamanhos fixos: startEvent/endEvent = 36x36; task = 100x80;
  exclusiveGateway = 50x50.
- Espaçamento horizontal fixo de 150px entre o fim de uma forma e o início da
  próxima (ex: task em x=200 largura 100 termina em x=300; a próxima forma
  começa em x=450).
- Alinhe verticalmente pelo centro: todas as formas da mesma linha devem ter
  o centro vertical (y + altura/2) idêntico.
- Waypoints de bpmndi:BPMNEdge devem sair do centro da borda DIREITA da forma
  de origem (x_origem + largura, y_origem + altura/2) e entrar no centro da
  borda ESQUERDA da forma de destino (x_destino, y_destino + altura/2) — uma
  linha reta horizontal, sem desvios, quando ambas estão na mesma linha.
- NUNCA posicione uma forma cujo retângulo (x, y, largura, altura) sobreponha
  o retângulo de outra forma ou o caminho de uma aresta.
- NÃO adicione atributos de cor/estilo (ex: bioc:stroke, bioc:fill, cor de
  destaque) nem qualquer namespace que não esteja declarado no elemento raiz
  bpmn:definitions. Use apenas os namespaces bpmn, bpmndi, dc e di.

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
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_MODEL

    async def generate(
        self, transcription: str, max_retries: int = 3
    ) -> BpmnGenerationResult:
        if not transcription or len(transcription.strip()) < 50:
            raise ValueError("Transcrição muito curta ou vazia (mínimo 50 caracteres)")

        messages: list[types.Content] = []
        initial_prompt = _GENERATION_PROMPT.format(transcription=transcription[:50_000])
        last_error = "formato inválido"

        for attempt in range(1, max_retries + 1):
            user_msg = initial_prompt if attempt == 1 else _RETRY_PROMPT.format(error=last_error)
            messages.append(types.Content(role="user", parts=[types.Part(text=user_msg)]))

            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=messages,
            )
            raw = response.text
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
