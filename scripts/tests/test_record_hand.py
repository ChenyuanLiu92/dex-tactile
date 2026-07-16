import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_record_hand_script_forwards_help_without_virtualenv_warning():
    environment = os.environ.copy()
    environment["VIRTUAL_ENV"] = "/tmp/unrelated-environment"
    result = subprocess.run(
        [str(ROOT / "scripts" / "record_hand.sh"), "--help"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        timeout=20,
    )
    assert result.returncode == 0
    assert "--task" in result.stdout
    assert "does not match" not in result.stderr
