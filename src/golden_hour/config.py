from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="GH_", env_file=".env")

    ollama_url: str = "http://localhost:11434"
    model: str = "gemma3:4b"


settings = Settings()
