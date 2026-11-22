"""What to make: Shorts, horizontal clips, or a long horizontal compilation.

Of 290 clip videos uploaded in 2026 by Japanese, Korean and English clip channels, 4% were vertical
Shorts (reports/키리누키 영상 레퍼런스 검토.md). Korean and English channels posted horizontal clips of
1.9-2.5 minutes (median; quartiles 1.5-3.9), Japanese channels horizontal videos of about 10 minutes,
a third of them with chapters. A preset sets the layout, how long the highlights are found to be,
how many, and whether they are joined, so each form starts from what channels actually upload.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["PRESETS", "Preset", "get_preset"]


@dataclass(frozen=True)
class Preset:
    key: str
    #: ``blur`` (9:16 with a blurred background) or ``none`` (the stream's own framing).
    layout: str
    #: How long a highlight is found to be: seconds before and after the moment, and the bounds.
    lead: float
    tail: float
    min_length: float
    max_length: float
    #: How many highlights.
    top: int
    #: Join the clips into one video with chapters, with this fade between them.
    compile: bool = False
    fade: float = 0.0
    #: The line at the top of each clip's first seconds (``"auto"``: the stream's topic), or none.
    context: str | None = None
    #: Words light up as they are spoken (karaoke); off: plain sentence captions.
    karaoke: bool = True


#: Horizontal clips show plain sentence captions: the Korean clip channels around one CHZZK VTuber caption
#: every line in white or on a dark plate, with no colour moving across the words (reports/독케익 키리누키 채널 분석.md).
PRESETS: dict[str, Preset] = {
    "shorts": Preset("shorts", "blur", lead=20.0, tail=10.0, min_length=15.0, max_length=90.0, top=10),
    "clip": Preset("clip", "none", lead=45.0, tail=30.0, min_length=60.0, max_length=180.0, top=8, context="auto", karaoke=False),
    "long": Preset("long", "none", lead=40.0, tail=25.0, min_length=45.0, max_length=150.0, top=6, compile=True, fade=0.3, context="auto", karaoke=False),
}


def get_preset(key: str | None) -> Preset:
    try:
        return PRESETS[(key or "shorts").lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown preset {key!r}; choose one of {', '.join(PRESETS)}") from exc
