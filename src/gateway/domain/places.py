from pydantic import BaseModel, Field


class CanonicalPlace(BaseModel):
    id: str
    name: str
    country_code: str = Field(min_length=2, max_length=2)
    lat: float
    lng: float
    provider: str
    raw: dict | None = None
