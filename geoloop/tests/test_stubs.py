from __future__ import annotations

import pytest

from geoloop.controller.stub import StubController
from geoloop.sensors.stub import StubSensor


class TestStubSensor:
    async def test_should_return_default_value(self):
        sensor = StubSensor("test-1")
        assert await sensor.read() == pytest.approx(20.0)

    async def test_should_return_configured_value(self):
        sensor = StubSensor("test-1", value=15.5)
        assert await sensor.read() == pytest.approx(15.5)

    async def test_should_return_none_when_configured(self):
        sensor = StubSensor("test-1", value=None)
        assert await sensor.read() is None

    def test_sensor_id_matches_constructor(self):
        sensor = StubSensor("loop_inlet")
        assert sensor.sensor_id == "loop_inlet"

    async def test_value_can_be_changed(self):
        sensor = StubSensor("test-1", value=10.0)
        assert await sensor.read() == pytest.approx(10.0)
        sensor.value = 25.0
        assert await sensor.read() == pytest.approx(25.0)


class TestStubController:
    async def test_should_be_off_initially(self):
        ctrl = StubController()
        assert await ctrl.is_on() is False

    async def test_should_be_on_after_turn_on(self):
        ctrl = StubController()
        await ctrl.turn_on()
        assert await ctrl.is_on() is True

    async def test_should_be_off_after_turn_off(self):
        ctrl = StubController()
        await ctrl.turn_on()
        await ctrl.turn_off()
        assert await ctrl.is_on() is False

    async def test_should_handle_multiple_toggles(self):
        ctrl = StubController()
        await ctrl.turn_on()
        await ctrl.turn_on()
        assert await ctrl.is_on() is True
        await ctrl.turn_off()
        assert await ctrl.is_on() is False
