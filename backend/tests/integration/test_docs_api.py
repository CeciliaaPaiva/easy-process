import uuid

from app.services.bpmn_generator import BpmnGenerationResult
from app.services.documentation import ProcessDocumentation
from app.services.transcription import TranscriptionResult
from app.workers.process_audio import process_audio_pipeline
from tests.integration.conftest import register_user

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Aprovar"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""

MOCK_DOC = ProcessDocumentation(
    description="Processo de aprovação simples.",
    activities=[{"name": "Aprovar", "responsible": "Gestor"}],
    business_rules=["Requer aprovação do gerente"],
    decision_points=[],
    exceptions=[],
)


async def _ready_process(client, mocker) -> tuple[dict, str]:
    auth = await register_user(client)
    proj = await client.post(
        "/api/v1/projects", json={"name": "Projeto Docs"}, headers=auth["headers"]
    )
    project_id = proj.json()["id"]

    mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/fake.mp3")
    mocker.patch("app.api.v1.processes.process_audio_pipeline")
    mocker.patch(
        "app.workers.process_audio.transcription_service.transcribe",
        return_value=TranscriptionResult(text="Processo de aprovação.", duration=10.0),
    )
    mocker.patch(
        "app.workers.process_audio.bpmn_generator_service.generate",
        return_value=BpmnGenerationResult(
            bpmn_xml=VALID_BPMN, summary="Aprovação.", actors=[], tasks=[]
        ),
    )

    upload = await client.post(
        f"/api/v1/projects/{project_id}/processes",
        data={"name": "Processo Docs"},
        files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
        headers=auth["headers"],
    )
    process_id = upload.json()["id"]
    await process_audio_pipeline(uuid.UUID(process_id))
    return auth, process_id


class TestGetDocs:
    async def test_get_docs_returns_structured_documentation(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)

        mocker.patch(
            "app.services.documentation.documentation_service.generate",
            return_value=MOCK_DOC,
        )

        resp = await client.get(
            f"/api/v1/processes/{process_id}/docs", headers=auth["headers"]
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["description"] == MOCK_DOC.description
        assert len(data["activities"]) == 1
        assert data["business_rules"] == MOCK_DOC.business_rules
        assert data["process_id"] == process_id

    async def test_docs_on_pending_process_returns_400(self, client, mocker):
        auth = await register_user(client)
        proj = await client.post(
            "/api/v1/projects", json={"name": "P"}, headers=auth["headers"]
        )
        mocker.patch("app.api.v1.processes.save_audio", return_value="/tmp/f.mp3")
        mocker.patch("app.api.v1.processes.process_audio_pipeline")

        upload = await client.post(
            f"/api/v1/projects/{proj.json()['id']}/processes",
            data={"name": "Pendente"},
            files={"audio": ("audio.mp3", b"f", "audio/mpeg")},
            headers=auth["headers"],
        )
        process_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/processes/{process_id}/docs", headers=auth["headers"]
        )
        assert resp.status_code == 400

    async def test_docs_other_tenant_returns_404(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)
        auth_b = await register_user(client)

        resp = await client.get(
            f"/api/v1/processes/{process_id}/docs", headers=auth_b["headers"]
        )
        assert resp.status_code == 404


class TestRegenerateDocs:
    async def test_regenerate_returns_fresh_docs(self, client, mocker):
        auth, process_id = await _ready_process(client, mocker)

        mocker.patch(
            "app.services.documentation.documentation_service.generate",
            return_value=MOCK_DOC,
        )

        resp = await client.post(
            f"/api/v1/processes/{process_id}/docs", headers=auth["headers"]
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == MOCK_DOC.description
