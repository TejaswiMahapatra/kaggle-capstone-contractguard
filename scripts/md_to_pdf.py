#!/usr/bin/env python3
"""Convert markdown file to PDF using fpdf2."""

import re
import sys
from pathlib import Path

from fpdf import FPDF


class MarkdownPDF(FPDF):
    """Custom PDF class for markdown conversion."""

    def __init__(self):
        super().__init__()
        self.set_margins(20, 20, 20)
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        pass

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.cell(0, 10, f"Page {self.page_no()}", align="C")


def md_to_pdf(input_path: str, output_path: str | None = None) -> str:
    """Convert a markdown file to PDF.

    Args:
        input_path: Path to the markdown file
        output_path: Optional output path (defaults to same name with .pdf)

    Returns:
        Path to the generated PDF
    """
    input_file = Path(input_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    if output_path is None:
        output_path = str(input_file.with_suffix(".pdf"))

    # Read markdown content
    content = input_file.read_text(encoding="utf-8")

    # Create PDF
    pdf = MarkdownPDF()
    pdf.add_page()

    # Available width for text (page width - margins)
    effective_width = pdf.w - pdf.l_margin - pdf.r_margin

    def write_text(text: str, font: str = "Helvetica", style: str = "", size: int = 11):
        """Write text with specified formatting."""
        pdf.set_font(font, style, size)
        # Clean text and handle special characters
        text = text.replace("\u2014", "-").replace("\u2013", "-")
        text = text.replace("\u201c", '"').replace("\u201d", '"')
        text = text.replace("\u2018", "'").replace("\u2019", "'")
        pdf.multi_cell(effective_width, 6, text)

    # Process content line by line
    for line in content.split("\n"):
        line = line.rstrip()

        # Skip empty lines but add spacing
        if not line:
            pdf.ln(3)
            continue

        # Horizontal rule
        if line.startswith("---"):
            pdf.ln(2)
            pdf.set_draw_color(200, 200, 200)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            continue

        # Headers
        if line.startswith("# "):
            pdf.ln(4)
            write_text(line[2:], style="B", size=18)
            pdf.ln(2)
        elif line.startswith("## "):
            pdf.ln(3)
            write_text(line[3:], style="B", size=14)
            pdf.ln(1)
        elif line.startswith("### "):
            pdf.ln(2)
            write_text(line[4:], style="B", size=12)
        # Bold line (entire line is bold)
        elif line.startswith("**") and line.endswith("**") and line.count("**") == 2:
            write_text(line[2:-2], style="B", size=11)
        # List items
        elif line.startswith("- "):
            # Handle bold text within list items
            text = line[2:]
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # Remove bold markers
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(8, 6, chr(149))  # Bullet point
            pdf.multi_cell(effective_width - 8, 6, text)
        elif re.match(r"^\([a-z]\)", line):
            # Lettered list items like (a), (b), etc.
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            pdf.set_font("Helvetica", "", 11)
            pdf.cell(8, 6, "")  # Indent
            pdf.multi_cell(effective_width - 8, 6, text)
        elif re.match(r"^\d+\.", line):
            # Numbered list items
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            pdf.set_font("Helvetica", "", 11)
            pdf.multi_cell(effective_width, 6, text)
        else:
            # Regular paragraph - strip bold markers for simplicity
            text = re.sub(r"\*\*([^*]+)\*\*", r"\1", line)
            write_text(text, size=11)

    # Save PDF
    pdf.output(output_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python md_to_pdf.py <input.md> [output.pdf]")
        sys.exit(1)

    input_file = sys.argv[1]
    output_file = sys.argv[2] if len(sys.argv) > 2 else None

    try:
        result = md_to_pdf(input_file, output_file)
        print(f"PDF created: {result}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
