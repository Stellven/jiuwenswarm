"""Build the presentation PDF from the present-level pages. Documentation export only; proves nothing about runtime.

Usage (needs reportlab, pypdf; Mermaid PNGs rendered first, e.g. with @mermaid-js/mermaid-cli):
  python build_pdf.py --diagrams DIR --output FILE
DIR holds PNGs named <page>-<n>.png, n = order of the Mermaid block in that page (README.md -> README-1.png,
capabilities/README.md -> capabilities_README-1.png). flow views: flow-1 overview, flow-2 full (flow.md); the three variants are in flow-variants.md.
"""
import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as RLImage, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer,
                                Table, TableStyle)

ap = argparse.ArgumentParser()
ap.add_argument('--diagrams', type=Path, required=True)
ap.add_argument('--output', type=Path, required=True)
ap.add_argument('--font-dir', type=Path, default=Path('C:/Windows/Fonts'))
opt = ap.parse_args()
V = Path(__file__).resolve().parents[1]

pdfmetrics.registerFont(TTFont('Body', str(opt.font_dir / 'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('Bold', str(opt.font_dir / 'segoeuib.ttf')))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold')
navy, teal, muted = map(HexColor, ['#172D45', '#087E8B', '#516174'])
ST = {
    'title': ParagraphStyle('t', fontName='Bold', fontSize=19, leading=23, textColor=navy, spaceAfter=4),
    'sub': ParagraphStyle('s', fontName='Body', fontSize=8, leading=10, textColor=muted, spaceAfter=8),
    'h': ParagraphStyle('h', fontName='Bold', fontSize=10.5, leading=13, textColor=teal, spaceBefore=5, spaceAfter=3),
    'p': ParagraphStyle('p', fontName='Body', fontSize=8, leading=10.2, textColor=navy, spaceAfter=3),
    'b': ParagraphStyle('b', fontName='Body', fontSize=8, leading=10.2, textColor=navy, leftIndent=11, bulletIndent=0, spaceAfter=2),
    'c': ParagraphStyle('c', fontName='Body', fontSize=6.9, leading=8.4, textColor=navy),
    'ch': ParagraphStyle('ch', fontName='Bold', fontSize=6.9, leading=8.4, textColor=navy),
}
W = 595.28 - 84


def inline(t):
    t = re.sub(r'\[([^\]]+)\]\([^)]*\)', r'\1', t)
    t = escape(t.replace('\u2013', '-').replace('\u2014', '-').replace('\u2192', '->').replace('\u2260', '!='))
    t = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', t)
    return re.sub(r'`([^`]+)`', r'<font name="Bold">\1</font>', t)


def body(md):
    return re.sub(r'^---\n.*?\n---\n', '', md, flags=re.S)


def sections(path):
    """-> dict heading -> text (## level), plus '' for the intro."""
    text = body((V / path).read_text(encoding='utf-8'))
    out, cur, buf = {}, '', []
    for line in text.split('\n'):
        m = re.match(r'## (.+)$', line)
        if m:
            out[cur] = '\n'.join(buf)
            cur, buf = m.group(1).strip(), []
        else:
            buf.append(line)
    out[cur] = '\n'.join(buf)
    return out


def mermaid_index(path, text):
    """Number the mermaid blocks of a page so images can be matched."""
    return text


def flow(md, page_key, count_start=0):
    items, lines, i = [], md.split('\n'), 0
    block = count_start
    while i < len(lines):
        ln = lines[i]
        if ln.startswith('```mermaid'):
            block += 1
            i += 1
            while not lines[i].startswith('```'):
                i += 1
            png = opt.diagrams / f'{page_key}-{block}.png'
            if png.exists():
                with Image.open(png) as im:
                    iw, ih = im.size
                s = min(W / iw, 290 / ih)
                items.append(KeepTogether([RLImage(str(png), iw * s, ih * s), Spacer(1, 4)]))
            i += 1
            continue
        if ln.startswith('```'):
            i += 1
            while not lines[i].startswith('```'):
                i += 1
            i += 1
            continue
        if ln.startswith('|') and i + 1 < len(lines) and re.match(r'\|[-| ]+\|', lines[i + 1]):
            rows = []
            while i < len(lines) and lines[i].startswith('|'):
                if not re.match(r'\|[-| ]+\|$', lines[i]):
                    rows.append([c.strip() for c in lines[i].strip().strip('|').split('|')])
                i += 1
            n = len(rows[0])
            data = [[Paragraph(inline(c), ST['ch'] if r == 0 else ST['c']) for c in row[:n]] for r, row in enumerate(rows)]
            t = Table(data, colWidths=[W / n] * n, repeatRows=1)
            t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), HexColor('#EDF5F7')), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                                   ('GRID', (0, 0), (-1, -1), 0.3, HexColor('#D9E1E8')), ('TOPPADDING', (0, 0), (-1, -1), 3),
                                   ('BOTTOMPADDING', (0, 0), (-1, -1), 3)]))
            items += [t, Spacer(1, 4)]
            continue
        m = re.match(r'(\s*)(?:[-*]|\d+\.) (.+)', ln)
        if m:
            items.append(Paragraph(inline(m.group(2)), ST['b'], bulletText='-' if not re.match(r'\s*\d', ln) else re.match(r'\s*(\d+)\.', ln).group(1) + '.'))
        elif ln.startswith('### '):
            items.append(Paragraph(inline(ln[4:]), ST['h']))
        elif ln.strip() and not ln.startswith('<!--'):
            items.append(Paragraph(inline(ln.strip()), ST['p']))
        i += 1
    return items, block


