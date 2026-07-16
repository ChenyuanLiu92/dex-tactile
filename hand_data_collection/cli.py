from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .collector import CollectionOptions, collect_episode


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Record one RH56DFTP hand episode to HDF5.")
    result.add_argument("--task", required=True, help="Natural-language episode task label.")
    result.add_argument(
        "--operator",
        default="anonymous",
        help="Pseudonymous operator label stored in HDF5 metadata.",
    )
    result.add_argument("--duration", type=float, help="Optional recording duration in seconds.")
    result.add_argument("--output", type=Path, default=Path("datasets/hand"))
    result.add_argument("--source", choices=("auto", "viewer", "standalone"), default="auto")
    result.add_argument("--viewer-url", default="http://127.0.0.1:8787")
    result.add_argument("--startup-timeout", type=float, default=30.0)
    return result


def main() -> None:
    args = parser().parse_args()
    if args.duration is not None and args.duration <= 0:
        raise SystemExit("--duration must be positive")
    if args.startup_timeout <= 0:
        raise SystemExit("--startup-timeout must be positive")
    options = CollectionOptions(
        task=args.task,
        operator=args.operator,
        output=args.output,
        duration=args.duration,
        source=args.source,
        viewer_url=args.viewer_url,
        startup_timeout=args.startup_timeout,
    )
    try:
        asyncio.run(collect_episode(options))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
