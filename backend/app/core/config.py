from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@db:5432/bpmn_platform"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-flash-lite-latest"
    GEMINI_MODEL_TRANSCRIPTION: str = ""
    GEMINI_MODEL_ANALYSIS: str = ""
    GEMINI_MODEL_GENERATION: str = ""
    GEMINI_MODEL_REFINEMENT: str = ""

    @property
    def gemini_model_transcription(self) -> str:
        return self.GEMINI_MODEL_TRANSCRIPTION or self.GEMINI_MODEL

    @property
    def gemini_model_analysis(self) -> str:
        return self.GEMINI_MODEL_ANALYSIS or self.GEMINI_MODEL

    @property
    def gemini_model_generation(self) -> str:
        return self.GEMINI_MODEL_GENERATION or self.GEMINI_MODEL

    @property
    def gemini_model_refinement(self) -> str:
        return self.GEMINI_MODEL_REFINEMENT or self.GEMINI_MODEL

    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100
    MAX_AUDIO_DURATION_MINUTES: int = 30

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    ENVIRONMENT: str = "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
