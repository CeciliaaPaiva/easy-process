import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.transcription import TranscriptionResult, TranscriptionService


def _make_gemini_response(data: dict) -> MagicMock:
    resp = MagicMock()
    resp.text = json.dumps(data)
    return resp


class TestTranscriptionService:
    @pytest.fixture
    def service(self):
        return TranscriptionService()

    @pytest.mark.asyncio
    async def test_transcribe_returns_correct_result(self, service, tmp_path, mocker):
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        mocker.patch.object(
            service._client.aio.models,
            "generate_content",
            new=AsyncMock(
                return_value=_make_gemini_response(
                    {
                        "text": "Analista recebe o pedido e encaminha para aprovação.",
                        "language": "pt",
                        "duration": 6.5,
                    }
                )
            ),
        )

        result = await service.transcribe(str(audio_file))

        assert isinstance(result, TranscriptionResult)
        assert "Analista" in result.text
        assert result.duration == pytest.approx(6.5)
        assert result.language == "pt"

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found_raises(self, service):
        with pytest.raises(FileNotFoundError, match="Arquivo não encontrado"):
            await service.transcribe("/tmp/nao_existe.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_empty_text_returns_zero_duration(
        self, service, tmp_path, mocker
    ):
        audio_file = tmp_path / "silent.wav"
        audio_file.write_bytes(b"fake wav data")

        mocker.patch.object(
            service._client.aio.models,
            "generate_content",
            new=AsyncMock(
                return_value=_make_gemini_response(
                    {"text": "", "language": "pt", "duration": 0}
                )
            ),
        )

        result = await service.transcribe(str(audio_file))

        assert result.text == ""
        assert result.duration == 0.0

    @pytest.mark.asyncio
    async def test_transcribe_invalid_json_raises_runtime_error(
        self, service, tmp_path, mocker
    ):
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        resp = MagicMock()
        resp.text = "não é json"
        mocker.patch.object(
            service._client.aio.models,
            "generate_content",
            new=AsyncMock(return_value=resp),
        )

        with pytest.raises(RuntimeError, match="Falha ao transcrever"):
            await service.transcribe(str(audio_file))


class TestMimeType:
    @pytest.fixture
    def service(self):
        return TranscriptionService()

    @pytest.mark.parametrize(
        ("filename", "expected"),
        [
            ("audio.mp3", "audio/mp3"),
            ("audio.wav", "audio/wav"),
            ("audio.m4a", "audio/mp4"),
            ("audio.ogg", "audio/ogg"),
            # gravado pelo MediaRecorder do navegador — sem mapeamento explícito,
            # o fallback de mimetypes.guess_type() classifica como "video/webm" e
            # o Gemini rejeita como "vídeo corrompido, 0 frames"
            ("audio.webm", "audio/webm"),
        ],
    )
    def test_known_extensions_map_to_audio_mime_type(self, service, filename, expected):
        assert service._mime_type(Path(filename)) == expected

    def test_unknown_extension_falls_back_to_audio_mpeg(self, service):
        assert service._mime_type(Path("audio.xyz")) == "audio/mpeg"
