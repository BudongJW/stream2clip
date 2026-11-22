"""Background music and sound effects: built-in effects, levels, the mix graph, the sound library, credits and license checks."""

from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np
import pytest

from stream2clip.compliance import build_description, check_upload
from stream2clip.ffmpeg import AudioLayer, AudioMix, ExportOptions, build_export_command, mix_filters, mix_input_args
from stream2clip.highlights import Highlight
from stream2clip.soundtrack import (
    BUILTIN_EFFECTS,
    LICENSES,
    RATE,
    Effect,
    Sound,
    SoundLibrary,
    Soundtrack,
    active_level,
    builtin_sound,
    check_sounds,
    credit_lines,
    effect_for,
    plan_mix,
    render_builtin,
    resolve_sound,
    synth,
    write_wav,
)
from stream2clip.sources import SourceInfo

from .conftest import needs_ffmpeg

SRC = SourceInfo(url="https://www.youtube.com/watch?v=abc", title="t", channel="c", live_status="was_live", availability="public")


def tone(freq: float, seconds: float, amplitude: float = 0.1, rate: int = RATE) -> np.ndarray:
    return (amplitude * np.sin(2 * np.pi * freq * np.arange(int(seconds * rate)) / rate)).astype(np.float32)


# --------------------------------------------------------------------------- built-in effects and levels


@pytest.mark.parametrize("name", BUILTIN_EFFECTS)
def test_builtin_effects_are_drawn_the_same_every_time(name):
    samples = synth(name)
    assert samples.dtype == np.float32 and 0.1 < samples.size / RATE < 2.0 and np.isfinite(samples).all()
    assert float(np.abs(samples).max()) == pytest.approx(10 ** (-3 / 20), abs=1e-3)  # peak at -3 dBFS
    assert abs(float(samples[-1])) < 1e-3  # no click at the end
    assert np.array_equal(samples, synth(name))
    assert active_level(samples, RATE) > -30


def test_builtin_effects_sound_different():
    def centroid(x):
        spectrum = np.abs(np.fft.rfft(x))
        return float((np.fft.rfftfreq(x.size, 1 / RATE) * spectrum).sum() / spectrum.sum())

    assert centroid(synth("boom")) < 500 < centroid(synth("ding")) < centroid(synth("sparkle"))
    with pytest.raises(ValueError):
        synth("airhorn")


def test_wav_files_are_stereo_48k(tmp_path):
    path = render_builtin("pop", tmp_path)
    with wave.open(str(path)) as handle:
        assert (handle.getnchannels(), handle.getframerate(), handle.getsampwidth()) == (2, RATE, 2)
        assert handle.getnframes() == synth("pop").size
    assert write_wav(np.array([2.0, -2.0]), tmp_path / "loud.wav").stat().st_size > 44  # out-of-range samples are clipped, not wrapped


def test_active_level_ignores_pauses():
    talk = tone(440, 2.0)
    expected = 20 * np.log10(0.1 / np.sqrt(2))
    assert active_level(talk, RATE) == pytest.approx(expected, abs=0.2)
    with_pauses = np.concatenate([talk, np.zeros(RATE * 6, dtype=np.float32)])
    assert active_level(with_pauses, RATE) == pytest.approx(expected, abs=0.2)
    assert active_level(np.zeros(RATE), RATE) == -90.0
    assert active_level(np.zeros(10), RATE) == -90.0


def test_auto_effect_follows_the_chat():
    assert effect_for({"react_laugh": 30, "react_shock": 2}) == "pop"
    assert effect_for({"react_shock": 9}) == "boom"
    assert effect_for({"react_cute": 4, "react_hype": 3}) == "sparkle"
    assert effect_for({}) == effect_for(None) == "ding"  # a marker with no reaction counted


# --------------------------------------------------------------------------- the ffmpeg graph


def test_mix_graph_ducks_music_and_places_effects():
    mix = AudioMix((
        AudioLayer("bgm.mp3", gain=-14.5, loop=True, offset=3.0, fade_in=0.5, fade_out=1.5, duck=True, duck_threshold=0.02),
        AudioLayer("ding.wav", gain=-2.0, at=4.25),
        AudioLayer("late.wav", at=12.0),  # after the end: left out of the graph
    ), length=10.0)
    graph = mix_filters(mix, first_input=1)
    assert graph.startswith("[0:a:0]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=duration=10.000,apad=whole_dur=10.000,asplit=2[mv][mk0];")
    assert "[1:a:0]aresample=48000" in graph and "volume=-14.5dB" in graph and "afade=t=in:st=0:d=0.500" in graph and "afade=t=out:st=8.500:d=1.500" in graph
    assert "[mr0][mk0]sidechaincompress=threshold=0.0200:ratio=8:attack=50:release=600[ml0]" in graph
    assert "[2:a:0]" in graph and "adelay=delays=4250:all=1" in graph and "atrim=duration=5.750" in graph
    assert "[3:a:0]" not in graph
    assert graph.endswith("[mv][ml0][ml1]amix=inputs=3:duration=first:dropout_transition=0:normalize=0,alimiter=limit=0.8913:level=0[a]")
    assert mix_input_args(mix) == ["-stream_loop", "-1", "-ss", "3.000", "-i", "bgm.mp3", "-i", "ding.wav", "-i", "late.wav"]


