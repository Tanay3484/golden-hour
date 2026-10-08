"""Domain and API models.

All datetimes are naive local time at the forecast location (design §3).
"""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class TimeRange(BaseModel):
    start: time
    end: time

    @model_validator(mode="after")
    def _end_after_start(self) -> "TimeRange":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class HourlyWeather(BaseModel):
    time: datetime
    temp_c: float
    precip_prob: int = Field(ge=0, le=100)
    wind_kmh: float
    uv: float
    cloud_cover: int = Field(ge=0, le=100)


class DayLight(BaseModel):
    date: date
    sunrise: datetime
    sunset: datetime


class Forecast(BaseModel):
    timezone: str
    utc_offset_seconds: int
    hours: list[HourlyWeather]
    days: list[DayLight]


class Place(BaseModel):
    name: str
    country: str | None = None
    lat: float
    lon: float


class WindowWeather(BaseModel):
    temp_c: float
    precip_prob: int = Field(ge=0, le=100)
    wind_kmh: float
    uv: float
    cloud_cover: int = Field(ge=0, le=100)


class Window(BaseModel):
    start: datetime
    end: datetime
    duration_min: int
    day: Literal["today", "tomorrow"]
    score: int = Field(ge=0, le=100)
    reasons: list[str]
    weather: WindowWeather


class Plan(BaseModel):
    timezone: str
    sunrise: datetime
    sunset: datetime
    best: Window | None
    alternates: list[Window] = Field(default_factory=list, max_length=2)
    note: str | None = None


class PlanRequest(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    free_ranges: list[TimeRange] = Field(default_factory=list)


class Suggestion(BaseModel):
    title: str = Field(max_length=60)
    steps: list[str] = Field(min_length=1, max_length=3)
    what_to_notice: str
    bring: list[str] = Field(default_factory=list, max_length=3)
    source: Literal["model", "fallback"] = "model"


class SuggestionContext(BaseModel):
    window: Window
    place_name: str | None = None
