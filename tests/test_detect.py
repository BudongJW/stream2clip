from __future__ import annotations

import io
import os
from pathlib import Path

import numpy as np
import pytest

from stream2clip import detect, plugins
from stream2clip.cli import main
from stream2clip.detect import Face, avatar_box, decode_yolo, letterbox, nms, sample_times, suggest_avatar
from stream2clip.geometry import Region

from .conftest import needs_ffmpeg

ASPECT = 1080 / (1920 * 0.42)


class ScriptedDetector:
    """Returns a prepared list of faces for each frame it is shown."""

    def __init__(self, per_frame):
        self.per_frame = list(per_frame)
        self.calls = 0

    def detect(self, image):
        faces = self.per_frame[self.calls % len(self.per_frame)]
        self.calls += 1
        return [Face(Region(*box), score) for box, score in faces]


def frames(n, size=(854, 480)):
    return [np.zeros((size[1], size[0], 3), np.uint8) for _ in range(n)]


def test_letterbox_keeps_aspect_and_reports_the_mapping():
    image = np.zeros((480, 854, 3), np.uint8)
    image[100:200, 300:400] = 255
    tensor, scale, pad_x, pad_y = letterbox(image, 640)
    assert tensor.shape == (1, 3, 640, 640) and tensor.dtype == np.float32
    assert scale == pytest.approx(640 / 854) and (pad_x, pad_y) == (0, 140)
    assert tensor[0, :, 10, 10] == pytest.approx(114 / 255)  # grey padding above the picture
    x, y = round(350 * scale + pad_x), round(150 * scale + pad_y)
    assert tensor[0, :, y, x] == pytest.approx(1.0)  # the white square lands where the mapping says


def test_decode_yolo_maps_back_to_source_pixels_and_merges_duplicates():
    scale, pad_x, pad_y = 640 / 854, 0, 140
    # the same face reported by three anchors, a weak one, and a second face
    rows = np.array([
        [587.0, 404.3, 61.0, 58.8, 0.84],
        [587.1, 404.5, 61.2, 59.0, 0.83],
        [586.9, 404.1, 60.8, 58.6, 0.80],
        [300.0, 300.0, 40.0, 40.0, 0.10],
        [100.0, 250.0, 50.0, 50.0, 0.60],
    ])
    for output in (rows.T[None], rows):  # (1, 5, N) as the model gives it, or (N, 5)
        faces = decode_yolo(output, scale, pad_x, pad_y, (854, 480))
        assert [f.score for f in faces] == [0.84, 0.60]
        assert faces[0].region == Region(743, 313, 81, 79)  # what the real model found on a stream frame
    assert decode_yolo(rows, scale, pad_x, pad_y, (854, 480), threshold=0.9) == []


def test_nms_keeps_the_best_of_overlapping_boxes():
    boxes = np.array([[0, 0, 10, 10], [1, 1, 11, 11], [50, 50, 60, 60]], dtype=float)
    assert nms(boxes, np.array([0.5, 0.9, 0.7])) == [1, 2]


def test_sample_times_skips_intro_and_ending():
    times = sample_times(1000, 5)
    assert times == pytest.approx([80, 290, 500, 710, 920])
    assert sample_times(1000, 1) == [500] and sample_times(0, 5) == []


def test_avatar_box_shape_and_placement():
    face = Region(741, 316, 85, 79)  # bottom-right corner of a 854x480 stream
    box = avatar_box(face, (854, 480), ASPECT)
    assert box.width / box.height == pytest.approx(ASPECT, abs=0.03)
    assert box.width % 2 == 0 and box.height % 2 == 0
    assert box.x >= 0 and box.y >= 0 and box.right <= 854 and box.bottom <= 480  # pushed back inside the frame
    assert box.contains(face.x, face.y) and box.contains(face.right - 1, face.bottom - 1)
    assert face.y - box.y > box.bottom - face.bottom  # more room above the face (hair, ears) than below
    # A frame too small for the usual zoom: the box shrinks instead of leaving the frame.
    small = avatar_box(Region(40, 30, 60, 60), (160, 90), ASPECT)
    assert small.right <= 160 and small.bottom <= 90 and small.width / small.height == pytest.approx(ASPECT, abs=0.06)


def test_avatar_is_the_face_that_stays_put():
    avatar = [((741 + dx, 316 + dy, 85, 79), 0.83) for dx, dy in ((0, 0), (26, 1), (-3, -5), (-1, 27), (4, 1), (16, 21), (-5, -4), (0, 3))]
    per_frame = [[a] for a in avatar]
    per_frame[0] += [((595, 231, 71, 73), 0.80), ((73, 194, 90, 90), 0.78)]  # game characters come and go
    per_frame[1] += [((124, 341, 56, 53), 0.90)]
    per_frame[4] += [((125, 340, 58, 53), 0.90)]
    found = suggest_avatar(frames(8), ScriptedDetector(per_frame), aspect=ASPECT)
    assert found is not None and (found.hits, found.frames) == (8, 8) and found.presence == 1.0
    assert found.face.x == pytest.approx(741, abs=6) and found.face.width == pytest.approx(85, abs=4)
    for (x, y, w, h), _ in avatar:  # every position the head was seen in is inside the box
        assert found.region.contains(x, y) and found.region.contains(x + w - 1, y + h - 1)
    assert found.region.right <= 854 and found.region.bottom <= 480


