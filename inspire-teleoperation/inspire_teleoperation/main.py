#!/usr/bin/env python3
"""Compose Quest tracking and robot modules into the Web application.

The shipped composition enables the dexterous-hand module.  Sources, frame
contracts, lifecycle orchestration, and output modules live outside this entry
point so an arm module can be registered alongside it without changing the
control loop.
"""

import argparse
import os
import sys
import time

import numpy as np
try:
    import logging_mp
except ModuleNotFoundError:
    # logging_mp is convenient in the full robot stack, but standard logging
    # is sufficient for this single-process entry point and for --help.
    import logging as logging_mp

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

try:
    logging_mp.basicConfig(level=logging_mp.INFO)
except RuntimeError:
    # logging_mp rejects reconfiguration when this module is imported by an
    # application that has already initialised Python logging.
    pass
logger_mp = logging_mp.getLogger(__name__)


class TeleopState:
    """Runtime state changed by validated web-console actions."""

    def __init__(self, start_immediately=False):
        self.running = True
        self.tracking_enabled = start_immediately

    def apply_action(self, action):
        if action == "run":
            self.tracking_enabled = True
            logger_mp.info("Hand tracking enabled.")
        elif action == "pause":
            self.tracking_enabled = False
            logger_mp.info("Hand tracking stopped; retaining the last hand target.")
        elif action == "disconnect":
            self.tracking_enabled = False
            logger_mp.info("Device session disconnected; returning to setup.")
        elif action == "quit":
            self.tracking_enabled = False
            self.running = False
        else:
            raise ValueError(f"Unknown teleoperation action: {action!r}")


def _copy_landmarks(shared_array, landmarks, side):
    """Validate the 25x3 Quest landmark payload before sharing it with control."""
    data = np.asarray(landmarks, dtype=np.float64)
    if data.shape != (25, 3):
        raise ValueError(f"Quest {side} hand landmarks must have shape (25, 3), got {data.shape}.")
    if not np.isfinite(data).all():
        raise ValueError(f"Quest {side} hand landmarks contain NaN or infinity.")
    with shared_array.get_lock():
        shared_array[:] = data.ravel()


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Standalone Quest hand teleoperation for six-DOF dexterous hands."
    )
    parser.add_argument("--frequency", type=float, default=60.0, help="Quest landmark polling rate in Hz (default: 60).")
    parser.add_argument("--hand-frequency", type=float, default=100.0, help="hand command rate in Hz (default: 100).")
    parser.add_argument(
        "--tactile-frequency",
        type=float,
        default=10.0,
        help="tactile polling rate in Hz, 1-60 (default: 10).",
    )
    parser.add_argument("--left-hand-host", help="Enable the left hand at this Modbus TCP address.")
    parser.add_argument(
        "--right-hand-host",
        default="192.168.11.210",
        help="Enable the right hand at this Modbus TCP address (default: 192.168.11.210).",
    )
    parser.add_argument("--modbus-port", type=int, default=6000, help="Modbus TCP port for both hands (default: 6000).")
    parser.add_argument("--left-device-id", type=int, default=1, help="Left-hand Modbus device ID (default: 1).")
    parser.add_argument("--right-device-id", type=int, default=1, help="Right-hand Modbus device ID (default: 1).")
    parser.add_argument("--modbus-timeout", type=float, default=3.0, help="Modbus request timeout in seconds (default: 3).")
    parser.add_argument("--target-speed", type=int, default=300, help="Joint speed used in fixed mode, 0-1000 (default: 300).")
    parser.add_argument(
        "--speed-mode",
        choices=["adaptive_v2", "adaptive_v1", "adaptive", "fixed"],
        default="adaptive_v2",
        help=(
            "Joint speed strategy; adaptive is an alias for adaptive_v2 "
            "(default: adaptive_v2)."
        ),
    )
    parser.add_argument("--display-mode", choices=["immersive", "ego", "pass-through"], default="pass-through",
                        help="Quest display mode. No image stream is opened by this module (default: pass-through).")
    parser.add_argument("--image-width", type=int, default=640, help="Placeholder XR image width required by televuer (default: 640).")
    parser.add_argument("--image-height", type=int, default=480, help="Placeholder XR image height required by televuer (default: 480).")
    parser.add_argument("--binocular", action="store_true", help="Configure the Quest viewer for binocular images if a display stream is added later.")
    parser.add_argument(
        "--hide-hand-markers",
        action="store_true",
        help="Hide Quest hand joint/skeleton markers (shown by default).",
    )
    parser.add_argument("--start", action="store_true", help="Enable tracking immediately after the web setup is confirmed.")
    parser.add_argument(
        "--open-on-exit",
        action="store_true",
        help="Command all joints to 1000 (open) when a device session disconnects cleanly.",
    )
    parser.add_argument("--web-host", default="127.0.0.1", help="Web console listen address (default: 127.0.0.1).")
    parser.add_argument("--web-port", type=int, default=8080, help="Web console port (default: 8080).")
    parser.add_argument(
        "--browser",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Open the web console in the default browser (default: enabled).",
    )
    parser.add_argument(
        "--language",
        choices=["auto", "zh", "en"],
        default="auto",
        help="Web console language: auto, zh, or en (default: auto).",
    )
    args = parser.parse_args(argv)
    if not args.left_hand_host and not args.right_hand_host:
        parser.error("At least one hand host must be configured.")
    if args.frequency <= 0 or args.hand_frequency <= 0:
        parser.error("--frequency and --hand-frequency must be positive.")
    if not 1 <= args.tactile_frequency <= 60:
        parser.error("--tactile-frequency must be in the range 1-60.")
    if args.image_width <= 0 or args.image_height <= 0:
        parser.error("--image-width and --image-height must be positive.")
    if not 1 <= args.modbus_port <= 65535:
        parser.error("--modbus-port must be in the range 1-65535.")
    if not 1 <= args.left_device_id <= 254 or not 1 <= args.right_device_id <= 254:
        parser.error("--left-device-id and --right-device-id must be in the range 1-254.")
    if args.modbus_timeout <= 0:
        parser.error("--modbus-timeout must be positive.")
    if not 0 <= args.target_speed <= 1000:
        parser.error("--target-speed must be in the range 0-1000.")
    if not 1 <= args.web_port <= 65535:
        parser.error("--web-port must be in the range 1-65535.")
    return args


