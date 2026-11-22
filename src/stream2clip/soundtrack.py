"""Background music and sound effects for clips: which file plays where, how loud, and the credit it needs.

* Built-in sound effects (``pop``, ``ding``, ``whoosh``, ``boom``, ``sparkle``) are drawn by
  :func:`synth` from numbers alone. They are part of stream2clip, so they need no download,
  no credit and no license check.
* Music and other effects are files the user downloaded from a free library. A *sound
  library* is a folder with ``sounds.json`` that keeps, next to each file, where it came from
  and under which license (:class:`Sound`). The credit line of the description and the
  pre-upload check (:func:`check_sounds`) are read from there.
* :func:`plan_mix` turns a :class:`Soundtrack` into the :class:`~stream2clip.ffmpeg.AudioMix`
  of one clip: the music is set a number of dB under the clip's own sound (measured, see
  :func:`active_level`) and lowered further while someone speaks; effects go to the start,
  the peak or the end of the clip.

Only numpy and the standard library are used here; ffmpeg decodes the files (:func:`measure`).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import wave
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable, Sequence

import numpy as np

from .ffmpeg import AudioLayer, AudioMix
from .i18n import mark, shown, tr

if TYPE_CHECKING:  # pragma: no cover
    from .compliance import Issue

__all__ = [
    "AUTO_EFFECT",
    "BUILTIN_EFFECTS",
    "LICENSES",
    "Effect",
    "License",
    "Sound",
    "SoundLibrary",
    "Soundtrack",
    "active_level",
    "builtin_sound",
    "check_sounds",
    "credit_lines",
    "effect_for",
    "get_license",
    "library_dir",
    "measure",
    "plan_mix",
    "render_builtin",
    "resolve_sound",
    "synth",
    "write_wav",
]

RATE = 48000
LIBRARY_FILE = "sounds.json"
LIBRARY_SCHEMA = "stream2clip.sounds/v1"
KINDS = ("bgm", "sfx")


# --------------------------------------------------------------------------- licenses


@dataclass(frozen=True)
class License:
    """What a license or a site's terms allow for a sound under a clip (a checklist, not legal advice).

    ``attribution``: ``required`` (a credit in the description), ``optional`` or ``none``.
    ``commercial``: may be used in a monetized video. ``sync``: may be put to picture at all
    (Creative Commons counts music timed to a moving image as an adaptation, which ND forbids).
    ``url`` and ``checked`` say which official text the entry was read from, and when.
    """

    key: str
    name: str
    url: str
    checked: str
    attribution: str = "required"
    commercial: bool = True
    sync: bool = True
    share_alike: bool = False
    notes: tuple[str, ...] = ()
    #: May be used through a program that makes videos (a site's own terms may forbid this).
    video_tools: bool = True
    #: May be uploaded to YouTube and other video sites.
    social: bool = True
    #: The provider's credit wording, filled with the sound's ``title``, ``author`` and ``url``.
    credit_template: str = ""


def _cc(key: str, name: str, path: str, *, commercial: bool = True, sync: bool = True, share_alike: bool = False, notes: tuple[str, ...] = ()) -> License:
    return License(key, name, f"https://creativecommons.org/licenses/{path}/", "2026-11-22", "required", commercial, sync, share_alike, notes)


_NC = (mark("비영리(NC) 조건: 수익 창출 영상에는 사용하지 않는 것이 안전"),)
_ND = (mark("변경 금지(ND) 조건: 음악을 영상에 맞춰 넣는 것도 변경에 해당하여 사용 불가"),)
_SA = (mark("동일 조건(SA): 음악을 넣은 영상도 같은 라이선스로 공개해야 할 수 있음"),)

#: Licenses a sound in a library can name. Every entry points at the official text it was read from.
LICENSES: dict[str, License] = {
    "cc0": License("cc0", "CC0 1.0", "https://creativecommons.org/publicdomain/zero/1.0/", "2026-11-22", attribution="none"),
    "cc-by-4.0": _cc("cc-by-4.0", "CC BY 4.0", "by/4.0"),
    "cc-by-3.0": _cc("cc-by-3.0", "CC BY 3.0", "by/3.0"),
    "cc-by-sa-4.0": _cc("cc-by-sa-4.0", "CC BY-SA 4.0", "by-sa/4.0", share_alike=True, notes=_SA),
    "cc-by-nc-4.0": _cc("cc-by-nc-4.0", "CC BY-NC 4.0", "by-nc/4.0", commercial=False, notes=_NC),
    "cc-by-nc-sa-4.0": _cc("cc-by-nc-sa-4.0", "CC BY-NC-SA 4.0", "by-nc-sa/4.0", commercial=False, share_alike=True, notes=_NC + _SA),
    "cc-by-nd-4.0": _cc("cc-by-nd-4.0", "CC BY-ND 4.0", "by-nd/4.0", sync=False, notes=_ND),
    "cc-by-nc-nd-4.0": _cc("cc-by-nc-nd-4.0", "CC BY-NC-ND 4.0", "by-nc-nd/4.0", commercial=False, sync=False, notes=_NC + _ND),
    "youtube-audio-library": License(
        "youtube-audio-library", "YouTube Audio Library", "https://support.google.com/youtube/answer/3376882", "2026-11-22", attribution="none",
        notes=(mark("YouTube Studio의 오디오 보관함에서 직접 내려받은 곡만 해당. YouTube 밖에서의 사용 조건은 Studio 안의 약관 확인"),),
    ),
    "youtube-audio-library-cc": License(
        "youtube-audio-library-cc", "YouTube Audio Library (Creative Commons)", "https://support.google.com/youtube/answer/3376882", "2026-11-22",
        notes=(mark("오디오 보관함의 저작자 표시 문구를 그대로 credit에 기록"),),
    ),
    "pixabay": License(
        "pixabay", "Pixabay Content License", "https://pixabay.com/service/terms/", "2026-11-22 (terms of 2026-10-20)", attribution="optional",
        notes=(mark("Content ID에 등록된 곡(방패 표시)은 소유권 주장이 걸릴 수 있음. 곡 페이지 주소와 내려받은 파일 이름 보관"), mark("음원 파일 자체의 재배포 금지")),
        credit_template="{title} by {author} via Pixabay",
    ),
    "incompetech": License(
        "incompetech", "Kevin MacLeod (incompetech.com), CC BY 4.0", "https://incompetech.com/music/royalty-free/faq.html", "2026-11-22",
        notes=(mark("Content ID에 미리 등록된 곡: 소유권 주장이 걸리면 설명란의 크레디트로 이의 제기"),),
        credit_template='"{title}" Kevin MacLeod (incompetech.com) Licensed under Creative Commons: By Attribution 4.0 License http://creativecommons.org/licenses/by/4.0/',
    ),
    "uppbeat": License(
        "uppbeat", "Uppbeat Basic License (free)", "https://uppbeat.io/uppbeat-basic-license", "2026-11-22",
        notes=(mark("내려받을 때 받은 크레디트 문구를 그대로 credit에 기록. 1회 내려받기는 영상 1개에만 사용"), mark("유료 광고 영상 사용 금지, 개인 크리에이터 한정")),
    ),
    "mixkit": License(
        "mixkit", "Mixkit Free License", "https://mixkit.co/license/", "2026-11-22", attribution="none",
        notes=(mark("음원 파일 자체의 재배포 금지"),),
    ),
    "sonniss-gdc": License(
        "sonniss-gdc", "Sonniss GDC Bundle License 2.0", "https://sonniss.com/gdc-bundle-license/", "2026-11-22", attribution="none",
        notes=(mark("음원 파일 자체의 재배포 금지"),),
    ),
    "bensound-free": License(
        "bensound-free", "Bensound Free License", "https://www.bensound.com/terms-and-conditions", "2026-11-22 (terms of 2026-06-22)", video_tools=False,
        notes=(mark("무료 라이선스는 영상 1개마다 라이선스 코드 발급 필요"),),
    ),
    "bbc-remarc": License(
        "bbc-remarc", "BBC RemArc Licence", "https://sound-effects.bbcrewind.co.uk/licensing", "2026-11-22", commercial=False, social=False,
        credit_template="{title} bbc.co.uk - (c) copyright BBC",
    ),
    # Japanese and Korean libraries common in clip channels (each site's own terms, read on the date given)
    "opentracks": License(
        "opentracks", "OpenTracks (DOVA-SYNDROME)", "https://opentracks.com/help/articles/license/", "2026-11-22", attribution="optional",
        notes=(mark("2026-09-15에 DOVA-SYNDROME에서 이름 변경. 작곡가별 추가 조건이 있으면 그쪽이 우선"), mark("정치, 종교, 사상 목적의 영상과 작곡가의 평판을 해치는 사용 금지")),
    ),
    "soundeffect-lab": License(
        "soundeffect-lab", "Sound Effect Lab (soundeffect-lab.info)", "https://soundeffect-lab.info/agreement/", "2026-11-22", attribution="optional",
        credit_template="効果音ラボ",
    ),
    "maou": License("maou", "Maou-damashii (maou.audio)", "https://maou.audio/rule/", "2026-11-22", attribution="optional", credit_template="音楽：魔王魂"),
    "otologic": License(
        "otologic", "OtoLogic, CC BY 4.0", "https://otologic.jp/free/license.html", "2026-11-22",
        credit_template="BGM by OtoLogic(CC BY 4.0)",
    ),
    "amacha": License(
        "amacha", "Amacha Music Studio (amachamusic.chagasi.com)", "https://amachamusic.chagasi.com/terms.html", "2026-11-22", attribution="optional",
        notes=(mark("편곡한 곡을 쓰면 크레디트 필수"),),
    ),
    "pocket-sound": License(
        "pocket-sound", "Pocket Sound (pocket-se.info)", "https://pocket-se.info/rules/", "2026-11-22 (terms of 2025-09-06)",
        credit_template="効果音：ポケットサウンド https://pocket-se.info/",
    ),
    "taira-komori": License("taira-komori", "Taira Komori (taira-komori.net)", "https://taira-komori.net/welcome.html", "2026-11-22", attribution="optional"),
    "springin": License(
        "springin", "Springin' Sound Stock", "https://springin.org/sound-stock/guideline/", "2026-11-22", attribution="optional",
        credit_template="BGM：Springin' Sound Stock",
    ),
    "bgm-president": License(
        "bgm-president", "BGM President (bgmpresident.com)", "https://bgmpresident.com/policy.html", "2026-11-22",
        notes=(mark("무료 사용은 영상 사이트 업로드까지. 광고, 홍보 영상과 라이브 방송은 유료 이용권 필요"),),
        credit_template="BGM: {title} (https://bgmpresident.com)",
    ),
    "sellbuymusic-free": License(
        "sellbuymusic-free", "Sellbuymusic free music", "https://sellbuymusic.com/ko/legal/terms", "2026-11-22 (terms of 2025-12-01)",
        notes=(mark("무료 음원은 크레디트 필수. 사이트가 안내하는 문구를 그대로 credit에 기록"),),
    ),
    "own": License("own", "own work / licensed", "", "", attribution="optional", notes=(mark("직접 만들었거나 사용권을 산 음원: 계약 조건 직접 확인"),)),
    "builtin": License("builtin", "stream2clip built-in", "", "", attribution="none"),
}


def get_license(key: str | None) -> License | None:
    return LICENSES.get((key or "").strip().lower()) if key else None


# --------------------------------------------------------------------------- sounds and the library


@dataclass(frozen=True)
class Sound:
    """A sound file and what is known about it. ``license`` is a key of :data:`LICENSES` ("" = not recorded)."""

    path: Path
    kind: str = "bgm"
    name: str = ""
    title: str = ""
    author: str = ""
    url: str = ""
    license: str = ""
    #: The credit line exactly as the provider asks for it; empty: built from title, author, source and license.
    credit: str = ""
    tags: tuple[str, ...] = ()
    builtin: bool = False
    #: Seconds into an effect where its hit is (the bang of a boom, the end of a whoosh): that moment lands on the event.
    hit: float = 0.0

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"A sound is one of {', '.join(KINDS)}, not {self.kind!r}")
        if self.hit < 0:
            raise ValueError("hit is seconds into the sound")

    @property
    def label(self) -> str:
        return self.name or self.title or self.path.stem

    def credit_line(self) -> str:
        """The line for the description: the provider's own wording, else title, author, source and license (as Creative Commons suggests)."""
        if self.builtin:
            return ""
        if self.credit.strip():
            return " ".join(self.credit.split())
        lic = get_license(self.license)
        if lic is not None and lic.attribution == "none" and not (self.title or self.author):
            return ""
        if lic is not None and lic.credit_template and self.title:
            return " ".join(lic.credit_template.format(title=self.title, author=self.author or "?", url=self.url).split())
        title = f'"{self.title}"' if self.title else self.path.stem
        parts = [title + (f" by {self.author}" if self.author else "")]
        if self.url:
            parts.append(self.url)
        if lic is not None and lic.key not in ("own", "builtin"):
            parts.append(f"{lic.name}" + (f" {lic.url}" if lic.url else ""))
        return " / ".join(parts)

    def to_dict(self, root: Path | None = None) -> dict:
        path = self.path
        if root is not None:
            try:
                path = self.path.resolve().relative_to(root.resolve())
            except ValueError:
                pass
        data = {"name": self.name, "file": path.as_posix(), "kind": self.kind, "title": self.title, "author": self.author,
                "url": self.url, "license": self.license, "credit": self.credit, "tags": list(self.tags), "hit": self.hit or None}
        return {key: value for key, value in data.items() if value not in ("", [], None) or key in ("name", "file", "kind", "license")}

    @classmethod
    def from_dict(cls, data: dict, root: Path) -> "Sound":
        file = Path(str(data["file"]))
        return cls(
            path=file if file.is_absolute() else root / file, kind=str(data.get("kind") or "bgm"), name=str(data.get("name") or ""),
            title=str(data.get("title") or ""), author=str(data.get("author") or ""), url=str(data.get("url") or ""),
            license=str(data.get("license") or ""), credit=str(data.get("credit") or ""), tags=tuple(str(t) for t in data.get("tags") or ()),
            hit=float(data.get("hit") or 0.0),
        )


