"""Settings from the environment, with an optional `.env` file.

Secrets never leave this module except as values passed to the code that needs them.
"""

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing values."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    db_path: Path
    log_dir: Path
    host: str
    port: int
    llm_base_url: str
    llm_api_key: str
    llm_model: str

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)


def get_settings() -> Settings:
    load_dotenv(ROOT / ".env")
    env = os.environ.get
    return Settings(
        data_dir=Path(env("STARCOACH_DATA_DIR", str(ROOT / "data" / "torob-dataset"))),
        db_path=Path(env("STARCOACH_DB", str(ROOT / "data" / "starcoach.db"))),
        log_dir=Path(env("STARCOACH_LOG_DIR", str(ROOT / "logs"))),
        host=env("STARCOACH_HOST", "127.0.0.1"),
        port=int(env("STARCOACH_PORT", "8000")),
        llm_base_url=env("LLM_BASE_URL", ""),
        llm_api_key=env("LLM_API_KEY", ""),
        llm_model=env("LLM_MODEL", ""),
    )
