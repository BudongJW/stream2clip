"""Find the VTuber avatar in a stream and suggest a box for the ``stack`` layout.

An avatar sits in the same corner for a whole stream, so this does not track
anything frame by frame: a handful of frames are sampled, anime faces are
detected in each, and the face that keeps turning up in the same place is taken
as the avatar. Game characters and thumbnails come and go; the avatar stays.
The result is one fixed :class:`~stream2clip.geometry.Region` per stream
(``--layout stack --avatar auto``).

The default detector is ``deepghs/anime_face_detection`` (``face_detect_v1.4_n``,
MIT, 12 MB ONNX, YOLOv8 output layout) run with onnxruntime
(``pip install "stream2clip[detect]"``). Everything except :class:`OnnxFaceDetector`
is plain numpy, and any object with a ``detect(image)`` method can stand in for it
(see :func:`stream2clip.plugins.register_face_detector`).
"""

from __future__ import annotations

import hashlib
import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol, Sequence, runtime_checkable

import numpy as np

from .frames import ensure_rgba
from .geometry import Region

__all__ = [
    "Face",
    "FaceDetector",
    "AvatarSuggestion",
    "OnnxFaceDetector",
    "MODEL_URL",
    "MODEL_SHA256",
    "model_path",
    "ensure_model",
    "letterbox",
    "decode_yolo",
    "nms",
    "sample_times",
    "avatar_box",
    "suggest_avatar",
    "suggest_avatar_for_video",
    "draw_suggestion",
]

MODEL_NAME = "face_detect_v1.4_n"
MODEL_URL = "https://huggingface.co/deepghs/anime_face_detection/resolve/main/face_detect_v1.4_n/model.onnx"
MODEL_SHA256 = "fd860b650a4377046842c3cd80d01b0b408bdfbdb4acee5759630f82c6ef04a9"
#: Score threshold published with the model (best F1).
MODEL_THRESHOLD = 0.278


@dataclass(frozen=True)
class Face:
    region: Region
    score: float


@runtime_checkable
class FaceDetector(Protocol):
    def detect(self, image: np.ndarray) -> list[Face]: ...  # image: (h, w, 3 or 4) uint8 RGB(A)


@dataclass(frozen=True)
class AvatarSuggestion:
    """``region`` is the box to crop; ``face`` the typical face inside it."""

    region: Region
    face: Region
    frames: int  # frames looked at
    hits: int  # frames in which this face was found
    score: float  # mean detector score

    @property
    def presence(self) -> float:
        return self.hits / self.frames if self.frames else 0.0


# --------------------------------------------------------------------------- model file


def model_path() -> Path:
    """Where the default model is kept (``STREAM2CLIP_MODEL_DIR`` or the user cache)."""
    base = os.environ.get("STREAM2CLIP_MODEL_DIR")
    root = Path(base) if base else Path.home() / ".cache" / "stream2clip"
    return root / f"{MODEL_NAME}.onnx"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def ensure_model(path: str | os.PathLike[str] | None = None, *, download: bool = True) -> Path:
    """Return the model file, downloading the default one (12 MB) on first use.

    The download is checked against a pinned SHA-256, so a changed or truncated
    file is rejected instead of being loaded.
    """
    if path is not None:
        given = Path(path)
        if not given.is_file():
            raise FileNotFoundError(f"Face detection model not found: {given}")
        return given
    target = model_path()
    if target.is_file():
        return target
    if not download:
        raise FileNotFoundError(f"Face detection model not found: {target} (download {MODEL_URL})")
    target.parent.mkdir(parents=True, exist_ok=True)
    partial = target.with_suffix(".part")
    with urllib.request.urlopen(MODEL_URL, timeout=60) as response, partial.open("wb") as fh:  # noqa: S310 - fixed https URL
        while True:
            block = response.read(1 << 16)
            if not block:
                break
            fh.write(block)
    got = _sha256(partial)
    if got != MODEL_SHA256:
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Downloaded face model has an unexpected checksum ({got[:12]}...); not using it")
    partial.replace(target)
    return target


