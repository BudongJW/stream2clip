"""Scoring highlights against the timestamps viewers leave in the comments."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from stream2clip.cli import main
from stream2clip.evaluation import (
    Label,
    Score,
    combine_scores,
    comment_timestamps,
    evaluate_streams,
    labels_from_comments,
    load_stream,
    parse_sweep,
    score_highlights,
)
from stream2clip.highlights import HighlightConfig
from stream2clip.sources import build_info_command


def span(start, end):
    return SimpleNamespace(start=float(start), end=float(end))


def test_timestamps_in_a_comment():
    assert comment_timestamps("12:34 草 / 1:02:03 ここ好き / 0:05 start") == [754.0, 3723.0, 5.0]
    assert comment_timestamps("no time here, score 3:2:1:0 and 12:345") == []  # runs of numbers are not times
    assert comment_timestamps("at 5:75 and 1:70:00") == []  # not valid clock values
    assert comment_timestamps("99:59 is fine as minutes, 2:00:00 too") == [5999.0, 7200.0]
    assert comment_timestamps("1:00 2:00:00", duration=3600) == [60.0]  # beyond the end of the stream
    assert comment_timestamps("ver 1.2:30 released") == []  # a version number, not a time


def test_labels_group_nearby_timestamps_and_count_comments():
    comments = [
        {"text": "24:09 falls off the cliff\n50:02 the scream"},
        "24:11 lol and again 24:12",  # the same viewer twice: one vote
        {"text": "24:20 best part"},
        {"text": None},
        "nothing",
    ]
    labels = labels_from_comments(comments)
    assert [(label.time, label.votes) for label in labels] == [(1452.0, 3), (3002.0, 1)]  # the middle of 1449, 1451, 1452, 1460
    assert labels_from_comments(comments, min_votes=2) == [Label(1452.0, 3)]
    assert labels_from_comments(comments, gap=5)[0].votes == 2  # 24:20 is now a moment of its own
    assert labels_from_comments([]) == []


def test_score_counts_hits_and_compares_with_chance():
    labels = [Label(100.0), Label(500.0), Label(900.0)]
    highlights = [span(90, 120), span(300, 330), span(880, 895)]  # the third ends 5 s before its label: inside the tolerance
    score = score_highlights(highlights, labels, 1000.0, tolerance=10)
    assert (score.highlights, score.labels, score.hits, score.found) == (3, 3, 2, 2)
    assert score.precision == pytest.approx(2 / 3) and score.recall == pytest.approx(2 / 3)
    # A 30 s span hits one of three labels from 50 s of start positions each: 150 of 970.
    assert score_highlights([span(0, 30)], labels, 1000.0, tolerance=10).chance == pytest.approx(150 / 970)
    assert score.chance == pytest.approx((150 / 970 + 150 / 970 + 105 / 985) / 3)
    assert score.lift == pytest.approx(score.precision / score.chance) and score.lift > 4

    everything = score_highlights([span(0, 1000)], labels, 1000.0)
    assert everything.precision == 1.0 and everything.chance == 1.0 and everything.lift == 1.0  # selecting the whole stream proves nothing
    empty = score_highlights([], labels, 1000.0)
    assert (empty.precision, empty.recall, empty.chance, empty.lift) == (0.0, 0.0, 0.0, 0.0)
    assert score_highlights(highlights, [], 1000.0).lift == 0.0


def test_scores_are_pooled_by_counts():
    pooled = combine_scores([Score(10, 20, 6, 8, 0.4), Score(2, 5, 2, 1, 0.1)])
    assert (pooled.highlights, pooled.labels, pooled.hits, pooled.found) == (12, 25, 8, 9)
    assert pooled.chance == pytest.approx((0.4 * 10 + 0.1 * 2) / 12) and pooled.precision == pytest.approx(8 / 12)
    assert combine_scores([]).lift == 0.0


def test_sweep_parsing():
    base = HighlightConfig()
    settings = parse_sweep("threshold=1.5, 2,2.5", base)
    assert [name for name, _ in settings] == ["threshold=1.5", "threshold=2.0", "threshold=2.5"] and settings[0][1].threshold == 1.5
    assert parse_sweep("delay=4", base)[0][1].chat_delay == 4.0  # the command-line name
    assert parse_sweep("top=3", base)[0][1].top == 3 and isinstance(parse_sweep("top=3", base)[0][1].top, int)
    for bad in ("nonsense=1", "threshold", "skip_greetings=1", "weights=2"):
        with pytest.raises(ValueError, match="Cannot sweep"):
            parse_sweep(bad, base)


def make_stream(folder, moments=(900, 2400), comments=("15:10 草", "15:12 ここ", "40:05 かわいい"), duration=3600):
    folder.mkdir(parents=True)
    rows = ["time,author,text"] + [f"{t},u{t % 40},なるほど" for t in range(0, duration, 3)]
    for at in moments:
        rows += [f"{at + 6 + i * 0.05:.2f},r{i},草" for i in range(160)]
    (folder / "chat.csv").write_text("\n".join(rows), encoding="utf-8")
    (folder / "info.json").write_text(json.dumps({"id": folder.name, "duration": duration, "comments": [{"text": c} for c in comments]}), encoding="utf-8")
    return folder


def test_evaluate_a_folder_of_streams(tmp_path, capsys):
    good = make_stream(tmp_path / "good")
    stream = load_stream(good)
    assert (stream.name, stream.duration, len(stream.messages)) == ("good", 3600.0, 1200 + 320)
    assert [(label.time, label.votes) for label in stream.labels] == [(912.0, 2), (2405.0, 1)]
    rows, pooled = evaluate_streams([stream])
    assert rows[0][0] == "good" and pooled.highlights == 2 and pooled.hits == 2 and pooled.found == 2 and pooled.lift > 5

    make_stream(tmp_path / "unmarked", comments=("great stream",))
    out = tmp_path / "result.json"
    assert main(["evaluate", str(good), str(tmp_path / "unmarked"), "--sweep", "threshold=2,50", "-o", str(out)]) == 0
    printed = capsys.readouterr()
    assert "skip   unmarked" in printed.err and "[defaults]" in printed.out and "[threshold=50.0]" in printed.out and "all 1 streams" in printed.out
    data = json.loads(out.read_text(encoding="utf-8"))
    assert [r["setting"] for r in data["results"]] == ["defaults", "threshold=2.0", "threshold=50.0"]
    assert data["results"][0]["pooled"]["precision"] == 1.0 and data["results"][2]["pooled"]["highlights"] == 0  # nothing passes a threshold of 50

    assert main(["evaluate", str(tmp_path / "unmarked")]) == 1 and "No stream with viewer timestamps" in capsys.readouterr().err
    (tmp_path / "empty").mkdir()
    assert main(["evaluate", str(tmp_path / "empty")]) == 1 and "no chat replay" in capsys.readouterr().err
    assert main(["evaluate", str(tmp_path / "empty"), str(good)]) == 0  # an incomplete folder does not stop the others
    printed = capsys.readouterr()
    assert "skip" in printed.err and "no chat replay" in printed.err and "all 1 streams" in printed.out


def test_info_command_can_ask_for_comments():
    assert "--write-comments" not in build_info_command("URL", ytdlp=["yt-dlp"])
    cmd = build_info_command("URL", ytdlp=["yt-dlp"], comments=150)
    assert cmd[cmd.index("--extractor-args") + 1] == "youtube:max_comments=150,all,0,0;comment_sort=top" and cmd[-1] == "URL" and "--write-comments" in cmd
