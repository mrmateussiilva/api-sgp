from typing import List, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    # Configurações do Banco de Dados
    DATABASE_URL: str = "sqlite:///db/banco.db"

    # Configurações da API
    API_V1_STR: str = ""
    PROJECT_NAME: str = "API Sistema de Fichas"
    VERSION: str = "0.1.0"

    # Configurações de CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost",
        "http://127.0.0.1",
    ]
    BACKEND_CORS_ALLOW_ORIGIN_REGEX: Optional[str] = r"tauri://.*"

    # Configurações de Segurança
    SECRET_KEY: str = "your-secret-key-here"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


settings = Settings()
