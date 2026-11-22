"""Subtitle translation with a name glossary (no translation service is built in; tests use a fake)."""

from __future__ import annotations

import json

import pytest

from stream2clip import plugins
from stream2clip.cli import main
from stream2clip.subtitles import Cue, Word
from stream2clip.translation import Glossary, get_translator, holodex_names, translate_cues

from .conftest import needs_ffmpeg


class FakeTranslator:
    """Pretends to translate: wraps each line in 《》 and remembers what it was asked."""

    def __init__(self):
        self.calls = []

    def translate(self, texts, target, source=None):
        self.calls.append((list(texts), target, source))
        return [f"《{t}》" for t in texts]


def test_glossary_files_and_longest_match_first(tmp_path):
    csv_file = tmp_path / "names.csv"
    csv_file.write_text("source,target,note\n兎田ぺこら,우사다 페코라,hololive\nぺこら,페코라,\nさくらみこ,,not filled in yet\n", encoding="utf-8")
    glossary = Glossary.load(csv_file)
    assert glossary.terms == {"兎田ぺこら": "우사다 페코라", "ぺこら": "페코라"}  # the row without a target is skipped
    assert glossary.apply("兎田ぺこらとぺこらの配信") == "우사다 페코라と페코라の配信"  # not "兎田페코라"

    json_file = tmp_path / "names.json"
    json_file.write_text(json.dumps({"草": "ㅋㅋ"}, ensure_ascii=False), encoding="utf-8")
    assert Glossary.load(json_file).apply("草") == "ㅋㅋ"

    saved = glossary.save(tmp_path / "out.csv", {"ぺこら": "nickname"})
    assert Glossary.load(saved).terms == glossary.terms and "nickname" in saved.read_text(encoding="utf-8")
    assert len(glossary) == 2


def test_translate_cues_keeps_timing_and_pins_names():
    cues = [
        Cue(1.0, 2.5, "ぺこらです", (Word(1.0, 1.6, "ぺこら"), Word(1.6, 2.5, "です"))),
        Cue(3.0, 4.0, ""),
        Cue(5.0, 6.0, "こんにちは\nみんな"),
    ]
    fake = FakeTranslator()
    out = translate_cues(cues, fake, target="ko", source="ja", glossary=Glossary({"ぺこら": "페코라"}))
    assert [(c.start, c.end) for c in out] == [(1.0, 2.5), (3.0, 4.0), (5.0, 6.0)]
    assert out[0].text == "《페코라です》" and out[0].words == ()  # the name went in already translated; word timing is dropped
    assert out[1].text == "" and out[2].text == "《こんにちは みんな》"
    assert fake.calls == [(["페코라です", "こんにちは みんな"], "ko", "ja")]  # empty cues are not sent

    # A translator that leaves a name untouched: the glossary fixes it afterwards.
    class Lazy:
        def translate(self, texts, target, source=None):
            return ["ぺこら 왔어요" for _ in texts]

    assert translate_cues([Cue(0, 1, "x")], Lazy(), glossary=Glossary({"ぺこら": "페코라"}))[0].text == "페코라 왔어요"


def test_bilingual_batches_and_bad_translators():
    cues = [Cue(i, i + 1, f"line {i}") for i in range(5)]
    fake = FakeTranslator()
    out = translate_cues(cues, fake, bilingual=True, batch=2)
    assert out[0].text == "line 0\n《line 0》" and [len(call[0]) for call in fake.calls] == [2, 2, 1]

    class Short:
        def translate(self, texts, target, source=None):
            return texts[:-1]

    with pytest.raises(ValueError, match="returned 1 lines for 2"):
        translate_cues(cues[:2], Short())


def test_bilingual_lines_are_not_rewrapped():
    from stream2clip.subtitles import to_ass

    class Korean:
        def translate(self, texts, target, source=None):
            return ["전부 맞았다고 생각했는데 하나도 안 맞았어요" for _ in texts]

    cue = translate_cues([Cue(0.0, 2.0, "全部当たっているだろう")], Korean(), bilingual=True)[0]
    line = next(ln for ln in to_ass([cue]).splitlines() if ln.startswith("Dialogue"))
    import re

    text = line.split(",,", 2)[-1]
    # each line in the font of its own language: Japanese kanji are not drawn in their Korean shapes
    assert "{" + chr(92) + "fnNoto Sans JP}全部" in text and "{" + chr(92) + "fnNoto Sans KR}전부" in text
    # one break, exactly between the two lines (Korean has spaces; wrapping by length used to split inside it)
    assert re.sub(r"[{][^}]*[}]", "", text) == "全部当たっているだろう" + chr(92) + "N전부 맞았다고 생각했는데 하나도 안 맞았어요"