def test_mix_graph_without_the_clips_own_sound():
    graph = mix_filters(AudioMix((AudioLayer("bgm.mp3", loop=True, duck=True),), length=5.0, voice=False), first_input=1, voice_in=None)
    assert graph.startswith("anullsrc=r=48000:cl=stereo,atrim=duration=5.000")
    assert "sidechaincompress" not in graph and "asplit" not in graph  # nothing to duck under


def test_export_command_with_music():
    mix = AudioMix((AudioLayer("bgm.mp3", loop=True),), length=4.0)
    cmd = build_export_command("in.mp4", "out.mp4", ExportOptions(format="mp4", fps=30, start=10, end=14, mix=mix), ffmpeg="ffmpeg")
    assert cmd[cmd.index("-stream_loop") + 3 : cmd.index("-stream_loop") + 4] == ["bgm.mp3"]
    assert cmd.index("in.mp4") < cmd.index("bgm.mp3")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert graph.count("[v]") == 1 and graph.endswith("[a]") and "-an" not in cmd
    assert cmd[cmd.index("-map", cmd.index("-map") + 1) + 1] == "[a]"
    shortened = build_export_command("in.mp4", "out.mp4", ExportOptions(format="mp4", fps=30, start=10, end=14, keep=((0.0, 1.0), (2.0, 4.0)), mix=mix), ffmpeg="ffmpeg")
    graph = shortened[shortened.index("-filter_complex") + 1]
    assert "concat=n=2:v=0:a=1[kv]" in graph and "[kv]aresample=48000" in graph  # silences go first, the music goes under what is left
    with pytest.raises(ValueError, match="no sound"):
        ExportOptions(format="gif", mix=mix)
    with pytest.raises(ValueError, match="audio=True"):
        build_export_command("in.mp4", "out.mp4", ExportOptions(format="mp4", audio=False, mix=mix), ffmpeg="ffmpeg")


def test_layers_check_their_values():
    for bad in ({"at": -1}, {"fade_in": -0.1}, {"duck_threshold": 2.0}, {"duck_ratio": 50}):
        with pytest.raises(ValueError):
            AudioLayer("x.wav", **bad)
    with pytest.raises(ValueError):
        AudioMix((), length=0)


# --------------------------------------------------------------------------- the plan of one clip


def fixed_levels(level: float = -14.0, seconds: float = 1.0):
    return lambda sound: (level, seconds)


def test_music_sits_under_the_clip_and_tracks_take_turns():
    music = (Sound(Path("a.mp3"), name="a"), Sound(Path("b.mp3"), name="b"))
    track = Soundtrack(music=music, under=12.0, music_start=5.0)
    first = plan_mix(track, 0, length=20.0, voice_level=-20.0, levels=fixed_levels(-10.0))
    layer = first.mix.layers[0]
    assert layer.path == Path("a.mp3") and layer.gain == -22.0 and layer.loop and layer.duck and layer.offset == 5.0
    assert layer.duck_threshold == pytest.approx(10 ** (-42 / 20), rel=1e-3)  # 22 dB under the clip's -20 dB
    assert plan_mix(track, 1, length=20.0, voice_level=-20.0, levels=fixed_levels()).mix.layers[0].path == Path("b.mp3")
    assert plan_mix(track, 2, length=20.0, voice_level=-20.0, levels=fixed_levels()).mix.layers[0].path == Path("a.mp3")
    fixed = Soundtrack(music=music[:1], volume=-30.0, duck=False)
    assert plan_mix(fixed, 0, length=5.0, voice_level=-20.0, levels=fixed_levels()).mix.layers[0].gain == -30.0
    silent = plan_mix(Soundtrack(music=music[:1]), 0, length=5.0, voice_level=None, levels=fixed_levels(-10.0))
    assert not silent.mix.voice and not silent.mix.layers[0].duck and silent.mix.layers[0].gain == -22.0  # taken as a -20 dB clip
    assert plan_mix(Soundtrack(), 0, length=5.0, voice_level=-20.0, levels=fixed_levels()) is None


def test_effects_land_on_their_moment():
    boom, whoosh = builtin_sound("boom"), builtin_sound("whoosh")
    track = Soundtrack(effects=(Effect(boom, "peak"), Effect(whoosh, "peak"), Effect(boom, "start"), Effect(boom, "end"), Effect(boom, 30.0)), effect_gap=0)
    plan = plan_mix(track, 0, length=10.0, voice_level=-20.0, peak=4.0, levels=fixed_levels(-10.0, 1.1))
    assert [round(p.at, 2) for p in plan.sounds] == [4.0, 3.7, 0.0, 8.9]  # the whoosh swells into the peak; 30 s is past the end
    assert plan.skipped == ["boom: after the end"]
    assert plan.sounds[0].gain == -13.0  # 3 dB under the clip's -20 dB
    auto = plan_mix(Soundtrack(effects=(Effect(builtin_sound("auto")),)), 0, length=10.0, voice_level=-20.0, peak=2.0, reactions={"react_shock": 5}, levels=fixed_levels())
    assert auto.sounds[0].sound.name == "boom"
    with pytest.raises(ValueError):
        Effect(boom, "middle")


