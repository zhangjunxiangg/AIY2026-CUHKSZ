"""Configuration provenance that prevents synthetic values reaching production."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .errors import failure


@dataclass(frozen=True)
class ConfigurationProvenance:
    """Traceable origin for safety, calibration, and approach values."""

    kind: str
    source: str
    measured_at: float | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"synthetic", "measured"}:
            raise ValueError("Configuration kind must be synthetic or measured")
        if not isinstance(self.source, str) or not self.source.strip():
            raise ValueError("Configuration source must be non-empty")
        object.__setattr__(self, "source", self.source.strip())

        if self.kind == "synthetic":
            if self.measured_at is not None:
                raise ValueError("Synthetic configuration cannot carry a measured timestamp")
            return

        if isinstance(self.measured_at, bool) or not isinstance(self.measured_at, (int, float)):
            raise ValueError("Measured configuration requires a timestamp")
        timestamp = float(self.measured_at)
        if not math.isfinite(timestamp) or timestamp <= 0.0:
            raise ValueError("Measured timestamp must be finite and positive")
        object.__setattr__(self, "measured_at", timestamp)

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "source": self.source,
            "measured_at": self.measured_at,
        }


def require_production(provenance: ConfigurationProvenance) -> ConfigurationProvenance:
    """Reject anything other than traceable measured configuration."""

    if not isinstance(provenance, ConfigurationProvenance):
        raise failure("INVALID_INPUT", "provenance must be ConfigurationProvenance")
    if provenance.kind != "measured":
        raise failure(
            "PRODUCTION_CONFIG_REQUIRED",
            "Synthetic configuration is offline-only and cannot authorize production motion",
            configuration_kind=provenance.kind,
            source=provenance.source,
        )
    return provenance
