from __future__ import annotations

from dataclasses import replace

from viewer.backend.control.controller import ControlSnapshot, ControlState, Preset
from viewer.backend.preset_cli import run_direct_pose, select_mode


class FakeController:
    def __init__(self, interrupt=False):
        self.value = ControlSnapshot(
            state=ControlState.DISCONNECTED,
            connected=False,
        )
        self.interrupt = interrupt
        self.started = False
        self.stopped = False
        self.estopped = False
        self.selected = None

    def start(self):
        self.started = True
        self.value = replace(
            self.value,
            state=ControlState.DISARMED,
            connected=True,
            actual=[500] * 6,
        )

    def snapshot(self):
        return self.value

    def move_to_preset(self, preset):
        self.selected = preset
        self.value = replace(
            self.value,
            state=ControlState.POSITIONING,
            preset=preset,
            targets=[1000] * 6,
        )
        return self.value

    def tick(self):
        if self.interrupt:
            raise KeyboardInterrupt
        self.value = replace(
            self.value,
            state=ControlState.DISARMED,
            preset=None,
            actual=[1000] * 6,
        )
        return self.value

    def estop(self):
        self.estopped = True
        self.value = replace(self.value, state=ControlState.ESTOPPED, preset=None)

    def stop(self):
        self.stopped = True


def test_select_mode_uses_viewer_when_connected_and_disarmed():
    mode = select_mode({"connected": True, "control_state": "DISARMED"})

    assert mode == "viewer"


def test_select_mode_uses_direct_only_when_viewer_is_absent():
    assert select_mode(None) == "direct"


def test_select_mode_rejects_live_viewer_in_non_disarmed_state():
    try:
        select_mode({"connected": True, "control_state": "FAULT"})
    except RuntimeError as error:
        assert "connected and DISARMED" in str(error)
    else:
        raise AssertionError("Expected non-DISARMED Viewer to be rejected")


def test_direct_pose_uses_controller_and_closes_after_completion():
    controller = FakeController()
    messages = []

    result = run_direct_pose(
        Preset.OPEN,
        controller=controller,
        emit=messages.append,
        sleep=lambda _seconds: None,
    )

    assert result == 0
    assert controller.started
    assert controller.selected is Preset.OPEN
    assert controller.stopped
    assert not controller.estopped
    assert any("DIRECT MODBUS" in message for message in messages)


def test_direct_pose_holds_on_keyboard_interrupt_before_closing():
    controller = FakeController(interrupt=True)

    result = run_direct_pose(
        Preset.HOME,
        controller=controller,
        emit=lambda _message: None,
        sleep=lambda _seconds: None,
    )

    assert result == 130
    assert controller.estopped
    assert controller.stopped
