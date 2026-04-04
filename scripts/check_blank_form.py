import pdfplumber

path = "blank_form.pdf"
JOHNSON = ["JOHNSON", "EMILY", "425-62", "553-24"]
print(f"Checking {path} for Johnson data leaks...")
with pdfplumber.open(path) as pdf:
    total_leaks = 0
    for pn in range(1, min(len(pdf.pages)+1, 29)):
        text = " ".join(w["text"] for w in pdf.pages[pn-1].extract_words())
        hits = [t for t in JOHNSON if t in text]
        if hits:
            total_leaks += len(hits)
            # Get exact coordinates
            words_with_hits = [w for w in pdf.pages[pn-1].extract_words()
                                if any(t in w["text"] for t in JOHNSON)]
            for w in words_with_hits:
                print(f"  p{pn:02d}: x={w['x0']:.1f} y={w['top']:.1f} text={w['text']!r}")

    if total_leaks == 0:
        print("CLEAN - no Johnson data found in blank_form.pdf")
    else:
        print(f"\n{total_leaks} leaking words found")
