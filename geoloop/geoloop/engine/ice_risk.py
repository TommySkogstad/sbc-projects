from __future__ import annotations

from typing import TYPE_CHECKING

from geoloop.engine.models import (
    EvaluationResult,
    HeatingDecision,
    IceRiskLevel,
    SensorReadings,
)

if TYPE_CHECKING:
    from geoloop.weather.met_client import WeatherForecast

# Standardverdier for temperaturgrenser
DEFAULT_ICE_TEMP_MIN = -3.0
DEFAULT_ICE_TEMP_MAX = 3.0
DEFAULT_CRITICAL_TEMP_MIN = -1.0
DEFAULT_CRITICAL_TEMP_MAX = 2.0


def _classify_risk(
    forecast: WeatherForecast,
    ice_temp_min: float = DEFAULT_ICE_TEMP_MIN,
    ice_temp_max: float = DEFAULT_ICE_TEMP_MAX,
    critical_temp_min: float = DEFAULT_CRITICAL_TEMP_MIN,
    critical_temp_max: float = DEFAULT_CRITICAL_TEMP_MAX,
) -> tuple[IceRiskLevel, dict[str, object]]:
    """Klassifiser isrisiko basert på 24t værprognose.

    Skanner alle tidspunkter i prognosen og ser etter:
    - Temperatur i faresonen [ice_temp_min, ice_temp_max]
    - Temperatur nær 0°C kombinert med nedbør (mest kritisk)
    """
    timeseries = forecast.timeseries[:24]
    if not timeseries:
        return IceRiskLevel.NONE, {"reason": "Ingen prognosedata"}

    ice_zone_hours = 0
    critical_hours = 0
    precip_near_zero_hours = 0

    for snapshot in timeseries:
        temp = snapshot.air_temperature
        precip = snapshot.precipitation_amount

        if temp is None:
            continue

        if ice_temp_min <= temp <= ice_temp_max:
            ice_zone_hours += 1

        if critical_temp_min <= temp <= critical_temp_max:
            critical_hours += 1
            if precip is not None and precip > 0:
                precip_near_zero_hours += 1

    details = {
        "ice_zone_hours": ice_zone_hours,
        "critical_hours": critical_hours,
        "precip_near_zero_hours": precip_near_zero_hours,
        "timeseries_count": len(timeseries),
    }

    # Nedbør nær 0°C = høyest risiko
    if precip_near_zero_hours >= 1:
        return IceRiskLevel.HIGH, details

    # Mange timer i kritisk sone uten nedbør
    if critical_hours >= 4:
        return IceRiskLevel.HIGH, details

    # Noe tid i faresonen
    if ice_zone_hours >= 6:
        return IceRiskLevel.MODERATE, details

    if ice_zone_hours >= 2:
        return IceRiskLevel.LOW, details

    return IceRiskLevel.NONE, details


def evaluate(
    forecast: WeatherForecast,
    sensor_readings: SensorReadings | None = None,
    currently_on: bool = False,
    ice_temp_min: float = DEFAULT_ICE_TEMP_MIN,
    ice_temp_max: float = DEFAULT_ICE_TEMP_MAX,
    critical_temp_min: float = DEFAULT_CRITICAL_TEMP_MIN,
    critical_temp_max: float = DEFAULT_CRITICAL_TEMP_MAX,
) -> EvaluationResult:
    """Evaluer isrisiko og beslutt handling.

    Ren funksjon uten sideeffekter.

    Beslutningslogikk:
    - HIGH:     TURN_ON  (isfare, kjør uansett)
    - MODERATE: TURN_ON  (sikkerhetsbias)
    - LOW:      KEEP     (hysterese — behold nåværende tilstand)
    - NONE:     TURN_OFF (ingen fare, spar energi)
    """
    risk_level, details = _classify_risk(
        forecast, ice_temp_min, ice_temp_max, critical_temp_min, critical_temp_max
    )

    if risk_level == IceRiskLevel.HIGH:
        return EvaluationResult(
            decision=HeatingDecision.TURN_ON,
            risk_level=risk_level,
            reason="Høy isrisiko — varme slås på",
            details=details,
        )

    if risk_level == IceRiskLevel.MODERATE:
        return EvaluationResult(
            decision=HeatingDecision.TURN_ON,
            risk_level=risk_level,
            reason="Moderat isrisiko — varme slås på (sikkerhetsbias)",
            details=details,
        )

    if risk_level == IceRiskLevel.LOW:
        state_str = "på" if currently_on else "av"
        return EvaluationResult(
            decision=HeatingDecision.KEEP,
            risk_level=risk_level,
            reason=f"Lav isrisiko — beholder nåværende tilstand ({state_str})",
            details=details,
        )

    # NONE
    return EvaluationResult(
        decision=HeatingDecision.TURN_OFF,
        risk_level=risk_level,
        reason="Ingen isrisiko — varme slås av",
        details=details,
    )
