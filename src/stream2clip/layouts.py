"""Vertical (9:16) layouts for Shorts / Reels / TikTok as ffmpeg filtergraph fragments.

* ``center`` - fill the frame, crop the middle
* ``fit``    - whole picture letterboxed on the brand background
* ``blur``   - whole picture over a blurred, zoomed copy of itself
* ``stack``  - VTuber layout: avatar region on top, game/screen region below
* ``pip``    - the game fills the frame, the avatar sits in a corner

Avatar and game boxes are in **source pixels** (``Region``). They usually stay
put for a whole stream, so pick them once (e.g. with the GUI region selector or
an anime-face detector plugin) and reuse them for every clip.

The avatar can also come from **its own video** (``avatar_source``): the green-screen
or alpha recording of the avatar that clippers ask a streamer for. It is keyed
(``avatar_key``) and laid over the game instead of being cut out of the stream as a box.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from .brand import INK, PAPER
from .chroma import colorkey_filter
from .geometry import Region

__all__ = ["AVATAR_LAYOUTS", "CORNERS", "LAYOUTS", "VerticalLayout"]

LAYOUTS = ("center", "fit", "blur", "stack", "pip")
#: The layouts that show the avatar on its own and so need to know where it is.
AVATAR_LAYOUTS = ("stack", "pip")
CORNERS = ("top-left", "top-right", "bottom-left", "bottom-right")


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
    #: ``pip``: where the avatar goes and how wide it is, as a fraction of the frame width.
    corner: str = "top-right"
    inset: float = 0.42
    #: A separate recording of the avatar, in step with the stream (see ``avatar_offset``).
    avatar_source: "str | os.PathLike[str] | None" = None
    #: Colour removed from ``avatar_source`` (a green screen); ``None`` uses the file's own alpha.
    avatar_key: str | None = "#00FF00"
    avatar_similarity: float = 0.18
    avatar_blend: float = 0.06
    #: Seconds to add to a stream time to get the time in ``avatar_source`` (0 when both start together).
    avatar_offset: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in LAYOUTS:
            raise ValueError(f"Unknown layout {self.kind!r}; choose one of {', '.join(LAYOUTS)}")
        if self.kind in AVATAR_LAYOUTS and self.avatar is None and self.avatar_source is None:
            raise ValueError(f"The {self.kind} layout needs an avatar region (x,y,w,h in source pixels) or an avatar video")
        if self.avatar_source is not None and self.kind not in AVATAR_LAYOUTS:
            raise ValueError(f"An avatar video is used by the layouts {', '.join(AVATAR_LAYOUTS)}, not by {self.kind}")
        if not 0.1 <= self.split <= 0.9:
            raise ValueError("split must be between 0.1 and 0.9")
        if not 0.1 <= self.inset <= 0.9:
            raise ValueError("inset must be between 0.1 and 0.9")
        if self.corner not in CORNERS:
            raise ValueError(f"Unknown corner {self.corner!r}; choose one of {', '.join(CORNERS)}")
        if self.width % 2 or self.height % 2:
            raise ValueError("width and height must be even")

    @property
    def size(self) -> tuple[int, int]:
        return (self.width, self.height)

    @property
    def uses_avatar_video(self) -> bool:
        return self.avatar_source is not None

    def _avatar_cutout(self, avatar_inp: str, fps: float | None) -> str:
        """``avatar_inp`` -> ``[lcut]``: the avatar video cropped, with its background made transparent."""
        steps = [f"fps={fps:g}"] if fps else []
        if self.avatar is not None:
            steps.append(f"crop={self.avatar.width}:{self.avatar.height}:{self.avatar.x}:{self.avatar.y}")
        steps.append("format=rgba")
        if self.avatar_key is not None:
            steps.append(colorkey_filter(self.avatar_key, self.avatar_similarity, self.avatar_blend))
        return f"{avatar_inp}{','.join(steps)}[lcut];"

    def graph(self, inp: str = "[0:v]", out: str = "[lay]", *, avatar_inp: str | None = None, fps: float | None = None) -> str:
        """Filtergraph fragment reading ``inp`` and producing ``out`` at ``width`` x ``height``.

        With ``avatar_source`` set, ``avatar_inp`` is the label of that second input (``[1:v]``)
        and ``fps`` the frame rate ``inp`` already has, so that both run in step.
        """
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
        if self.uses_avatar_video and avatar_inp is None:
            raise ValueError("This layout takes the avatar from its own video: pass the label of that input as avatar_inp")
        game_crop = f"crop={self.game.width}:{self.game.height}:{self.game.x}:{self.game.y}," if self.game else ""
        a = self.avatar
        if self.kind == "stack":
            top_h = _even(H * self.split)
            bottom_h = H - top_h
            game = f"{game_crop}scale={W}:{bottom_h}:force_original_aspect_ratio=increase,crop={W}:{bottom_h}[lgms];"
            if self.uses_avatar_video:
                # The cut-out avatar stands on the brand colour, feet on the seam. The plain panel is made
                # from the avatar frames themselves so that it ends when they do.
                return (
                    f"{self._avatar_cutout(avatar_inp, fps)}"
                    f"[lcut]split=2[lcf][lcb];"
                    f"[lcb]format=rgb24,scale={W}:{top_h},drawbox=x=0:y=0:w=iw:h=ih:color={bg}:t=fill[lpanel];"
                    f"[lcf]scale={W}:{top_h}:force_original_aspect_ratio=decrease[lcfs];"
                    f"[lpanel][lcfs]overlay=(W-w)/2:H-h[lavs];"
                    f"{inp}{game}"
                    f"[lavs][lgms]vstack=inputs=2,setsar=1{out}"
                )
            assert a is not None
            return (
                f"{inp}split=2[lav][lgm];"
                f"[lav]crop={a.width}:{a.height}:{a.x}:{a.y},scale={W}:{top_h}:force_original_aspect_ratio=increase,crop={W}:{top_h}[lavs];"
                f"[lgm]{game}"
                f"[lavs][lgms]vstack=inputs=2,setsar=1{out}"
            )
        # pip
        inset_w = _even(W * self.inset)
        margin = _even(W * 0.04)
        x = str(margin) if self.corner.endswith("left") else f"W-w-{margin}"
        y = str(margin) if self.corner.startswith("top") else f"H-h-{margin}"
        if self.uses_avatar_video:
            return (
                f"{self._avatar_cutout(avatar_inp, fps)}"
                f"[lcut]scale={inset_w}:-2[lavs];"
                f"{inp}{game_crop}{cover}[lgms];"
                f"[lgms][lavs]overlay={x}:{y},setsar=1{out}"
            )
        assert a is not None
        frame = _even(W * 0.006)  # a thin frame keeps the box apart from the game picture
        return (
            f"{inp}split=2[lav][lgm];"
            f"[lav]crop={a.width}:{a.height}:{a.x}:{a.y},scale={inset_w}:-2,"
            f"pad=iw+{2 * frame}:ih+{2 * frame}:{frame}:{frame}:color=0x{PAPER.lstrip('#')}[lavs];"
            f"[lgm]{game_crop}{cover}[lgms];"
            f"[lgms][lavs]overlay={x}:{y},setsar=1{out}"
        )
