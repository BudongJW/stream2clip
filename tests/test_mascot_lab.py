"""The mascot design lab (packaging/mascot_lab.py): its reference sheets, its record of how each file was made,
and the steps that need none of the lab's models."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def lab():
    spec = importlib.util.spec_from_file_location("mascot_lab", ROOT / "packaging" / "mascot_lab.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_sheets_and_design_files_are_recorded(lab):
    specs = lab.sheet_specs()
    assert {"turnaround", "expressions"} <= set(specs)
    for name, sheet in specs.items():
        assert sheet["items"] and all((lab.MASCOT / file).is_file() for _label, file in sheet["items"]), name
        assert (lab.DESIGN / f"sheet_{name}.png").is_file(), name  # built and kept with the pictures it shows
    manifest = json.loads(lab.MANIFEST.read_text(encoding="utf-8"))["files"]
    made = {p.relative_to(lab.DESIGN).as_posix() for p in lab.DESIGN.rglob("*") if p.is_file() and p != lab.MANIFEST}
    assert made == set(manifest)  # every file says how it was made, and nothing gone is still listed
    for name, entry in manifest.items():
        assert entry["tool"] and entry["made"], name
        if not name.startswith("sheet_") and not name.endswith("_views.png"):
            assert entry["licence"] and entry["model"], name  # which model, under which licence
        if "Space" in entry["tool"]:
            assert entry["seed"] is not None and entry["input"], name  # a hosted picture can be made again


def test_models_are_pinned_and_free_to_use(lab):
    for model in lab.LOCAL_MODELS.values():
        assert len(model["revision"]) == 40 and model["licence"] in ("MIT", "CreativeML OpenRAIL-M")
    assert len(lab.TRIPOSR_CODE[1]) == 40 and lab.REMBG_MODEL == "isnet-anime"  # rembg's default is non-commercial
    assert "Hunyuan" not in json.dumps(lab.LOCAL_MODELS) + lab.EDIT_SPACE + lab.TRELLIS_SPACE  # its licence excludes South Korea
    assert set(lab.ANGLES) == {"front", "front-right", "right", "back-right", "back", "back-left", "left", "front-left"}


def test_a_triposr_mesh_is_turned_for_gltf(lab):
    class Visual:
        kind = "vertex"
        vertex_colors = np.array([[255, 128, 0, 255]], dtype=np.uint8)

    class Mesh:
        visual = Visual()

        def apply_transform(self, matrix):
            self.matrix = matrix

    mesh = lab.gltf_ready(Mesh())
    up, front = mesh.matrix[:3, :3] @ np.array([0, 0, 1]), mesh.matrix[:3, :3] @ np.array([1, 0, 0])
    assert up.tolist() == [0, 1, 0] and front.tolist() == [0, 0, 1]  # TripoSR's z up, facing +x -> glTF's y up, facing +z
    assert np.linalg.det(mesh.matrix[:3, :3]) == pytest.approx(1.0)  # a turn, not a mirror
    assert mesh.visual.vertex_colors.tolist() == [[255, 56, 0, 255]]  # sRGB to linear, alpha kept


def test_scenes_keep_the_character_and_go_on_the_next_day(lab, monkeypatch, tmp_path, capsys):
    names = [s[1] for s in lab.SCENES]
    assert len(names) == len(set(names)) >= 12 and names[0] == "fullbody"  # the whole figure first: the outfits stand on it
    for group, name, label, prompt, lora in lab.SCENES:
        assert group in lab.SHEETS and label and lora in ("angles", "anime"), name
        assert "cat-ear headphones" in prompt and "hair clip" in prompt, name  # every picture keeps what makes her Kiri
        assert ("green background" in prompt) != (group == "daily"), name  # scenes have their place; the rest can be cut out
    monkeypatch.setattr(lab, "DESIGN", tmp_path)
    made = []

    def edit(inputs, prompt, output, *, lora, seed):
        if len(made) == 3:
            raise RuntimeError("You have exceeded your ZeroGPU runs limit.")
        made.append(output.stem)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(b"png")

    monkeypatch.setattr(lab, "hosted_edit", edit)
    assert lab.make_scenes() == 3 and made == ["raw_fullbody", "raw_editing", "raw_streaming"]
    assert "10 left" in capsys.readouterr().err  # the spent allowance stops the run, it does not fail it
    made.clear()
    made.append("next day")
    assert lab.make_scenes(["ramen"]) == 0 and made == ["next day", "raw_ramen"]  # already made: not asked for again
    assert [label for label, _file in lab.sheet_specs()["daily"]["items"]] == ["클립 편집", "방송 중", "라면"]

    def broken(*args, **kwargs):
        raise RuntimeError("The model failed")

    monkeypatch.setattr(lab, "hosted_edit", broken)
    with pytest.raises(RuntimeError, match="model failed"):  # any other failure is not taken for the allowance
        lab.make_scenes(["gaming"])


def test_commands_need_the_lab(lab, monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("STREAM2CLIP_MASCOT_LAB", str(tmp_path / "none"))
    assert lab.main(["sheets"]) == 2 and "setup" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        lab.main(["angle", "upside-down", "-o", str(tmp_path / "x.png")])
