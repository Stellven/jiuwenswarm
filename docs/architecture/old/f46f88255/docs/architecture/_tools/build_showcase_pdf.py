"""Build the portable presentation from curated Markdown and rendered Mermaid PNGs.

Usage: python build_showcase_pdf.py --diagrams DIR --output FILE
Render the showcase Mermaid blocks and core information flow before invoking.
This exports documentation; it neither runs the product nor establishes acceptance.
"""
from io import BytesIO
import argparse
import re
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab.pdfgen import canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, PageBreak, Table, TableStyle
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from pypdf import PdfReader, PdfWriter
from PIL import Image

args = argparse.ArgumentParser()
args.add_argument('--diagrams', type=Path, required=True)
args.add_argument('--output', type=Path, required=True)
args.add_argument('--font-dir', type=Path, default=Path('C:/Windows/Fonts'))
opt = args.parse_args()
vault = Path(__file__).resolve().parents[1]
showcase = vault/'presentation/showcase'
pdfmetrics.registerFont(TTFont('Body', str(opt.font_dir/'segoeui.ttf')))
pdfmetrics.registerFont(TTFont('Bold', str(opt.font_dir/'segoeuib.ttf')))
pdfmetrics.registerFontFamily('Body', normal='Body', bold='Bold')
navy, teal, muted = map(HexColor, ['#172D45', '#087E8B', '#516174'])
styles = {
    'title': ParagraphStyle('title', fontName='Bold', fontSize=20, leading=24, textColor=navy, spaceAfter=14),
    'heading': ParagraphStyle('heading', fontName='Bold', fontSize=11, leading=14, textColor=teal, spaceBefore=9, spaceAfter=7),
    'body': ParagraphStyle('body', fontName='Body', fontSize=9, leading=12, textColor=navy, spaceAfter=7),
    'cell': ParagraphStyle('cell', fontName='Body', fontSize=7.5, leading=10, textColor=navy),
    'source': ParagraphStyle('source', fontName='Body', fontSize=8, leading=10, textColor=muted, spaceAfter=9),
}
def inline(text):
    # Local Markdown links stay human-readable; the owning filename remains visible.
    text = re.sub(r'\[([^]]+)\]\(([^)]+)\)', r'\1', text)
    text = escape(text.replace('`', '').replace('\u2013', '-').replace('\u2014', '-'))
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

def section(file, heading):
    text = (showcase/file).read_text(encoding='utf-8')
    body = text.split('## '+heading+'\n', 1)[1].split('\n## ', 1)[0]
    return [line[2:] for line in body.splitlines() if line.startswith('- ')]

flows = []
def page(title, source, groups):
    if flows:
        flows.append(PageBreak())
    flows.append(Paragraph(inline(title), styles['title']))
    flows.append(Paragraph('5 October 2026 | Specified design | Implementation validation pending', styles['source']))
    for heading, bullets in groups:
        flows.append(Paragraph(inline(heading), styles['heading']))
        for bullet in bullets:
            flows.append(Paragraph(inline(bullet), styles['body'], bulletText='-'))
    flows.append(Paragraph('Read in Obsidian: presentation/showcase/'+source, styles['source']))

page('M1 architecture - current snapshot', 'README.md', [
    ('The system', section('README.md','Two-minute summary')),
    ('Component roles', section('presentation.md','Deployment and component roles')[1:4]),
    ('Scope', section('presentation.md','Three tracks')[:3]),
])

flows.append(PageBreak())
flows.append(Paragraph('The twelve capabilities', styles['title']))
flows.append(Paragraph('Eight production work capabilities, one shared verifier and three retrieval operators. See capsules.md for exact ports and owning contracts.', styles['source']))
text = (showcase/'capsules.md').read_text(encoding='utf-8')
inventory = text.split('## Inventory and execution',1)[1].split('## Production ports',1)[0]
rows = [line.strip('|').split('|') for line in inventory.splitlines() if line.startswith('|') and not line.startswith('|---')]
table = Table([[Paragraph(inline(cell.strip()),styles['cell']) for cell in row] for row in rows], colWidths=[145,236,130], repeatRows=1)
table.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),HexColor('#EDF5F7')),('VALIGN',(0,0),(-1,-1),'TOP'),('GRID',(0,0),(-1,-1),0.3,HexColor('#D9E1E8')),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
flows.append(table)
flows.append(Paragraph('Build and improve',styles['heading']))
for bullet in section('capsules.md','Construction and optimization'):
    flows.append(Paragraph(inline(bullet),styles['body'],bulletText='-'))

