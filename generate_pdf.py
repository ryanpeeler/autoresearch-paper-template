#!/usr/bin/env python3
"""Generate a professional academic PDF from a markdown paper.

Reads author and title from config.yaml. Parses markdown sections and renders
with reportlab using Times Roman font and academic formatting.

Usage:
    python3 generate_pdf.py --input paper_final.md --config config.yaml --output paper.pdf
"""

import argparse
import re
import sys
from pathlib import Path

import yaml
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.colors import HexColor
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)
from reportlab.lib import colors


# ── Styles ──

def build_styles():
    s = {}
    s['title'] = ParagraphStyle('title', fontName='Times-Bold', fontSize=16, leading=20,
                                 alignment=TA_CENTER, spaceAfter=6, textColor=HexColor('#1a1a1a'))
    s['author'] = ParagraphStyle('author', fontName='Times-Roman', fontSize=12, leading=15,
                                  alignment=TA_CENTER, spaceAfter=4)
    s['abstract_label'] = ParagraphStyle('al', fontName='Times-Bold', fontSize=11, leading=14,
                                          spaceBefore=12, spaceAfter=4)
    s['abstract'] = ParagraphStyle('abs', fontName='Times-Italic', fontSize=10, leading=13,
                                    alignment=TA_JUSTIFY, leftIndent=36, rightIndent=36, spaceAfter=4)
    s['keywords'] = ParagraphStyle('kw', fontName='Times-Roman', fontSize=9, leading=12,
                                    leftIndent=36, rightIndent=36, spaceAfter=16)
    s['h1'] = ParagraphStyle('h1', fontName='Times-Bold', fontSize=13, leading=17,
                              spaceBefore=18, spaceAfter=8, textColor=HexColor('#1a1a1a'))
    s['h2'] = ParagraphStyle('h2', fontName='Times-Bold', fontSize=11, leading=14,
                              spaceBefore=14, spaceAfter=6, textColor=HexColor('#2a2a2a'))
    s['h3'] = ParagraphStyle('h3', fontName='Times-BoldItalic', fontSize=10, leading=13,
                              spaceBefore=10, spaceAfter=4, textColor=HexColor('#333333'))
    s['body'] = ParagraphStyle('body', fontName='Times-Roman', fontSize=10, leading=13,
                                alignment=TA_JUSTIFY, spaceBefore=2, spaceAfter=6, firstLineIndent=18)
    s['body_first'] = ParagraphStyle('bf', fontName='Times-Roman', fontSize=10, leading=13,
                                      alignment=TA_JUSTIFY, spaceBefore=2, spaceAfter=6)
    s['bullet'] = ParagraphStyle('bul', fontName='Times-Roman', fontSize=10, leading=13,
                                  alignment=TA_JUSTIFY, leftIndent=36, bulletIndent=18, spaceAfter=3)
    s['ref'] = ParagraphStyle('ref', fontName='Times-Roman', fontSize=9, leading=12,
                               leftIndent=18, firstLineIndent=-18, spaceAfter=3)
    s['footer'] = ParagraphStyle('ft', fontName='Times-Italic', fontSize=8, leading=10,
                                  alignment=TA_CENTER, textColor=HexColor('#888888'))
    s['table_note'] = ParagraphStyle('tn', fontName='Times-Italic', fontSize=9, leading=12,
                                      spaceAfter=4)
    return s


def add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Times-Roman', 9)
    canvas.setFillColor(HexColor('#888888'))
    canvas.drawCentredString(letter[0] / 2, 0.5 * inch, str(canvas.getPageNumber()))
    canvas.restoreState()


def h_rule():
    t = Table([['',]], colWidths=[6.5 * inch])
    t.setStyle(TableStyle([('LINEBELOW', (0, 0), (-1, 0), 1, HexColor('#cccccc'))]))
    return t


# ── Markdown to Reportlab ──

