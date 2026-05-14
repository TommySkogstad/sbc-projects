from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx

_FORECAST_URL = (
    "https://api.met.no/weatherapi/locationforecast/2.0/compact"
)


@dataclass
class WeatherSnapshot:
    time: datetime
    air_temperature: float | None = None
    precipitation_amount: float | None = None
    relative_humidity: float | None = None
    wind_speed: float | None = None


@dataclass
class WeatherForecast:
    current: WeatherSnapshot
    timeseries: list[WeatherSnapshot] = field(default_factory=list)


def _parse_timeseries_entry(entry: dict) -> WeatherSnapshot:
    time = datetime.fromisoformat(entry["time"])
    instant = entry["data"]["instant"]["details"]
    precip = (
        entry["data"]
        .get("next_1_hours", {})
        .get("details", {})
        .get("precipitation_amount")
    )
    return WeatherSnapshot(
        time=time,
        air_temperature=instant.get("air_temperature"),
        precipitation_amount=precip,
        relative_humidity=instant.get("relative_humidity"),
        wind_speed=instant.get("wind_speed"),
    )


class MetClient:
    """Asynkron klient for api.met.no locationforecast."""

    def __init__(self, user_agent: str) -> None:
        self._user_agent = user_agent
        self._expires: datetime | None = None
        self._last_forecast: WeatherForecast | None = None

    async def fetch_forecast(
        self, lat: float, lon: float
    ) -> WeatherForecast:
        """Hent værprognose. Bruker cache dersom Expires-header ikke er utløpt."""
        now = datetime.now(timezone.utc)
        if (
            self._expires is not None
            and now < self._expires
            and self._last_forecast is not None
        ):
            return self._last_forecast

        async with httpx.AsyncClient() as client:
            resp = await client.get(
                _FORECAST_URL,
                params={"lat": lat, "lon": lon},
                headers={"User-Agent": self._user_agent},
            )
            resp.raise_for_status()

        expires_header = resp.headers.get("Expires")
        if expires_header:
            self._expires = parsedate_to_datetime(expires_header)

        data = resp.json()
        timeseries = data["properties"]["timeseries"]

        snapshots = [_parse_timeseries_entry(e) for e in timeseries]
        forecast = WeatherForecast(
            current=snapshots[0],
            timeseries=snapshots[1:],
        )
        self._last_forecast = forecast
        return forecast
