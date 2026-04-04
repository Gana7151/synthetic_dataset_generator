import sys
from pypdf import PdfReader

pdf_path = "test_output_variant_001.pdf"
pages_to_check = [12, 14, 15, 17]

try:
    reader = PdfReader(pdf_path)
    for pnum in pages_to_check:
        print(f"--- Checking Page {pnum} ---")
        page_idx = pnum - 1
        if page_idx < len(reader.pages):
            page = reader.pages[page_idx]
            text = page.extract_text()
            if text and text.strip():
                lines = [ln.strip() for ln in text.split('\\n') if ln.strip()]
                print(f"Found {len(lines)} lines of text.")
                print("Sample:", lines[:5] if len(lines) > 5 else lines)
            else:
                print("Page is blank or text extraction failed.")
        else:
            print(f"Page {pnum} does not exist in the PDF.")
        print()
except Exception as e:
    print(f"Error checking PDF: {e}")
    sys.exit(1)