def escape_xml(text: str) -> str:
    """Escape XML special chars but preserve reportlab tags."""
    # First escape ampersands that aren't already part of entities
    text = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', text)
    # Don't escape < and > used in reportlab tags
    return text


def md_inline(text: str) -> str:
    """Convert inline markdown (bold, italic) to reportlab XML."""
    text = escape_xml(text)
    # Bold: **text** or __text__
    text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'__(.+?)__', r'<b>\1</b>', text)
    # Italic: *text* or _text_ (but not inside bold)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    # Remove markdown links, keep text: [text](url)
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    # Remove image references
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)
    return text.strip()


def parse_md_to_story(md_text: str, title: str, author: str, styles: dict) -> list:
    """Parse markdown text into a reportlab story."""
    s = styles
    story = []
    lines = md_text.split('\n')

    # Title and author
    story.append(Spacer(1, 0.3 * inch))
    # Split title on colon if present for two-line display
    if ':' in title and len(title) > 50:
        parts = title.split(':', 1)
        story.append(Paragraph(md_inline(parts[0].strip() + ':'), s['title']))
        story.append(Paragraph(md_inline(parts[1].strip()), s['title']))
    else:
        story.append(Paragraph(md_inline(title), s['title']))
    story.append(Spacer(1, 8))
    story.append(Paragraph(author, s['author']))
    story.append(Spacer(1, 8))
    story.append(h_rule())

    in_abstract = False
    in_references = False
    in_table = False
    table_rows = []
    table_caption = ""
    after_heading = False
    skip_title = True  # Skip the first # heading (title)
    prev_blank = False

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            prev_blank = True
            i += 1
            continue

        # Skip title line and author line
        if skip_title and stripped.startswith('# '):
            skip_title = False
            i += 1
            continue

        # Skip author line (bold)
        if stripped.startswith('**') and stripped.endswith('**') and 'author' not in stripped.lower():
            if any(name_word in stripped.lower() for name_word in ['ryan', 'peeler', author.lower().split()[0].lower()]):
                i += 1
                continue

        # Skip horizontal rules
        if stripped == '---':
            i += 1
            continue

        # Skip blockquotes (degraded mode notes, etc.)
        if stripped.startswith('>'):
            i += 1
            continue

        # Skip image references
        if stripped.startswith('!['):
            i += 1
            continue

        # Table detection
        if '|' in stripped and stripped.startswith('|'):
            if not in_table:
                in_table = True
                table_rows = []
                # Check if previous non-blank line was a table caption
            cells = [c.strip() for c in stripped.split('|')[1:-1]]
            # Skip separator rows
            if all(set(c) <= {'-', ':', ' '} for c in cells):
                i += 1
                continue
            table_rows.append(cells)
            i += 1
            continue
        elif in_table:
            # End of table — render it
            in_table = False
            if table_rows:
                t = Table(table_rows, repeatRows=1)
                t_style = TableStyle([
                    ('FONTNAME', (0, 0), (-1, 0), 'Times-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 8.5),
                    ('LEADING', (0, 0), (-1, -1), 11),
                    ('FONTNAME', (0, 1), (-1, -1), 'Times-Roman'),
                    ('BACKGROUND', (0, 0), (-1, 0), HexColor('#e8e8e8')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#cccccc')),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('LEFTPADDING', (0, 0), (-1, -1), 5),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 5),
                    ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, HexColor('#f7f7f7')]),
                ])
                t.setStyle(t_style)
                story.append(Spacer(1, 6))
                story.append(t)
                story.append(Spacer(1, 8))
                table_rows = []
            # Don't increment i — process current line normally

        # Headings
        if stripped.startswith('## ') and 'abstract' in stripped.lower():
            in_abstract = True
            story.append(Paragraph("Abstract", s['abstract_label']))
            after_heading = True
            i += 1
            continue

        if stripped.startswith('## ') and 'reference' in stripped.lower():
            in_references = True
            in_abstract = False
            story.append(Spacer(1, 12))
            story.append(h_rule())
            story.append(Paragraph("References", s['h1']))
            after_heading = True
            i += 1
            continue

        if stripped.startswith('## '):
            in_abstract = False
            heading_text = stripped.lstrip('# ').strip()
            story.append(Paragraph(md_inline(heading_text), s['h1']))
            after_heading = True
            i += 1
            continue

        if stripped.startswith('### '):
            in_abstract = False
            heading_text = stripped.lstrip('# ').strip()
            story.append(Paragraph(md_inline(heading_text), s['h2']))
            after_heading = True
            i += 1
            continue

        if stripped.startswith('#### '):
            heading_text = stripped.lstrip('# ').strip()
            story.append(Paragraph(md_inline(heading_text), s['h3']))
            after_heading = True
            i += 1
            continue

        # Keywords line
        if stripped.lower().startswith('**keywords'):
            text = md_inline(stripped)
            story.append(Paragraph(text, s['keywords']))
            story.append(h_rule())
            in_abstract = False
            i += 1
            continue

        # Table caption (italic line starting with *)
        if stripped.startswith('*') and stripped.endswith('*') and 'table' in stripped.lower():
            story.append(Paragraph(md_inline(stripped.strip('*')), s['table_note']))
            i += 1
            continue

        # Bullet points
        if stripped.startswith('- ') or stripped.startswith('* '):
            text = md_inline(stripped[2:])
            story.append(Paragraph(f"\u2022 {text}", s['bullet']))
            after_heading = False
            i += 1
            continue

        # Numbered lists
        m = re.match(r'^(\d+)\.\s+', stripped)
        if m:
            text = md_inline(stripped[m.end():])
            story.append(Paragraph(f"{m.group(1)}. {text}", s['bullet']))
            after_heading = False
            i += 1
            continue

        # Body text
        text = md_inline(stripped)
        if not text:
            i += 1
            continue

        if in_abstract:
            story.append(Paragraph(text, s['abstract']))
        elif in_references:
            story.append(Paragraph(text, s['ref']))
        elif after_heading:
            story.append(Paragraph(text, s['body_first']))
            after_heading = False
        else:
            story.append(Paragraph(text, s['body']))

        prev_blank = False
        i += 1

    # Footer
    story.append(Spacer(1, 18))
    story.append(h_rule())
    story.append(Spacer(1, 6))
    story.append(Paragraph("Generated with AutoResearchClaw", s['footer']))

    return story


