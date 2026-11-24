"""Caption fonts to choose from: free fonts clip channels use, fetched on demand and checked against pinned checksums.

Each :class:`CaptionFont` is one file from a pinned source (Google Fonts' repository at one commit, or a
tagged release), under a licence that lets it be redistributed (SIL Open Font License). Nothing is
fetched until a font is asked for (:func:`install`, ``stream2clip fonts install``, a caption look that
needs it); the file only lands in :func:`fonts_dir` when its SHA-256 matches. ffmpeg's ``subtitles``
filter is pointed at that folder (``fontsdir``), so captions can use these fonts without installing them
in the system.

``family`` is the name the caption script asks for: the font's legacy family name, which for the
heavy weights of a family is a name of its own ("Gothic A1 Black"). ``bold`` says whether to ask for
the bold face of that family; a font that is heavy by design is asked for as it is, so that no
synthetic bold thickens it further. Only the standard library is used.
"""

from __future__ import annotations

import os
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

__all__ = ["CAPTION_FONTS", "CaptionFont", "find", "fonts_dir", "install", "installed", "installed_families", "missing_for"]

_GF = "https://raw.githubusercontent.com/google/fonts/06bfe0d62a98375cb09c942fa18e68bd32cff057/ofl"
_PRETENDARD = "https://raw.githubusercontent.com/orioncactus/pretendard/v1.3.9"


@dataclass(frozen=True)
class CaptionFont:
    key: str
    #: The family name a caption style asks for (the font's legacy family name).
    family: str
    file: str
    url: str
    sha256: str
    size: int
    #: Scripts the font draws: "ko" (Hangul), "ja" (kana and kanji), "en" (Latin). Captions in another script fall back.
    scripts: tuple[str, ...]
    #: What clip channels use it for: dialogue, title, emphasis, cute, handwriting, game.
    roles: tuple[str, ...]
    licence_url: str
    #: Ask for the family's bold face (a family whose bold is a face of its own, not a family of its own).
    bold: bool = False
    licence: str = "OFL-1.1"

    @property
    def megabytes(self) -> float:
        return round(self.size / 1_000_000, 1)


def _gf(folder: str, file: str) -> tuple[str, str]:
    return f"{_GF}/{folder}/{file}", f"{_GF}/{folder}/OFL.txt"


def _font(key: str, family: str, source: tuple[str, str], sha256: str, size: int, scripts: tuple[str, ...], roles: tuple[str, ...], bold: bool = False) -> CaptionFont:
    url, licence_url = source
    return CaptionFont(key, family, url.rsplit("/", 1)[1], url, sha256, size, scripts, roles, licence_url, bold)


