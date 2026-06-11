import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # 搜索
    serpapi_key: str = ""
    google_api_key: str = ""
    google_cse_id: str = ""

    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def is_vercel(self) -> bool:
        return os.getenv("VERCEL") == "1"


settings = Settings()
