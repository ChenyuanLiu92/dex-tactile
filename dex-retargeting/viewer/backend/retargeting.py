"""Compatibility exports for the packaged Inspire RH56 retargeter."""

from dex_retargeting.inspire_retargeting import (
    ACTUATOR_JOINTS,
    SEGMENT_CONSTRAINTS,
    ContactLatch,
    InspireVisionRetargeter,
    ProfileCalibrationSession,
    build_constraint_targets,
    map_joints_to_actuators,
    smooth_contact_activations,
)

__all__ = [
    "ACTUATOR_JOINTS",
    "SEGMENT_CONSTRAINTS",
    "ContactLatch",
    "InspireVisionRetargeter",
    "ProfileCalibrationSession",
    "build_constraint_targets",
    "map_joints_to_actuators",
    "smooth_contact_activations",
]