def test_translator_lookup(monkeypatch):
    monkeypatch.setattr(plugins, "_collect", lambda group: {})
    with pytest.raises(RuntimeError, match="no built-in translation service"):
        get_translator()
    fake = FakeTranslator()
    monkeypatch.setattr(plugins, "_collect", lambda group: {"fake": lambda: fake} if group.endswith("translators") else {})
    assert get_translator() is fake and get_translator("fake") is fake
    with pytest.raises(RuntimeError, match="Unknown translator"):
        get_translator("deepl")


def test_holodex_draft_glossary():
    asked = []

    def get(url, headers):
        asked.append((url, headers))
        page = [
            {"name": "兎田ぺこら", "english_name": "Usada Pekora", "org": "Hololive", "group": "3rd Generation"},
            {"name": "Retired Talent", "english_name": "Someone", "inactive": True},
        ] if "offset=0" in url else [{"name": "さくらみこ", "english_name": "Sakura Miko", "org": "Hololive"}]
        return json.dumps(page).encode()

    glossary, notes = holodex_names("Hololive", "KEY", get=get, limit=2)
    assert glossary.terms == {"兎田ぺこら": "Usada Pekora", "さくらみこ": "Sakura Miko"}  # Japanese -> English, to be edited to Korean
    assert notes["兎田ぺこら"] == "Hololive / 3rd Generation"
    assert len(asked) == 2 and asked[0][1]["X-APIKEY"] == "KEY" and "org=Hololive" in asked[0][0] and "offset=2" in asked[1][0]
    with pytest.raises(ValueError, match="API key"):
        holodex_names("Hololive", "")


def test_cli_glossary_command(tmp_path, capsys):
    path = tmp_path / "g.csv"
    path.write_text("source,target\nぺこら,페코라\n", encoding="utf-8")
    assert main(["glossary", str(path), "--text", "ぺこらだよ"]) == 0
    assert "1 terms" in capsys.readouterr().out
    assert main(["glossary", str(tmp_path / "new.csv"), "--holodex", "Hololive", "--api-key", ""]) == 1  # no key: explained, not a traceback
    assert "API key" in capsys.readouterr().err


@needs_ffmpeg
def test_cli_clips_with_translation(green_screen_video, tmp_path, monkeypatch, capsys):
    fake = FakeTranslator()
    monkeypatch.setitem(plugins._RUNTIME["stream2clip.translators"], "fake", lambda: fake)
    srt = tmp_path / "subs.srt"
    srt.write_text("1\n00:00:00,100 --> 00:00:00,900\nぺこらです\n\n2\n00:00:01,000 --> 00:00:01,800\nこんにちは\n", encoding="utf-8")
    glossary = tmp_path / "names.csv"
    glossary.write_text("source,target\nぺこら,페코라\n", encoding="utf-8")
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.0, "end": 2.0}]}), encoding="utf-8")
    out = tmp_path / "clips"
    args = ["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(srt), "--translate", "ko",
            "--glossary", str(glossary), "--bilingual", "--layout", "none", "-f", "gif", "--fps", "5", "-o", str(out)]
    assert main(args) == 0
    ass = (out / "clip_01.ass").read_text(encoding="utf-8")
    assert "《페코라です》" in ass and "ぺこらです" in ass and "《こんにちは》" in ass  # bilingual: original and translation
    assert fake.calls and fake.calls[0][1] == "ko" and (out / "clip_01.gif").exists()

    assert main(["clips", str(green_screen_video), "--highlights", str(highlights), "--translate", "ko", "-o", str(out)]) == 1
    assert "--subtitles or --transcribe" in capsys.readouterr().err


# --------------------------------------------------------------------------- names in speech recognition


