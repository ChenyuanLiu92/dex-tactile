import numpy as np

from dex_retargeting.inspire_retargeting import InspireVisionRetargeter
from dex_retargeting.constants import OPERATOR2MANO_RIGHT
from dex_retargeting.quest import estimate_hand_frame, quest_to_mano, quest_to_mediapipe


def _media_pose(index_curl: bool = False) -> np.ndarray:
    points = np.zeros((21, 3), dtype=float)
    points[[1, 2, 3, 4]] = [
        [0.030, -0.010, 0.0], [0.052, -0.016, 0.0],
        [0.072, -0.022, 0.0], [0.092, -0.028, 0.0],
    ]
    for start, x, lengths in (
        (5, 0.022, (0.022, 0.054, 0.086, 0.118)),
        (9, 0.000, (0.022, 0.060, 0.098, 0.136)),
        (13, -0.022, (0.020, 0.053, 0.086, 0.118)),
        (17, -0.044, (0.016, 0.043, 0.070, 0.097)),
    ):
        points[start : start + 4] = [[x, -length, 0.0] for length in lengths]
    if index_curl:
        points[[6, 7, 8]] = [[0.022, -0.050, -0.018], [0.022, -0.055, -0.045], [0.022, -0.030, -0.055]]
    return points


def _quest_pose(media: np.ndarray) -> np.ndarray:
    quest = np.zeros((24, 3), dtype=float)
    quest[0] = media[0]
    quest[[2, 3, 4, 5, 19]] = np.stack([
        media[1], media[2], (media[2] + media[3]) / 2, media[3], media[4],
    ])
    for source, destination in ((range(5, 9), (6, 7, 8, 20)), (range(9, 13), (9, 10, 11, 21)), (range(13, 17), (12, 13, 14, 22)), (range(17, 21), (16, 17, 18, 23))):
        quest[list(destination)] = media[list(source)]
    quest[15] = media[17] + np.array([-0.01, 0.01, 0.0])
    return quest


def test_quest_topology_preserves_wrist_fingers_and_thumb_endpoints():
    media = _media_pose()
    converted = quest_to_mediapipe(_quest_pose(media))

    np.testing.assert_allclose(converted[0], media[0])
    np.testing.assert_allclose(converted[5:21], media[5:21])
    np.testing.assert_allclose(converted[1], media[1])
    np.testing.assert_allclose(converted[4], media[4])


def test_quest_to_mano_is_invariant_to_world_translation_and_rotation():
    quest = _quest_pose(_media_pose())
    angle = np.deg2rad(37)
    rotation = np.array([[np.cos(angle), -np.sin(angle), 0], [np.sin(angle), np.cos(angle), 0], [0, 0, 1]])

    reference = quest_to_mano(quest)
    transformed = quest_to_mano(quest @ rotation.T + np.array([0.4, -0.2, 0.7]))
    np.testing.assert_allclose(transformed, reference, atol=1e-7)


def test_quest_and_d435_paths_produce_the_same_non_thumb_solver_constraints():
    media = _media_pose()
    centered = media - media[0:1]
    d435_mano = centered @ estimate_hand_frame(centered) @ OPERATOR2MANO_RIGHT
    quest_mano = quest_to_mano(_quest_pose(media))

    np.testing.assert_allclose(quest_mano[[0, *range(5, 21)]], d435_mano[[0, *range(5, 21)]], atol=1e-8)
    np.testing.assert_allclose(quest_mano[[1, 4]], d435_mano[[1, 4]], atol=1e-8)


def test_real_rh56_solver_responds_to_quest_index_flexion():
    solver = InspireVisionRetargeter()
    open_targets = None
    curled_targets = None
    for _ in range(5):
        _, open_targets = solver.retarget(quest_to_mano(_quest_pose(_media_pose())))
    for _ in range(8):
        _, curled_targets = solver.retarget(quest_to_mano(_quest_pose(_media_pose(index_curl=True))))

    assert open_targets is not None and curled_targets is not None
    assert curled_targets[3] < open_targets[3] - 40
