import json
import logging
import mimetypes
from dataclasses import dataclass, field
from pathlib import Path

from google import genai
from google.genai import types

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_INSTRUCTION = (
    "Você é um transcritor de áudio especialista em português do Brasil. "
    "Transcreva o áudio fornecido literalmente, palavra por palavra. "
    "Responda SOMENTE com JSON válido, sem markdown, sem texto antes ou depois."
)

_PROMPT = """\
Transcreva o áudio a seguir e retorne um JSON com a seguinte estrutura:
{
  "text": "transcrição completa do áudio",
  "language": "código do idioma detectado, ex: pt",
  "duration": duração aproximada do áudio em segundos (número)
}"""

_MIME_TYPES = {
    ".mp3": "audio/mp3",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
}


@dataclass
class TranscriptionSegment:
    start: float
    end: float
    text: str


@dataclass
class TranscriptionResult:
    text: str
    segments: list[TranscriptionSegment] = field(default_factory=list)
    language: str = "pt"
    duration: float = 0.0


class TranscriptionService:
    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self._model_name = settings.GEMINI_MODEL

    def _mime_type(self, path: Path) -> str:
        mime_type = _MIME_TYPES.get(path.suffix.lower())
        if mime_type:
            return mime_type
        guessed, _ = mimetypes.guess_type(path.name)
        return guessed or "audio/mpeg"

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")

        audio_bytes = path.read_bytes()
        audio_part = types.Part.from_bytes(
            data=audio_bytes, mime_type=self._mime_type(path)
        )

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=[audio_part, _PROMPT],
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
            raise RuntimeError("Falha ao transcrever áudio: resposta inválida da IA") from exc

        return TranscriptionResult(
            text=data.get("text", ""),
            language=data.get("language", "pt"),
            duration=float(data.get("duration") or 0.0),
        )


transcription_service = TranscriptionService()
