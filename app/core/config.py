
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",  # 무시되지 않는 추가 환경변수로 인한 ValidationError 방지
    )

    env: str = Field(default="local", validation_alias="ENV")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    cors_origins: list[str] = Field(default_factory=list, validation_alias="CORS_ORIGINS")
    data_path: str = Field(default="data/tarot-images.json", validation_alias="DATA_PATH")
    use_db: bool = Field(default=False, validation_alias="USE_DB")
    db_url: str | None = Field(default=None, validation_alias="DB_URL")
    meanings_path: str | None = Field(default=None, validation_alias="MEANINGS_PATH")
    prefer_local_images: bool = Field(default=True, validation_alias="PREFER_LOCAL_IMAGES")
    google_api_key: str | None = Field(default=None, validation_alias="GOOGLE_API_KEY")
    # Security / limits
    api_key: str | None = Field(default=None, validation_alias="API_KEY")
    hmac_secret: str | None = Field(default=None, validation_alias="HMAC_SECRET")
    auth_required: bool = Field(default=False, validation_alias="AUTH_REQUIRED")
    redis_url: str | None = Field(default=None, validation_alias="REDIS_URL")
    max_body_bytes: int = Field(default=65536, validation_alias="MAX_BODY_BYTES")
    llm_max_output_tokens: int = Field(default=512, validation_alias="LLM_MAX_OUTPUT_TOKENS")
    llm_temperature: float = Field(default=0.6, validation_alias="LLM_TEMPERATURE")
    rate_limit_default: str = Field(default="60/minute", validation_alias="RATE_LIMIT_DEFAULT")
    rate_limit_health: str = Field(default="5/second", validation_alias="RATE_LIMIT_HEALTH")
    rate_limit_cards: str = Field(default="120/minute", validation_alias="RATE_LIMIT_CARDS")
    rate_limit_reading_post: str = Field(default="10/minute", validation_alias="RATE_LIMIT_READING_POST")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _parse_cors_origins(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    @field_validator("env", mode="before")
    @classmethod
    def _validate_env(cls, v: str) -> str:
        if v is None:
            return "local"
        val = str(v).strip().lower()
        allowed = {"local", "dev", "prod"}
        if val not in allowed:
            raise ValueError(f"ENV must be one of {sorted(allowed)}")
        return val


settings = Settings()
