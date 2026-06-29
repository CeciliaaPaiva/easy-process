import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.bpmn_generator import BpmnGeneratorService

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Aprovar solicitação"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

MOCK_RESPONSE = {
    "bpmn_xml": VALID_BPMN,
    "summary": "Processo de aprovação de solicitações.",
    "actors": ["Analista", "Gerente"],
    "tasks": [{"name": "Aprovar solicitação", "responsible": "Gerente"}],
}

TRANSCRIPTION = "O analista recebe a solicitação e encaminha para aprovar."


def _make_gemini_response(text: str) -> MagicMock:
    resp = MagicMock()
    resp.text = text
    return resp


class TestBpmnGeneratorService:
    @pytest.fixture
    def service(self):
        return BpmnGeneratorService()

    @pytest.fixture
    def mock_chat(self, service, mocker):
        chat = MagicMock()
        mocker.patch.object(service._model, "start_chat", return_value=chat)
        return chat

    @pytest.mark.asyncio
    async def test_generates_valid_bpmn(self, service, mock_chat):
        mock_chat.send_message_async = AsyncMock(
            return_value=_make_gemini_response(json.dumps(MOCK_RESPONSE))
        )

        result = await service.generate(TRANSCRIPTION)

        assert result.bpmn_xml == VALID_BPMN
        assert result.summary == MOCK_RESPONSE["summary"]
        assert result.actors == MOCK_RESPONSE["actors"]
        assert result.tasks == MOCK_RESPONSE["tasks"]

    @pytest.mark.asyncio
    async def test_raises_value_error_for_short_transcription(self, service):
        with pytest.raises(ValueError, match="curta"):
            await service.generate("curto")

    @pytest.mark.asyncio
    async def test_retries_on_invalid_bpmn_then_succeeds(self, service, mock_chat):
        mock_chat.send_message_async = AsyncMock(
            side_effect=[
                _make_gemini_response(
                    '{"bpmn_xml": "not valid xml", "summary": "", "actors": [], "tasks": []}'
                ),
                _make_gemini_response(json.dumps(MOCK_RESPONSE)),
            ]
        )

        result = await service.generate(TRANSCRIPTION, max_retries=2)
        assert "startEvent" in result.bpmn_xml or "Start_1" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_raises_runtime_error_after_max_retries(self, service, mock_chat):
        mock_chat.send_message_async = AsyncMock(
            return_value=_make_gemini_response("não é json")
        )

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.generate(TRANSCRIPTION, max_retries=2)