def library_dir() -> Path:
    """``STREAM2CLIP_SOUNDS_DIR``, else ``sounds`` in the app's settings folder."""
    override = os.environ.get("STREAM2CLIP_SOUNDS_DIR")
    if override:
        return Path(override)
    folder = os.environ.get("STREAM2CLIP_CONFIG_DIR")
    if folder:
        root = Path(folder)
    elif sys.platform == "win32":
        root = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "stream2clip"
    elif sys.platform == "darwin":
        root = Path.home() / "Library" / "Application Support" / "stream2clip"
    else:
        root = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "stream2clip"
    return root / "sounds"


class SoundLibrary:
    """A folder of sounds with ``sounds.json``: the files, and for each its source and license."""

    def __init__(self, folder: str | os.PathLike[str] | None = None) -> None:
        self.folder = Path(folder) if folder is not None else library_dir()
        self.sounds: list[Sound] = []
        manifest = self.folder / LIBRARY_FILE
        if manifest.is_file():
            data = json.loads(manifest.read_text(encoding="utf-8"))
            if data.get("schema") != LIBRARY_SCHEMA:
                raise ValueError(f"{manifest} is not a stream2clip sound library ({LIBRARY_SCHEMA})")
            self.sounds = [Sound.from_dict(item, self.folder) for item in data.get("sounds", [])]

    def __iter__(self):
        return iter(self.sounds)

    def __len__(self) -> int:
        return len(self.sounds)

    def find(self, name: str) -> Sound | None:
        key = name.strip().lower()
        return next((s for s in self.sounds if s.name.lower() == key), None)

    def for_file(self, path: str | os.PathLike[str]) -> Sound | None:
        target = Path(path).resolve()
        return next((s for s in self.sounds if s.path.resolve() == target), None)

    def save(self) -> Path:
        self.folder.mkdir(parents=True, exist_ok=True)
        manifest = self.folder / LIBRARY_FILE
        data = {"schema": LIBRARY_SCHEMA, "sounds": [s.to_dict(self.folder) for s in self.sounds]}
        manifest.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return manifest

    def add(self, file: str | os.PathLike[str], *, kind: str = "bgm", name: str = "", copy: bool = True, hit: float = 0.0, **facts) -> Sound:
        """Put a file in the library (copied into the folder unless it is there already) and remember its facts."""
        source = Path(file)
        if not source.is_file():
            raise FileNotFoundError(f"No such sound file: {source}")
        lic = str(facts.get("license") or "").strip().lower()
        if lic and lic not in LICENSES:
            raise ValueError(f"Unknown license {lic!r}; choose one of {', '.join(LICENSES)}")
        name = (name or source.stem).strip()
        if self.find(name) is not None:
            raise ValueError(f"The library already has a sound named {name!r}")
        if self.folder.resolve() in source.resolve().parents or not copy:
            path = source
        else:
            self.folder.mkdir(parents=True, exist_ok=True)
            path = self.folder / source.name
            if path.exists():
                raise FileExistsError(f"{path} is already in the library folder")
            shutil.copy2(source, path)
        sound = Sound(path=path, kind=kind, name=name, license=lic, tags=tuple(facts.pop("tags", ()) or ()), hit=hit,
                      **{key: str(value or "") for key, value in facts.items() if key in ("title", "author", "url", "credit")})
        self.sounds.append(sound)
        self.save()
        return sound

    def remove(self, name: str) -> Sound:
        sound = self.find(name)
        if sound is None:
            raise KeyError(name)
        self.sounds.remove(sound)
        self.save()
        return sound


