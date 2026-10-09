from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GH_", env_file=".env")

    ollama_url: str = "http://localhost:11434"
    model: str = "gemma3:4b"
    llm_timeout_s: float = 60
    # CPU threads for inference. Unset = Ollama's default (all host cores), which on a 1-CPU
    # container oversubscribes and halved speed in testing; Render sets 1 (001 design §5).
    llm_num_thread: int | None = None
    # Public Overpass instances, tried in order (spec 002 design §4.2). Env: JSON list.
    overpass_urls: list[str] = [
        "https://overpass-api.de/api/interpreter",
        "https://overpass.private.coffee/api/interpreter",
    ]
    overpass_budget_s: float = 25

    @field_validator("ollama_url")
    @classmethod
    def _add_scheme(cls, v: str) -> str:
        # Render's `fromService: hostport` gives "host:port" with no scheme (design §5).
        v = v.rstrip("/")
        return v if v.startswith(("http://", "https://")) else f"http://{v}"


settings = Settings()
