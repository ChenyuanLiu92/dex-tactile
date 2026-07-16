import pytest

from inspire_visualizer_api.device.mapping import CHANNELS, device_to_joint_values


def test_right_hand_maps_open_and_closed_device_values_to_urdf_joints() -> None:
    opened = device_to_joint_values("right", [1000] * 6)
    closed = device_to_joint_values("right", [0] * 6)

    assert tuple(CHANNELS) == (
        "little",
        "ring",
        "middle",
        "index",
        "thumb_bend",
        "thumb_rotate",
    )
    assert opened == {
        "right_little_1_joint": 0.0,
        "right_ring_1_joint": 0.0,
        "right_middle_1_joint": 0.0,
        "right_index_1_joint": 0.0,
        "right_thumb_2_joint": 0.0,
        "right_thumb_1_joint": 0.0,
    }
    assert closed == {
        "right_little_1_joint": 1.6,
        "right_ring_1_joint": 1.6,
        "right_middle_1_joint": 1.6,
        "right_index_1_joint": 1.6,
        "right_thumb_2_joint": 0.75,
        "right_thumb_1_joint": 1.7,
    }


def test_left_thumb_bend_uses_negative_urdf_direction() -> None:
    midpoint = device_to_joint_values("left", [500] * 6)

    assert midpoint["left_thumb_1_joint"] == pytest.approx(-0.475)
    assert midpoint["left_thumb_swing_joint"] == pytest.approx(0.85)


@pytest.mark.parametrize("values", ([0] * 5, [0, 0, 0, 0, 0, 1001]))
def test_mapping_rejects_invalid_device_values(values: list[int]) -> None:
    with pytest.raises(ValueError):
        device_to_joint_values("right", values)
