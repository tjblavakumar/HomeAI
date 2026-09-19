from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Paths are resolved relative to the repo root (backend/.. )
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(REPO_ROOT / ".env"), extra="ignore")

    openai_api_key: str = ""
    tavily_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    database_url: str = f"sqlite:///{DATA_DIR / 'app.db'}"
    chroma_dir: str = str(DATA_DIR / "chroma")
    uploads_dir: str = str(DATA_DIR / "uploads")


settings = Settings()

# Ensure local data directories exist on startup
DATA_DIR.mkdir(parents=True, exist_ok=True)
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
