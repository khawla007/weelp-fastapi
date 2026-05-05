from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mapbox_token: str
    mapbox_base_url: str = "https://api.mapbox.com"
    nominatim_base_url: str = "https://nominatim.openstreetmap.org"
    nominatim_user_agent: str
    gateway_port: int = 9000
    cors_origins: str = "http://localhost:3000"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
