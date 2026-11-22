from __future__ import annotations

import random

import numpy as np
import pytest

from stream2clip.chat import ChatMessage
from stream2clip.highlights import (
    HighlightConfig,
    classify_reactions,
    detect_highlights,
    is_routine,
    load_highlights,
    render_timeline,
    robust_z,
)
from stream2clip.sources import HeatmapPoint


def stream(events, duration=3600, seed=0, base_rate=0.5):
    rng = random.Random(seed)
    msgs, t = [], 0.0
    while t < duration:
        t += rng.expovariate(base_rate)
        msgs.append(ChatMessage(t, rng.choice(["ok", "なるほど", "그렇구나", "そうだね"]), f"u{rng.randrange(200)}"))
    for at, word, n in events:
        for _ in range(n):
            msgs.append(ChatMessage(at + 6 + rng.random() * 20, word, f"r{rng.randrange(5000)}"))
    return sorted(msgs, key=lambda m: m.time)


@pytest.mark.parametrize("text, cats", [
    ("草", {"laugh"}), ("wwwww", {"laugh"}), ("ㅋㅋㅋㅋ", {"laugh"}), ("KEKW", {"laugh"}), ("888888", {"hype"}),
    ("ㄷㄷㄷ", {"hype"}), ("かわいい", {"cute"}), ("???", {"shock"}), ("hello", set()),
])
def test_classify(text, cats):
    assert classify_reactions(text) == cats


# Vocabulary added after reading a real 85-minute archive (44k messages): with only the
# patterns above 11% of the messages counted as reactions, although the chat was reacting
# all the time with a single trailing w, "え？", "！？", claps and channel emotes.
@pytest.mark.parametrize("text, cats", [
    ("えｗ", {"laugh"}), ("そうねw", {"laugh"}), ("w", {"laugh"}), ("ｗ", {"laugh"}),
    ("wow", set()), ("now", set()), ("brb in a few", set()),  # English words ending in w are not laughs
    ("え", {"shock"}), ("え？", {"shock"}), ("えっ", {"shock"}), ("あっ", {"shock"}), ("ん？", {"shock"}), ("お？", {"shock"}),
    ("えらい", set()), ("あした", set()),  # only when the interjection is the whole message
    ("！？", {"shock"}), ("え！？", {"shock"}), ("こわ", {"shock"}), ("こっわ", {"shock"}), ("うわ", {"shock"}),
    ("👏👏👏", {"hype"}), ("ポエム助かる", {"hype"}), ("こんぺこ～", set()), ("気のせいだよ", set()),
])
def test_classify_real_chat_vocabulary(text, cats):
    assert classify_reactions(text) == cats


def test_classify_uses_custom_emoji():
    assert classify_reactions("", (":_kusa:",)) == {"laugh"}
    assert classify_reactions(":_きゃー:", (":_きゃー:",)) == {"cute"}
    # the emote goes on its own line, so "the message ends with w" still sees the text
    assert classify_reactions("たしかにw", (":_ぺこ:",)) == {"laugh"}
    assert classify_reactions("え？", (":_はてな:",)) == {"shock"}


@pytest.mark.parametrize("text, routine", [
    ("こんぺこ～", True), ("こんばんは", True), ("こんるし！", True), ("おつぺこでした～", True), ("お疲れ様でした", True), ("乙", True),
    ("konpeko~", True), ("hello", True), ("hi!", True), ("bye bye", True), ("안녕하세요", True), ("수고하셨습니다", True),
    ("こんなの初めて", False), ("こんど見る", False), ("乙女ゲーム", False), ("history", False), ("草", False), ("え？", False),
])
def test_greetings_and_goodbyes(text, routine):
    assert is_routine(text) is routine


def test_sign_off_is_not_a_highlight():
    # On a real archive the goodbye flood at the end ("おつぺこ～" x 200) ranked 8th of 10.
    events = [(1200, "草", 150)]
    msgs = stream(events, duration=3600)
    rng = random.Random(1)
    msgs += [ChatMessage(3560 + rng.random() * 30, rng.choice(["おつぺこ～", "おつかれさま", "bye", "수고하셨습니다"]), f"g{i}") for i in range(300)]
    msgs += [ChatMessage(5 + rng.random() * 30, rng.choice(["こんぺこ～", "こんばんは", "hello"]), f"h{i}") for i in range(300)]
    found = detect_highlights(msgs, duration=3600).highlights
    assert [round(h.peak / 100) for h in found] == [12]
    # Opting out brings the two floods back.
    loud = detect_highlights(msgs, duration=3600, config=HighlightConfig(skip_greetings=False)).highlights
    assert len(loud) == 3
    # Super Chats sent together with a goodbye still count as paid events.
    paid = msgs + [ChatMessage(2400 + i, "おつぺこ", f"p{i}", kind="paid", amount=500) for i in range(12)]
    assert any(h.stats.get("paid") for h in detect_highlights(paid, duration=3600).highlights)


