"""Runtime settings, read from environment variables or a local .env file."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql://clausecheck:clausecheck@localhost:5432/clausecheck"
    corpus_manifest_path: Path = PROJECT_ROOT / "data" / "corpus_manifest.json"
    eval_runs_dir: Path = PROJECT_ROOT / "eval" / "runs"
    ollama_url: str = "http://localhost:11434"


@lru_cache
def get_settings() -> Settings:
    return Settings()