def test_effects_keep_their_distance():
    boom, pop, whoosh = builtin_sound("boom"), builtin_sound("pop"), builtin_sound("whoosh")
    track = Soundtrack(effects=(Effect(boom, "peak"), Effect(pop, 5.5), Effect(whoosh, "peak"), Effect(pop, "start"), Effect(pop, "end")))
    plan = plan_mix(track, 0, length=12.0, voice_level=-20.0, peak=4.0, levels=fixed_levels(-10.0, 0.14))
    assert [(p.sound.name, p.at, p.moved) for p in plan.sounds] == [("boom", 4.0, 0.0), ("pop", 7.0, 1.5), ("pop", 0.0, 0.0), ("pop", 11.86, 0.0)]
    assert plan.skipped == ["whoosh: within 3 s of another effect"]  # 3 s away from the boom is more than it may move
    hits = sorted(p.at + p.sound.hit for p in plan.sounds)
    assert min(b - a for a, b in zip(hits, hits[1:])) >= 3.0 - 1e-6


def test_short_clip_effects_are_not_pushed_past_the_end():
    """Found on 10 s clips of a real stream: keeping its distance, the end ding moved to 9.7 s and was cut after 0.3 s."""
    ding = builtin_sound("ding")
    track = Soundtrack(effects=(Effect(ding, "peak"), Effect(ding, "end")))
    plan = plan_mix(track, 0, length=10.0, voice_level=-20.0, peak=6.16, levels=fixed_levels(-10.0, 1.4))
    assert [p.at for p in plan.sounds] == [6.16] and plan.skipped == ["ding: within 3 s of another effect"]  # left out, not cut short
    roomy = plan_mix(Soundtrack(effects=(Effect(ding, "peak"), Effect(ding, 7.0))), 0, length=12.0, voice_level=-20.0, peak=5.0, levels=fixed_levels(-10.0, 1.4))
    assert [p.at for p in roomy.sounds] == [5.0, 8.0]  # moved later while all of it still fits
    late = plan_mix(Soundtrack(effects=(Effect(ding, 9.5),)), 0, length=10.0, voice_level=-20.0, levels=fixed_levels(-10.0, 1.4))
    assert late.sounds[0].at == 9.5 and late.mix.layers[0].fade_out == pytest.approx(0.1)  # asked for that late: it stays, faded out
    assert plan.mix.layers[0].fade_out == 0.0


def test_effects_land_between_subtitle_lines():
    from stream2clip.soundtrack import place_effect

    lines = [(1.0, 3.0), (3.4, 6.0)]
    assert place_effect(2.8, [], gap=3.0, low=0.0, high=10.0, lines=lines) == 3.0  # the end of the line, 0.2 s later
    assert place_effect(2.0, [], gap=3.0, low=0.0, high=10.0, lines=lines) == 2.0  # mid-line, no edge within 0.75 s: stays
    assert place_effect(2.8, [], gap=3.0, low=0.0, high=10.0, lines=lines, on_sound=True) == 2.8  # on the shout itself: stays
    assert place_effect(3.2, [], gap=3.0, low=0.0, high=10.0, lines=lines) == 3.2  # already between lines
    assert place_effect(5.0, [3.0], gap=3.0, low=0.0, high=10.0) == 6.0
    assert place_effect(5.0, [3.0, 8.0], gap=3.0, low=0.0, high=10.0) is None
    assert place_effect(9.5, [], gap=3.0, low=0.0, high=9.0) is None  # past the end, and nothing to step aside from
    plan = plan_mix(Soundtrack(effects=(Effect(builtin_sound("ding"), 2.8),)), 0, length=10.0, voice_level=-20.0, lines=lines, levels=fixed_levels())
    assert (plan.sounds[0].at, plan.sounds[0].moved) == (3.0, 0.2)
    exact = plan_mix(Soundtrack(effects=(Effect(builtin_sound("ding"), 2.8),), snap=False), 0, length=10.0, voice_level=-20.0, lines=lines, levels=fixed_levels())
    assert exact.sounds[0].at == 2.8  # asked to stay where it was put
    snapped = plan_mix(Soundtrack(effects=(Effect(builtin_sound("ding")),)), 0, length=10.0, voice_level=-20.0, peak=2.8, peak_on_sound=True, lines=lines, levels=fixed_levels())
    assert snapped.sounds[0].at == 2.8


def test_talk_is_found_in_the_sound():
    from stream2clip.soundtrack import sounding_spans

    rate = 16000
    quiet = np.zeros(int(0.1 * rate), dtype=np.float32)
    talk = np.concatenate([tone(300, 1.0, rate=rate), np.zeros(rate, dtype=np.float32), tone(300, 0.5, rate=rate), quiet, tone(300, 0.5, rate=rate)])
    assert sounding_spans(talk, rate) == [(0.0, 1.0), (2.0, 3.1)]  # a 0.1 s breath does not split a line
    assert sounding_spans(np.zeros(rate, dtype=np.float32), rate) == [] and sounding_spans(np.zeros(10, dtype=np.float32), rate) == []


