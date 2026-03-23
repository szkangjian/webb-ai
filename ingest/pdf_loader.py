"""
PDF loader for Webb Schools documents.
Place PDF files in data/pdfs/ and run this script.
"""

import os
import json
from pypdf import PdfReader

PDF_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "pdfs")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "scraped")


def load_pdf(filepath):
    """Extract text from a PDF file."""
    reader = PdfReader(filepath)
    pages = []
    for i, page in enumerate(reader.pages):
        text = page.extract_text()
        if text and text.strip():
            pages.append(text.strip())
    return "\n\n".join(pages)


def load_all_pdfs():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    pdf_files = [f for f in os.listdir(PDF_DIR) if f.endswith(".pdf")]
    if not pdf_files:
        print(f"No PDF files found in {PDF_DIR}")
        print("Place your Webb Schools PDFs there and run again.")
        return

    for filename in pdf_files:
        filepath = os.path.join(PDF_DIR, filename)
        print(f"Loading: {filename}")
        text = load_pdf(filepath)
        if not text:
            print(f"  SKIP: no text extracted")
            continue

        slug = filename.replace(".pdf", "").replace(" ", "_").lower()
        output = {
            "url": f"local://{filename}",
            "title": filename.replace(".pdf", "").replace("_", " "),
            "content": text,
        }
        out_path = os.path.join(OUTPUT_DIR, f"pdf_{slug}.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  Saved: pdf_{slug}.json ({len(text)} chars)")

    print(f"\nDone. PDFs loaded into {OUTPUT_DIR}")


if __name__ == "__main__":
    load_all_pdfs()