def test_robust_z_handles_sparse_and_flat():
    assert robust_z(np.zeros(10)).max() == 0
    z = robust_z(np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 5.0]))
    assert z[-1] > 2 and z[0] == 0


def test_finds_planted_moments_with_delay_correction():
    events = [(600, "草", 120), (1500, "ㅋㅋㅋ", 120), (2700, "888888", 120)]
    res = detect_highlights(stream(events), duration=3600)
    top = sorted(res.highlights[:3], key=lambda h: h.start)
    assert len(res.highlights) >= 3
    for h, (at, _, _) in zip(top, events):
        assert h.start <= at <= h.end  # the moment itself (before chat reacted) is inside
        assert h.end - h.start <= 90
        assert any("채팅 급증" in r for r in h.reasons) and any("반응" in r for r in h.reasons)
    assert [h.rank for h in res.highlights] == list(range(1, len(res.highlights) + 1))


def test_quiet_stream_has_no_highlights():
    res = detect_highlights(stream([], seed=2), duration=1800, config=HighlightConfig(threshold=4.0))
    assert res.highlights == []


def test_nearby_peaks_merge_and_respect_max_length():
    cfg = HighlightConfig(max_length=60, merge_gap=20)
    res = detect_highlights(stream([(1000, "草", 100), (1030, "草", 100)], seed=4), duration=2400, config=cfg)
    first = res.highlights[0]
    assert first.end - first.start <= 60
    assert sum(1 for h in res.highlights if 950 < h.peak < 1070) == 1


def test_audio_and_heatmap_only():
    audio = np.full(360, -40.0)
    audio[200:204] = -10
    heat = [HeatmapPoint(i * 10.0, (i + 1) * 10.0, 1.0 if 99 <= i <= 102 else 0.1) for i in range(180)]
    res = detect_highlights(audio=audio, audio_window=5.0, heatmap=heat, config=HighlightConfig(chat_delay=0))
    h = res.highlights[0]
    assert h.start <= 1000 <= h.end
    assert any("음량" in r for r in h.reasons) and any("많이 다시 본" in r for r in h.reasons)


def test_reaction_counts_per_category_are_in_the_stats():
    found = detect_highlights(stream([(600, "草", 120), (2000, "え？", 90)]), duration=3600).highlights
    by_time = sorted(found, key=lambda h: h.start)
    assert by_time[0].stats["react_laugh"] >= 100 and by_time[0].stats["react_shock"] == 0
    assert by_time[1].stats["react_shock"] >= 70 and by_time[1].stats["react_laugh"] == 0


def test_paid_signal_reported():
    msgs = stream([(900, "ナイス", 80)], seed=5) + [ChatMessage(910, "ナイス", "sc", kind="paid", amount=1000, currency="¥")]
    res = detect_highlights(sorted(msgs, key=lambda m: m.time), duration=1800)
    assert any("슈퍼챗" in r for r in res.highlights[0].reasons)


def test_requires_some_input():
    with pytest.raises(ValueError):
        detect_highlights([])


def test_json_roundtrip_and_timeline(tmp_path):
    res = detect_highlights(stream([(300, "草", 100)]), duration=900)
    path = res.save(tmp_path / "h.json")
    loaded = load_highlights(path)
    assert [(h.rank, round(h.start, 2)) for h in loaded] == [(h.rank, round(h.start, 2)) for h in res.highlights]
    img = render_timeline(res, tmp_path / "t.png", width=800, height=240)
    assert img.size == (800, 240) and (tmp_path / "t.png").exists()


# --------------------------------------------------------------------------- clocks and the chat delay


def test_sound_and_most_replayed_land_where_they_happen():
    from stream2clip.highlights import HighlightConfig, detect_highlights

    rng = np.random.default_rng(1)
    levels = -30.0 + rng.normal(0, 0.5, 1200)  # one second per value
    levels[600:615] = -5.0  # shouting from 10:00 to 10:15 on the video's clock
    result = detect_highlights(audio=levels, audio_window=1.0, duration=1200.0, config=HighlightConfig(top=1))
    assert abs(result.highlights[0].peak - 607.5) <= 5.0  # not 8 s early, as when sound was read on the chat's clock

    heat = [HeatmapPoint(i * 12.0, (i + 1) * 12.0, 1.0 if i == 50 else 0.1) for i in range(100)]
    result = detect_highlights(heatmap=heat, duration=1200.0, config=HighlightConfig(top=1))
    assert abs(result.highlights[0].peak - 606.0) <= 7.0


