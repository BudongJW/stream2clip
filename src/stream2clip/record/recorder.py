"""Real-time region recorder ("움짤 녹화").

Frames are grabbed at a fixed rate and streamed into a lossless FFV1/Matroska
intermediate (alpha preserved). When recording stops, the intermediate can be
exported to any number of formats (GIF, WebP, MP4, WebM, MOV, APNG) with
:meth:`Recording.export` - the same code path used for VOD clips.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Callable

import numpy as np

from ..capture import BackendFactory, CaptureBackend, default_backend
from ..capture.cursor import CursorProvider, draw_cursor
from ..export import FFmpegError, export
from ..ffmpeg import ExportOptions, RawVideoInput, build_capture_command
from ..frames import ensure_rgba
from ..geometry import Region

__all__ = ["Recorder", "Recording", "RecorderState", "FrameFilter"]

#: Optional per-frame hook (e.g. live chroma key preview, watermark, face blur).
FrameFilter = Callable[[np.ndarray], np.ndarray]


class RecorderState(Enum):
    IDLE = "idle"
    RECORDING = "recording"
    STOPPED = "stopped"
    FAILED = "failed"


@dataclass(frozen=True)
class Recording:
    """A finished capture stored as a lossless intermediate file."""

    path: Path
    region: Region
    fps: float
    frames: int
    duration: float

    def export(self, output: str | os.PathLike[str], options: ExportOptions | None = None, *, ffmpeg: str | None = None) -> Path:
        options = options or ExportOptions()
        if options.fps is None:
            from dataclasses import replace

            options = replace(options, fps=self.fps)
        return export(self.path, output, options, ffmpeg=ffmpeg)

    def discard(self) -> None:
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


class Recorder:
    """Record ``region`` of a capture backend at ``fps`` until :meth:`stop`.

    The capture loop keeps wall-clock timing: if a grab is slow, the previous
    frame is repeated so the clip plays back at real speed.
    """

    def __init__(
        self,
        region: Region,
        *,
        fps: float = 15.0,
        backend_factory: BackendFactory | None = None,
        cursor: CursorProvider | None = None,
        frame_filter: FrameFilter | None = None,
        output: str | os.PathLike[str] | None = None,
        max_duration: float | None = None,
        ffmpeg: str | None = None,
        on_frame: Callable[[int, float], None] | None = None,
    ) -> None:
        if region.is_empty:
            raise ValueError("Cannot record an empty region")
        if fps <= 0 or fps > 120:
            raise ValueError("fps must be in (0, 120]")
        self.region = region
        self.fps = float(fps)
        self._backend_factory = backend_factory or default_backend
        self._cursor = cursor
        self._filter = frame_filter
        self._max_duration = max_duration
        self._ffmpeg = ffmpeg
        self._on_frame = on_frame
        if output is None:
            fd, name = tempfile.mkstemp(prefix="stream2clip-", suffix=".mkv")
            os.close(fd)
            output = name
        self.output = Path(output)

        self.state = RecorderState.IDLE
        self.error: BaseException | None = None
        self.frames_written = 0
        self._started_at: float | None = None
        self._stopped_at: float | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._ready = threading.Event()

    # ------------------------------------------------------------------ public API
    @property
    def elapsed(self) -> float:
        if self._started_at is None:
            return 0.0
        end = self._stopped_at if self._stopped_at is not None else time.monotonic()
        return max(0.0, end - self._started_at)

    @property
    def is_recording(self) -> bool:
        return self.state is RecorderState.RECORDING

    def start(self) -> None:
        if self.state is not RecorderState.IDLE:
            raise RuntimeError(f"Recorder already {self.state.value}")
        self.state = RecorderState.RECORDING
        self._thread = threading.Thread(target=self._run, name="stream2clip-recorder", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10)
        if self.error is not None:
            raise RuntimeError(f"Recording failed to start: {self.error}") from self.error

    def stop(self, *, timeout: float = 30.0) -> Recording:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=timeout)
        if self.error is not None:
            self.state = RecorderState.FAILED
            raise RuntimeError(f"Recording failed: {self.error}") from self.error
        self.state = RecorderState.STOPPED
        return Recording(self.output, self.region, self.fps, self.frames_written, self.frames_written / self.fps)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the recorder stops on its own (``max_duration``) or ``timeout``."""
        if self._thread is None:
            return True
        self._thread.join(timeout)
        return not self._thread.is_alive()

    # ------------------------------------------------------------------ internals
    def _grab(self, backend: CaptureBackend) -> np.ndarray:
        frame = ensure_rgba(backend.grab(self.region))
        h, w = frame.shape[:2]
        if (w, h) != (self.region.width, self.region.height):
            canvas = np.zeros((self.region.height, self.region.width, 4), dtype=np.uint8)
            canvas[: min(h, self.region.height), : min(w, self.region.width)] = frame[: self.region.height, : self.region.width]
            frame = canvas
        if self._cursor is not None:
            pos = self._cursor()
            if pos is not None:
                frame = draw_cursor(frame, pos[0] - self.region.x, pos[1] - self.region.y)
        if self._filter is not None:
            frame = ensure_rgba(self._filter(frame))
        return frame

    def _run(self) -> None:
        backend: CaptureBackend | None = None
        try:
            backend = self._backend_factory()
            raw = RawVideoInput(self.region.width, self.region.height, self.fps)
            cmd = build_capture_command(raw, self.output, ffmpeg=self._ffmpeg)
            self._proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            interval = 1.0 / self.fps
            frame = self._grab(backend)
            self._started_at = time.monotonic()
            self._ready.set()
            assert self._proc.stdin is not None
            while True:
                now = time.monotonic()
                elapsed = now - self._started_at
                if self._stop.is_set() or (self._max_duration is not None and elapsed >= self._max_duration):
                    break
                due = int(elapsed * self.fps) + 1
                payload = frame.tobytes()
                while self.frames_written < due:
                    self._proc.stdin.write(payload)
                    self.frames_written += 1
                if self._on_frame is not None:
                    self._on_frame(self.frames_written, elapsed)
                next_tick = self._started_at + self.frames_written * interval
                delay = next_tick - time.monotonic()
                if delay > 0:
                    self._stop.wait(delay)
                frame = self._grab(backend)
            self._stopped_at = time.monotonic()
            self._finish()
        except BaseException as exc:  # noqa: BLE001 - surfaced through stop()/start()
            self.error = exc
            self._stopped_at = time.monotonic()
            self._abort()
        finally:
            self._ready.set()
            if backend is not None:
                backend.close()

    def _finish(self) -> None:
        proc = self._proc
        if proc is None:
            return
        assert proc.stdin is not None
        proc.stdin.close()
        stderr = proc.stderr.read().decode("utf-8", "replace") if proc.stderr else ""
        code = proc.wait(timeout=60)
        if code != 0:
            raise FFmpegError(list(map(str, proc.args)), code, stderr)  # type: ignore[arg-type]

    def _abort(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            if proc.stdin and not proc.stdin.closed:
                proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def record(
    region: Region,
    output: str | os.PathLike[str],
    options: ExportOptions | None = None,
    *,
    duration: float,
    fps: float = 15.0,
    backend_factory: BackendFactory | None = None,
    cursor: CursorProvider | None = None,
) -> Path:
    """Convenience: record ``duration`` seconds of ``region`` and export to ``output``."""
    recorder = Recorder(region, fps=fps, backend_factory=backend_factory, cursor=cursor, max_duration=duration)
    recorder.start()
    recorder.wait()
    recording = recorder.stop()
    try:
        return recording.export(output, options)
    finally:
        recording.discard()


def keep_intermediate(recording: Recording, destination: str | os.PathLike[str]) -> Path:
    """Move the lossless intermediate somewhere permanent (e.g. for later re-exports)."""
    dest = Path(destination)
    shutil.move(str(recording.path), dest)
    return dest