# --------------------------------------------------------------------------- YOLO pre / post-processing


def letterbox(image: np.ndarray, size: int = 640) -> tuple[np.ndarray, float, int, int]:
    """Fit ``image`` into a grey ``size`` x ``size`` square.

    Returns ``(tensor, scale, pad_x, pad_y)`` with ``tensor`` shaped ``(1, 3, size, size)``
    float32 in 0..1; a point ``(x, y)`` of the source is at ``(x * scale + pad_x, y * scale + pad_y)``.
    """
    from PIL import Image

    rgb = ensure_rgba(image)[..., :3]
    h, w = rgb.shape[:2]
    scale = min(size / w, size / h)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    pad_x, pad_y = (size - new_w) // 2, (size - new_h) // 2
    canvas = np.full((size, size, 3), 114, dtype=np.uint8)
    resized = np.asarray(Image.fromarray(rgb, "RGB").resize((new_w, new_h), Image.Resampling.BILINEAR))
    canvas[pad_y : pad_y + new_h, pad_x : pad_x + new_w] = resized
    tensor = canvas.astype(np.float32).transpose(2, 0, 1)[None] / 255.0
    return tensor, scale, pad_x, pad_y


def _iou(box: np.ndarray, others: np.ndarray) -> np.ndarray:
    x0 = np.maximum(box[0], others[:, 0])
    y0 = np.maximum(box[1], others[:, 1])
    x1 = np.minimum(box[2], others[:, 2])
    y1 = np.minimum(box[3], others[:, 3])
    inter = np.clip(x1 - x0, 0, None) * np.clip(y1 - y0, 0, None)
    area = (box[2] - box[0]) * (box[3] - box[1])
    areas = (others[:, 2] - others[:, 0]) * (others[:, 3] - others[:, 1])
    return inter / np.maximum(area + areas - inter, 1e-9)


def nms(boxes: np.ndarray, scores: np.ndarray, iou: float = 0.5) -> list[int]:
    """Indices of the boxes (``x0, y0, x1, y1``) kept by non-maximum suppression, best first."""
    order = list(np.argsort(-scores, kind="stable"))
    keep: list[int] = []
    while order:
        best = order.pop(0)
        keep.append(int(best))
        if order:
            rest = np.array(order)
            order = list(rest[_iou(boxes[best], boxes[rest]) <= iou])
    return keep


def decode_yolo(
    output: np.ndarray, scale: float, pad_x: int, pad_y: int, image_size: tuple[int, int], *, threshold: float = MODEL_THRESHOLD, iou: float = 0.5
) -> list[Face]:
    """Turn a single-class YOLOv8 output into faces in source pixels.

    ``output`` is what the model returns, ``(1, 5, N)`` with rows cx, cy, w, h, score,
    or an already transposed ``(N, 5)`` array.
    """
    rows = np.asarray(output, dtype=np.float64)
    if rows.ndim == 3:
        rows = rows[0].T
    elif rows.shape[1] != 5 and rows.shape[0] == 5:
        rows = rows.T
    rows = rows[rows[:, 4] >= threshold]
    if not len(rows):
        return []
    width, height = image_size
    x0 = (rows[:, 0] - rows[:, 2] / 2 - pad_x) / scale
    y0 = (rows[:, 1] - rows[:, 3] / 2 - pad_y) / scale
    x1 = (rows[:, 0] + rows[:, 2] / 2 - pad_x) / scale
    y1 = (rows[:, 1] + rows[:, 3] / 2 - pad_y) / scale
    boxes = np.stack([np.clip(x0, 0, width), np.clip(y0, 0, height), np.clip(x1, 0, width), np.clip(y1, 0, height)], axis=1)
    faces = []
    for i in nms(boxes, rows[:, 4], iou):
        region = Region.from_points(*boxes[i])
        if region.width >= 2 and region.height >= 2:
            faces.append(Face(region, float(rows[i, 4])))
    return faces