def test_chat_and_sound_meet_on_the_chat_clock():
    from stream2clip.highlights import HighlightConfig, detect_highlights

    rng = random.Random(4)
    messages = [ChatMessage(t + rng.random(), "なるほど", f"u{rng.randrange(80)}") for t in range(0, 1200, 3)]
    messages += [ChatMessage(608.0 + rng.random() * 6, "草", f"r{i}") for i in range(120)]  # 8 s after the moment
    levels = -30.0 + np.random.default_rng(2).normal(0, 0.5, 1200)
    levels[600:605] = -5.0
    cfg = HighlightConfig(window=1.0, smooth=1, top=1)
    both = detect_highlights(sorted(messages, key=lambda m: m.time), audio=levels, audio_window=1.0, duration=1200.0, config=cfg)
    # The shout and the laughter it drew 8 s later share seconds of the chat's clock (read on the video's
    # clock, the shout sat 8 s before the laughter and they shared none).
    loud = set(np.flatnonzero(both.signals["audio"] > 5).tolist())
    laughing = set(np.flatnonzero(both.signals["reactions"] > 5).tolist())
    assert loud & laughing and min(loud) == 608
    assert abs(both.highlights[0].peak - 602.5) <= 5.0 and "음량" in " ".join(both.highlights[0].reasons)


def test_estimate_chat_delay_from_the_sound():
    from stream2clip.highlights import estimate_chat_delay

    rng = np.random.default_rng(7)
    n = 3600
    levels = -30.0 + rng.normal(0, 1.0, n)
    loud = rng.choice(np.arange(60, n - 60), 40, replace=False)
    for at in loud:
        levels[at:at + 4] = -8.0
    messages = [ChatMessage(float(t), "a", "u") for t in rng.uniform(0, n, 4000)]
    for at in loud:  # viewers answer 6 s later
        messages += [ChatMessage(float(at + 6 + rng.uniform(0, 3)), "草", f"r{i}") for i in range(30)]
    delay, agreement = estimate_chat_delay(messages, levels)
    assert abs(delay - 5.5) <= 1.5 and agreement > 0.2  # from the middle of the sound (+2 s) to the middle of the chat (+7.5 s)

    unrelated = [ChatMessage(float(t), "a", "u") for t in rng.uniform(0, n, 6000)]
    assert estimate_chat_delay(unrelated, levels) is None  # no lag stands out: the set delay stays
    assert estimate_chat_delay(messages, levels[:60]) is None  # too short to tell


def test_find_highlights_estimates_the_delay_when_asked(tmp_path, monkeypatch):
    from stream2clip import audio, pipeline
    from stream2clip.highlights import HighlightConfig

    rng = np.random.default_rng(3)
    fine = -30.0 + rng.normal(0, 1.0, 1800)
    loud = rng.choice(np.arange(60, 1740), 25, replace=False)
    for at in loud:
        fine[at:at + 4] = -8.0
    messages = [ChatMessage(float(t), "a", f"u{i}") for i, t in enumerate(rng.uniform(0, 1800, 2000))]
    for at in loud:
        messages += [ChatMessage(float(at + 5 + rng.uniform(0, 2)), "草", f"r{i}") for i in range(30)]
    monkeypatch.setattr(audio, "audio_levels", lambda path, window=10.0, track=None: fine if window == 1.0 else fine[: len(fine) // 5 * 5].reshape(-1, 5).mean(axis=1))
    monkeypatch.setattr(pipeline, "probe", lambda path: type("Info", (), {"duration": 1800.0})())
    result = pipeline.find_highlights(tmp_path / "vod.mp4", messages=sorted(messages, key=lambda m: m.time), audio=True, config=HighlightConfig(estimate_delay=True))
    assert result.estimated_delay is not None and abs(result.estimated_delay[0] - 4.0) <= 1.5  # middle of the sound to middle of the chat
    plain = pipeline.find_highlights(tmp_path / "vod.mp4", messages=sorted(messages, key=lambda m: m.time), audio=True, config=HighlightConfig())
    assert plain.estimated_delay is None  # only when asked


def test_cli_delay_auto_needs_the_video_and_the_chat(tmp_path, capsys):
    from stream2clip.cli import main

    chat = tmp_path / "chat.csv"
    chat.write_text("time,author,text\n1.0,a,hi\n", encoding="utf-8")
    assert main(["highlights", "--chat", str(chat), "--delay", "auto"]) == 1
    assert "--delay auto" in capsys.readouterr().err
