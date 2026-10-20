from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    max_upload_mb: int = 20
    max_rows: int = 200_000
    max_columns: int = 100
    max_datasets: int = 100
    max_session_datasets: int = 5
    max_store_mb: int = 500
    dataset_ttl_seconds: int = 7200
    data_dir: Path = Path("/tmp/datalens-datasets")
    chart_point_limit: int = 2000
    ollama_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "qwen3:4b"
    ai_timeout_seconds: float = 90
    cookie_secure: bool = False
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"


settings = Settings()
