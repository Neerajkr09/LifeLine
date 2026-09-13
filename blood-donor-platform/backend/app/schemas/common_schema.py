"""Shared schema building blocks reused across auth / user / request schemas."""
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator

T = TypeVar("T")


class AddressSchema(BaseModel):
    address_line: str = Field(..., min_length=3, max_length=200)
    postcode: str = Field(..., min_length=3, max_length=15)
    city_town: str = Field(..., min_length=2, max_length=100)

    @field_validator("address_line", "postcode", "city_town")
    @classmethod
    def strip_whitespace(cls, v: str) -> str:
        return v.strip()


class GeoLocationSchema(BaseModel):
    """GeoJSON Point: longitude first, then latitude (Mongo 2dsphere convention)."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)

    def to_geojson(self) -> dict[str, Any]:
        return {"type": "Point", "coordinates": [self.longitude, self.latitude]}


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = ""
    data: Optional[T] = None


class MessageResponse(BaseModel):
    success: bool = True
    message: str
