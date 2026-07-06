import sys
from pathlib import Path

import markdown
from xhtml2pdf import pisa

SRC = Path(__file__).parent / "README.md"
OUT = Path(__file__).parent / "README.pdf"

CSS = """
<style>
@page {
    size: A4 landscape;   /* code lines with long trailing comments need the extra width */
    margin: 1.4cm;
}
body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; line-height: 1.4; }
h1 { font-size: 18pt; margin-top: 18pt; }
h2 { font-size: 14pt; margin-top: 16pt; border-bottom: 1px solid #999; padding-bottom: 2pt; }
h3 { font-size: 12pt; margin-top: 12pt; }
code { font-family: Courier, monospace; background-color: #f0f0f0; padding: 1pt 2pt;
       font-size: 8pt; word-wrap: break-word; }
pre {
    font-family: Courier, monospace;
    background-color: #f5f5f5;
    padding: 6pt;
    font-size: 7pt;
    line-height: 1.3;
    white-space: pre-wrap;      /* wrap long lines instead of clipping/overlapping */
    word-wrap: break-word;
    overflow-wrap: break-word;
    border: 0.5pt solid #ccc;
}
blockquote { border-left: 2pt solid #999; margin-left: 4pt; padding-left: 8pt; color: #333; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0; }
th, td { border: 0.5pt solid #999; padding: 4pt; font-size: 8pt; text-align: left;
         word-wrap: break-word; }
hr { border: none; border-top: 0.5pt solid #999; margin: 10pt 0; }
</style>
"""

def main():
    md_text = SRC.read_text(encoding="utf-8")
    body_html = markdown.markdown(md_text, extensions=["extra", "sane_lists"])
    full_html = f"<html><head>{CSS}</head><body>{body_html}</body></html>"

    with open(OUT, "wb") as f:
        result = pisa.CreatePDF(full_html, dest=f)

    if result.err:
        print(f"Failed with {result.err} errors.")
        sys.exit(1)

    print(f"Wrote {OUT}")

if __name__ == "__main__":
    main()
