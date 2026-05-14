from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture(autouse=True)
def mock_gpiozero():
    """Mock gpiozero-modulen slik at tester kan kjøres uten RPi-hardware."""
    mock_module = MagicMock()
    with patch.dict(sys.modules, {"gpiozero": mock_module}):
        yield mock_module


@pytest.fixture
def make_controller(mock_gpiozero):
    """Opprett RelayController med mockede OutputDevices."""
    mock_k1 = MagicMock()
    mock_k2 = MagicMock()
    mock_gpiozero.OutputDevice.side_effect = [mock_k1, mock_k2]

    from geoloop.controller.relay import RelayController

    ctrl = RelayController(heat_pump_pin=26, circulation_pump_pin=20)
    return ctrl, mock_gpiozero.OutputDevice, mock_k1, mock_k2


class TestRelayController:
    def test_should_create_two_output_devices(self, make_controller):
        _, mock_cls, _, _ = make_controller
        assert mock_cls.call_count == 2
        mock_cls.assert_any_call(26, active_high=True, initial_value=False)
        mock_cls.assert_any_call(20, active_high=True, initial_value=False)

    async def test_should_turn_on_both_relays(self, make_controller):
        ctrl, _, mock_k1, mock_k2 = make_controller
        await ctrl.turn_on()
        mock_k1.on.assert_called_once()
        mock_k2.on.assert_called_once()

    async def test_should_turn_off_both_relays(self, make_controller):
        ctrl, _, mock_k1, mock_k2 = make_controller
        await ctrl.turn_off()
        mock_k1.off.assert_called_once()
        mock_k2.off.assert_called_once()

    async def test_should_report_on_after_turn_on(self, make_controller):
        ctrl, _, _, _ = make_controller
        await ctrl.turn_on()
        assert await ctrl.is_on() is True

    async def test_should_report_off_after_turn_off(self, make_controller):
        ctrl, _, _, _ = make_controller
        await ctrl.turn_on()
        await ctrl.turn_off()
        assert await ctrl.is_on() is False

    async def test_should_report_off_initially(self, make_controller):
        ctrl, _, _, _ = make_controller
        assert await ctrl.is_on() is False

    def test_close_should_release_gpio(self, make_controller):
        ctrl, _, mock_k1, mock_k2 = make_controller
        ctrl.close()
        mock_k1.close.assert_called_once()
        mock_k2.close.assert_called_once()

    def test_should_pass_active_high_false(self, mock_gpiozero):
        mock_k1 = MagicMock()
        mock_k2 = MagicMock()
        mock_gpiozero.OutputDevice.side_effect = [mock_k1, mock_k2]

        from geoloop.controller.relay import RelayController

        RelayController(
            heat_pump_pin=26, circulation_pump_pin=20, active_high=False
        )
        mock_gpiozero.OutputDevice.assert_any_call(
            26, active_high=False, initial_value=False
        )
        mock_gpiozero.OutputDevice.assert_any_call(
            20, active_high=False, initial_value=False
        )
