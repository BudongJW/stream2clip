from __future__ import annotations

import random

import numpy as np
import pytest

from stream2clip.chat import ChatMessage
from stream2clip.highlights import (
    HighlightConfig,
    classify_reactions,
    detect_highlights,
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
        msgs.append(ChatMessage(t, rng.choice(["hello", "こんばんは", "안녕하세요", "おつ"]), f"u{rng.randrange(200)}"))
    for at, word, n in events:
        for _ in range(n):
            msgs.append(ChatMessage(at + 6 + rng.random() * 20, word, f"r{rng.randrange(5000)}"))
    return sorted(msgs, key=lambda m: m.time)


@pytest.mark.parametrize("text, cats", [
    ("草", {"laugh"}), ("wwwww", {"laugh"}), ("ㅋㅋㅋㅋ", {"laugh"}), ("KEKW", {"laugh"}), ("888888", {"hype"}),
    ("ㄷㄷㄷ", {"hype"}), ("かわいい", {"cute"}), ("???", {"shock"}), ("hello", set()), ("w", set()),
])
def test_classify(text, cats):
    assert classify_reactions(text) == cats


def test_classify_uses_custom_emoji():
    assert classify_reactions("", (":_kusa:",)) == {"laugh"}


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