#: The catalog, Korean first. Sizes and checksums were taken from the pinned files (2026-11-23).
CAPTION_FONTS: tuple[CaptionFont, ...] = (
    # Korean: the heavy gothics of variety captions, the rounded fonts of cute clips, handwriting, game titles
    _font("black-han-sans", "Black Han Sans", _gf("blackhansans", "BlackHanSans-Regular.ttf"),
          "31960809284026681774a8e52dc19ebcad26cf69b0ad9d560f288296fbb52739", 998_424, ("ko", "en"), ("title", "emphasis")),
    _font("do-hyeon", "Do Hyeon", _gf("dohyeon", "DoHyeon-Regular.ttf"),
          "35644be7f28e0a68a447b1f7af351dcde5674b870f24f7b5f43e26d00b4ab653", 879_764, ("ko", "en"), ("dialogue",)),
    _font("jua", "Jua", _gf("jua", "Jua-Regular.ttf"),
          "769677aef240bfc3b9965f2b50748075bff885e6c6992fc591a3fb268279f898", 2_119_352, ("ko", "en"), ("dialogue", "cute")),
    _font("gothic-a1-black", "Gothic A1 Black", _gf("gothica1", "GothicA1-Black.ttf"),
          "6398ff5c6923c74cb453390892dcb982ec0a6c43b35da8590a8f32702d8c079d", 2_260_752, ("ko", "en"), ("dialogue", "title")),
    _font("gothic-a1-extrabold", "Gothic A1 ExtraBold", _gf("gothica1", "GothicA1-ExtraBold.ttf"),
          "37a65353a646fea5a1ac90585d1bb8f9b997ecae0b79c4f1f187566f910e3f9d", 2_281_144, ("ko", "en"), ("dialogue",)),
    _font("nanum-gothic-extrabold", "NanumGothicExtraBold", _gf("nanumgothic", "NanumGothic-ExtraBold.ttf"),
          "5c4568e5295a8c52bc30e7efa1ea6d2de43556268ef42daba93540a1ece691ae", 2_112_720, ("ko", "en"), ("dialogue",)),
    _font("pretendard-black", "Pretendard Black", (f"{_PRETENDARD}/packages/pretendard/dist/public/static/Pretendard-Black.otf", f"{_PRETENDARD}/LICENSE"),
          "94628b0bcea8936b6e5c30d98d685eb9bbaffb0fe2ed255542ecc656c248e021", 1_559_552, ("ko", "en"), ("title", "dialogue")),
    _font("pretendard-extrabold", "Pretendard ExtraBold", (f"{_PRETENDARD}/packages/pretendard/dist/public/static/Pretendard-ExtraBold.otf", f"{_PRETENDARD}/LICENSE"),
          "c35fe941b7568d52a96010561540e47f9d3948dfde66ba25bc1908233e0a40cd", 1_568_512, ("ko", "en"), ("dialogue",)),
    _font("sunflower", "Sunflower", _gf("sunflower", "Sunflower-Bold.ttf"),
          "6b033627817f6619433afe82028013dc45a78ff82406b1dbe5b16e1bbc370e0a", 746_300, ("ko", "en"), ("dialogue",), bold=True),
    _font("dongle", "Dongle", _gf("dongle", "Dongle-Bold.ttf"),
          "944c498c0d1a1832ab36f173b1b3aa5ae77b2a914e00c4d79e05338fae36472d", 4_476_536, ("ko", "en"), ("cute",), bold=True),
    _font("single-day", "Single Day", _gf("singleday", "SingleDay-Regular.ttf"),
          "716ff67a4b0675b35c26d60a4bb83173f7d153ab754474ed36c3369593ca1ca8", 816_524, ("ko",), ("cute",)),
    _font("yeon-sung", "Yeon Sung", _gf("yeonsung", "YeonSung-Regular.ttf"),
          "49ac2a11009f5f58307d377911eb45d210cf4c1d379d9eca38fb4cdad5491ef6", 2_511_004, ("ko", "en"), ("handwriting",)),
    _font("nanum-pen", "Nanum Pen", _gf("nanumpenscript", "NanumPenScript-Regular.ttf"),
          "6f0d1ab29c7894010dc88831fb7a0a51edb79136e450344183de5b1a8b52bd43", 3_201_664, ("ko", "en"), ("handwriting",)),
    _font("gugi", "Gugi", _gf("gugi", "Gugi-Regular.ttf"),
          "c0b1f979979cfc309fb2438fa9464f96173353e0c4842cc7a5919658184ed9d3", 990_856, ("ko", "en"), ("game", "emphasis")),
    # Japanese: the thick and rounded telop fonts of 切り抜き
    _font("dela-gothic-one", "Dela Gothic One", _gf("delagothicone", "DelaGothicOne-Regular.ttf"),
          "4ff87a0965f1b0505e5a2c58424bc6ad3cff27e56a82f21c2fc9d6b0e3857ee2", 2_508_848, ("ja", "en"), ("title", "emphasis")),
    _font("rounded-mplus-extrabold", "Rounded Mplus 1c ExtraBold",
          (f"{_GF}/mplusrounded1c/MPLUSRounded1c-ExtraBold.ttf", f"{_GF}/mplusrounded1c/METADATA.pb"),
          "990f04475a93ef0c7a3fadbaa3307d449172c75ca7c0f9bd754c614b93190e15", 3_628_252, ("ja", "en"), ("dialogue",)),
    _font("rounded-mplus-black", "Rounded Mplus 1c Black",
          (f"{_GF}/mplusrounded1c/MPLUSRounded1c-Black.ttf", f"{_GF}/mplusrounded1c/METADATA.pb"),
          "eedef669badebcf3b736253ea3d563e2a0ed97b82d39f0bded428d31f40dbf94", 3_635_260, ("ja", "en"), ("dialogue", "title")),
    _font("zen-maru-gothic-black", "Zen Maru Gothic Black", _gf("zenmarugothic", "ZenMaruGothic-Black.ttf"),
          "6bd74fe76cd39ee0ec18775c3661d845343fb3f6f8fa09a3076638417baf741f", 3_710_324, ("ja", "en"), ("dialogue", "cute")),
    _font("rocknroll-one", "RocknRoll One", _gf("rocknrollone", "RocknRollOne-Regular.ttf"),
          "dc0f5ff975851827f63f2c6bfed128ffbca14b6399a10fb5e1711215c0108526", 2_682_824, ("ja", "en"), ("emphasis", "game")),
    _font("reggae-one", "Reggae One", _gf("reggaeone", "ReggaeOne-Regular.ttf"),
          "aebe62598732d76036f30ec11bb0ec5f68938e373a06d1b4ceb6b9cf1abf3db2", 2_153_256, ("ja", "en"), ("emphasis",)),
    # English
    _font("anton", "Anton", _gf("anton", "Anton-Regular.ttf"),
          "a4ba3a92350ebb031da0cb47630ac49eb265082ca1bc0450442f4a83ab947cab", 170_812, ("en",), ("title", "dialogue")),
    _font("bebas-neue", "Bebas Neue", _gf("bebasneue", "BebasNeue-Regular.ttf"),
          "08e4623805102d819f58601e46e345648846075e363b2ceb23313c2d1c83ec73", 61_400, ("en",), ("title",)),
    _font("bangers", "Bangers", _gf("bangers", "Bangers-Regular.ttf"),
          "4160a7311de9342674cce9160cde9fcbb30f48190397d86ff1b70b455af65824", 93_148, ("en",), ("emphasis", "cute")),
    _font("archivo-black", "Archivo Black", _gf("archivoblack", "ArchivoBlack-Regular.ttf"),
          "dd9a89a019b4849f66ab75455fe7bdf931311042cbb0f0f97acc061539703180", 90_988, ("en",), ("dialogue", "title")),
)


