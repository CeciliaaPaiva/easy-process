import uuid

from tests.integration.conftest import register_user

VALID_BPMN = """\
<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL" id="Def_1">
  <bpmn:process id="Process_1">
    <bpmn:startEvent id="Start_1"/>
    <bpmn:task id="Task_1" name="Tarefa"/>
    <bpmn:endEvent id="End_1"/>
  </bpmn:process>
</bpmn:definitions>"""


async def _create_project(client, headers) -> str:
    resp = await client.post(
        "/api/v1/projects",
        json={"name": "Projeto Teste"},
        headers=headers,
    )
    return resp.json()["id"]


async def _upload(client, project_id, headers, mocker, name="Processo"):
    mocker.patch(
        "app.api.v1.processes.save_audio",
        return_value="/tmp/fake/audio.mp3",
    )
    mocker.patch("app.api.v1.processes.process_audio_pipeline")
    return await client.post(
        f"/api/v1/projects/{project_id}/processes",
        data={"name": name},
        files={"audio": ("audio.mp3", b"fake mp3", "audio/mpeg")},
        headers=headers,
    )


class TestUploadAudio:
    async def test_upload_valid_audio_returns_201(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])

        resp = await _upload(
            client, project_id, auth["headers"], mocker, "Reunião de kickoff"
        )

        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert data["name"] == "Reunião de kickoff"
        assert data["project_id"] == project_id

    async def test_upload_invalid_format_returns_400(self, client, mocker):
        mocker.patch("app.workers.process_audio.process_audio_pipeline")

        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])

        resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Arquivo Errado"},
            files={"audio": ("doc.pdf", b"pdf content", "application/pdf")},
            headers=auth["headers"],
        )
        assert resp.status_code == 400

    async def test_upload_to_nonexistent_project_returns_404(self, client, mocker):
        mocker.patch("app.workers.process_audio.process_audio_pipeline")

        auth = await register_user(client)
        fake_id = str(uuid.uuid4())

        resp = await client.post(
            f"/api/v1/projects/{fake_id}/processes",
            data={"name": "Teste"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth["headers"],
        )
        assert resp.status_code == 404

    async def test_upload_to_other_tenant_project_returns_404(self, client, mocker):
        mocker.patch("app.workers.process_audio.process_audio_pipeline")

        auth_a = await register_user(client)
        auth_b = await register_user(client)

        project_id = await _create_project(client, auth_a["headers"])

        resp = await client.post(
            f"/api/v1/projects/{project_id}/processes",
            data={"name": "Invasão"},
            files={"audio": ("audio.mp3", b"fake", "audio/mpeg")},
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


class TestGetProcess:
    async def test_get_process_status(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])
        upload = await _upload(
            client, project_id, auth["headers"], mocker, "Processo Status"
        )
        process_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == process_id

    async def test_get_other_tenant_process_returns_404(self, client, mocker):
        auth_a = await register_user(client)
        auth_b = await register_user(client)

        project_id = await _create_project(client, auth_a["headers"])
        upload = await _upload(
            client, project_id, auth_a["headers"], mocker, "Processo Privado"
        )
        process_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/processes/{process_id}",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


class TestListProcesses:
    async def test_list_returns_processes_for_project(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])

        await _upload(client, project_id, auth["headers"], mocker, "Processo 1")
        await _upload(client, project_id, auth["headers"], mocker, "Processo 2")

        resp = await client.get(
            f"/api/v1/projects/{project_id}/processes",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        names = [p["name"] for p in resp.json()]
        assert "Processo 1" in names
        assert "Processo 2" in names

    async def test_list_processes_other_tenant_returns_404(self, client, mocker):
        auth_a = await register_user(client)
        auth_b = await register_user(client)
        project_id = await _create_project(client, auth_a["headers"])

        resp = await client.get(
            f"/api/v1/projects/{project_id}/processes",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404

    async def test_list_processes_nonexistent_project_returns_404(self, client):
        auth = await register_user(client)
        resp = await client.get(
            f"/api/v1/projects/{uuid.uuid4()}/processes",
            headers=auth["headers"],
        )
        assert resp.status_code == 404


class TestProcessStatus:
    async def test_status_returns_id_status_version(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])
        upload = await _upload(client, project_id, auth["headers"], mocker, "Status Test")
        process_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/processes/{process_id}/status",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == process_id
        assert data["status"] == "pending"
        assert data["version"] == 1

    async def test_status_other_tenant_returns_404(self, client, mocker):
        auth_a = await register_user(client)
        auth_b = await register_user(client)
        project_id = await _create_project(client, auth_a["headers"])
        upload = await _upload(client, project_id, auth_a["headers"], mocker, "Privado")
        process_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/processes/{process_id}/status",
            headers=auth_b["headers"],
        )
        assert resp.status_code == 404


class TestBpmnEndpoints:
    async def test_get_bpmn_when_not_ready_returns_400(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])
        upload = await _upload(
            client, project_id, auth["headers"], mocker, "Não Pronto"
        )
        process_id = upload.json()["id"]

        resp = await client.get(
            f"/api/v1/processes/{process_id}/bpmn",
            headers=auth["headers"],
        )
        assert resp.status_code == 400

    async def test_update_bpmn_with_valid_xml(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])
        upload = await _upload(
            client, project_id, auth["headers"], mocker, "Edição BPMN"
        )
        process_id = upload.json()["id"]

        resp = await client.put(
            f"/api/v1/processes/{process_id}/bpmn",
            json={"bpmn_xml": VALID_BPMN, "change_description": "Ajuste manual"},
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["version"] == 2

    async def test_update_bpmn_with_invalid_xml_returns_400(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])
        upload = await _upload(
            client, project_id, auth["headers"], mocker, "XML Inválido"
        )
        process_id = upload.json()["id"]

        resp = await client.put(
            f"/api/v1/processes/{process_id}/bpmn",
            json={"bpmn_xml": "<invalid>"},
            headers=auth["headers"],
        )
        assert resp.status_code == 400

    async def test_list_versions(self, client, mocker):
        auth = await register_user(client)
        project_id = await _create_project(client, auth["headers"])
        upload = await _upload(client, project_id, auth["headers"], mocker, "Versões")
        process_id = upload.json()["id"]

        await client.put(
            f"/api/v1/processes/{process_id}/bpmn",
            json={"bpmn_xml": VALID_BPMN},
            headers=auth["headers"],
        )

        resp = await client.get(
            f"/api/v1/processes/{process_id}/versions",
            headers=auth["headers"],
        )
        assert resp.status_code == 200
        assert len(resp.json()) >= 1