def test_glossary_heard_spellings_fix_transcripts(tmp_path):
    path = tmp_path / "names.csv"
    path.write_text("source,target,note,heard\n兎田ぺこら,우사다 페코라,,兎田ペコラ\nぺこら,페코라,,ペコラ|ぺコラ\nさくらみこ,,,\n", encoding="utf-8")
    glossary = Glossary.load(path)
    assert glossary.terms == {"兎田ぺこら": "우사다 페코라", "ぺこら": "페코라"}
    assert glossary.heard == {"兎田ペコラ": "兎田ぺこら", "ペコラ": "ぺこら", "ぺコラ": "ぺこら"}
    assert glossary.names() == ["兎田ぺこら", "ぺこら", "さくらみこ"]  # a name without a translation still helps recognition
    assert glossary.fix("兎田ペコラとぺコラ") == "兎田ぺこらとぺこら"  # the full name first

    # A name recognition split over two words becomes one word over their time: the karaoke still lights it up.
    cue = Cue(0.0, 2.0, "ペコラが来た", (Word(0.0, 0.3, "ペ"), Word(0.3, 0.6, "コラが"), Word(0.6, 2.0, "来た")))
    fixed = glossary.fix_cues([cue])[0]
    assert fixed.text == "ぺこらが来た" and fixed.words == (Word(0.0, 0.6, "ぺこらが"), Word(0.6, 2.0, "来た"))
    english = Glossary({}, {"iron mouse": "Ironmouse"}, ("Ironmouse",))
    words = (Word(0.0, 0.5, "hi"), Word(0.5, 1.0, "iron"), Word(1.0, 1.5, "mouse"), Word(1.5, 2.0, "here"))
    assert english.fix_cues([Cue(0.0, 2.0, "hi iron mouse here", words)])[0].words == (Word(0.0, 0.5, "hi"), Word(0.5, 1.5, "Ironmouse"), Word(1.5, 2.0, "here"))
    assert Glossary({"a": "b"}).fix_cues([cue]) == [cue]  # nothing misheard listed: unchanged

    json_file = tmp_path / "names.json"
    json_file.write_text(json.dumps({"ぺこら": {"target": "페코라", "heard": ["ペコラ"]}, "草": "ㅋㅋ"}, ensure_ascii=False), encoding="utf-8")
    loaded = Glossary.load(json_file)
    assert loaded.terms == {"ぺこら": "페코라", "草": "ㅋㅋ"} and loaded.heard == {"ペコラ": "ぺこら"}

    saved = Glossary.load(glossary.save(tmp_path / "out.csv"))
    assert (saved.terms, saved.heard, saved.vocabulary) == (glossary.terms, glossary.heard, glossary.vocabulary)


def test_transcriber_listens_for_the_glossary_names(monkeypatch):
    import numpy as np

    from stream2clip import audio
    from stream2clip.subtitles import FasterWhisperTranscriber

    class Model:
        def transcribe(self, samples, *, language=None, word_timestamps=False, vad_filter=False, hotwords=None, initial_prompt=None):
            self.hints = {"hotwords": hotwords, "initial_prompt": initial_prompt}
            return iter([]), None

    class OlderModel:  # faster-whisper before hotwords: the names go in the initial prompt
        def transcribe(self, samples, *, language=None, word_timestamps=False, vad_filter=False, initial_prompt=None):
            self.hints = {"initial_prompt": initial_prompt}
            return iter([]), None

    monkeypatch.setattr(audio, "decode_pcm", lambda path, sample_rate: np.zeros(160, dtype=np.float32))
    for model, expected in ((Model(), {"hotwords": "兎田ぺこら ぺこら", "initial_prompt": None}), (OlderModel(), {"initial_prompt": "兎田ぺこら ぺこら"})):
        transcriber = FasterWhisperTranscriber.__new__(FasterWhisperTranscriber)  # no model download
        transcriber._model, transcriber._vad, transcriber.hotwords = model, True, ("兎田ぺこら", "ぺこら")
        assert transcriber.transcribe("clip.wav", language="ja") == [] and model.hints == expected


@needs_ffmpeg
def test_cli_clips_fix_misheard_names_without_translating(green_screen_video, tmp_path):
    srt = tmp_path / "subs.srt"
    srt.write_text("1\n00:00:00,100 --> 00:00:00,900\nペコラです\n", encoding="utf-8")
    glossary = tmp_path / "names.csv"
    glossary.write_text("source,target,note,heard\nぺこら,,,ペコラ\n", encoding="utf-8")
    highlights = tmp_path / "h.json"
    highlights.write_text(json.dumps({"highlights": [{"rank": 1, "start": 0.0, "end": 2.0}]}), encoding="utf-8")
    out = tmp_path / "clips"
    assert main(["clips", str(green_screen_video), "--highlights", str(highlights), "--subtitles", str(srt), "--glossary", str(glossary),
                 "--layout", "none", "-f", "gif", "--fps", "5", "-o", str(out)]) == 0
    ass = (out / "clip_01.ass").read_text(encoding="utf-8")
    assert "ぺこらです" in ass and "ペコラ" not in ass