def resolve_sound(spec: str, kind: str = "bgm", library: SoundLibrary | None = None) -> Sound:
    """A sound from what a user typed: a built-in effect, a name in the library, or a file (with its library entry if it has one)."""
    text = spec.strip()
    if not text:
        raise ValueError("No sound given")
    if text.lower() in BUILTIN_EFFECTS or text.lower() == AUTO_EFFECT:
        if kind != "sfx":
            raise ValueError(f"{text} is a built-in sound effect, not music")
        return builtin_sound(text)
    library = library if library is not None else SoundLibrary()
    found = library.find(text)
    if found is not None:
        return found if found.kind == kind else replace(found, kind=kind)
    path = Path(text)
    if path.is_file():
        known = library.for_file(path)
        if known is None and (path.parent / LIBRARY_FILE).is_file() and path.parent.resolve() != library.folder.resolve():
            known = SoundLibrary(path.parent).for_file(path)  # a folder of its own with its own sounds.json
        if known is not None:
            return known if known.kind == kind else replace(known, kind=kind)
        return Sound(path=path, kind=kind, name=path.stem)
    choices = ", ".join(BUILTIN_EFFECTS) if kind == "sfx" else ""
    names = ", ".join(s.name for s in library if s.kind == kind)
    raise ValueError(f"No sound {text!r}: give a file, a name in the sound library ({names or 'empty'})" + (f", or a built-in effect ({choices})" if choices else ""))


