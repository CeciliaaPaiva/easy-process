from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
    _model: Any = None

    def _load_model(self) -> Any:
        if self._model is None:
            try:
                import whisper  # type: ignore[import-untyped]

                from app.core.config import settings

                self._model = whisper.load_model(settings.WHISPER_MODEL)
            except ImportError as exc:
                raise RuntimeError(
                    "openai-whisper não está instalado. "
                    "Execute no container: pip install openai-whisper"
                ) from exc
        return self._model

    async def transcribe(self, audio_path: str) -> TranscriptionResult:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError(f"Arquivo não encontrado: {audio_path}")

        model = self._load_model()
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: model.transcribe(str(path), language="pt"),
        )

        segments = [
            TranscriptionSegment(start=s["start"], end=s["end"], text=s["text"])
            for s in result.get("segments", [])
        ]
        duration = segments[-1].end if segments else 0.0

        return TranscriptionResult(
            text=result["text"],
            segments=segments,
            language=result.get("language", "pt"),
            duration=duration,
        )


transcription_service = TranscriptionService()
