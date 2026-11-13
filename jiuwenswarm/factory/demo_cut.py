"""Cut a raw factory tmux recording (script typescript + timing) into a compressed video.

The raw recording is never modified. Waits longer than an automatically chosen cap are shortened
and labelled on screen ("⏩ 6 min 12 s compressed"), and a footer always shows the real elapsed run
time, so the compression is transparent. Optional still cards (PNG) go before/after the terminal.

    python -m jiuwenswarm.factory.demo_cut --typescript S.typescript --timing S.timing \
        --out demo.mp4 --ffmpeg /path/ffmpeg [--target 330] [--card intro.png:12 ...] \
        [--caption 0:Task given to the agent ...]

Needs pyte and Pillow (presentation tooling only; not a factory dependency).
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path

import pyte
from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (21, 23, 28)
FG = (220, 222, 226)
PALETTE = {
    'black': (138, 142, 150), 'red': (232, 96, 88), 'green': (110, 200, 120), 'brown': (217, 138, 27),
    'yellow': (217, 138, 27), 'blue': (110, 150, 230), 'magenta': (200, 120, 200), 'cyan': (100, 190, 200),
    'white': (220, 222, 226), 'brightblack': (128, 132, 140), 'brightred': (240, 120, 110),
    'brightgreen': (130, 220, 140), 'brightyellow': (240, 170, 60), 'brightblue': (140, 170, 240),
    'brightmagenta': (220, 150, 220), 'brightcyan': (130, 210, 220), 'brightwhite': (245, 245, 245),
    'default': FG,
}
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'
FONT_BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
UI_FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'


def read_recording(typescript, timing):
    data = Path(typescript).read_bytes()
    if data.startswith(b'Script started'):
        data = data[data.index(b'\n') + 1:]
    chunks, t, pos = [], 0.0, 0
    for line in Path(timing).read_text().splitlines():
        parts = line.split()
        if len(parts) != 2:
            continue
        delay, size = float(parts[0]), int(parts[1])
        t += delay
        chunks.append((t, data[pos:pos + size]))
        pos += size
    return chunks


def snapshots(chunks, cols, rows, quantum=0.5):
    """Screen states at most every `quantum` seconds of real time (plus the final state)."""
    screen = pyte.Screen(cols, rows)
    stream = pyte.ByteStream(screen)
    out, last_t, last_key = [], -1e9, None
    for i, (t, chunk) in enumerate(chunks):
        stream.feed(chunk)
        nxt = chunks[i + 1][0] if i + 1 < len(chunks) else None
        # Capture when the burst ends (next chunk is later than quantum) or quantum elapsed.
        if nxt is None or nxt - t >= quantum or t - last_t >= quantum:
            state = tuple(tuple((c.data, c.fg, c.bold) for c in (screen.buffer[y][x] for x in range(cols)))
                          for y in range(rows))
            if state != last_key:
                out.append((t, state))
                last_key, last_t = state, t
    return out


def choose_cap(gaps, target):
    lo, hi = 0.05, max(gaps + [1.0])
    for _ in range(60):
        mid = (lo + hi) / 2
        if sum(min(g, mid) for g in gaps) > target:
            hi = mid
        else:
            lo = mid
    return lo


def fmt(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600:d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'


def human(seconds):
    seconds = int(seconds)
    return f'{seconds // 60} min {seconds % 60:02d} s' if seconds >= 60 else f'{seconds} s'


class Renderer:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        size = 18
        while True:
            font = ImageFont.truetype(FONT, size)
            cw = font.getlength('M')
            if cw * cols <= W - 40 and (size + 3) * rows <= H - 80 or size <= 8:
                break
            size -= 1
        self.font, self.bold = font, ImageFont.truetype(FONT_BOLD, size)
        self.cw, self.lh = cw, size + 3
        self.ox = int((W - cw * cols) / 2)
        self.oy = 14
        self.ui = ImageFont.truetype(UI_FONT, 26)
        self.ui_big = ImageFont.truetype(UI_FONT, 34)

    def color(self, name):
        if isinstance(name, str) and len(name) == 6:
            try:
                return tuple(int(name[i:i + 2], 16) for i in (0, 2, 4))
            except ValueError:
                pass
        return PALETTE.get(name, FG)

    def frame(self, state, footer, caption=None, banner=None):
        img = Image.new('RGB', (W, H), BG)
        draw = ImageDraw.Draw(img)
        for y, row in enumerate(state):
            x = 0
            while x < len(row):
                ch, fg, bold = row[x]
                run = [ch]
                j = x + 1
                while j < len(row) and row[j][1] == fg and row[j][2] == bold:
                    run.append(row[j][0])
                    j += 1
                text = ''.join(run)
                if text.strip():
                    draw.text((self.ox + x * self.cw, self.oy + y * self.lh), text,
                              font=self.bold if bold else self.font, fill=self.color(fg))
                x = j
        bar_y = H - 58
        draw.rectangle((0, bar_y, W, H), fill=(12, 13, 16))
        if caption:
            draw.text((28, bar_y + 13), caption, font=self.ui, fill=(245, 245, 245))
        draw.text((W - 28, bar_y + 13), footer, font=self.ui, fill=(150, 154, 162), anchor='ra')
        if banner:
            bw = draw.textlength(banner, font=self.ui_big) + 60
            x0, y0 = (W - bw) / 2, H / 2 - 40
            draw.rounded_rectangle((x0, y0, x0 + bw, y0 + 70), 14, fill=(36, 38, 46), outline=(217, 138, 27), width=2)
            draw.text((W / 2, y0 + 35), banner, font=self.ui_big, fill=(240, 170, 60), anchor='mm')
        return img


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument('--typescript', required=True)
    p.add_argument('--timing', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--ffmpeg', default=shutil.which('ffmpeg') or 'ffmpeg')
    p.add_argument('--cols', type=int, default=172)
    p.add_argument('--rows', type=int, default=48)
    p.add_argument('--target', type=float, default=330, help='seconds of terminal footage')
    p.add_argument('--min-hold', type=float, default=0.12)
    p.add_argument('--start', type=float, default=0, help='real seconds to skip at the start')
    p.add_argument('--card', action='append', default=[], help='PNG:seconds; "@end" suffix puts it after')
    p.add_argument('--caption', action='append', default=[], help='REAL_SECONDS:text (shown until the next)')
    p.add_argument('--label', default='recorded run · real terminal output')
    a = p.parse_args(argv)

    chunks = read_recording(a.typescript, a.timing)
    shots = [(t, s) for t, s in snapshots(chunks, a.cols, a.rows) if t >= a.start]
    end = chunks[-1][0]
    gaps = [(shots[i + 1][0] if i + 1 < len(shots) else end) - shots[i][0] for i in range(len(shots))]
    cap = choose_cap(gaps, a.target)
    captions = sorted((float(c.split(':', 1)[0]), c.split(':', 1)[1]) for c in a.caption)
    render = Renderer(a.cols, a.rows)
    work = Path(tempfile.mkdtemp(prefix='demo-cut-'))
    entries = []

    def add(img, seconds):
        path = work / f'{len(entries):05d}.png'
        img.save(path)
        entries.append((path, seconds))

    for spec in a.card:
        if not spec.endswith('@end'):
            path, seconds = spec.rsplit(':', 1)
            entries.append((Path(path).resolve(), float(seconds)))
    for (t, state), gap in zip(shots, gaps):
        caption = next((text for at, text in reversed(captions) if at <= t), None)
        footer = f'{a.label} · run time {fmt(t)}'
        shown = max(a.min_hold, min(gap, cap))
        if gap > cap * 3 and gap > 20:
            # Show the state briefly, then the labelled skip over the same frozen screen.
            add(render.frame(state, footer, caption), min(cap, 1.5))
            add(render.frame(state, footer, caption, f'⏩  {human(gap)} of waiting compressed'), 1.6)
        else:
            add(render.frame(state, footer, caption), shown)
    for spec in a.card:
        if spec.endswith('@end'):
            path, seconds = spec[:-4].rsplit(':', 1)
            entries.append((Path(path).resolve(), float(seconds)))
    concat = work / 'list.txt'
    with open(concat, 'w') as handle:
        for path, seconds in entries:
            handle.write(f"file '{path}'\nduration {seconds:.3f}\n")
        handle.write(f"file '{entries[-1][0]}'\n")
    subprocess.run([a.ffmpeg, '-y', '-loglevel', 'error', '-f', 'concat', '-safe', '0', '-i', str(concat),
                    '-vf', f'scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color=0x15171c,fps=30,format=yuv420p',
                    '-c:v', 'libx264', '-preset', 'veryfast', '-crf', '20', a.out], check=True)
    total = sum(s for _, s in entries)
    print(f'{a.out}: {total:.0f} s video from {end / 60:.1f} min real run; {len(shots)} screen states; cap {cap:.2f} s')
    shutil.rmtree(work, ignore_errors=True)


if __name__ == '__main__':
    main()