# --------------------------------------------------------------------------- built-in effects


def _envelope(n: int, attack: float, decay: float) -> np.ndarray:
    t = np.arange(n) / RATE
    rise = np.clip(t / max(attack, 1e-4), 0.0, 1.0)
    return rise * np.exp(-t / decay)


def _sweep(start: float, stop: float, seconds: float) -> np.ndarray:
    """A sine gliding from ``start`` to ``stop`` Hz (exponentially, as the ear hears pitch)."""
    n = int(seconds * RATE)
    freq = start * (stop / start) ** (np.arange(n) / max(1, n - 1))
    return np.sin(2 * np.pi * np.cumsum(freq) / RATE)


def _band_noise(seconds: float, low: float, high: float, seed: int) -> np.ndarray:
    """White noise whose pass band moves from ``low`` to ``high`` Hz over its length (short overlapping FFT blocks)."""
    n = int(seconds * RATE)
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(n + 2048)
    block, hop = 2048, 512
    window = np.hanning(block)
    freqs = np.fft.rfftfreq(block, 1.0 / RATE)
    out = np.zeros(n + 2048)
    count = (n - block) // hop + 2
    for i in range(count):
        a = i * hop
        center = low * (high / low) ** min(1.0, a / max(1, n))
        band = np.exp(-0.5 * (np.log(np.maximum(freqs, 1.0) / center) / 0.45) ** 2)
        out[a : a + block] += np.fft.irfft(np.fft.rfft(noise[a : a + block] * window) * band, n=block) * window
    out = out[:n]
    return out / (np.abs(out).max() or 1.0)


