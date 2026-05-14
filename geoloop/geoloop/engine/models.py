from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class IceRiskLevel(Enum):
    HIGH = "high"
    MODERATE = "moderate"
    LOW = "low"
    NONE = "none"


class HeatingDecision(Enum):
    TURN_ON = "turn_on"
    TURN_OFF = "turn_off"
    KEEP = "keep"


@dataclass
class SensorReadings:
    """Sensoravlesninger fra varmesløyfen."""

    loop_inlet: float | None = None
    loop_outlet: float | None = None
    hp_inlet: float | None = None
    hp_outlet: float | None = None
    tank: float | None = None


@dataclass
class EvaluationResult:
    """Resultat fra isrisiko-evaluering."""

    decision: HeatingDecision
    risk_level: IceRiskLevel
    reason: str
    details: dict[str, object] = field(default_factory=dict)
