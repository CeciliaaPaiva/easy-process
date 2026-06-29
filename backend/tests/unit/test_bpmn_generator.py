import json
from unittest.mock import AsyncMock

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


class TestBpmnGeneratorService:
    @pytest.fixture
    def service(self):
        return BpmnGeneratorService()

    @pytest.mark.asyncio
    async def test_generates_valid_bpmn(self, service, mocker):
        mock_content = mocker.MagicMock()
        mock_content.text = json.dumps(MOCK_RESPONSE)

        mock_response = mocker.MagicMock()
        mock_response.content = [mock_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=mock_response,
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
    async def test_retries_on_invalid_bpmn_then_succeeds(self, service, mocker):
        bad_content = mocker.MagicMock()
        bad_content.text = (
            '{"bpmn_xml": "not valid xml", "summary": "", "actors": [], "tasks": []}'
        )
        good_content = mocker.MagicMock()
        good_content.text = json.dumps(MOCK_RESPONSE)

        bad_resp = mocker.MagicMock()
        bad_resp.content = [bad_content]
        good_resp = mocker.MagicMock()
        good_resp.content = [good_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            side_effect=[bad_resp, good_resp],
        )

        result = await service.generate(TRANSCRIPTION, max_retries=2)
        assert "startEvent" in result.bpmn_xml or "Start_1" in result.bpmn_xml

    @pytest.mark.asyncio
    async def test_raises_runtime_error_after_max_retries(self, service, mocker):
        bad_content = mocker.MagicMock()
        bad_content.text = "não é json"

        bad_resp = mocker.MagicMock()
        bad_resp.content = [bad_content]

        mocker.patch.object(
            service._client.messages,
            "create",
            new_callable=AsyncMock,
            return_value=bad_resp,
        )

        with pytest.raises(RuntimeError, match="tentativas"):
            await service.generate(TRANSCRIPTION, max_retries=2)
