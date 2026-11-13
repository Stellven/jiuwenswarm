"""Three still cards (1920x1080 PNG) for the terminal-first demo video; Pillow only.
    python docs/demo/cards_pil.py OUTDIR
Colour vocabulary: plain engine grey, CC-guided change amber, confirmed green, preliminary labelled."""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BG, FG, GREY, AMBER, GREEN = (21, 23, 28), (230, 230, 232), (154, 158, 168), (224, 160, 64), (127, 208, 138)
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
BOLD = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'


def card(lines, path):
    img = Image.new('RGB', (1920, 1080), BG)
    d = ImageDraw.Draw(img)
    y = max(60, (1080 - sum(size + gap for _, size, _, _, gap in lines)) // 2)
    for text, size, color, bold, gap in lines:
        font = ImageFont.truetype(BOLD if bold else FONT, size)
        d.text((110, y), text, font=font, fill=color)
        y += size + gap
    img.save(path)


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    card([('A capability capsule gives an agent an engineering method', 52, FG, True, 14),
          ('choose a useful change → apply it to llama.cpp → build → test → decide what to do next', 32, GREY, False, 60),
          ('Today: expert streaming on a Jetson Orin Nano (8 GB), Qwen3.6-35B-A3B', 36, FG, False, 22),
          ('Plain llama.cpp cf34d3113  ·  frozen quick contract (32 tokens, byte-identical greedy output)', 30, GREY, False, 22),
          ('Real recording of the agent working through CCs; long waits are compressed and labelled.', 30, GREY, False, 70),
          ('grey = plain engine    amber = CC-guided change    green = confirmed    "PRELIMINARY" = not confirmed', 28, AMBER, False, 0)],
         out / 'intro.png')
    card([('Result and scope of the claim', 52, FG, True, 28),
          ('THIS RECORDING · fresh candidate: demand fill only · quick contract (32 tokens) · decode ms/token', 30, AMBER, True, 14),
          ('   1-round ABBA   plain 903.98 → fill 839.69   (1.106 → 1.191 tok/s)   gate null (7.7% vs 7.8% threshold)', 30, FG, False, 6),
          ('   3-round ABBA   plain 956.92 → fill 854.44   (1.045 → 1.170 tok/s)   gate null (A/A noise 12.8% on this host)', 30, FG, False, 6),
          ('   Output identical to the frozen reference in every run; fill engaged.  PRELIMINARY — not a confirmed keep.', 30, AMBER, False, 44),
          ('RECORDED EVIDENCE · 64-token contract (a different workload — never combined with the above)', 30, GREEN, True, 14),
          ('   J-OM13, 12 runs, gate improved:  plain 841.5 → factory 711.4 ms/token (1.19 → 1.41 tok/s), output identical', 30, FG, False, 6),
          ('   plain factory/llamacpp:bare-cf34d311  vs  fill + predictive reads image bd173c08-restored-0b514fba', 28, GREY, False, 6),
          ('   Run 4 (fallback, one lab run per endpoint):  903.95 → 785.22 ms/token', 30, FG, False, 40),
          ('Startup and prefill are reported separately; nothing here is a model-accuracy claim.', 26, GREY, False, 0)],
         out / 'result.png')
    card([('This capability is implemented and measured.', 56, FG, True, 8),
          ('What other engineering methods can we package?', 56, FG, True, 50),
          ('Future candidates — opportunities, not working products or promised gains', 30, GREY, False, 30),
          ('•  Adaptive expert-read policy', 36, AMBER, True, 4),
          ('    choose fill / prediction depth / read size from live readiness counters', 28, GREY, False, 26),
          ('•  Workload-aware CPU/GPU placement', 36, AMBER, True, 4),
          ('    decide which experts live on the GPU for this workload', 28, GREY, False, 26),
          ('•  KV-cache / context-memory management', 36, AMBER, True, 4),
          ('    long-context memory on an 8 GB board as its own CC', 28, GREY, False, 0)],
         out / 'closing.png')
    print(*sorted(out.glob('*.png')), sep='\n')


if __name__ == '__main__':
    main(sys.argv[1])
