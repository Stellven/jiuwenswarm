"""Ordinary synthetic Markdown-to-PDF transport; no answers or product imports.

Optional dependency: reportlab in this interpreter. Exact canonical text is
subsequently captured by the product's pinned intake extractor, not this script.
"""
from functools import partial
import hashlib
from html import escape
import json
from pathlib import Path
import sys


def generate(raw, destination):
    import reportlab
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    target = Path(destination)
    if target.exists():
        raise FileExistsError(target)
    styles = getSampleStyleSheet()
    styles['BodyText'].fontSize = 10.5; styles['BodyText'].leading = 15
    story = []
    for paragraph in raw.decode('utf-8').strip().split('\n\n'):
        heading = paragraph.startswith('# ')
        text = paragraph[2:] if heading else paragraph
        story.append(Paragraph(escape(text).replace('\n', ' '), styles['Heading2'] if heading else styles['BodyText']))
        story.append(Spacer(1, 9))
    SimpleDocTemplate(str(target), pagesize=letter, leftMargin=48, rightMargin=48,
        topMargin=42, bottomMargin=42, title='Synthetic research comparison fixture',
        author='Local development fixture').build(story, canvasmaker=partial(Canvas, invariant=1))
    return {'generator': 'reportlab', 'version': reportlab.Version,
            'logical_source_sha256': hashlib.sha256(raw).hexdigest(),
            'pdf_sha256': hashlib.sha256(target.read_bytes()).hexdigest()}


if __name__ == '__main__':
    print(json.dumps(generate(sys.stdin.buffer.read(), sys.argv[1])))
