from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://user:pass@db:5432/bpmn_platform"

    JWT_SECRET: str = "change-me-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    ANTHROPIC_API_KEY: str = ""
    WHISPER_MODEL: str = "base"

    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_SIZE_MB: int = 100

    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    ENVIRONMENT: str = "development"

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"


settings = Settings()