def test_effect_specs_from_the_command_line(tmp_path):
    library = SoundLibrary(tmp_path / "lib")
    assert Effect.parse("ding", library).when == "peak"
    assert Effect.parse("boom@start", library).when == "start"
    parsed = Effect.parse("pop@1.5", library)
    assert parsed.when == 1.5 and parsed.sound.builtin
    with pytest.raises(ValueError, match="built-in"):
        resolve_sound("ding", "bgm", library)
    with pytest.raises(ValueError, match="No sound"):
        resolve_sound("nothing-here", "sfx", library)


# --------------------------------------------------------------------------- library, credits, checks


def test_library_remembers_where_a_sound_came_from(tmp_path):
    downloaded = write_wav(tone(300, 0.5), tmp_path / "downloads" / "OtoLogic - Cafe.wav")
    library = SoundLibrary(tmp_path / "lib")
    sound = library.add(downloaded, name="cafe", license="otologic", title="Cafe", url="https://otologic.jp/free/bgm/x.html", tags=("chill",))
    assert sound.path == tmp_path / "lib" / "OtoLogic - Cafe.wav" and sound.path.is_file()  # copied in
    saved = json.loads((tmp_path / "lib" / "sounds.json").read_text(encoding="utf-8"))
    assert saved["schema"] == "stream2clip.sounds/v1" and saved["sounds"][0]["file"] == "OtoLogic - Cafe.wav"
    again = SoundLibrary(tmp_path / "lib")
    assert again.find("CAFE") == sound and resolve_sound("cafe", "bgm", again) == sound
    assert resolve_sound(str(sound.path), "bgm", again).license == "otologic"  # a file is matched to its entry
    with pytest.raises(ValueError, match="already"):
        again.add(downloaded, name="cafe", license="otologic")
    with pytest.raises(ValueError, match="Unknown license"):
        again.add(downloaded, name="other", license="free-for-sure")
    assert again.add(downloaded, name="cafe-sfx", kind="sfx", license="otologic").path == sound.path  # the same file is not copied twice
    namesake = write_wav(tone(900, 0.5), tmp_path / "elsewhere" / "OtoLogic - Cafe.wav")
    assert again.add(namesake, name="other-cafe", license="cc0").path.name == "OtoLogic - Cafe-2.wav"
    again.remove("cafe-sfx")
    again.remove("other-cafe")
    loose = resolve_sound(str(downloaded), "bgm", again)
    assert loose.license == "" and loose.name == "OtoLogic - Cafe"
    again.remove("cafe")
    assert SoundLibrary(tmp_path / "lib").find("cafe") is None


def test_credit_lines_follow_the_provider():
    assert Sound(Path("x.mp3"), title="Sunny", author="Ann", url="https://example.org/s", license="cc-by-4.0").credit_line() == (
        '"Sunny" by Ann / https://example.org/s / CC BY 4.0 https://creativecommons.org/licenses/by/4.0/'
    )
    assert Sound(Path("x.mp3"), title="Cafe", license="otologic").credit_line() == "BGM by OtoLogic(CC BY 4.0)"
    assert Sound(Path("x.mp3"), title="Wallpaper", license="incompetech").credit_line().startswith('"Wallpaper" Kevin MacLeod (incompetech.com) Licensed under')
    assert Sound(Path("x.mp3"), title="t", license="pixabay", credit="Music by  Someone\nfrom Pixabay").credit_line() == "Music by Someone from Pixabay"
    assert builtin_sound("pop").credit_line() == "" and Sound(Path("x.wav"), license="cc0").credit_line() == ""
    same = Sound(Path("x.mp3"), title="Cafe", license="otologic")
    assert credit_lines([same, same, builtin_sound("ding")]) == ["BGM by OtoLogic(CC BY 4.0)"]


def test_every_license_names_its_official_text():
    for key, lic in LICENSES.items():
        assert lic.key == key and lic.attribution in ("required", "optional", "none")
        if key not in ("own", "builtin"):
            assert lic.url.startswith("https://") and lic.checked.startswith("2026-")


def test_license_checks():
    def levels(sound, description=None):
        return {i.level for i in check_sounds([sound], description=description)}, " ".join(i.message for i in check_sounds([sound], description=description))

    assert check_sounds([builtin_sound("ding")]) == []
    kinds, text = levels(Sound(Path("mystery.mp3"), name="mystery"))
    assert "warning" in kinds and "라이선스가 기록되지 않은" in text
    kinds, text = levels(Sound(Path("x.mp3"), name="x", title="t", author="a", license="cc-by-nd-4.0"))
    assert "error" in kinds and "영상에 넣는 것을 허락하지" in text
    kinds, text = levels(Sound(Path("x.mp3"), name="x", title="t", author="a", license="cc-by-nc-4.0"))
    assert "error" not in kinds and "영리 목적" in text
    assert "영상을 만드는 프로그램" in levels(Sound(Path("x.mp3"), name="x", license="bensound-free", credit="c"))[1]
    assert "영상 사이트 게시" in levels(Sound(Path("x.mp3"), name="x", license="bbc-remarc", title="t"))[1]
    cc = Sound(Path("x.mp3"), name="x", title="t", author="a", license="cc-by-4.0")
    assert "error" in levels(cc, description="no credit here")[0]
    assert "error" not in levels(cc, description="BGM\n" + cc.credit_line())[0]
    assert "크레디트에 쓸 제목과 작가" in levels(Sound(Path("x.mp3"), name="x", license="cc-by-4.0"))[1]
    assert any("Content ID" in i.message for i in check_sounds([cc]))


