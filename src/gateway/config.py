from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mapbox_token: str
    mapbox_base_url: str = "https://api.mapbox.com"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str
    gateway_port: int = 9100
    gateway_public_url: str = "http://localhost:9100"
    cors_origins: str = "http://localhost:3000,https://weelp.com"

    redis_url: str = "redis://localhost:6379/0"
    cache_ttl_seconds: int = 300
    circuit_breaker_threshold: int = 5
    circuit_breaker_ttl_seconds: int = 30
    rate_limit_per_min: int = 60
    rate_limit_per_min_auth: int = 600
    rate_limit_storage_uri: str | None = None
    log_level: str = "INFO"

    jwt_secret: str
    jwt_algorithm: str = "HS256"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