story = []


def page(title, sub, parts):
    if story:
        story.append(PageBreak())
    story.append(Paragraph(inline(title), ST['title']))
    story.append(Paragraph(sub, ST['sub']))
    for head, items in parts:
        if head:
            story.append(Paragraph(inline(head), ST['h']))
        story.extend(items)


def pick(path, key, names, skip_diagrams=False, only_blocks=None):
    secs = sections(path)
    out = []
    count = 0
    for n in names:
        txt = secs[n]
        items, count_after = flow(txt, key, count)
        out.append((n if n not in ('',) else None, items))
        count = count_after
    return out


def diagram_only(key, n, caption):
    png = opt.diagrams / f'{key}-{n}.png'
    with Image.open(png) as im:
        iw, ih = im.size
    s = min(W / iw, 470 / ih)
    return [Paragraph(caption, ST['sub']), RLImage(str(png), iw * s, ih * s)]


STATUS = '5 October 2026 | Specified design | Implementation validation pending'
page('M1 architecture: what the system is and what we decided', STATUS,
     [(None, flow(sections('flow.md')['The flow in nine lines'], 'flow')[0]),
      ('Capsule or not', flow(sections('terms.md')['Capsule or not'], 'terms')[0])])
page('Flow: data in, governed DAG, answer out', STATUS, [(None, diagram_only('flow', 1, 'Overview. Fixed outer flow; planned nodes are fixed after freeze; every capsule call is followed by its Gate.'))]
     + [('Failures', flow(sections('flow.md')['How failures are handled'], 'flow', 2)[0])])
page('Flow with observability and RSI shown', STATUS, [(None, diagram_only('flow', 2, 'Full view. Observability lines are derived views only; RSI is a separate offline area.'))])
page('Placement and model routing', STATUS, pick('placement.md', 'placement', ['Decisions', 'Placement graph', 'Model routing in one view']))
page('Verification: Gates, verifier CC, test policy', STATUS, pick('verification.md', 'verification', ['Rules', 'Count and scope', 'Two tiers', 'Verdicts', 'Test policy']))
page('Runtime, exceptions, permissions, observability', STATUS, pick('runtime.md', 'runtime', ['Who does what during a run', 'One call, in order', 'Exception handling', 'Permissions and credentials', 'Observability']))
page('RSI: the separate improvement area', STATUS, pick('rsi.md', 'rsi', ['Position', 'Flow', 'What may change', 'Benchmarks per capsule', 'Admission and the Puppet Gate']))
page('Build order and how docs map to code', STATUS, pick('build-order.md', 'build-order', ['Steps', 'Working rules']))
dec = sections('decisions.md')
page('Decisions, PRD deviations, open items', STATUS, [('Current decisions', flow(dec['Current decisions'], 'decisions')[0]),
                                                          ('PRD deviations', flow(dec['PRD deviations'], 'decisions')[0]),
                                                          ('Open', flow(dec['Open'], 'decisions')[0])])


def frame(c, d):
    c.setFillColor(teal)
    c.rect(42, 806, 511, 3, fill=1, stroke=0)
    c.setFont('Bold', 8)
    c.setFillColor(muted)
    c.drawString(42, 818, 'M1 / ARCHITECTURE')
    c.setFont('Body', 8)
    c.drawString(42, 22, 'Source: docs/architecture/README.md')
    c.drawRightString(553, 22, str(d.page))


opt.output.parent.mkdir(parents=True, exist_ok=True)
SimpleDocTemplate(str(opt.output), pagesize=(595.28, 841.89), leftMargin=42, rightMargin=42, topMargin=46, bottomMargin=36,
                  title='M1 architecture', author='M1 Architecture').build(story, onFirstPage=frame, onLaterPages=frame)
print('built', opt.output)