def test_description_lists_the_credits_and_the_check_reads_them():
    cc = Sound(Path("x.mp3"), name="x", title="Sunny", author="Ann", license="cc-by-4.0")
    text = build_description(SRC, credits=credit_lines([cc]))
    assert text.splitlines()[0] == "【元配信 / 원본 방송】" and "BGM, 효과음\n" + cc.credit_line() in text
    assert "BGM" not in build_description(SRC)
    issues = check_upload(SRC, description=text, sounds=[cc], length=30.0)
    assert not [i for i in issues if i.level == "error"]
    long = check_upload(SRC, description=text, sounds=[cc], length=75.0)
    assert any(i.level == "warning" and "1분" in i.message for i in long)
    assert not any("1분" in i.message for i in check_upload(SRC, description=text, sounds=[builtin_sound("pop")], length=75.0))


# --------------------------------------------------------------------------- clips with sound


@pytest.fixture
def talk_then_pause(tmp_path) -> Path:
    """4 s: a 440 Hz "voice" for two seconds, then silence."""
    out = tmp_path / "talk.mp4"
    subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:r=10:d=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=2,apad=whole_dur=4", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(out)],
        check=True,
    )
    return out


def band_level(samples: np.ndarray, rate: int, freq: float) -> float:
    spectrum = np.abs(np.fft.rfft(samples * np.hanning(samples.size)))
    freqs = np.fft.rfftfreq(samples.size, 1 / rate)
    return 20 * np.log10(spectrum[(freqs > freq - 30) & (freqs < freq + 30)].max() + 1e-9)


def decoded(path: Path, rate: int = 8000) -> np.ndarray:
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(rate), "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(pcm, dtype=np.float32)


@needs_ffmpeg
def test_clip_with_music_and_an_effect(talk_then_pause, tmp_path):
    from stream2clip.export import probe
    from stream2clip.pipeline import compile_folder, make_clips

    music = write_wav(tone(1500, 1.5, amplitude=0.125), tmp_path / "music.wav")  # shorter than the clip: it loops
    library = SoundLibrary(tmp_path / "lib")
    song = library.add(music, name="tone", license="cc-by-4.0", title="Tone", author="Me", url="https://example.org/tone")
    track = Soundtrack(music=(song,), effects=(Effect(builtin_sound("boom"), 3.0),))
    results = make_clips(talk_then_pause, [Highlight(1, 0.0, 4.0, 1.0, 5.0, ["x"])], tmp_path / "clips", options=ExportOptions(format="mp4", fps=10), soundtrack=track, source=SRC)
    clip = results[0]
    assert probe(clip.path).duration == pytest.approx(4.0, abs=0.15) and probe(clip.path).has_audio
    sound = decoded(clip.path)
    talking, pause, hit = sound[4000:12000], sound[17600:23200], sound[24000:28000]  # 0.5-1.5 s, 2.2-2.9 s, 3.0-3.5 s
    assert band_level(talking, 8000, 440) > band_level(talking, 8000, 1500) + 12  # the voice stays on top
    assert band_level(pause, 8000, 1500) > band_level(talking, 8000, 1500) + 3  # the music comes back up when nobody talks
    assert band_level(pause, 8000, 440) < band_level(talking, 8000, 440) - 40
    assert np.sqrt(np.mean(hit ** 2)) > 3 * np.sqrt(np.mean(pause ** 2))  # the boom at 3 s
    assert [s.sound.label for s in clip.sounds] == ["tone", "boom"]
    assert song.credit_line() in clip.description.read_text(encoding="utf-8")
    assert not [i for i in clip.issues if i.level == "error"]
    index = json.loads((tmp_path / "clips" / "clips.json").read_text(encoding="utf-8"))
    assert [s["name"] for s in index["clips"][0]["sounds"]] == ["tone", "boom"] and index["clips"][0]["sounds"][0]["credit"] == song.credit_line()
    made = compile_folder(tmp_path / "clips")
    assert song.credit_line() in made.notes.read_text(encoding="utf-8")