def test_no_suggestion_without_a_steady_face():
    assert suggest_avatar(frames(6), ScriptedDetector([[]]), aspect=ASPECT) is None
    assert suggest_avatar([], ScriptedDetector([[]]), aspect=ASPECT) is None
    # a different place in every frame: nothing a fixed box could follow
    wandering = [[((100 * i, 40 * i, 60, 60), 0.9)] for i in range(6)]
    assert suggest_avatar(frames(6), ScriptedDetector(wandering), aspect=ASPECT) is None
    # seen in 2 of 6 frames only
    rare = [[((700, 300, 80, 80), 0.9)], [((702, 301, 80, 80), 0.9)], [], [], [], []]
    assert suggest_avatar(frames(6), ScriptedDetector(rare), aspect=ASPECT) is None
    assert suggest_avatar(frames(6), ScriptedDetector(rare), aspect=ASPECT, min_presence=0.3) is not None


def test_model_file_is_checked_before_use(tmp_path, monkeypatch):
    with pytest.raises(FileNotFoundError):
        detect.ensure_model(tmp_path / "missing.onnx")
    monkeypatch.setenv("STREAM2CLIP_MODEL_DIR", str(tmp_path / "cache"))
    with pytest.raises(FileNotFoundError):
        detect.ensure_model(download=False)

    monkeypatch.setattr(detect.urllib.request, "urlopen", lambda url, timeout=0: io.BytesIO(b"not the model"))
    with pytest.raises(RuntimeError, match="checksum"):
        detect.ensure_model()
    assert list((tmp_path / "cache").iterdir()) == []  # nothing left behind to be loaded later

    import hashlib

    payload = b"pretend model"
    monkeypatch.setattr(detect, "MODEL_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(detect.urllib.request, "urlopen", lambda url, timeout=0: io.BytesIO(payload))
    path = detect.ensure_model()
    assert path == detect.model_path() and path.read_bytes() == payload
    monkeypatch.setattr(detect.urllib.request, "urlopen", lambda url, timeout=0: pytest.fail("downloaded twice"))
    assert detect.ensure_model() == path


@pytest.fixture
def scripted_plugin(monkeypatch):
    detector = ScriptedDetector([[((100 + i % 2, 40, 30, 30), 0.9)] for i in range(4)])
    monkeypatch.setitem(plugins._RUNTIME["stream2clip.face_detectors"], "scripted", lambda: detector)
    return detector


@needs_ffmpeg
def test_grab_frames(green_screen_video):
    from stream2clip.export import grab_frames

    got = grab_frames(green_screen_video, [0.2, 1.0, 99.0])  # the last one is past the end
    assert len(got) == 2 and got[0].shape == (120, 160, 4) and got[0].dtype == np.uint8
    r, g, b = (int(v) for v in got[0][5, 150][:3])
    assert g > 250 and r < 5 and b < 5  # green background
    assert not np.array_equal(got[0], got[1])  # the square moved


@needs_ffmpeg
def test_cli_avatar_and_stack_auto(green_screen_video, scripted_plugin, tmp_path, capsys):
    preview = tmp_path / "preview.png"
    assert main(["avatar", str(green_screen_video), "--samples", "4", "--preview", str(preview)]) == 0
    out = capsys.readouterr().out
    assert "in 4/4 frames" in out and preview.exists()
    box = Region.parse(out.split()[1])
    assert box.contains(100, 40) and box.right <= 160 and box.bottom <= 120

    import json

    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.0, "end": 1.0}]}), encoding="utf-8")
    clips = tmp_path / "clips"
    args = ["clips", str(green_screen_video), "--highlights", str(highlights), "--layout", "stack", "--avatar", "auto",
            "--avatar-samples", "4", "--size", "108x192", "-f", "gif", "--fps", "5", "-o", str(clips)]
    assert main(args) == 0
    assert f"avatar {box}" in capsys.readouterr().out and (clips / "clip_01.gif").exists()


@needs_ffmpeg
def test_cli_avatar_reports_when_nothing_is_found(green_screen_video, monkeypatch, capsys):
    monkeypatch.setitem(plugins._RUNTIME["stream2clip.face_detectors"], "blind", lambda: ScriptedDetector([[]]))
    assert main(["avatar", str(green_screen_video)]) == 1
    assert "--avatar x,y,w,h" in capsys.readouterr().err


def _real_model() -> Path | None:
    for candidate in (os.environ.get("STREAM2CLIP_FACE_MODEL"), detect.model_path()):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def test_real_model_finds_the_faces_in_the_key_visual():
    """Runs only where the model is already on disk (it is never downloaded by the tests)."""
    pytest.importorskip("onnxruntime")
    model = _real_model()
    if model is None:
        pytest.skip("face model not downloaded (set STREAM2CLIP_FACE_MODEL or run `stream2clip avatar` once)")
    from PIL import Image

    image = np.asarray(Image.open(Path(__file__).parents[1] / "assets/brand/02_concept-image_keyvisual_1920x1080.png").convert("RGB"))
    faces = detect.OnnxFaceDetector(model).detect(image)
    assert faces and faces[0].score > 0.6
    assert faces[0].region.x == pytest.approx(1096, abs=20) and faces[0].region.width == pytest.approx(172, abs=20)
