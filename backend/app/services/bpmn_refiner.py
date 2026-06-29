from __future__ import annotations

import json
import re
from dataclasses import dataclass

from anthropic import AsyncAnthropic

from app.core.config import settings
from app.services.bpmn_validator import validate_bpmn_xml

_REFINER_SYSTEM = (
    "Você é um especialista em modelagem de processos BPMN 2.0. "
    "Recebe um diagrama BPMN em XML e uma instrução do usuário. "
    "Retorna SOMENTE JSON válido, sem texto adicional."
)

_REFINER_PROMPT = """\
BPMN ATUAL:
{bpmn_xml}

INSTRUÇÃO DO USUÁRIO: {instruction}

Responda APENAS com JSON válido:
{{
  "bpmn_xml": "<?xml version='1.0'?>...",
  "change_description": "Descrição do que foi alterado"
}}"""

_RETRY_PROMPT = (
    "O XML retornado é inválido: {error}. "
    "Retorne apenas JSON com bpmn_xml BPMN 2.0 válido contendo startEvent e endEvent."
)


@dataclass
class BpmnRefinementResult:
    bpmn_xml: str
    change_description: str


class BpmnRefinerService:
    def __init__(self) -> None:
        self._client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

    async def refine(
        self,
        bpmn_xml: str,
        instruction: str,
        history: list[dict[str, str]],
        max_retries: int = 3,
    ) -> BpmnRefinementResult:
        if not bpmn_xml or not instruction.strip():
            raise ValueError("BPMN e instrução são obrigatórios")

        messages: list[dict[str, str]] = list(history)
        messages.append(
            {
                "role": "user",
                "content": _REFINER_PROMPT.format(
                    bpmn_xml=bpmn_xml, instruction=instruction
                ),
            }
        )

        last_error = "formato inválido"

        for attempt in range(1, max_retries + 1):
            response = await self._client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=8096,
                system=_REFINER_SYSTEM,
                messages=messages,
            )

            raw = response.content[0].text
            data = self._parse_json(raw)

            if data is not None:
                bpmn = data.get("bpmn_xml", "")
                valid, err = validate_bpmn_xml(bpmn)
                if valid:
                    return BpmnRefinementResult(
                        bpmn_xml=bpmn,
                        change_description=data.get("change_description", ""),
                    )
                last_error = err
            else:
                last_error = "JSON inválido na resposta"

            if attempt < max_retries:
                messages.append({"role": "assistant", "content": raw})
                messages.append(
                    {
                        "role": "user",
                        "content": _RETRY_PROMPT.format(error=last_error),
                    }
                )

        raise RuntimeError(
            f"Não foi possível refinar BPMN após {max_retries} tentativas. "
            f"Último erro: {last_error}"
        )

    def _parse_json(self, text: str) -> dict | None:  # type: ignore[type-arg]
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


bpmn_refiner_service = BpmnRefinerService()