@needs_ffmpeg
def test_effect_follows_the_peak_when_silences_are_cut(tmp_path):
    from stream2clip.pipeline import make_clips

    video = tmp_path / "gaps.mp4"
    subprocess.run(  # a tone for the first second of every three: the peak at 6.5 s moves to 2.5 s once the pauses are cut down
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=160x120:r=10:d=9",
         "-f", "lavfi", "-i", "aevalsrc='0.4*sin(2*PI*440*t)*lt(mod(t,3),1)':s=48000:d=9", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(video)],
        check=True,
    )
    track = Soundtrack(effects=(Effect(builtin_sound("ding")),), snap=False)  # the peak as chat put it, to follow it through the cuts
    results = make_clips(video, [Highlight(1, 0.0, 9.0, 6.5, 5.0)], tmp_path / "clips", options=ExportOptions(format="mp4", fps=10), soundtrack=track, trim_silence=0.7)
    clip = results[0]
    assert clip.removed > 2.0
    from stream2clip.subtitles import clip_time

    assert clip.sounds[0].at == pytest.approx(clip_time(6.5, [(0.0, 1.25), (2.75, 4.25), (5.75, 7.25)]), abs=0.3)


@needs_ffmpeg
def test_clip_without_sound_gets_the_music_alone(tmp_path):
    from stream2clip.export import probe
    from stream2clip.pipeline import make_clips

    video = tmp_path / "mute.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=160x120:r=10:d=3", "-c:v", "libx264", "-preset", "ultrafast", str(video)], check=True)
    music = write_wav(tone(800, 1.0), tmp_path / "m.wav")
    results = make_clips(video, [Highlight(1, 0.0, 3.0, 1.0, 1.0)], tmp_path / "clips", options=ExportOptions(format="mp4", fps=10),
                         soundtrack=Soundtrack(music=(Sound(music, name="m", license="cc0"),)))
    assert probe(results[0].path).has_audio
    assert band_level(decoded(results[0].path)[4000:16000], 8000, 800) > 20


# --------------------------------------------------------------------------- command line


def test_sounds_command(tmp_path, capsys):
    from stream2clip.cli import main

    lib = tmp_path / "lib"
    song = write_wav(tone(500, 0.5), tmp_path / "song.wav")
    assert main(["sounds", "--sounds", str(lib), "add", str(song), "--name", "song", "--license", "pixabay", "--title", "Song", "--author", "Ann", "--tag", "chill"]) == 0
    out = capsys.readouterr().out
    assert "added  song" in out and "credit Song by Ann via Pixabay" in out
    assert main(["sounds", "--sounds", str(lib)]) == 0 and "song" in capsys.readouterr().out
    assert main(["sounds", "licenses"]) == 0
    listed = capsys.readouterr().out
    assert "bensound-free" in listed and "not through video tools" in listed and "https://opentracks.com/" in listed
    assert main(["sounds", "builtin", "pop", "ding", "-o", str(tmp_path / "fx")]) == 0
    assert sorted(p.name for p in (tmp_path / "fx").iterdir()) == ["ding.wav", "pop.wav"]
    assert main(["sounds", "--sounds", str(lib), "remove", "song"]) == 0
    assert SoundLibrary(lib).find("song") is None


def test_clip_options_build_a_soundtrack(tmp_path):
    from stream2clip.cli import _soundtrack, build_parser

    song = write_wav(tone(500, 0.5), tmp_path / "song.wav")
    args = build_parser().parse_args(["clips", "v.mp4", "--highlights", "h.json", "-o", str(tmp_path), "--bgm", str(song), "--bgm-under", "15", "--no-duck",
                                      "--sfx", "auto", "--sfx", "whoosh@start", "--sfx-gap", "2", "--sounds", str(tmp_path / "lib")])
    track = _soundtrack(args)
    assert track.music[0].path == song and track.under == 15.0 and not track.duck and track.effect_gap == 2.0
    assert [(e.sound.name, e.when) for e in track.effects] == [("auto", "peak"), ("whoosh", "start")]
    assert _soundtrack(build_parser().parse_args(["clips", "v.mp4", "--highlights", "h.json", "-o", str(tmp_path)])) is None


# --------------------------------------------------------------------------- loudness


LOUDNORM_LOG = """[Parsed_loudnorm_0 @ 000001]
{
	"input_i" : "-23.84",
	"input_tp" : "-6.46",
	"input_lra" : "7.10",
	"input_thresh" : "-34.30",
	"output_i" : "-14.02",
	"output_tp" : "-1.50",
	"output_lra" : "5.20",
	"output_thresh" : "-24.40",
	"normalization_type" : "dynamic",
	"target_offset" : "0.02"
}
"""


