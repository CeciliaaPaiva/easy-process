import json
import logging
from dataclasses import dataclass, field

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

DISCLAIMER = (
    "Estas sugestões são geradas automaticamente a partir do diagrama e servem como "
    "ponto de partida. Um analista de negócios pode aprofundar cada uma delas e "
    "desenhar o plano de implementação."
)

_SYSTEM_INSTRUCTION = (
    "Você é um consultor sênior de processos de negócio que analisa diagramas BPMN e "
    "gera sugestões de melhoria para o dono da empresa. Use terminologia técnica de BPM "
    "(ex.: gateway de decisão, handoff, retrabalho, SLA, throughput, ponto único de "
    "falha, paralelização) e seja direto — descrições curtas, sem enrolação. Aponte "
    "oportunidades concretas: atividades manuais repetitivas automatizáveis, ausência "
    "de paralelismo, pontos únicos de falha, handoffs excessivos entre atores, gargalos "
    "de tempo ou de aprovação. Cada sugestão deve terminar com uma frase curta de "
    "chamada para ação, mas VARIE a redação entre os findings — nunca repita a mesma "
    "frase duas vezes na mesma resposta (ex.: 'Ganho estimado: X'; 'Vale priorizar em "
    "consultoria dedicada'; 'Requer levantamento mais fino com um analista'; 'Candidato "
    "natural a um diagnóstico aprofundado'). Responda SOMENTE com JSON válido, sem "
    "markdown, sem texto antes ou depois."
)

_PROMPT = """\
Analise o BPMN XML abaixo e retorne um JSON com a seguinte estrutura:
{{
  "findings": [
    {{
      "title": "Nome curto e técnico da sugestão de melhoria",
      "description": "Explicação técnica e sucinta do problema, o impacto no negócio (tempo/custo/risco) e uma chamada para ação curta e variada (não repita a mesma frase entre findings)",
      "severity": "baixa" | "média" | "alta",
      "related_elements": ["id do elemento BPMN relacionado, se aplicável"]
    }}
  ]
}}

Se não encontrar nenhuma sugestão relevante, retorne "findings": [].

BPMN XML:
{bpmn_xml}"""


@dataclass
class BottleneckFinding:
    title: str
    description: str
    severity: str
    related_elements: list[str] = field(default_factory=list)


@dataclass
class BottleneckAnalysis:
    findings: list[BottleneckFinding]
    disclaimer: str = DISCLAIMER


class BottleneckAnalysisService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_MODEL

    async def analyze(self, bpmn_xml: str) -> BottleneckAnalysis:
        if not bpmn_xml or not bpmn_xml.strip():
            raise ValueError("BPMN XML não pode estar vazio")

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=_PROMPT.format(bpmn_xml=bpmn_xml[:60_000]),
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                response_mime_type="application/json",
            ),
        )

        raw = response.text.strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.error("Resposta do Gemini não é JSON válido: %s", raw[:200])
            raise RuntimeError(
                "Falha ao analisar gargalos: resposta inválida da IA"
            ) from exc

        findings = [
            BottleneckFinding(
                title=f.get("title", ""),
                description=f.get("description", ""),
                severity=f.get("severity", "baixa"),
                related_elements=f.get("related_elements", []),
            )
            for f in data.get("findings", [])
        ]

        return BottleneckAnalysis(findings=findings)


bottleneck_analysis_service = BottleneckAnalysisService()
