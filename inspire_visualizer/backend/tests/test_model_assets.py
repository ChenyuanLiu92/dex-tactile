import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse
from xml.etree import ElementTree

import pytest


MODELS_ROOT = Path(__file__).resolve().parents[2] / "web" / "public" / "models"


@pytest.mark.parametrize("side", ["left", "right"])
def test_visual_meshes_referenced_by_urdf_exist(side: str) -> None:
    urdf_path = MODELS_ROOT / side / f"{side}.urdf"
    root = ElementTree.parse(urdf_path).getroot()
    references = [
        mesh.attrib["filename"]
        for mesh in root.findall(".//visual/geometry/mesh")
    ]

    assert references
    for reference in references:
        parsed = urlparse(reference)
        relative_path = Path(parsed.path.lstrip("/")).relative_to("meshes")
        assert (MODELS_ROOT / side / "meshes" / relative_path).is_file(), reference


def test_model_manifest_matches_runtime_assets() -> None:
    manifest = json.loads((MODELS_ROOT / "manifest.json").read_text(encoding="utf-8"))

    for side in ("left", "right"):
        model = manifest["models"][side]
        urdf_path = MODELS_ROOT / model["urdf"]
        digest = hashlib.sha256(urdf_path.read_bytes()).hexdigest()
        mesh_count = len(list((MODELS_ROOT / side / "meshes").glob("*.STL")))

        assert digest == model["sha256"]
        assert mesh_count == model["mesh_count"]