def test_loudness_two_passes_in_the_graph():
    from stream2clip.ffmpeg import Loudness, audio_filters, build_loudness_command, parse_loudnorm

    measured = parse_loudnorm(LOUDNORM_LOG)
    assert measured == (-23.84, -6.46, 7.1, -34.3, 0.02)
    assert parse_loudnorm(LOUDNORM_LOG.replace('"-23.84"', '"-inf"')) is None and parse_loudnorm("no json here") is None
    assert Loudness().filter() == "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json"
    second = Loudness(measured=measured).filter()
    assert "measured_I=-23.84" in second and "offset=0.02" in second and "linear=true" in second and second.endswith(",aresample=48000")
    assert ":LRA=11:" in second  # the clip's own range (7.1) fits in the target's
    assert ":LRA=20:" in Loudness(measured=(-20.0, -3.0, 25.0, -30.0, 0.0)).filter()  # widened for a wide clip, at most 20
    plain = audio_filters(ExportOptions(format="mp4", loudness=Loudness(measured=measured)))
    assert plain.startswith("[0:a:0]loudnorm=I=-14") and plain.endswith("[a]")
    assert audio_filters(ExportOptions(format="mp4")) is None  # nothing to do: the track is copied through
    trimmed = audio_filters(ExportOptions(format="mp4", fps=10, keep=((0.0, 1.0), (2.0, 3.0)), loudness=Loudness()))
    assert "concat=n=2:v=0:a=1[pre];[pre]loudnorm=" in trimmed
    mix = AudioMix((AudioLayer("bgm.mp3", loop=True),), length=3.0)
    mixed = audio_filters(ExportOptions(format="mp4", mix=mix, loudness=Loudness()))
    assert "level=0[pre];[pre]loudnorm=" in mixed  # after the limiter of the mix
    cmd = build_loudness_command("in.mp4", ExportOptions(format="mp4", start=5, end=8, mix=mix, loudness=Loudness(measured=measured)), ffmpeg="ffmpeg")
    assert cmd[-3:] == ["-f", "null", "-"] and "bgm.mp3" in cmd and "-vn" in cmd and "print_format=json" in cmd[cmd.index("-filter_complex") + 1]
    with pytest.raises(ValueError, match="no sound"):
        ExportOptions(format="gif", loudness=Loudness())
    with pytest.raises(ValueError):
        Loudness(target=0)


def integrated(path: Path) -> float:
    import re

    log = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128", "-f", "null", "-"], capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", log)[-1])


@needs_ffmpeg
def test_export_brings_the_sound_to_the_target(talk_then_pause, tmp_path):
    from stream2clip.export import export, measure_loudness, probe
    from stream2clip.ffmpeg import Loudness

    quiet = tmp_path / "quiet.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(talk_then_pause), "-af", "volume=-12dB", "-c:v", "copy", "-c:a", "aac", str(quiet)], check=True)
    before = integrated(quiet)
    out = export(quiet, tmp_path / "loud.mp4", ExportOptions(format="mp4", fps=10, loudness=Loudness()))
    assert before < -24 and integrated(out) == pytest.approx(-14.0, abs=1.0)
    mute = tmp_path / "mute.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=64x64:r=10:d=2", "-c:v", "libx264", "-preset", "ultrafast", str(mute)], check=True)
    assert measure_loudness(mute, ExportOptions(format="mp4", loudness=Loudness())).loudness is None  # no sound: nothing to bring up
    assert not probe(export(mute, tmp_path / "still_mute.mp4", ExportOptions(format="mp4", fps=10, loudness=Loudness()))).has_audio


# --------------------------------------------------------------------------- effects on the moment


def burst_at(seconds: float, length: float = 8.0, rate: int = 16000) -> np.ndarray:
    rng = np.random.default_rng(1)
    samples = rng.normal(0, 0.002, int(length * rate)).astype(np.float32)  # a quiet room
    i = int(seconds * rate)
    piece = tone(300, 0.6, amplitude=0.4, rate=rate)[: samples.size - i]
    samples[i : i + piece.size] += piece
    return samples


def test_effects_snap_to_the_nearest_sharp_rise():
    from stream2clip.soundtrack import onset_near

    assert onset_near(burst_at(3.2), 16000, 4.0) == pytest.approx(3.2, abs=0.04)  # the shout began before chat reacted
    assert onset_near(burst_at(4.6), 16000, 4.0) == pytest.approx(4.6, abs=0.04)
    assert onset_near(burst_at(0.5), 16000, 4.0) == 4.0  # too far before: left where chat put it
    assert onset_near(burst_at(7.0)[: 16000 * 6], 16000, 4.0) == 4.0  # nothing near
    assert onset_near(np.zeros(100, dtype=np.float32), 16000, 0.5) == 0.5


@needs_ffmpeg
def test_peak_effect_lands_on_the_shout(tmp_path):
    from stream2clip.pipeline import make_clips

    video = tmp_path / "shout.mp4"
    subprocess.run(  # quiet until a loud tone starts at 1.3 s; chat's peak says 2.0 s
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=10:d=4",
         "-f", "lavfi", "-i", "aevalsrc=0.4*sin(2*PI*300*t)*gte(t\\,1.3)+0.002*sin(2*PI*50*t):s=48000:d=4", "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", str(video)],
        check=True,
    )
    h = Highlight(1, 0.0, 4.0, 2.0, 1.0)
    crowded = Soundtrack(effects=(Effect(builtin_sound("pop")), Effect(builtin_sound("ding"), 1.0)))
    snapped = make_clips(video, [h], tmp_path / "a", options=ExportOptions(format="mp4", fps=10), soundtrack=crowded)
    exact = make_clips(video, [h], tmp_path / "b", options=ExportOptions(format="mp4", fps=10), soundtrack=Soundtrack(effects=(Effect(builtin_sound("pop")),), snap=False))
    assert snapped[0].sounds[0].at == pytest.approx(1.3, abs=0.1) and exact[0].sounds[0].at == 2.0
    assert [s.sound.name for s in snapped[0].sounds] == ["pop"] and snapped[0].skipped_sounds == ["ding: within 3 s of another effect"]
    index = json.loads((tmp_path / "a" / "clips.json").read_text(encoding="utf-8"))
    assert index["clips"][0]["sounds_skipped"] == ["ding: within 3 s of another effect"]


