"""
Audits generated PDFs — extracts all text from key pages and checks
that synthetic identities appear (not Johnson's).
"""
import sys
import pdfplumber

JOHNSON_TRIGGERS = ["JOHNSON", "JOHN", "EMILY", "425-62-5489"]
PAGES_TO_CHECK = [1, 2, 7, 8, 23, 24]

def audit(pdf_path: str):
    print(f"\n{'='*60}")
    print(f"AUDIT: {pdf_path}")
    print(f"{'='*60}")
    with pdfplumber.open(pdf_path) as pdf:
        for page_num in PAGES_TO_CHECK:
            if page_num > len(pdf.pages):
                continue
            page = pdf.pages[page_num - 1]
            words = page.extract_words()
            text = " ".join(w["text"] for w in words)
            hits = [t for t in JOHNSON_TRIGGERS if t.upper() in text.upper()]
            status = "⚠️  JOHNSON DATA FOUND" if hits else "✅ Clean"
            print(f"\n  Page {page_num:02d}: {status}")
            if hits:
                print(f"    Triggers: {hits}")
            # Show first 300 chars of text for review
            preview = text[:300].replace("\n", " ")
            print(f"    Preview : {preview}")

if __name__ == "__main__":
    paths = sys.argv[1:] if len(sys.argv) > 1 else [
        "output/batch/test_output_variant_001.pdf",
        "output/batch/test_output_variant_002.pdf",
        "output/batch/test_output_variant_003.pdf",
    ]
    for p in paths:
        audit(p)
    print("\nDone.\n")