class OnnxFaceDetector:
    """``deepghs/anime_face_detection`` through onnxruntime (CPU is plenty: ~30 ms per frame)."""

    def __init__(self, model: str | os.PathLike[str] | None = None, *, threshold: float = MODEL_THRESHOLD, size: int = 640, download: bool = True) -> None:
        try:
            import onnxruntime  # type: ignore[import-not-found]
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError('Avatar detection needs onnxruntime: pip install "stream2clip[detect]"') from exc
        self.threshold = threshold
        self.size = size
        self._session = onnxruntime.InferenceSession(os.fspath(ensure_model(model, download=download)), providers=["CPUExecutionProvider"])
        self._input = self._session.get_inputs()[0].name

    def detect(self, image: np.ndarray) -> list[Face]:
        tensor, scale, pad_x, pad_y = letterbox(image, self.size)
        output = self._session.run(None, {self._input: tensor})[0]
        h, w = image.shape[:2]
        return decode_yolo(output, scale, pad_x, pad_y, (w, h), threshold=self.threshold)


# --------------------------------------------------------------------------- avatar box


def sample_times(duration: float, count: int = 12, *, margin: float = 0.08) -> list[float]:
    """``count`` evenly spread timestamps, skipping the first and last ``margin`` (intro / ending screens)."""
    if duration <= 0 or count < 1:
        return []
    lo, hi = duration * margin, duration * (1 - margin)
    if count == 1:
        return [(lo + hi) / 2]
    return [lo + (hi - lo) * i / (count - 1) for i in range(count)]


def avatar_box(face: Region, frame: tuple[int, int], aspect: float, *, zoom: float = 3.0, face_at: float = 0.55) -> Region:
    """Grow a face box into a head-and-shoulders box of the given ``aspect`` (width / height).

    The box is ``zoom`` face-heights tall with the face centre ``face_at`` of the way
    down - a detected anime face is roughly eyes-to-chin, so most of the room goes
    above it for hair, ears and hats. The box is pushed back inside the frame and
    shrunk if the frame is too small.
    """
    fw, fh = frame
    height = min(fh, max(face.height * zoom, face.width * 1.6 / aspect))
    width = height * aspect
    if width > fw:
        width, height = fw, fw / aspect
    cx = face.x + face.width / 2
    cy = face.y + face.height / 2
    x = min(max(0.0, cx - width / 2), fw - width)
    y = min(max(0.0, cy - height * face_at), fh - height)
    box = Region.from_points(x, y, x + width, y + height)
    return Region(box.x, box.y, max(2, box.width - box.width % 2), max(2, box.height - box.height % 2))


def _cluster(faces_per_frame: Sequence[Sequence[Face]]) -> list[list[tuple[int, Face]]]:
    """Group detections that stay in the same place across frames."""
    clusters: list[list[tuple[int, Face]]] = []
    for index, faces in enumerate(faces_per_frame):
        for face in sorted(faces, key=lambda f: -f.score):
            cx, cy = face.region.x + face.region.width / 2, face.region.y + face.region.height / 2
            best, best_distance = None, None
            for cluster in clusters:
                if any(i == index for i, _ in cluster):
                    continue  # one face per frame per cluster
                xs = np.median([f.region.x + f.region.width / 2 for _, f in cluster])
                ys = np.median([f.region.y + f.region.height / 2 for _, f in cluster])
                size = np.median([max(f.region.width, f.region.height) for _, f in cluster])
                distance = float(np.hypot(cx - xs, cy - ys))
                similar = 0.5 <= max(face.region.width, face.region.height) / max(size, 1e-9) <= 2.0
                # A Live2D head sways and leans, so "the same place" is within about one face size.
                if similar and distance <= size and (best_distance is None or distance < best_distance):
                    best, best_distance = cluster, distance
            if best is None:
                clusters.append([(index, face)])
            else:
                best.append((index, face))
    return clusters


