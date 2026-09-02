from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    database_url: str
    test_database_url: str

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("test_database_url")
    @classmethod
    def validate_test_database_url(cls, value: str) -> str:
        database_name = make_url(value).database or ""
        if not database_name.endswith("_test"):
            raise ValueError("test database name must end with _test")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
