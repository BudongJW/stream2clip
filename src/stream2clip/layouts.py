"""Vertical (9:16) layouts for Shorts / Reels / TikTok as ffmpeg filtergraph fragments.

* ``center`` - fill the frame, crop the middle
* ``fit``    - whole picture letterboxed on the brand background
* ``blur``   - whole picture over a blurred, zoomed copy of itself
* ``stack``  - VTuber layout: avatar region on top, game/screen region below

Avatar and game boxes are in **source pixels** (``Region``). They usually stay
put for a whole stream, so pick them once (e.g. with the GUI region selector or
an anime-face detector plugin) and reuse them for every clip.
"""

from __future__ import annotations

from dataclasses import dataclass

from .brand import INK
from .geometry import Region

__all__ = ["LAYOUTS", "VerticalLayout"]

LAYOUTS = ("center", "fit", "blur", "stack")


def _even(v: float) -> int:
    return max(2, int(round(v / 2)) * 2)


@dataclass(frozen=True)
class VerticalLayout:
    kind: str = "blur"
    width: int = 1080
    height: int = 1920
    avatar: Region | None = None
    game: Region | None = None
    split: float = 0.42
    blur: int = 24
    background: str = INK

    def __post_init__(self) -> None:
        if self.kind not in LAYOUTS:
            raise ValueError(f"Unknown layout {self.kind!r}; choose one of {', '.join(LAYOUTS)}")
        if self.kind == "stack" and self.avatar is None:
            raise ValueError("The stack layout needs an avatar region (x,y,w,h in source pixels)")
        if not 0.1 <= self.split <= 0.9:
            raise ValueError("split must be between 0.1 and 0.9")
        if self.width % 2 or self.height % 2:
            raise ValueError("width and height must be even")

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    def graph(self, inp: str = "[0:v]", out: str = "[lay]") -> str:
        """Filtergraph fragment reading ``inp`` and producing ``out`` at ``width`` x ``height``."""
        W, H = self.width, self.height
        cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
        contain = f"scale={W}:{H}:force_original_aspect_ratio=decrease"
        bg = "0x" + self.background.lstrip("#")
        if self.kind == "center":
            return f"{inp}{cover},setsar=1{out}"
        if self.kind == "fit":
            return f"{inp}{contain},pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={bg},setsar=1{out}"
        if self.kind == "blur":
            return (
                f"{inp}split=2[lbg][lfg];"
                f"[lbg]{cover},gblur=sigma={self.blur},eq=brightness=-0.06[lbgb];"
                f"[lfg]{contain}[lfgs];"
                f"[lbgb][lfgs]overlay=(W-w)/2:(H-h)/2,setsar=1{out}"
            )
        # stack
        top_h = _even(H * self.split)
        bottom_h = H - top_h
        a = self.avatar
        assert a is not None
        game_crop = f"crop={self.game.width}:{self.game.height}:{self.game.x}:{self.game.y}," if self.game else ""
        return (
            f"{inp}split=2[lav][lgm];"
            f"[lav]crop={a.width}:{a.height}:{a.x}:{a.y},scale={W}:{top_h}:force_original_aspect_ratio=increase,crop={W}:{top_h}[lavs];"
            f"[lgm]{game_crop}scale={W}:{bottom_h}:force_original_aspect_ratio=increase,crop={W}:{bottom_h}[lgms];"
            f"[lavs][lgms]vstack=inputs=2,setsar=1{out}"
        )
