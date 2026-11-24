"""Titles and hashtags for clips, in the forms clip channels use.

Measured on 290 clip videos uploaded in 2026 (reports/키리누키 영상 레퍼런스 검토.md): every Japanese
title carried a bracket tag such as 【ホロライブ切り抜き】, English titles mostly name the agency and
"Clip" or "Eng Sub" in brackets, Korean ones start with the agency in square brackets. The line that
makes people click goes first (the first ~30 characters decide), the tag after it. Korean clips of a
streamer outside an agency (523 titles around one CHZZK VTuber, reports/독케익 키리누키 채널 분석.md)
start with the streamer's name instead and name a collab partner as ``(w.이름)``.

The hook is the subtitle line at the highlight's peak; without subtitles, the stream's own title.
Only the standard library and :mod:`stream2clip.subtitles` are used.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from .subtitles import Cue, _width, script_of

if TYPE_CHECKING:  # pragma: no cover
    from .translation import Glossary

__all__ = ["AGENCY_NAMES", "CLIP_WORDS", "GAME_TEMPLATES", "GENERIC_TAGS", "KIRINUKI_TAGS", "PLATFORM_TAGS", "SOLO_TEMPLATES", "TEMPLATES", "ClipTitle", "clip_title",
           "context_line", "guest_part", "hashtags", "hook_line", "stream_topic", "talent_name", "title_language"]

#: Agency names as clip titles write them, per language (proper names, not interface text).
AGENCY_NAMES: dict[str, dict[str, str]] = {
    "hololive": {"ja": "ホロライブ", "ko": "홀로라이브", "en": "Hololive"},
    "nijisanji": {"ja": "にじさんじ", "ko": "니지산지", "en": "NIJISANJI"},
    "vspo": {"ja": "ぶいすぽっ!", "ko": "브이스포", "en": "VSPO!"},
    "aogiri": {"ja": "あおぎり高校", "ko": "아오기리 고교", "en": "Aogiri High School"},
}
#: The word for "clip" in the tag and hashtags.
CLIP_WORDS = {"ja": "切り抜き", "ko": "클립", "en": "Clip"}
#: Title forms per language; {hook}, {talent}, {agency}, {clip}, {game}, {guests} are filled in, empty parts are tidied away.
TEMPLATES = {
    "ja": "{hook}{guests}【{talent}/{agency}{clip}】",
    "ko": "[{agency}] {hook}{guests} | {talent}",
    "en": "{hook}{guests} 【{agency} {clip} | {talent}】",
}
#: Korean clips of a streamer outside an agency put the streamer's name in the bracket: 56% of 523 clip
#: titles around one CHZZK VTuber started with it (reports/독케익 키리누키 채널 분석.md).
SOLO_TEMPLATES = {"ko": "[{talent}] {hook}{guests}"}
#: ``template="game"``: the game in a second bracket, as those channels title game streams.
GAME_TEMPLATES = {
    "ja": "{hook}{guests}【{game}】【{talent}/{agency}{clip}】",
    "ko": "[{talent}][{game}] {hook}{guests}",
    "en": "{hook}{guests} 【{game} | {talent}】",
}
#: Who else is in the clip, after the hook: ``(w.니니아)`` in Korean clip titles.
GUEST_FORMS = {"ja": " (w/{0})", "ko": " (w.{0})", "en": " (w/ {0})"}
GUEST_SEPARATORS = {"ja": "、", "ko": ", ", "en": ", "}
#: How long the hook may be, in full-width characters (a Latin letter counts about half).
HOOK_WIDTH = {"ja": 30, "ko": 24, "en": 34}
TITLE_LIMIT = 100  # YouTube's
#: What channel names add around the name: Ch., 公式, and VTuber as a word of its own (CHZZK's "버튜버 독케익" is 독케익).
_CHANNEL_NOISE = re.compile(r"\b(?:ch|channel|official|vtuber)\b\.?|チャンネル|채널|公式|버튜버(?=\s|$)|【[^】]*】|\[[^\]]*\]", re.IGNORECASE)
_TAG = re.compile(r"【[^】]*】|\[[^\]]*\]|〔[^〕]*〕|#\S+")


@dataclass(frozen=True)
class ClipTitle:
    title: str
    hashtags: tuple[str, ...]
    language: str
    hook: str


def title_language(*, translate_to: str | None = None, language: str | None = None, cues: Sequence[Cue] = (), fallback: str = "") -> str:
    """``ja`` / ``ko`` / ``en``: the language viewers read the clip in (its subtitles), else that of ``fallback``."""
    for code in (translate_to, language):
        if code:
            code = code.split("-")[0].lower()
            return code if code in TEMPLATES else "en"
    script = script_of(" ".join(c.text for c in cues[:20])) or script_of(fallback)
    return {"ja": "ja", "ko": "ko", "zh": "ja"}.get(script, "en")


def talent_name(channel: str, language: str, glossary: "Glossary | None" = None) -> str:
    """The talent's name from a channel name such as ``Pekora Ch. 兎田ぺこら``, in the form ``language`` reads best.

    Japanese keeps the Japanese name; English takes the Latin one; Korean takes the glossary's
    translation of the Japanese name, else the Latin one.
    """
    cleaned = " ".join(_CHANNEL_NOISE.sub(" ", channel or "").split())
    parts = [p.strip(" -/|:") for p in re.split(r"\s{2,}|\s[/|]\s|\s-\s", cleaned) if p.strip(" -/|:")]
    words = cleaned.split()
    latin = " ".join(w for w in words if re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*", w)).strip()
    native = " ".join(w for w in words if any(ord(ch) > 0x2E80 for ch in w)).strip()
    if not (latin or native):
        return parts[0] if parts else ""
    if language == "ja":
        return native or latin
    translated = glossary.apply(native) if glossary is not None and native else ""
    translated = translated if translated and translated != native and script_of(translated) in ("", language) else ""
    if language == "ko":
        return translated or latin or native
    return latin or translated or native


_CJK = "぀-ヿ㐀-鿿＀-￯"
_INNER_SPACE = re.compile(f"(?<=[{_CJK}])\\s+(?=[{_CJK}])")


def _clean(text: str) -> str:
    """One line: no tags, no spaces that automatic captions leave between Japanese words, sentence stops as spaces."""
    text = _TAG.sub(" ", text.replace("\n", " "))
    text = _INNER_SPACE.sub("", " ".join(text.split()))
    text = re.sub("。+", " ", text)  # ideographic full stops: titles run sentences together with a space
    return " ".join(text.split()).strip(" 、,.")


def _cut(text: str, width: float) -> str:
    """At most ``width`` full-width characters, cut after a phrase or a word when it has to be shorter."""
    if _width(text) <= width:
        return text
    out = ""
    for ch in text:
        if _width(out + ch) > width - 1.5:
            break
        out += ch
    if " " in out[len(out) // 2 :]:
        out = out[: out.rindex(" ")]
    return out.rstrip(" 、,") + "..."


def hook_line(cues: Sequence[Cue], peak: float, *, width: float = 30, fallback: str = "") -> str:
    """The line said at ``peak`` (seconds on the cues' clock), joined with the next when it is very short."""
    spoken = [c for c in sorted(cues, key=lambda c: c.start) if _clean(c.text)]
    at = next((i for i, c in enumerate(spoken) if c.start <= peak <= c.end), None)
    if at is None:
        at = next((i for i, c in enumerate(spoken) if c.start > peak), len(spoken) - 1 if spoken else None)
    if at is None:
        return _cut(_clean(fallback), width)
    text = _clean(spoken[at].text)
    if _width(text) < 6 and at + 1 < len(spoken):
        text = text + " " + _clean(spoken[at + 1].text)  # two lines, as two sentences are: with a space
    return _cut(text, width)


#: The third hashtag, after the agency and the talent.
GENERIC_TAGS = {"ja": "#切り抜き", "ko": "#버튜버", "en": "#VTuber"}
#: Korean clips also name the stream's platform and the kind of video; of 139 clip descriptions around a
#: CHZZK VTuber, 80% had hashtags and the top tags were 치지직, 버튜버 and 키리누키 (41 videos each).
PLATFORM_TAGS = {"chzzk": {"ko": "#치지직"}, "soop": {"ko": "#숲"}}
KIRINUKI_TAGS = {"ko": "#키리누키"}


def hashtags(language: str, *, agency: str | None = None, talent: str = "", platform: str | None = None) -> tuple[str, ...]:
    """The agency (with 切り抜き in Japanese), the talent and a general one; Korean adds the platform and 키리누키.

    YouTube shows the first three above the title, so in Korean, without an agency, those are the name,
    버튜버 and the platform (CHZZK, SOOP), as Korean clip channels write them.
    """
    name = re.sub(r"[\s!]", "", AGENCY_NAMES.get(agency or "", {}).get(language, ""))
    tags = []
    if name:
        tags.append("#" + name + (CLIP_WORDS["ja"] if language == "ja" else ""))
    if talent:
        tags.append("#" + re.sub(r"[\s!./]", "", talent))
    tags.append(GENERIC_TAGS.get(language, "#VTuber"))
    tags.append(PLATFORM_TAGS.get(platform or "", {}).get(language, ""))
    tags.append(KIRINUKI_TAGS.get(language, ""))
    seen: list[str] = []
    for tag in tags:
        if len(tag) > 1 and tag.lower() not in [t.lower() for t in seen]:
            seen.append(tag)
    return tuple(seen[:5 if language == "ko" else 3])


def guest_part(guests: Sequence[str], language: str) -> str:
    """`` (w.니니아, 계춘회)``: the others in a collab, as clip titles add them after the hook; empty without any."""
    names = [" ".join(g.split()) for g in guests if g and g.strip()]
    if not names:
        return ""
    return GUEST_FORMS.get(language, GUEST_FORMS["en"]).format(GUEST_SEPARATORS.get(language, ", ").join(names))


def clip_title(
    *,
    cues: Sequence[Cue] = (),
    peak: float = 0.0,
    channel: str = "",
    stream_title: str = "",
    agency: str | None = None,
    language: str = "ja",
    glossary: "Glossary | None" = None,
    template: str | None = None,
    translated: bool = False,
    guests: Sequence[str] = (),
    game: str = "",
    platform: str | None = None,
) -> ClipTitle:
    """A title for one clip: the hook (the line at ``peak``, on the cues' clock) and a bracket tag with the talent and agency.

    Without an agency a Korean title puts the talent in front (``[독케익] 진짜 너무 맛있다``). ``guests``
    are added as ``(w.이름)``; ``template="game"`` puts ``game`` in a second bracket; ``platform``
    (``chzzk``, ``soop``) adds that platform's hashtag in Korean.
    """
    language = language if language in TEMPLATES else "en"
    talent = talent_name(channel, language, glossary)
    agency_name = AGENCY_NAMES.get(agency or "", {}).get(language, "")
    hook = hook_line(cues, peak, width=HOOK_WIDTH[language], fallback=stream_title)
    if template == "game":
        form = GAME_TEMPLATES[language]
    else:
        form = template or (TEMPLATES[language] if agency_name else SOLO_TEMPLATES.get(language, TEMPLATES[language]))
    parts = {"talent": talent, "agency": agency_name, "clip": CLIP_WORDS[language], "game": " ".join((game or "").split()), "guests": guest_part(guests, language)}
    title = _tidy(form.format(hook=hook, **parts))
    if translated and language == "en" and "sub" not in title.lower():
        title += " [Eng Sub]"
    if len(title) > TITLE_LIMIT:  # the hook gives way first
        room = len(hook) - (len(title) - TITLE_LIMIT) - 3
        hook = (hook[: max(room, 0)].rstrip() + "...") if room > 0 else ""
        title = _tidy(form.format(hook=hook, **parts))[:TITLE_LIMIT]
    return ClipTitle(title, hashtags(language, agency=agency, talent=talent, platform=platform), language, hook)


_BRACKETED = re.compile(r"【([^】]+)】|\[([^\]]+)\]|〔([^〕]+)〕")
_AGENCY_WORDS = re.compile("|".join(re.escape(name) for names in AGENCY_NAMES.values() for name in names.values()) + r"|hololive|holo|vtuber|ホロ", re.IGNORECASE)


def context_line(stream_title: str, *, channel: str = "", width: float = 24) -> str:
    """What is going on, for the line at the top of a clip's first seconds: the stream's topic.

    Stream titles put the game or the kind of stream in a bracket tag (``【気のせいすぎるRPG】``); the first
    tag that is not the agency or the talent's name is the topic. Without one, the title itself.
    """
    topic = stream_topic(stream_title, channel=channel)
    return _cut(topic, width) if topic else _cut(_clean(stream_title or ""), width)


def stream_topic(stream_title: str, *, channel: str = "") -> str:
    """The first bracket tag of a stream title that is not the agency or the talent (the game, the kind of stream); empty without one."""
    names = {part for part in re.split(r"[\s/|]+", channel) if len(part) > 1}
    for match in _BRACKETED.finditer(stream_title or ""):
        tag = next(group for group in match.groups() if group)
        pieces = [p for p in re.split(r"[/|]", tag) if p.strip()]
        if pieces and all(_AGENCY_WORDS.search(p) or p.strip() in names or any(n in p for n in names) for p in pieces):
            continue  # 【ホロライブ/兎田ぺこら】 says who, not what
        return " ".join(tag.split())
    return ""


def _tidy(title: str) -> str:
    """Remove what empty parts leave behind: ``【/】``, ``[] ``, `` | `` at an end, doubled spaces."""
    title = re.sub(r"【\s*[/|]?\s*】|\[\s*\]", "", title)
    title = re.sub(r"【\s*[/|]\s*", "【", title)
    title = re.sub(r"\s*[/|]\s*】", "】", title)
    title = re.sub(r"(?:\s*\|\s*)+$|^\s*\|\s*", "", title.strip())
    title = re.sub(r"\s{2,}", " ", title)
    return title.strip()