def _apply_web_config(args, config):
    """Apply the validated connection form to the command-line namespace."""

    args.left_hand_host = config["left_host"] if config["left_enabled"] else None
    args.right_hand_host = config["right_host"] if config["right_enabled"] else None
    for name in (
        "left_device_id", "right_device_id", "modbus_port", "modbus_timeout",
        "target_speed", "speed_mode", "frequency", "hand_frequency",
        "tactile_frequency", "start", "open_on_exit", "hide_hand_markers",
    ):
        setattr(args, name, config[name])


def main():
    args = parse_args()
    from inspire_teleoperation.web_ui import HandTeleoperationWebUI, TeleopSnapshot

    state = TeleopState()
    web_ui = HandTeleoperationWebUI(args)

    try:
        web_ui.start(open_browser=args.browser)
        logger_mp.info("Hand teleoperation web console: %s", web_ui.url)
        while state.running:
            runtime = None
            session_error = ""
            logger_mp.info("Waiting for connection settings and safety confirmation.")
            config = web_ui.wait_for_setup()
            if config is None:
                state.apply_action("quit")
                break

            _apply_web_config(args, config)
            state.tracking_enabled = args.start
            web_ui.set_phase("connecting")

            try:
                # Import hardware integrations only after the browser setup form is
                # confirmed, keeping --help and the setup page hardware-independent.
                from inspire_teleoperation.api import TeleopFrame
                from inspire_teleoperation.hand_module import HandTeleopModule
                from inspire_teleoperation.quest_source import QuestSource
                from inspire_teleoperation.runtime import TeleopRuntime

                source = QuestSource(
                    binocular=args.binocular,
                    image_shape=(args.image_height, args.image_width, 3),
                    display_mode=args.display_mode,
                    show_hand_markers=not args.hide_hand_markers,
                )
                hand_module = HandTeleopModule(
                    left_host=args.left_hand_host,
                    right_host=args.right_hand_host,
                    open_on_exit=args.open_on_exit,
                    port=args.modbus_port,
                    left_device_id=args.left_device_id,
                    right_device_id=args.right_device_id,
                    timeout=args.modbus_timeout,
                    target_speed=args.target_speed,
                    speed_mode=args.speed_mode,
                    fps=args.hand_frequency,
                    tactile_frequency=args.tactile_frequency,
                )
                runtime = TeleopRuntime(source, [hand_module])
                runtime.set_enabled(state.tracking_enabled)
                runtime.start()

                logger_mp.info("Hand teleoperation is ready.")
                logger_mp.info(
                    "Use the web console to start or stop tracking, change speed, "
                    "or disconnect the devices."
                )
                enabled_sides = [
                    side
                    for side, host in (
                        ("left", args.left_hand_host),
                        ("right", args.right_hand_host),
                    )
                    if host
                ]
                logger_mp.info("Enabled hand(s): %s.", ", ".join(enabled_sides))
                logger_mp.info("Keep clear of enabled hands while commands are enabled.")
                web_ui.set_phase("live")

                session_started_at = time.monotonic()
                loop_sample_started_at = session_started_at
                loop_sample_count = 0
                loop_hz = 0.0
                session_active = True

                while state.running and session_active:
                    cycle_start = time.monotonic()
                    tactile_selection = web_ui.poll_tactile_selection()
                    if tactile_selection is not None:
                        hand_module.set_tactile_sides(tactile_selection)
                    action = web_ui.poll_action()
                    if action == "run":
                        state.apply_action("run")
                        runtime.set_enabled(True)
                    elif action == "pause":
                        state.apply_action("pause")
                        runtime.set_enabled(False)
                    elif action == "disconnect":
                        state.apply_action("disconnect")
                        runtime.set_enabled(False)
                        web_ui.set_phase("disconnecting")
                        session_active = False
                        continue
                    elif action == "quit":
                        state.apply_action("quit")
                        runtime.set_enabled(False)
                        continue
                    elif action == "speed_mode":
                        mode = hand_module.toggle_speed_mode()
                        logger_mp.info("Switched to %s joint speed mode.", mode)
                    elif action == "motion_filter":
                        enabled = hand_module.toggle_motion_filter()
                        logger_mp.info(
                            "Motion micro-filter %s.",
                            "enabled" if enabled else "disabled",
                        )
                    elif action == "calibrate_force":
                        if state.tracking_enabled:
                            state.apply_action("pause")
                            runtime.set_enabled(False)
                        web_ui.set_calibration_state("running")
                        try:
                            calibrated_sides = hand_module.calibrate_force_sensors()
                        except Exception as error:
                            web_ui.set_calibration_state("failed", str(error))
                            logger_mp.exception(
                                "Force-sensor calibration failed: %s", error
                            )
                        else:
                            calibrated = ", ".join(calibrated_sides)
                            web_ui.set_calibration_state("completed", calibrated)
                            logger_mp.info(
                                "Force-sensor calibration completed for: %s; "
                                "unloaded force readings are stable.",
                                calibrated,
                            )

                    try:
                        runtime.step()
                    except (AttributeError, TypeError, ValueError) as error:
                        # A transient malformed XR frame must not become a robot
                        # command or kill the control session.
                        logger_mp.warning(
                            "Ignoring invalid Quest tracking frame: %s", error
                        )
                        runtime.dispatch(TeleopFrame.empty())

                    loop_sample_count += 1
                    sample_elapsed = time.monotonic() - loop_sample_started_at
                    if sample_elapsed >= 0.5:
                        loop_hz = loop_sample_count / sample_elapsed
                        loop_sample_started_at = time.monotonic()
                        loop_sample_count = 0

                    module_statuses = runtime.status()
                    hand_status = module_statuses[hand_module.name]
                    telemetry = hand_status.telemetry
                    web_ui.publish(
                        TeleopSnapshot(
                            tracking_enabled=state.tracking_enabled,
                            motion_data_ready=bool(telemetry["motion_data_ready"]),
                            loop_hz=loop_hz,
                            elapsed_seconds=time.monotonic() - session_started_at,
                            left_enabled=telemetry["left_enabled"],
                            right_enabled=telemetry["right_enabled"],
                            left_state=telemetry["left_state"],
                            right_state=telemetry["right_state"],
                            left_target=telemetry["left_target"],
                            right_target=telemetry["right_target"],
                            speed_mode=telemetry["speed_mode"],
                            motion_filter_enabled=telemetry[
                                "motion_filter_enabled"
                            ],
                            left_speed=telemetry["left_speed"],
                            right_speed=telemetry["right_speed"],
                            modules={
                                name: {
                                    "ready": status.ready,
                                    "detail": status.detail,
                                }
                                for name, status in module_statuses.items()
                            },
                            tactile=telemetry["tactile"],
                        )
                    )

                    sleep_time = (1.0 / args.frequency) - (
                        time.monotonic() - cycle_start
                    )
                    if sleep_time > 0:
                        time.sleep(sleep_time)
            except KeyboardInterrupt:
                raise
            except Exception as error:
                session_error = str(error)
                web_ui.set_phase("error", session_error)
                logger_mp.exception("Device session stopped due to an error.")
            finally:
                if runtime is not None:
                    try:
                        runtime.set_enabled(False)
                        runtime.close()
                    except Exception as error:
                        logger_mp.exception("Failed to close the device session cleanly.")
                        if not session_error:
                            session_error = str(error)

            if state.running:
                web_ui.return_to_setup(session_error)
    except KeyboardInterrupt:
        logger_mp.info("Keyboard interrupt received; exiting hand teleoperation.")
    finally:
        web_ui.set_phase("stopping")
        web_ui.set_phase("stopped")
        web_ui.stop()


if __name__ == "__main__":
    main()
