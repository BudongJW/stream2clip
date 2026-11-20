"""Build the demo stream the README pictures are made with: a quarter of an hour of the mascot playing a brick game "live".

Everything in it is the project's own. The game is drawn here and plays itself; the avatar is the mascot's emotes used the way a
PNG avatar is (mouth by the loudness of the voice, expressions by what happens in the game); the voice is the system's speech
synthesis (Windows; silent elsewhere or with --no-speech); the chat is made up to follow the game, with bursts after its big
moments. So the app can be shown at work on moving footage without anybody else's stream.

    python packaging/build_demo_stream.py OUT_DIR [--seconds 900] [--no-speech]

Writes stream.mp4, live_chat.csv, stream.ko.vtt (what is said) and events.json (when the big moments are).
Needs ffmpeg on PATH, numpy and Pillow.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS, RATE = 1280, 720, 30, 48000
INK, PANEL, PINK, YELLOW, BLUE, GREEN, PURPLE, WHITE = "#15131F", "#1F1B2E", "#FF4F8B", "#FFD84D", "#4D9FFF", "#4ADE80", "#B66DFF", "#F7F4FA"
ROWS = [PINK, YELLOW, BLUE, GREEN, PURPLE, WHITE]
COLS, BRICK_W, BRICK_H, GAP, LEFT, TOP = 16, 70, 24, 6, 32, 96
AVATAR = (948, 392, 300)  # x, y, size of the avatar box
BANNERS = ["연쇄 폭발!", "레전드 장면!", "스테이지 클리어!", "한 번 더!"]
OPENING = "안녕하세요, 키리입니다. 오늘은 벽돌깨기를 해 볼게요."
CLOSING = "오늘 방송은 여기까지! 봐 주셔서 감사합니다."
BEFORE = ["어, 잠깐만요. 뭔가 올 것 같은데요?", "이번엔 진짜 느낌이 좋아요.", "집중, 집중. 지금이에요!", "마지막으로 한 번만 더!"]
DURING = ["우와! 이게 뭐야! 대박이다!", "와아, 다 깨진다! 레전드!", "됐다! 스테이지 클리어!", "하하하, 또 터졌어요!"]
AFTER = ["방금 거 클립 따 주세요!", "채팅 엄청 빠르네요. 고마워요!", "이 장면은 꼭 남겨야 해요.", "오늘 운이 좋네요."]
FILLER = ["차근차근 깨 보겠습니다.", "채팅 감사합니다. 계속 가 볼게요.", "공이 생각보다 빠르네요.", "조금만 더 하면 될 것 같아요."]
CHATTER = ["ㅎㅇ", "오늘도 왔어요", "なるほど", "화이팅", "gl", "오", "집중 키리", "nice", "가즈아", "ㅋㅋ"]
CHEERS = ["ㅋㅋㅋㅋ", "와", "대박", "레전드", "草", "!!!", "미쳤다", "88888", "클립각", "wwww", "gg", "!clip"]


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("malgunbd.ttf", "NotoSansKR-Bold.otf", "NotoSansCJK-Bold.ttc", "AppleSDGothicNeo.ttc", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def moments(seconds: float) -> list[float]:
    """When the big moments are: the first after 110 seconds, then every 200, none in the last minute.

    Far apart on purpose: a chat that bursts every minute has no "usual" level to stand out from.
    """
    return [round(t, 1) for t in np.arange(110.0, seconds - 60.0, 200.0)]


def lines(seconds: float) -> list[tuple[float, str]]:
    """What the streamer says and when (seconds from the start)."""
    said = [(2.0, OPENING), (seconds - 12.0, CLOSING)]
    for i, m in enumerate(moments(seconds)):
        said += [(m - 7.0, BEFORE[i % len(BEFORE)]), (m + 0.8, DURING[i % len(DURING)]), (m + 9.0, AFTER[i % len(AFTER)]), (m + 30.0, FILLER[i % len(FILLER)])]
    said.append((15.0, FILLER[0]))
    # nothing else is being said when the goodbye begins
    return sorted((t, text) for t, text in said if text == CLOSING or 0 < t < seconds - 20)


def chat_rows(seconds: float, seed: int = 7) -> list[str]:
    """A chat log (time, author, text): steady talk, and a burst that starts a few seconds after each big moment."""
    rng = random.Random(seed)
    rows, t = [], 0.0
    while t < seconds:
        t += rng.expovariate(0.7)
        rows.append((t, f"u{rng.randrange(260)}", rng.choice(CHATTER)))
    for m in moments(seconds):
        for _ in range(rng.randrange(170, 240)):
            rows.append((m + 3 + abs(rng.gauss(0, 7.5)), f"r{rng.randrange(4000)}", rng.choice(CHEERS)))
    return ["time,author,text"] + [f"{t:.2f},{author},{text}" for t, author, text in sorted(rows) if t < seconds]


def speak(texts: list[str], folder: Path) -> dict[str, Path]:
    """Each line as a WAV file, by the system's Korean voice (Windows). An empty dict where that is not there."""
    if sys.platform != "win32":
        return {}
    files = {text: folder / f"line_{i:02d}.wav" for i, text in enumerate(dict.fromkeys(texts))}
    script = ["Add-Type -AssemblyName System.Speech", "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer", "try { $s.SelectVoiceByHints('Female', 'Adult', 0, [Globalization.CultureInfo]'ko-KR') } catch {}", "$s.Rate = 2"]
    for text, path in files.items():
        script += [f"$s.SetOutputToWaveFile('{path}')", f"$s.Speak('{text}')"]
    script += ["$s.Dispose()", "exit"]
    done = subprocess.run(["powershell", "-NoProfile", "-Command", "-"], input=("\n".join(script) + "\n").encode("cp949"), capture_output=True)  # commands on stdin: no script file
    return {text: path for text, path in files.items() if path.is_file() and path.stat().st_size > 1000} if done.returncode == 0 else {}