def _pop() -> np.ndarray:
    return _sweep(900, 260, 0.14) * _envelope(int(0.14 * RATE), 0.002, 0.035)


def _ding() -> np.ndarray:
    n = int(1.4 * RATE)
    t = np.arange(n) / RATE
    tone = np.zeros(n)
    for ratio, level, decay in ((1.0, 1.0, 0.55), (2.0, 0.45, 0.32), (2.76, 0.3, 0.22), (5.4, 0.12, 0.1)):
        tone += level * np.sin(2 * np.pi * 1320 * ratio * t) * np.exp(-t / decay)
    return tone * np.clip(t / 0.003, 0.0, 1.0)


def _whoosh() -> np.ndarray:
    n = int(0.6 * RATE)
    shape = np.sin(np.pi * np.arange(n) / n) ** 2
    return _band_noise(0.6, 350, 3800, seed=7) * shape


def _boom() -> np.ndarray:
    n = int(1.1 * RATE)
    body = _sweep(110, 38, 1.1) * _envelope(n, 0.004, 0.32)
    hit = _band_noise(1.1, 900, 120, seed=11) * _envelope(n, 0.001, 0.05) * 0.6
    return np.tanh(2.2 * (body + hit)) / np.tanh(2.2)


def _sparkle() -> np.ndarray:
    n = int(1.0 * RATE)
    rng = np.random.default_rng(5)
    out = np.zeros(n)
    t = np.arange(int(0.12 * RATE)) / RATE
    for k in range(18):
        at = int((k * 0.045 + rng.uniform(0, 0.02)) * RATE)
        freq = rng.uniform(2400, 6200)
        ping = np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.03) * (1.0 - k / 22)
        out[at : at + ping.size] += ping[: n - at]
    return out


