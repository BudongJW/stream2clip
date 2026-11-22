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
    track = Soundtrack(effects=(Effect(boom, "peak"), Effect(whoosh, "peak"), Effect(boom, "start"), Effect(boom, "end"), Effect(boom, 30.0)))
    plan = plan_mix(track, 0, length=10.0, voice_level=-20.0, peak=4.0, levels=fixed_levels(-10.0, 1.1))
    assert [round(p.at, 2) for p in plan.sounds] == [4.0, 3.7, 0.0, 8.9]  # the whoosh swells into the peak; 30 s is past the end
    assert plan.sounds[0].gain == -13.0  # 3 dB under the clip's -20 dB
    auto = plan_mix(Soundtrack(effects=(Effect(builtin_sound("auto")),)), 0, length=10.0, voice_level=-20.0, peak=2.0, reactions={"react_shock": 5}, levels=fixed_levels())
    assert auto.sounds[0].sound.name == "boom"
    with pytest.raises(ValueError):
        Effect(boom, "middle")


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
    track = Soundtrack(effects=(Effect(builtin_sound("ding")),))
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
                                      "--sfx", "auto", "--sfx", "whoosh@start", "--sounds", str(tmp_path / "lib")])
    track = _soundtrack(args)
    assert track.music[0].path == song and track.under == 15.0 and not track.duck
    assert [(e.sound.name, e.when) for e in track.effects] == [("auto", "peak"), ("whoosh", "start")]
    assert _soundtrack(build_parser().parse_args(["clips", "v.mp4", "--highlights", "h.json", "-o", str(tmp_path)])) is None