def read_wav(path: Path) -> np.ndarray:
    """A WAV file as mono float samples at RATE."""
    with wave.open(str(path), "rb") as wav:
        raw = np.frombuffer(wav.readframes(wav.getnframes()), dtype=np.int16 if wav.getsampwidth() == 2 else np.uint8).astype(np.float32)
        raw = (raw / 32768.0) if wav.getsampwidth() == 2 else (raw - 128.0) / 128.0
        if wav.getnchannels() > 1:
            raw = raw.reshape(-1, wav.getnchannels()).mean(axis=1)
        rate = wav.getframerate()
    return np.interp(np.arange(0, len(raw), rate / RATE), np.arange(len(raw)), raw).astype(np.float32)


def blip(freq: float, length: float, volume: float) -> np.ndarray:
    t = np.arange(int(RATE * length)) / RATE
    return (np.sin(2 * np.pi * freq * t) * np.exp(-t * 18) * volume).astype(np.float32)


class Game:
    """A brick game that plays itself. step() moves it one frame on and returns the sounds of that frame."""

    def __init__(self, seed: int = 7) -> None:
        self.rng = random.Random(seed)
        self.stage, self.score, self.paddle = 1, 0, W / 2
        self.bricks: set[tuple[int, int]] = set()
        self.balls: list[list[float]] = []
        self.sparks: list[list[float]] = []
        self.wild = False  # a big moment: many balls, and none is lost
        self.fill()
        self.serve(2)

    def fill(self) -> None:
        self.bricks = {(c, r) for c in range(COLS) for r in range(len(ROWS))}

    def serve(self, count: int = 1, speed: float = 540.0) -> None:
        for _ in range(count):
            angle = math.radians(self.rng.uniform(-60, 60))
            self.balls.append([self.paddle, 640.0, speed * math.sin(angle), -speed * math.cos(angle)])

    def frenzy(self) -> None:
        self.wild = True
        self.serve(10, 680.0)

    def calm(self) -> None:
        self.wild = False
        self.balls = self.balls[:2]

    def step(self, dt: float) -> list[str]:
        sounds = []
        target = min((b for b in self.balls if b[3] > 0), key=lambda b: -b[1], default=self.balls[0] if self.balls else [W / 2])[0]
        self.paddle += max(-780 * dt, min(780 * dt, target - self.paddle))
        self.paddle = max(80.0, min(W - 80.0, self.paddle))
        for ball in self.balls:
            for _ in range(2):
                ball[0] += ball[2] * dt / 2
                ball[1] += ball[3] * dt / 2
                if ball[0] < 8 or ball[0] > W - 8:
                    ball[2] = -ball[2]
                    ball[0] = max(8.0, min(W - 8.0, ball[0]))
                if ball[1] < 62:
                    ball[3] = abs(ball[3])
                if self.wild and ball[1] > H - 12:
                    ball[3] = -abs(ball[3])
                if 650 <= ball[1] <= 668 and ball[3] > 0 and abs(ball[0] - self.paddle) < 84:
                    speed = math.hypot(ball[2], ball[3])
                    angle = math.radians(62 * (ball[0] - self.paddle) / 84)
                    ball[2], ball[3] = speed * math.sin(angle), -speed * math.cos(angle)
                    sounds.append("paddle")
                col, row = int((ball[0] - LEFT) // (BRICK_W + GAP)), int((ball[1] - TOP) // (BRICK_H + GAP))
                if (col, row) in self.bricks:
                    self.bricks.discard((col, row))
                    ball[3] = -ball[3]
                    self.score += 10 * self.stage
                    sounds.append("brick")
                    x, y = LEFT + col * (BRICK_W + GAP) + BRICK_W / 2, TOP + row * (BRICK_H + GAP) + BRICK_H / 2
                    self.sparks += [[x, y, self.rng.uniform(-160, 160), self.rng.uniform(-200, 40), 0.5, row] for _ in range(3)]
        self.balls = [b for b in self.balls if b[1] < H + 20]
        if len(self.balls) < 2:
            self.serve()
        if len(self.bricks) < 10:
            self.stage += 1
            self.fill()
            sounds.append("stage")
        for spark in self.sparks:
            spark[0] += spark[2] * dt
            spark[1] += spark[3] * dt
            spark[3] += 600 * dt
            spark[4] -= dt
        self.sparks = [s for s in self.sparks if s[4] > 0][-160:]
        return sounds


def build(out: Path, seconds: float = 900.0, *, speech: bool = True, seed: int = 7) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    big = moments(seconds)
    said = lines(seconds)
    voices = speak([text for _, text in said], out) if speech else {}

    # ---- sound: the voice first (the mouth follows it), game sounds are added while the frames are drawn
    total = int(seconds * RATE)
    voice, sfx = np.zeros(total, dtype=np.float32), np.zeros(total, dtype=np.float32)
    cues = []
    for at, text in said:
        if text in voices:
            samples = read_wav(voices[text])[: total - int(at * RATE)]
            voice[int(at * RATE): int(at * RATE) + len(samples)] += samples * 0.9
            cues.append((at, at + len(samples) / RATE, text))
        else:
            cues.append((at, at + 1.2 + len(text) * 0.11, text))
    window = RATE // FPS
    loud = np.sqrt((voice[: (total // window) * window].reshape(-1, window) ** 2).mean(axis=1))
    sounds = {"brick": blip(880, 0.07, 0.10), "paddle": blip(330, 0.09, 0.12), "stage": np.concatenate([blip(f, 0.12, 0.2) for f in (523, 659, 784, 1047)]),
              "frenzy": np.concatenate([blip(f, 0.09, 0.22) for f in (392, 494, 587, 784, 988)])}

    # ---- pictures that do not change
    back = Image.new("RGB", (W, H), INK)
    draw = ImageDraw.Draw(back)
    for y in range(0, H, 40):
        draw.line([(0, y), (W, y)], fill="#1A1727")
    draw.rectangle([0, 0, W, 54], fill=PANEL)
    draw.rounded_rectangle([18, 12, 96, 42], radius=15, fill=PINK)
    draw.text((57, 27), "LIVE", font=font(18), fill=WHITE, anchor="mm")
    draw.text((112, 27), "키리의 벽돌깨기 방송", font=font(22), fill=WHITE, anchor="lm")
    ax, ay, size = AVATAR
    draw.rounded_rectangle([ax - 8, ay - 8, ax + size + 8, ay + size + 8], radius=22, fill=PANEL, outline=PINK, width=4)
    emotes = {name: Image.open(ROOT / "assets" / "brand" / "mascot" / f"kiri_{name}_512.png").convert("RGBA").resize((size, size), Image.Resampling.LANCZOS)
              for name in ("focus", "wink", "surprised", "laugh", "cut", "turn_left")}
    hud, banner = font(24), font(92)

    encoder = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
                                "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", str(out / "video_only.mp4")], stdin=subprocess.PIPE)
    game = Game(seed)
    frames = int(seconds * FPS)
    for index in range(frames):
        t = index / FPS
        near = next((m for m in big if m <= t < m + 12), None)
        if near is not None and abs(t - near) < 0.5 / FPS:
            game.frenzy()
            sfx[int(t * RATE): int(t * RATE) + len(sounds["frenzy"])] += sounds["frenzy"][: total - int(t * RATE)]
        if any(abs(t - (m + 11)) < 0.5 / FPS for m in big):
            game.calm()
        for kind in game.step(1 / FPS)[:4]:
            start = int(t * RATE)
            sfx[start: start + len(sounds[kind])] += sounds[kind][: total - start]

        frame = back.copy()
        draw = ImageDraw.Draw(frame)
        for col, row in game.bricks:
            x, y = LEFT + col * (BRICK_W + GAP), TOP + row * (BRICK_H + GAP)
            draw.rounded_rectangle([x, y, x + BRICK_W, y + BRICK_H], radius=5, fill=ROWS[row])
        for x, y, _vx, _vy, life, row in game.sparks:
            r = 2 + 6 * life
            draw.rectangle([x - r, y - r, x + r, y + r], fill=ROWS[int(row)])
        draw.rounded_rectangle([game.paddle - 80, 660, game.paddle + 80, 676], radius=8, fill=WHITE)
        for ball in game.balls:
            draw.ellipse([ball[0] - 9, ball[1] - 9, ball[0] + 9, ball[1] + 9], fill=YELLOW)
        draw.text((W - 24, 27), f"STAGE {game.stage}   SCORE {game.score:06d}", font=hud, fill=YELLOW, anchor="rm")
        if near is not None and t - near < 5:
            text = BANNERS[big.index(near) % len(BANNERS)]
            lift = int(18 * math.sin((t - near) * 9))
            draw.text((W // 2 - 150, 330 + lift), text, font=banner, fill=INK, anchor="mm", stroke_width=12, stroke_fill=INK)
            draw.text((W // 2 - 150, 330 + lift), text, font=banner, fill=YELLOW, anchor="mm", stroke_width=4, stroke_fill=PINK)
        # the avatar, as a PNG avatar works: expression by what happens, mouth by the loudness of the voice
        if near is not None:
            name = "surprised" if t - near < 2 else ("laugh" if t - near < 9 else "cut")
        elif index < len(loud) and loud[index] > 0.035:
            name = "wink" if (index // 3) % 2 == 0 else "focus"
        elif t % 17 > 15.6:
            name = "turn_left"
        else:
            name = "focus"
        bob = int(5 * math.sin(t * 2.4) + (9 * abs(math.sin(t * 11)) if near is not None and t - near < 9 else 0))
        frame.paste(emotes[name], (ax, ay + 4 - bob), emotes[name])
        encoder.stdin.write(frame.tobytes())
    encoder.stdin.close()
    encoder.wait()

    mix = np.clip(voice + sfx, -1.0, 1.0)
    with wave.open(str(out / "sound.wav"), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(RATE)
        wav.writeframes((mix * 32767).astype(np.int16).tobytes())
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(out / "video_only.mp4"), "-i", str(out / "sound.wav"), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-shortest", str(out / "stream.mp4")], check=True)
    for path in [out / "video_only.mp4", out / "sound.wav", *voices.values()]:
        path.unlink(missing_ok=True)

    (out / "live_chat.csv").write_text("\n".join(chat_rows(seconds, seed)), encoding="utf-8")

    def clock(value: float) -> str:
        return f"{int(value // 3600):02d}:{int(value % 3600 // 60):02d}:{value % 60:06.3f}"

    (out / "stream.ko.vtt").write_text("WEBVTT\n\n" + "\n\n".join(f"{clock(a)} --> {clock(b)}\n{text}" for a, b, text in cues) + "\n", encoding="utf-8")
    facts = {"seconds": seconds, "moments": big, "lines": len(cues), "spoken": bool(voices), "stages": game.stage, "score": game.score}
    (out / "events.json").write_text(json.dumps(facts, ensure_ascii=False, indent=1), encoding="utf-8")
    return facts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("out", type=Path)
    parser.add_argument("--seconds", type=float, default=900.0)
    parser.add_argument("--no-speech", action="store_true")
    args = parser.parse_args(argv)
    print(json.dumps(build(args.out, args.seconds, speech=not args.no_speech), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