# ── Main ──

def main():
    parser = argparse.ArgumentParser(description="Generate academic PDF from markdown")
    parser.add_argument('--input', '-i', required=True, help='Input markdown file')
    parser.add_argument('--config', '-c', default='config.yaml', help='Config YAML file')
    parser.add_argument('--output', '-o', default='paper.pdf', help='Output PDF path')
    args = parser.parse_args()

    # Read config
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path) as f:
            config = yaml.safe_load(f)
        author = config.get('author', 'Anonymous')
    else:
        author = 'Anonymous'

    # Read markdown
    md_path = Path(args.input)
    if not md_path.exists():
        print(f"ERROR: Input file not found: {md_path}")
        sys.exit(1)

    md_text = md_path.read_text(encoding='utf-8')

    # Extract title from first # heading
    title_match = re.search(r'^#\s+(.+)$', md_text, re.MULTILINE)
    title = title_match.group(1) if title_match else "Untitled Paper"

    # Build PDF
    doc = SimpleDocTemplate(
        args.output, pagesize=letter,
        leftMargin=1.0 * inch, rightMargin=1.0 * inch,
        topMargin=0.85 * inch, bottomMargin=0.85 * inch,
        title=title, author=author,
    )

    styles = build_styles()
    story = parse_md_to_story(md_text, title, author, styles)
    doc.build(story, onFirstPage=add_page_number, onLaterPages=add_page_number)
    print(f"PDF created: {args.output}")


if __name__ == "__main__":
    main()
