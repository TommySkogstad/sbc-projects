from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from geoloop.sensors.ds18b20 import DS18B20Sensor


@pytest.fixture
def sensor():
    return DS18B20Sensor("28-0123456789ab")


def _patch_read(return_value=None, side_effect=None):
    """Patch Path.read_text på klassenivå."""
    return patch.object(
        Path, "read_text", return_value=return_value, side_effect=side_effect
    )


class TestDS18B20:
    async def test_should_return_temperature_when_valid_reading(self, sensor):
        w1_output = "73 01 4b 46 7f ff 0d 10 41 : crc=41 YES\n73 01 4b 46 7f ff 0d 10 41 t=23187\n"
        with _patch_read(return_value=w1_output):
            result = await sensor.read()
        assert result == pytest.approx(23.187)

    async def test_should_return_none_when_crc_fails(self, sensor):
        w1_output = "73 01 4b 46 7f ff 0d 10 41 : crc=41 NO\n73 01 4b 46 7f ff 0d 10 41 t=23187\n"
        with _patch_read(return_value=w1_output):
            result = await sensor.read()
        assert result is None

    async def test_should_return_none_when_file_not_found(self, sensor):
        with _patch_read(side_effect=OSError):
            result = await sensor.read()
        assert result is None

    async def test_should_return_none_when_unexpected_format(self, sensor):
        with _patch_read(return_value="garbage"):
            result = await sensor.read()
        assert result is None

    async def test_should_return_negative_temperature(self, sensor):
        w1_output = "ff ff 4b 46 7f ff 0d 10 41 : crc=41 YES\nff ff 4b 46 7f ff 0d 10 41 t=-1250\n"
        with _patch_read(return_value=w1_output):
            result = await sensor.read()
        assert result == pytest.approx(-1.25)

    async def test_should_return_zero_temperature(self, sensor):
        w1_output = "00 00 4b 46 7f ff 0d 10 41 : crc=41 YES\n00 00 4b 46 7f ff 0d 10 41 t=0\n"
        with _patch_read(return_value=w1_output):
            result = await sensor.read()
        assert result == pytest.approx(0.0)

    async def test_should_return_none_when_no_t_equals_in_line(self, sensor):
        w1_output = "73 01 4b 46 7f ff 0d 10 41 : crc=41 YES\n73 01 4b 46 7f ff 0d 10 41\n"
        with _patch_read(return_value=w1_output):
            result = await sensor.read()
        assert result is None

    def test_sensor_id_matches_constructor(self, sensor):
        assert sensor.sensor_id == "28-0123456789ab"