def suggest_avatar(
    frames: Iterable[np.ndarray],
    detector: FaceDetector,
    *,
    aspect: float = 1080 / (1920 * 0.42),
    min_presence: float = 0.4,
    zoom: float = 3.0,
) -> AvatarSuggestion | None:
    """Pick the face that is in the same place in most ``frames`` and box it for the stack layout.

    Returns ``None`` when no face shows up in at least ``min_presence`` of the frames
    (no avatar on screen, or it moves around too much for one fixed box).
    """
    faces_per_frame: list[list[Face]] = []
    size: tuple[int, int] | None = None
    for frame in frames:
        h, w = frame.shape[:2]
        size = size or (w, h)
        faces_per_frame.append(list(detector.detect(frame)))
    if not faces_per_frame or size is None:
        return None
    clusters = _cluster(faces_per_frame)
    if not clusters:
        return None

    def rank(cluster: list[tuple[int, Face]]) -> tuple[int, float]:
        return (len(cluster), float(np.mean([f.score for _, f in cluster])))

    best = max(clusters, key=rank)
    if len(best) / len(faces_per_frame) < min_presence:
        return None
    regions = [f.region for _, f in best]
    # Box the whole area the head moves through, sized by the typical face.
    left, top = min(r.x for r in regions), min(r.y for r in regions)
    right, bottom = max(r.right for r in regions), max(r.bottom for r in regions)
    typical = Region.from_points(
        float(np.median([r.x for r in regions])), float(np.median([r.y for r in regions])),
        float(np.median([r.right for r in regions])), float(np.median([r.bottom for r in regions])),
    )
    cx, cy = (left + right) / 2, (top + bottom) / 2
    centred = Region.from_points(cx - typical.width / 2, cy - typical.height / 2, cx + typical.width / 2, cy + typical.height / 2)
    sway = max(right - left, bottom - top) / max(typical.width, typical.height, 1)
    region = avatar_box(centred, size, aspect, zoom=zoom * max(1.0, min(sway, 1.5) ** 0.5))
    return AvatarSuggestion(region=region, face=typical, frames=len(faces_per_frame), hits=len(best), score=float(np.mean([f.score for _, f in best])))


def suggest_avatar_for_video(
    video: str | os.PathLike[str],
    detector: FaceDetector | None = None,
    *,
    samples: int = 12,
    aspect: float = 1080 / (1920 * 0.42),
    min_presence: float = 0.4,
    ffmpeg: str | None = None,
) -> AvatarSuggestion | None:
    """Sample ``samples`` frames from ``video`` and call :func:`suggest_avatar`."""
    from .export import grab_frames, probe

    info = probe(video)
    if not info.duration:
        raise ValueError(f"Cannot tell how long {video} is")
    frames = grab_frames(video, sample_times(info.duration, samples), ffmpeg=ffmpeg)
    return suggest_avatar(frames, detector or default_detector(), aspect=aspect, min_presence=min_presence)


def default_detector() -> FaceDetector:
    """The first registered face-detector plugin, else the bundled ONNX model."""
    from .plugins import face_detectors

    for factory in face_detectors().values():
        return factory()
    return OnnxFaceDetector()


def draw_suggestion(frame: np.ndarray, suggestion: AvatarSuggestion):
    """Preview image: the suggested box and the typical face drawn on ``frame`` (PIL image)."""
    from PIL import Image, ImageDraw

    from .brand import HIGHLIGHT, LIVE_PINK

    image = Image.fromarray(ensure_rgba(frame)[..., :3], "RGB")
    draw = ImageDraw.Draw(image)
    stroke = max(2, image.width // 320)
    draw.rectangle(suggestion.region.as_box(), outline=LIVE_PINK, width=stroke)
    draw.rectangle(suggestion.face.as_box(), outline=HIGHLIGHT, width=max(1, stroke // 2))
    return image
