"""Retarget Quest hand landmarks to the six hardware joint commands."""

from __future__ import annotations

from pathlib import Path

import yaml
from dex_retargeting import RetargetingConfig


class HandRetargeting:
    """Build the left and right retargeters from this module's local assets."""

    def __init__(self, config_path: Path | None = None) -> None:
        module_dir = Path(__file__).resolve().parent
        assets_dir = module_dir / "assets"
        config_path = config_path or assets_dir / "hand_model" / "retargeting.yml"
        RetargetingConfig.set_default_urdf_dir(str(assets_dir))

        with config_path.open(encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file)
        if not isinstance(config, dict) or "left" not in config or "right" not in config:
            raise ValueError("Retargeting configuration must contain left and right sections")

        self.left_retargeting = RetargetingConfig.from_dict(config["left"]).build()
        self.right_retargeting = RetargetingConfig.from_dict(config["right"]).build()
        self.left_indices = self.left_retargeting.optimizer.target_link_human_indices
        self.right_indices = self.right_retargeting.optimizer.target_link_human_indices

        left_joint_names = self.left_retargeting.joint_names
        right_joint_names = self.right_retargeting.joint_names
        left_hardware_joint_names = (
            "L_pinky_proximal_joint",
            "L_ring_proximal_joint",
            "L_middle_proximal_joint",
            "L_index_proximal_joint",
            "L_thumb_proximal_pitch_joint",
            "L_thumb_proximal_yaw_joint",
        )
        right_hardware_joint_names = (
            "R_pinky_proximal_joint",
            "R_ring_proximal_joint",
            "R_middle_proximal_joint",
            "R_index_proximal_joint",
            "R_thumb_proximal_pitch_joint",
            "R_thumb_proximal_yaw_joint",
        )
        self.left_dex_retargeting_to_hardware = [
            left_joint_names.index(name) for name in left_hardware_joint_names
        ]
        self.right_dex_retargeting_to_hardware = [
            right_joint_names.index(name) for name in right_hardware_joint_names
        ]
