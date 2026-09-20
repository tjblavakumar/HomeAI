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
    downloads_dir: str = str(DATA_DIR / "downloads")

    # Local-network scan settings
    scan_subnet: str = ""  # e.g. "192.168.1.0/24"; empty = auto-detect
    scan_tcp_probe: bool = True  # probe common TCP ports to find hosts not in ARP cache
    # IEEE OUI (MAC vendor) database. Downloaded once to oui_db_path if missing.
    oui_db_path: str = str(DATA_DIR / "oui.txt")
    oui_db_url: str = "https://standards-oui.ieee.org/oui/oui.txt"
    # Use the LLM to refine a friendly product label from vendor/hostname/ports.
    scan_llm_label: bool = True


settings = Settings()

# Ensure local data directories exist on startup
DATA_DIR.mkdir(parents=True, exist_ok=True)
Path(settings.chroma_dir).mkdir(parents=True, exist_ok=True)
Path(settings.uploads_dir).mkdir(parents=True, exist_ok=True)
Path(settings.downloads_dir).mkdir(parents=True, exist_ok=True)