page('Runtime, recovery and improvement', 'runtime-and-improvement.md', [
    ('Production authority', section('runtime-and-improvement.md','Production authority and normal sequence')),
    ('Failure and recovery', section('runtime-and-improvement.md','Failure and recovery')),
    ('Admission and offline RSI', section('runtime-and-improvement.md','Admission, RSI and activation')[:3]),
])
page('Data, credentials and access', 'data-and-permissions.md', [
    ('Input and output', section('data-and-permissions.md','Inputs and outputs')),
    ('Evidence', section('data-and-permissions.md','Storage and evidence')),
    ('Permission boundaries', section('data-and-permissions.md','Permission boundaries')),
])
page('Contracts, planner and coding checks', 'validation-and-development.md', [
    ('Exact interfaces', section('schemas-and-connections.md','Rules for joining components')),
    ('Isolated planning', section('runtime-and-improvement.md','Planner and deferred interaction analysis')),
    ('Evidence and development', [section('validation-and-development.md','Evidence categories')[i] for i in [0,1,2]] + section('validation-and-development.md','Coding handoff')),
])

opt.output.parent.mkdir(parents=True, exist_ok=True)
scratch = opt.output.parent/'showcase-text.tmp.pdf'
def frame(c, doc):
    c.setFillColor(teal); c.rect(42,798,511,3,fill=1,stroke=0)
    c.setFont('Bold',8);c.setFillColor(muted);c.drawString(42,814,'M1 / ARCHITECTURE SNAPSHOT')
    c.setFont('Body',8);c.drawString(42,24,'Canonical contracts: docs/architecture/presentation/showcase/README.md')
SimpleDocTemplate(str(scratch), pagesize=(595.28,841.89), leftMargin=42,rightMargin=42,topMargin=56,bottomMargin=51).build(flows,onFirstPage=frame,onLaterPages=frame)

diagrams = opt.output.parent/'showcase-diagrams.tmp.pdf'
c = canvas.Canvas(str(diagrams))
views = [
    ('Every capsule and its research position','capsules-1.png',(1190.55,841.89),'Overview omits cross-stage fan-in. All exact inputs remain in pipeline.md and the final appendix.'),
    ('Monolith, tracks and trust boundaries','presentation-1.png',(841.89,1190.55),'Conditional participation is track-scoped. Capture remains required even where edges are hidden.'),
    ('Halt, durable advancement and recovery','runtime-and-improvement-1.png',(841.89,1190.55),'Production advancement requires committed Verification and release; failed persistence blocks dispatch.'),
    ('Isolated experimental authority','runtime-and-improvement-2.png',(841.89,595.28),'Approved ablation uses experimental evidence/advance, not fabricated production Verification.'),
    ('Appendix: core information flow - zoom to read','information-flow-4.png',(2383.94,1683.78),'All 23 required production input bindings plus publication inputs. Derived observability and RSI are hidden, not disabled.'),
]
for title,name,(w,h),caption in views:
    c.setPageSize((w,h));c.setFillColor(navy);c.setFont('Bold',16);c.drawString(36,h-40,title)
    c.setFont('Body',9);c.setFillColor(muted);c.drawString(36,h-60,caption)
    png=opt.diagrams/name
    with Image.open(png) as im: iw,ih=im.size
    scale=min((w-72)/iw,(h-120)/ih);dw,dh=iw*scale,ih*scale
    c.drawImage(str(png),(w-dw)/2,42+(h-120-dh)/2,dw,dh)
    c.setFont('Body',8);c.drawString(36,22,'Source: presentation/showcase/ and system/information-flow.md | Specified design, not runtime proof')
    c.showPage()
c.save()
writer=PdfWriter()
for part in [scratch,diagrams]:
    for page in PdfReader(part).pages:
        buffer = BytesIO()
        stamp = canvas.Canvas(buffer, pagesize=(float(page.mediabox.width),float(page.mediabox.height)))
        stamp.setFont("Body",8);stamp.setFillColor(muted)
        stamp.drawRightString(float(page.mediabox.width)-36,22,str(len(writer.pages)+1))
        stamp.save();buffer.seek(0)
        page.merge_page(PdfReader(buffer).pages[0])
        writer.add_page(page)
writer.add_metadata({'/Title':'M1 architecture snapshot','/Author':'M1 Architecture','/Subject':'Current contracts, capabilities, information flow and validation obligations'})
with opt.output.open('wb') as out:writer.write(out)
scratch.unlink();diagrams.unlink()
print(f'{len(writer.pages)} pages: {opt.output}')
