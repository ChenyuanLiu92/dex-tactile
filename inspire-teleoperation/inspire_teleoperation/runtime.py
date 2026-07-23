"""Composable teleoperation runtime and lifecycle management."""

from __future__ import annotations

from collections.abc import Iterable

from .api import ModuleStatus, TeleopFrame, TeleopModule, TeleopSource


class TeleopRuntime:
    """Fan frames from one source out to independently replaceable modules.

    Modules are started in declaration order and closed in reverse order.  A
    partially failed startup is rolled back, which is important when one robot
    subsystem connects successfully and a later one does not.
    """

    def __init__(self, source: TeleopSource, modules: Iterable[TeleopModule]) -> None:
        self.source = source
        self.modules = tuple(modules)
        names = [module.name for module in self.modules]
        if len(names) != len(set(names)):
            raise ValueError("teleoperation module names must be unique")
        self.enabled = False
        self._started = False
        self._started_modules: list[TeleopModule] = []

    def start(self) -> None:
        if self._started:
            return
        try:
            self.source.start()
            for module in self.modules:
                self._started_modules.append(module)
                module.start()
        except BaseException:
            try:
                self.close()
            except BaseException:
                # Preserve the startup error; close() has already attempted
                # every component even when one cleanup operation failed.
                pass
            raise
        self._started = True

    def set_enabled(self, enabled: bool) -> None:
        self.enabled = bool(enabled)

    def step(self) -> TeleopFrame:
        if not self._started:
            raise RuntimeError("teleoperation runtime has not been started")
        frame = self.source.read()
        return self.dispatch(frame)

    def dispatch(self, frame: TeleopFrame) -> TeleopFrame:
        """Deliver an existing frame, useful for replay and loss signaling."""

        if not self._started:
            raise RuntimeError("teleoperation runtime has not been started")
        if not isinstance(frame, TeleopFrame):
            raise TypeError("teleoperation source must return TeleopFrame")
        for module in self.modules:
            module.update(frame, enabled=self.enabled)
        return frame

    def status(self) -> dict[str, ModuleStatus]:
        return {module.name: module.status() for module in self.modules}

    def module(self, name: str) -> TeleopModule:
        for module in self.modules:
            if module.name == name:
                return module
        raise KeyError(f"unknown teleoperation module: {name!r}")

    def close(self) -> None:
        errors: list[BaseException] = []
        for module in reversed(self._started_modules):
            try:
                module.close()
            except BaseException as error:
                errors.append(error)
        self._started_modules.clear()
        try:
            self.source.close()
        except BaseException as error:
            errors.append(error)
        self._started = False
        if errors:
            raise RuntimeError("failed to close one or more teleoperation components") from errors[0]
