from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.transcription import TranscriptionResult, TranscriptionService


class TestTranscriptionService:
    @pytest.fixture
    def service(self):
        svc = TranscriptionService()
        svc._model = None
        return svc

    @pytest.fixture
    def mock_model(self):
        model = MagicMock()
        model.transcribe.return_value = {
            "text": " Analista recebe o pedido e encaminha para aprovação.",
            "segments": [
                {"start": 0.0, "end": 3.0, "text": " Analista recebe o pedido"},
                {"start": 3.0, "end": 6.5, "text": " e encaminha para aprovação."},
            ],
            "language": "pt",
        }
        return model

    @pytest.mark.asyncio
    async def test_transcribe_returns_correct_result(self, service, mock_model, tmp_path):
        audio_file = tmp_path / "audio.mp3"
        audio_file.write_bytes(b"fake audio data")

        with patch.object(service, "_load_model", return_value=mock_model):
            result = await service.transcribe(str(audio_file))

        assert isinstance(result, TranscriptionResult)
        assert "Analista" in result.text
        assert len(result.segments) == 2
        assert result.duration == pytest.approx(6.5)
        assert result.language == "pt"

    @pytest.mark.asyncio
    async def test_transcribe_file_not_found_raises(self, service):
        with pytest.raises(FileNotFoundError, match="Arquivo não encontrado"):
            await service.transcribe("/tmp/nao_existe.mp3")

    @pytest.mark.asyncio
    async def test_transcribe_empty_segments_returns_zero_duration(
        self, service, tmp_path
    ):
        audio_file = tmp_path / "silent.wav"
        audio_file.write_bytes(b"fake wav data")

        model = MagicMock()
        model.transcribe.return_value = {
            "text": "",
            "segments": [],
            "language": "pt",
        }

        with patch.object(service, "_load_model", return_value=model):
            result = await service.transcribe(str(audio_file))

        assert result.text == ""
        assert result.segments == []
        assert result.duration == 0.0

    @pytest.mark.asyncio
    async def test_load_model_raises_when_whisper_not_installed(self, service):
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "whisper":
                raise ImportError("No module named 'whisper'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=mock_import):
            with pytest.raises(RuntimeError, match="openai-whisper"):
                service._load_model()

    def test_model_loaded_once_across_calls(self, service, tmp_path):
        model = MagicMock()
        model.transcribe.return_value = {
            "text": "texto",
            "segments": [],
            "language": "pt",
        }

        with patch.object(service, "_load_model", return_value=model) as mock_load:
            service._model = model
            # _load_model should not be called if _model is already set
            loaded = service._load_model()

        assert loaded is model