_BUILTINS: dict[str, Callable[[], np.ndarray]] = {"pop": _pop, "ding": _ding, "whoosh": _whoosh, "boom": _boom, "sparkle": _sparkle}
#: Effects stream2clip draws itself: no download, no credit.
BUILTIN_EFFECTS = tuple(_BUILTINS)
_HITS = {"whoosh": 0.3}  # a whoosh swells into its moment
#: ``auto``: the built-in effect that fits what chat reacted with (see :func:`effect_for`).
AUTO_EFFECT = "auto"
_BY_REACTION = {"laugh": "pop", "shock": "boom", "cute": "sparkle", "hype": "ding"}


def builtin_sound(name: str) -> Sound:
    key = name.strip().lower()
    if key != AUTO_EFFECT and key not in _BUILTINS:
        raise ValueError(f"No built-in effect {name!r}; choose one of {', '.join(BUILTIN_EFFECTS)} or {AUTO_EFFECT}")
    return Sound(path=Path(f"{key}.wav"), kind="sfx", name=key, title=key, license="builtin", builtin=True, hit=_HITS.get(key, 0.0))


def effect_for(stats: "dict[str, float] | None") -> str:
    """The built-in effect for a highlight: what chat reacted with most (laugh: pop, shock: boom, cute: sparkle, hype: ding)."""
    counts = {name: float((stats or {}).get(f"react_{name}", 0)) for name in _BY_REACTION}
    best = max(counts, key=lambda name: counts[name])
    return _BY_REACTION[best] if counts[best] > 0 else "ding"


def synth(name: str) -> np.ndarray:
    """A built-in sound effect as mono float32 samples at 48 kHz, peak at -3 dBFS (the same every time)."""
    try:
        samples = _BUILTINS[name.lower()]()
    except KeyError as exc:
        raise ValueError(f"No built-in effect {name!r}; choose one of {', '.join(BUILTIN_EFFECTS)}") from exc
    tail = int(0.01 * RATE)  # no click at the end
    samples[-tail:] *= np.linspace(1.0, 0.0, tail)
    peak = float(np.abs(samples).max()) or 1.0
    return (samples / peak * 10 ** (-3 / 20)).astype(np.float32)


