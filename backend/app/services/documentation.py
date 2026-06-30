import json
import logging
from dataclasses import dataclass

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "Você é um analista de processos de negócio especialista em BPMN. "
    "Analise o diagrama BPMN fornecido e gere documentação técnica completa em português. "
    "Responda SOMENTE com JSON válido, sem markdown, sem texto antes ou depois."
)

_PROMPT = """\
Analise o BPMN XML abaixo e retorne um JSON com a seguinte estrutura:
{{
  "description": "Descrição geral do processo (2-3 parágrafos)",
  "activities": [
    {{
      "name": "Nome da atividade",
      "responsible": "Responsável/papel",
      "description": "O que é feito",
      "inputs": ["entrada 1"],
      "outputs": ["saída 1"]
    }}
  ],
  "business_rules": ["Regra de negócio identificada"],
  "decision_points": [
    {{
      "name": "Nome do gateway",
      "criteria": "Critério de decisão",
      "outcomes": ["resultado 1", "resultado 2"]
    }}
  ],
  "exceptions": ["Exceção ou tratamento de erro identificado"]
}}

BPMN XML:
{bpmn_xml}"""


@dataclass
class ProcessDocumentation:
    description: str
    activities: list[dict]
    business_rules: list[str]
    decision_points: list[dict]
    exceptions: list[str]


class DocumentationService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = "gemini-2.0-flash"

    async def generate(self, bpmn_xml: str) -> ProcessDocumentation:
        if not bpmn_xml or not bpmn_xml.strip():
            raise ValueError("BPMN XML não pode estar vazio")

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=_PROMPT.format(bpmn_xml=bpmn_xml[:60_000]),
            config=types.GenerateContentConfig(system_instruction=_SYSTEM_INSTRUCTION),
        )

        raw = response.text.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Resposta do Gemini não é JSON válido: %s", raw[:200])
            raise RuntimeError("Falha ao gerar documentação: resposta inválida da IA") from exc

        return ProcessDocumentation(
            description=data.get("description", ""),
            activities=data.get("activities", []),
            business_rules=data.get("business_rules", []),
            decision_points=data.get("decision_points", []),
            exceptions=data.get("exceptions", []),
        )


documentation_service = DocumentationService()
