import json
from datetime import datetime, timezone

import httpx
import pytest

from geoloop.weather.met_client import MetClient, _parse_timeseries_entry

SAMPLE_ENTRY = {
    "time": "2025-01-15T12:00:00Z",
    "data": {
        "instant": {
            "details": {
                "air_temperature": -2.5,
                "relative_humidity": 85.0,
                "wind_speed": 3.2,
            }
        },
        "next_1_hours": {
            "details": {"precipitation_amount": 0.3}
        },
    },
}

SAMPLE_RESPONSE = {
    "properties": {
        "timeseries": [
            SAMPLE_ENTRY,
            {
                "time": "2025-01-15T13:00:00Z",
                "data": {
                    "instant": {
                        "details": {
                            "air_temperature": -1.0,
                            "relative_humidity": 80.0,
                            "wind_speed": 2.0,
                        }
                    },
                },
            },
        ]
    }
}


class TestParseTimeseriesEntry:
    def test_should_parse_temperature_when_present(self):
        snap = _parse_timeseries_entry(SAMPLE_ENTRY)
        assert snap.air_temperature == -2.5

    def test_should_parse_precipitation_when_next_1_hours_present(self):
        snap = _parse_timeseries_entry(SAMPLE_ENTRY)
        assert snap.precipitation_amount == 0.3

    def test_should_return_none_precipitation_when_next_1_hours_missing(self):
        entry = {
            "time": "2025-01-15T13:00:00Z",
            "data": {
                "instant": {
                    "details": {
                        "air_temperature": -1.0,
                        "relative_humidity": 80.0,
                        "wind_speed": 2.0,
                    }
                }
            },
        }
        snap = _parse_timeseries_entry(entry)
        assert snap.precipitation_amount is None

    def test_should_parse_time_as_datetime(self):
        snap = _parse_timeseries_entry(SAMPLE_ENTRY)
        assert snap.time == datetime(2025, 1, 15, 12, 0, tzinfo=timezone.utc)


class TestMetClient:
    @pytest.mark.asyncio
    async def test_should_return_forecast_when_api_responds(self, monkeypatch):
        async def mock_get(self, url, **kwargs):
            return httpx.Response(
                200,
                json=SAMPLE_RESPONSE,
                headers={"Expires": "Wed, 15 Jan 2025 12:30:00 GMT"},
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        client = MetClient(user_agent="test/1.0")
        forecast = await client.fetch_forecast(59.91, 10.75)

        assert forecast.current.air_temperature == -2.5
        assert len(forecast.timeseries) == 1

    @pytest.mark.asyncio
    async def test_should_use_cache_when_not_expired(self, monkeypatch):
        call_count = 0

        async def mock_get(self, url, **kwargs):
            nonlocal call_count
            call_count += 1
            return httpx.Response(
                200,
                json=SAMPLE_RESPONSE,
                headers={"Expires": "Wed, 31 Dec 2099 23:59:59 GMT"},
                request=httpx.Request("GET", url),
            )

        monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)
        client = MetClient(user_agent="test/1.0")

        await client.fetch_forecast(59.91, 10.75)
        await client.fetch_forecast(59.91, 10.75)

        assert call_count == 1
