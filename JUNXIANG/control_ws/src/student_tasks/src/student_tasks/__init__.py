"""Stable SI-unit APIs for base_link robot motion and visual approach."""

from .approach import (
    ApproachConfiguration,
    ApproachController,
    ApproachResult,
    ApproachState,
    ScanProvider,
    TargetProvider,
)
from .backend import Cancellation, CancellationToken, MotionBackend
from .configuration import ConfigurationProvenance, require_production
from .core import MotionController
from .errors import ControlError, ControlFailure, ErrorCategory
from .geometry import CameraIntrinsics, RigidTransform, Vector3, base_planar_geometry, unproject_pixel
from .models import (
    BackendStatus,
    MotionRequest,
    MotionResult,
    Velocity,
    VerificationLevel,
    ZERO_VELOCITY,
)
from .perception import (
    BaseTargetObservation,
    CameraCalibration,
    NormalizedTarget,
    PixelDepthObservation,
    TargetNormalization,
    TargetPolicy,
    normalize_target,
)
from .safety import (
    LaserScanSnapshot,
    SafetyConfiguration,
    SafetyDecision,
    SafetyMonitor,
    SectorEvidence,
    SectorRule,
)

__all__ = [
    "ApproachConfiguration",
    "ApproachController",
    "ApproachResult",
    "ApproachState",
    "BackendStatus",
    "BaseTargetObservation",
    "Cancellation",
    "CancellationToken",
    "CameraCalibration",
    "CameraIntrinsics",
    "ConfigurationProvenance",
    "ControlError",
    "ControlFailure",
    "ErrorCategory",
    "LaserScanSnapshot",
    "MotionBackend",
    "MotionController",
    "MotionRequest",
    "MotionResult",
    "NormalizedTarget",
    "PixelDepthObservation",
    "RigidTransform",
    "SafetyConfiguration",
    "SafetyDecision",
    "SafetyMonitor",
    "ScanProvider",
    "SectorEvidence",
    "SectorRule",
    "TargetNormalization",
    "TargetPolicy",
    "TargetProvider",
    "Vector3",
    "Velocity",
    "VerificationLevel",
    "ZERO_VELOCITY",
    "base_planar_geometry",
    "normalize_target",
    "require_production",
    "unproject_pixel",
]