def fonts_dir() -> Path:
    """Where caption fonts are kept: ``STREAM2CLIP_FONTS_DIR`` or ``fonts`` in the tools folder (beside a downloaded ffmpeg)."""
    from .ffmpeg import tools_dir

    base = os.environ.get("STREAM2CLIP_FONTS_DIR")
    return Path(base) if base else tools_dir() / "fonts"


def find(name: str) -> CaptionFont | None:
    """The catalog font with this key or family name (any case), or ``None``."""
    wanted = " ".join(name.split()).lower()
    return next((f for f in CAPTION_FONTS if wanted in (f.key, f.family.lower())), None)


def installed(font: CaptionFont | str, folder: str | os.PathLike[str] | None = None) -> bool:
    entry = find(font) if isinstance(font, str) else font
    if entry is None:
        return False
    path = Path(folder or fonts_dir()) / entry.file
    return path.is_file() and path.stat().st_size == entry.size


def installed_families(folder: str | os.PathLike[str] | None = None) -> set[str]:
    """Family names (lower case) of the catalog fonts in the fonts folder."""
    return {f.family.lower() for f in CAPTION_FONTS if installed(f, folder)}


def missing_for(families: "list[str] | tuple[str, ...]", folder: str | os.PathLike[str] | None = None) -> list[CaptionFont]:
    """Catalog fonts that these family names need and the fonts folder does not have yet."""
    out = []
    for name in families:
        entry = find(name)
        if entry is not None and not installed(entry, folder) and entry not in out:
            out.append(entry)
    return out


def install(
    font: CaptionFont | str,
    *,
    folder: str | os.PathLike[str] | None = None,
    on_progress: Callable[[int, int], None] | None = None,
    opener: Callable[..., object] | None = None,
) -> Path:
    """Fetch one catalog font into the fonts folder (checked against its SHA-256) with its licence text beside it."""
    from .tools import download

    entry = find(font) if isinstance(font, str) else font
    if entry is None:
        raise ValueError(f"No caption font {font!r}; see `stream2clip fonts`")
    target = Path(folder or fonts_dir()) / entry.file
    if installed(entry, target.parent):
        return target
    download(entry.url, target, sha256=entry.sha256, size=entry.size, on_progress=on_progress, opener=opener)
    licence = target.with_name(f"{target.stem}-LICENSE.txt")
    if not licence.exists() and entry.licence_url.startswith("https://"):
        try:
            with (opener or urllib.request.urlopen)(entry.licence_url, timeout=60) as response:  # noqa: S310 - https only, checked above
                licence.write_bytes(response.read())
        except OSError:
            pass  # the font is usable; its licence is also at licence_url
    return target
