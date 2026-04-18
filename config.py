from typing import List, Optional
import warnings
import os
from pathlib import Path

from pydantic import field_validator, SecretStr, ValidationInfo
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)
    
    # Configurações de Diretórios Compartilhados
    # API_ROOT deve ser definido como variável de ambiente antes de importar Settings
    # O main.py configura isso automaticamente
    API_ROOT: Optional[str] = None  # Ex: "C:\api" ou "/opt/api"
    
    # Configurações do Banco de Dados
    # O main.py configura essas variáveis de ambiente antes da importação
    # Valores padrão são usados apenas em desenvolvimento (sem API_ROOT)
    DATABASE_URL: str = "sqlite:///db/banco.db"
    MEDIA_ROOT: str = "media"
    LOG_DIR: str = "logs"
    MAX_IMAGE_SIZE_MB: int = 10
    MATERIAL_STOCK_AUTO_DEDUCTION: bool = False

    # Configurações do ambiente
    ENVIRONMENT: str = "development"

    # Configurações da API
    API_V1_STR: str = ""
    PROJECT_NAME: str = "API Sistema de Fichas"
    VERSION: str = "1.3.4"
    PORT: Optional[int] = None

    # Configurações de CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "http://localhost:3000",
        "http://localhost",
        "http://127.0.0.1",
        "http://tauri.localhost",
        "tauri://localhost",
        "null",
    ]
    BACKEND_CORS_ALLOW_ORIGIN_REGEX: Optional[str] = (
        r"(null|tauri://.*|app://.*|capacitor://.*|https?://localhost(:\d+)?|"
        r"https?://127\.0\.0\.1(:\d+)?|https?://tauri\.localhost.*|https?://.*\.localhost.*|"
        r"https?://192\.168\.\d{1,3}\.\d{1,3}(:\d+)?|https?://10\.\d{1,3}\.\d{1,3}\.\d{1,3}(:\d+)?|"
        r"https://.*\.ngrok-free\.app|https://.*\.ngrok\.app)"
    )

    # Configurações de Segurança
    SECRET_KEY: SecretStr = SecretStr("change-me")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 8  # 8 dias
    
    # VPS Sync
    VPS_SYNC_URL: str = "https://api-sgp-mobile.finderbit.com.br/internal/sync/pedidos"
    VPS_SYNC_API_KEY: Optional[str] = None

    # MySQL remoto (PWA)
    DB_USER: Optional[str] = None
    DB_PASS: Optional[str] = None
    DB_HOST: Optional[str] = None
    DB_PORT: int = 3306
    DB_NAME: Optional[str] = None

    # Logging
    LOG_LEVEL: str = "INFO"

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    def assemble_cors_origins(cls, value):
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("SECRET_KEY")
    def ensure_secret_key(cls, value: SecretStr, info: ValidationInfo) -> SecretStr:
        secret = value.get_secret_value()
        if not secret or secret in {"changeme", "change-me", "your-secret-key-here"}:
            environment = (info.data or {}).get("ENVIRONMENT", "development")
            if environment.lower() == "production":
                raise ValueError("SECRET_KEY não pode usar o valor padrão em produção.")
            warnings.warn(
                "SECRET_KEY está usando o valor padrão. Configure uma variável de ambiente segura para produção.",
                RuntimeWarning,
                stacklevel=2,
            )
        return value


settings = Settings()