# --------------------------------------------------------------------------- Openverse


OPENVERSE_ITEM = {
    "id": "2f5d351d-a1de-41d9-ba70-c73ba285c875", "title": "Lofi Jazz Organ Loop 95 BPM.wav", "foreign_landing_url": "https://freesound.org/people/holizna/sounds/629154",
    "url": "https://cdn.freesound.org/previews/629/629154_12574855-hq.mp3", "creator": "holizna", "license": "cc0", "license_version": "1.0",
    "license_url": "https://creativecommons.org/publicdomain/zero/1.0/", "provider": "freesound", "source": "freesound",
    "attribution": "\"Lofi Jazz Organ Loop 95 BPM.wav\" by holizna is marked with CC0 1.0. To view the terms, visit https://creativecommons.org/publicdomain/zero/1.0/.",
    "duration": 40421, "filetype": "mp3",
}


class FakeOpenverse:
    """Answers like the Openverse API: a page of results for a search, one item for an id."""

    def __init__(self, *items):
        self.items, self.asked = items, []

    def __call__(self, url):
        self.asked.append(url)
        if "?" in url:
            return json.dumps({"result_count": len(self.items), "results": list(self.items)}).encode()
        return json.dumps(self.items[0]).encode()


def test_openverse_search_and_facts():
    from urllib.parse import parse_qs, urlparse

    from stream2clip.openverse import audio_detail, license_key, search_audio

    by_nc = {**OPENVERSE_ITEM, "id": "00000000-0000-0000-0000-000000000001", "license": "by-nc", "license_version": "3.0", "attribution": "x"}
    fake = FakeOpenverse(OPENVERSE_ITEM, by_nc)
    found = search_audio("lofi", kind="music", limit=50, get=fake)
    query = parse_qs(urlparse(fake.asked[0]).query)
    assert query == {"q": ["lofi"], "page_size": ["20"], "license_type": ["commercial,modification"], "length": ["short,medium"]}
    assert [f.key for f in found] == ["cc0", "cc-by-nc-3.0"] and found[0].seconds == pytest.approx(40.421)
    assert found[0].facts() == {"title": "Lofi Jazz Organ Loop 95 BPM.wav", "author": "holizna", "url": OPENVERSE_ITEM["foreign_landing_url"], "license": "cc0", "credit": OPENVERSE_ITEM["attribution"]}
    search_audio("whoosh", commercial=False, kind="sound_effect", get=fake)
    assert "license_type" not in fake.asked[1] and "length=shortest" in fake.asked[1]
    assert license_key("by", "4.0") == "cc-by-4.0" and license_key("pdm", "1.0") == "pdm" and license_key("sampling+", "1.0") == "" and license_key("by", "2.5") == ""
    assert audio_detail(OPENVERSE_ITEM["id"].upper(), get=fake).title.startswith("Lofi")
    with pytest.raises(ValueError):
        audio_detail("../../etc", get=fake)
    with pytest.raises(ValueError):
        search_audio("  ", get=fake)


def test_sounds_command_with_openverse(tmp_path, capsys, monkeypatch):
    from stream2clip import openverse
    from stream2clip.cli import main

    monkeypatch.setattr(openverse, "_http_get", FakeOpenverse(OPENVERSE_ITEM))
    assert main(["sounds", "search", "lofi"]) == 0
    out = capsys.readouterr().out
    assert OPENVERSE_ITEM["id"] in out and "cc0" in out and "freesound.org/people/holizna" in out and "does not endorse" in out
    song = write_wav(tone(500, 0.5), tmp_path / "organ.wav")
    assert main(["sounds", "--sounds", str(tmp_path / "lib"), "add", str(song), "--openverse", OPENVERSE_ITEM["id"], "--title", "Organ"]) == 0
    sound = SoundLibrary(tmp_path / "lib").find("organ")
    assert (sound.license, sound.author, sound.title, sound.url) == ("cc0", "holizna", "Organ", OPENVERSE_ITEM["foreign_landing_url"])  # what is given wins
    assert sound.credit == OPENVERSE_ITEM["attribution"]
    monkeypatch.setattr(openverse, "_http_get", FakeOpenverse({**OPENVERSE_ITEM, "license": "sampling+"}))
    capsys.readouterr()
    assert main(["sounds", "--sounds", str(tmp_path / "lib"), "add", str(song), "--name", "other", "--openverse", OPENVERSE_ITEM["id"]]) != 0
    assert "give --license" in capsys.readouterr().err and SoundLibrary(tmp_path / "lib").find("other") is None