def write_wav(samples: np.ndarray, path: str | os.PathLike[str], *, rate: int = RATE) -> Path:
    """16-bit stereo WAV of mono ``samples`` in -1..1."""
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(np.asarray(samples, dtype=np.float64), -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(os.fspath(out), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(np.repeat(pcm, 2).tobytes())
    return out


def render_builtin(name: str, folder: str | os.PathLike[str]) -> Path:
    """Write a built-in effect to ``folder/<name>.wav`` (for ffmpeg, or to try it in an editing program)."""
    return write_wav(synth(name), Path(folder) / f"{name.lower()}.wav")


# --------------------------------------------------------------------------- levels


def active_level(samples: np.ndarray, rate: int, *, frame: float = 0.05, spread: float = 20.0) -> float:
    """How loud a recording is while something sounds, in dBFS (-90: silence).

    The mean power of the 50 ms frames that come within ``spread`` dB of the loud parts
    (the 95th percentile frame): pauses do not pull a talk down, and a short effect is
    measured by its sound, not by its length.
    """
    step = max(1, int(round(frame * rate)))
    count = len(samples) // step
    if count == 0:
        return -90.0
    frames = np.asarray(samples[: count * step], dtype=np.float64).reshape(count, step)
    power = np.mean(frames * frames, axis=1)
    db = 10.0 * np.log10(np.maximum(power, 1e-12))
    loud = float(np.percentile(db, 95))
    if loud <= -80.0:
        return -90.0
    kept = power[db >= loud - spread]
    return max(-90.0, round(10.0 * np.log10(float(np.mean(kept))), 2))


def measure(path: str | os.PathLike[str], *, start: float | None = None, duration: float | None = 90.0, track: int | None = None, ffmpeg: str | None = None) -> tuple[float, float]:
    """(active level in dBFS, length in seconds of what was read) of a media file, decoded by ffmpeg at 16 kHz."""
    from .audio import decode_pcm

    rate = 16000
    samples = decode_pcm(path, sample_rate=rate, start=start, duration=duration, track=track, ffmpeg=ffmpeg)
    return active_level(samples, rate), len(samples) / rate


# --------------------------------------------------------------------------- the plan of one clip


@dataclass(frozen=True)
class Effect:
    """A sound effect and where it goes: ``start``, ``peak`` (the highlight's top moment), ``end``, or seconds from the start."""

    sound: Sound
    when: "str | float" = "peak"

    def __post_init__(self) -> None:
        if isinstance(self.when, str) and self.when not in ("start", "peak", "end"):
            raise ValueError(f"An effect goes at start, peak, end or a number of seconds, not {self.when!r}")
        if not isinstance(self.when, str) and float(self.when) < 0:
            raise ValueError("An effect's time is seconds from the start of the clip")

    @staticmethod
    def parse(text: str, library: SoundLibrary | None = None) -> "Effect":
        """``name``, ``name@peak``, ``name@start``, ``name@end`` or ``name@1.5`` (seconds)."""
        name, _, when = text.rpartition("@") if "@" in text else (text, "", "peak")
        when = when.strip().lower() or "peak"
        place: str | float = when if when in ("start", "peak", "end") else float(when)
        return Effect(resolve_sound(name, "sfx", library), place)


@dataclass(frozen=True)
class Soundtrack:
    """Music and effects for every clip of a run.

    ``music`` is taken in turn, one track per clip. It plays ``under`` dB below the clip's own
    sound (measured on each clip) unless ``volume`` fixes its gain in dB, starts ``music_start``
    seconds into the track, loops when the clip is longer, fades in and out, and is lowered
    while someone speaks (``duck``). Effects play ``effect_under`` dB below the clip's sound
    unless ``effect_volume`` fixes their gain.
    """

    music: tuple[Sound, ...] = ()
    effects: tuple[Effect, ...] = ()
    under: float = 12.0
    volume: float | None = None
    duck: bool = True
    music_start: float = 0.0
    fade_in: float = 0.5
    fade_out: float = 1.5
    effect_under: float = 3.0
    effect_volume: float | None = None

    def __post_init__(self) -> None:
        if any(s.kind != "bgm" for s in self.music):
            raise ValueError("music takes background music, not sound effects")
        if not 0.0 <= self.under <= 40.0:
            raise ValueError("under is a number of dB in 0..40")
        if self.music_start < 0:
            raise ValueError("music_start is seconds into the track")

    def __bool__(self) -> bool:
        return bool(self.music or self.effects)

    def music_for(self, index: int) -> Sound | None:
        return self.music[index % len(self.music)] if self.music else None


#: The level the clip's sound is taken to have when it has none (a clip without sound, or a silent one).
_NO_VOICE = -20.0
#: Ducking starts this many dB under the clip's active level. Measured on five highlights of a real stream
#: (talk, laughter and game music): at 15 dB quiet talking was left under the music (the music within 6 dB
#: of the clip in 17% of the sounding moments); at 22 dB that fell to 9%, the music still sat 15-20 LU under
#: the clip as a whole and came back in the pauses.
_DUCK_BELOW = 22.0


@dataclass
class PlannedSound:
    sound: Sound
    at: float
    gain: float

    def to_dict(self) -> dict:
        data = {"name": self.sound.label, "kind": self.sound.kind, "at": round(self.at, 2), "gain": round(self.gain, 1), "license": self.sound.license or None}
        if self.sound.credit_line():
            data["credit"] = self.sound.credit_line()
        return data


@dataclass
class MixPlan:
    mix: AudioMix
    sounds: list[PlannedSound] = field(default_factory=list)


def _gain(target: float, level: float) -> float:
    return round(float(np.clip(target - level, -60.0, 12.0)), 1)


def plan_mix(
    soundtrack: Soundtrack,
    index: int,
    *,
    length: float,
    voice_level: float | None,
    peak: float | None = None,
    reactions: "dict[str, float] | None" = None,
    levels: Callable[[Sound], tuple[float, float]],
    path_of: Callable[[Sound], "str | os.PathLike[str]"] = lambda s: s.path,
) -> MixPlan | None:
    """The mix of clip number ``index`` (0 first), ``length`` seconds long.

    ``voice_level`` is the active level of the clip's own sound (``None``: the clip has none).
    ``peak`` is the highlight's top moment in seconds from the clip's start, ``reactions`` its
    statistics (``react_laugh`` ...) for the ``auto`` effect. ``levels(sound)`` returns (active
    level, length) of a sound; ``path_of(sound)`` the file ffmpeg reads.
    """
    if not soundtrack or length <= 0:
        return None
    has_voice = voice_level is not None and voice_level > -60.0
    voice = voice_level if has_voice else _NO_VOICE
    layers: list[AudioLayer] = []
    planned: list[PlannedSound] = []
    music = soundtrack.music_for(index)
    if music is not None:
        level, _ = levels(music)
        gain = soundtrack.volume if soundtrack.volume is not None else _gain(voice - soundtrack.under, level)
        threshold = float(np.clip(10 ** ((voice - _DUCK_BELOW) / 20.0), 0.001, 0.5))  # duck whenever the clip is within 22 dB of its talking level
        layers.append(AudioLayer(path_of(music), gain=gain, offset=soundtrack.music_start, loop=True, fade_in=soundtrack.fade_in,
                                 fade_out=soundtrack.fade_out, duck=soundtrack.duck and has_voice, duck_threshold=threshold))
        planned.append(PlannedSound(music, 0.0, gain))
    for effect in soundtrack.effects:
        sound = builtin_sound(effect_for(reactions)) if effect.sound.builtin and effect.sound.name == AUTO_EFFECT else effect.sound
        level, seconds = levels(sound)
        if effect.when == "start":
            at = 0.0
        elif effect.when == "end":
            at = length - seconds
        else:
            moment = (peak if peak is not None else length / 2) if effect.when == "peak" else float(effect.when)
            at = moment - sound.hit
        at = max(0.0, at)
        if at >= length - 0.05:
            continue  # after the end of this clip
        gain = soundtrack.effect_volume if soundtrack.effect_volume is not None else _gain(voice - soundtrack.effect_under, level)
        layers.append(AudioLayer(path_of(sound), gain=gain, at=round(at, 3)))
        planned.append(PlannedSound(sound, at, gain))
    if not layers:
        return None
    return MixPlan(AudioMix(tuple(layers), length=length, voice=voice_level is not None), planned)


# --------------------------------------------------------------------------- credits and checks


def credit_lines(sounds: Iterable[Sound]) -> list[str]:
    """One credit line per sound that has one, in order, each once."""
    lines: list[str] = []
    for sound in sounds:
        line = sound.credit_line()
        if line and line not in lines:
            lines.append(line)
    return lines


def check_sounds(sounds: Sequence[Sound], *, description: str | None = None) -> "list[Issue]":
    """What to look at before uploading a clip with these sounds (``error``: the license does not allow it)."""
    from .compliance import Issue

    issues: list[Issue] = []
    seen: set[str] = set()
    if any(not sound.builtin for sound in sounds):
        issues.append(Issue("info", tr("무료 음원 대부분은 그 음원을 넣은 영상의 Content ID 등록을 금지합니다.")))
    for sound in sounds:
        if sound.builtin or sound.label in seen:
            continue
        seen.add(sound.label)
        lic = get_license(sound.license)
        if lic is None:
            issues.append(Issue("warning", tr("{0}: 라이선스가 기록되지 않은 음원입니다. 출처의 이용 약관을 확인하세요.").format(sound.label)))
            continue
        if not lic.sync:
            issues.append(Issue("error", tr("{0}: {1} 라이선스는 영상에 넣는 것을 허락하지 않습니다.").format(sound.label, lic.name)))
        if not lic.video_tools:
            issues.append(Issue("error", tr("{0}: {1}는 영상을 만드는 프로그램에서의 사용을 금지합니다.").format(sound.label, lic.name)))
        if not lic.social:
            issues.append(Issue("error", tr("{0}: {1}는 YouTube 등 영상 사이트 게시를 허락하지 않습니다.").format(sound.label, lic.name)))
        if not lic.commercial:
            issues.append(Issue("warning", tr("{0}: {1} 라이선스는 영리 목적 사용을 허락하지 않습니다. 수익 창출 영상에는 쓰지 마세요.").format(sound.label, lic.name)))
        if lic.attribution == "required":
            line = sound.credit_line()
            if description is not None and line and line not in " ".join(description.split()):
                issues.append(Issue("error", tr("{0}: 설명란에 음원 크레디트가 없습니다.").format(sound.label)))
            if not (sound.title or sound.credit) or not (sound.author or sound.credit):
                issues.append(Issue("warning", tr("{0}: 크레디트에 쓸 제목과 작가가 기록되지 않았습니다.").format(sound.label)))
        for note in lic.notes:
            issues.append(Issue("info", f"{sound.label}: {shown(note)}"))
        if lic.url:
            issues.append(Issue("info", tr("{0}: 이용 조건 원문 {1} (확인 {2})").format(sound.label, lic.url, lic.checked)))
    return issues
