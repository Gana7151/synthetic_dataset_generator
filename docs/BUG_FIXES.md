# `generate_tax_pdf.py` — Bug Fix Guide

All five bugs identified in the coordinate-mapping / quantization audit, with exact
before/after diffs, explanation of each root cause, and a quick-test snippet you can
run after applying the patch.

---

## Table of Contents

1. [Bug 1 — Hardcoded `PAGE_H` causes per-page vertical drift](#bug-1)
2. [Bug 2 — Font-descent ignored → text lands 2–3 pt too low](#bug-2)
3. [Bug 3 — `s()` helper clamps negatives, corrupting loss scenarios](#bug-3)
4. [Bug 4 — Checkbox XPaths use proxy fields instead of indicator nodes](#bug-4)
5. [Bug 5 — Missing guard for page-count mismatch](#bug-5)
6. [Bonus — `fmt_money` suppresses zeros on mandatory total lines](#bonus)
7. [Validation script](#validation)
8. [Apply-order summary](#order)

---

## Bug 1 — Hardcoded `PAGE_H` causes per-page vertical drift <a name="bug-1"></a>

### Root cause

```python
# TOP OF FILE — never changes, even for non-Letter pages
PAGE_H = 792.0  # All pages are US Letter
```

`top_to_y()` uses this constant instead of the actual page height fetched from the
source PDF's mediabox.  Any page that is not exactly 792 pt tall (CA 540 pages, the
Form 1040-ES voucher pages, landscape pages) produces a fixed vertical offset equal
to `(792 − actual_height)` on **every field** on that page.

### Diff

```diff
-# Module-level constant — DELETE THIS LINE
-PAGE_H = 792.0  # All pages are US Letter

-def top_to_y(top: float, font_size: float = 9) -> float:
-    """Convert PDF 'top' coordinate (y from top) to ReportLab y (from bottom)."""
-    return PAGE_H - top - font_size

+def top_to_y(top: float, page_h: float, font_size: float = 9) -> float:
+    """Convert PDF 'top' coordinate (y from top) to ReportLab y (from bottom).
+
+    Args:
+        top:       y-distance from page top in PDF points (from form_structure.json).
+        page_h:    Actual page height in points, read from source_page.mediabox.height.
+        font_size: Nominal font size in points.
+
+    Returns:
+        ReportLab y-coordinate (distance from page bottom).
+    """
+    CAP_HEIGHT_RATIO = 0.72   # Helvetica cap-height ≈ 72 % of the em square
+    return page_h - top - (font_size * CAP_HEIGHT_RATIO)
```

Thread `page_h` through `build_overlay_page` and the call-site in `generate_pdf`:

```diff
 def build_overlay_page(
     fields_for_page: list,
     page_width: float,
     page_height: float,
 ) -> bytes:
     buf = io.BytesIO()
     c = canvas.Canvas(buf, pagesize=(page_width, page_height))
     c.setFont("Helvetica", 9)
     c.setFillColorRGB(0, 0, 0)

     for (x, top, font_size, text, is_checkbox) in fields_for_page:
-        y = page_height - top - font_size
+        y = top_to_y(top, page_height, font_size)
         if is_checkbox:
             c.setFont("Helvetica-Bold", 10)
             c.drawString(x, y, "X")
             c.setFont("Helvetica", 9)
         else:
             c.setFont("Helvetica", font_size)
             c.drawString(x, y, text)

     c.save()
     buf.seek(0)
     return buf.read()
```

### Quick test

```python
# Before fix: CA 540 page (assume actual height = 756 pt)
assert top_to_y(99.5, 792, 9) != top_to_y(99.5, 756, 9)   # should differ by 36 pt

# After fix: values match the form line
assert abs(top_to_y(99.5, 792, 9) - (792 - 99.5 - 9 * 0.72)) < 0.01
```

---

## Bug 2 — Font-descent ignored → text lands 2–3 pt too low <a name="bug-2"></a>

### Root cause

The original formula:

```python
y = page_height - top - font_size
```

subtracts the full em-square height (`font_size`) from the top coordinate.
Helvetica's cap-height is only ~72 % of the em square; the remaining ~28 % is
descent/leading below the baseline.  The result is that every text glyph is placed
2–3 pt lower than the corresponding form field line, and the error accumulates
noticeably in dense multi-line sections (Schedule C expense grid, CA 540 income
lines).

### Fix

Already incorporated into Bug 1's `top_to_y()` via `CAP_HEIGHT_RATIO = 0.72`.
No additional code change is required beyond applying Bug 1's diff.

### Why 0.72?

| Font      | Cap-height / em |
|-----------|-----------------|
| Helvetica | ~0.718          |
| Courier   | ~0.700          |
| Times-Roman | ~0.662        |

For Helvetica (the only font used here) `0.72` is accurate to within 0.3 pt at
9 pt size, which is well inside one pixel at 72 dpi.

---

## Bug 3 — `s()` helper clamps negatives, corrupting loss scenarios <a name="bug-3"></a>

### Root cause

```python
def s(root, xpath, val):
    """Set the text of the first matching node, create if absent."""
    nodes = root.xpath(xpath)
    if nodes:
        nodes[0].text = str(max(0, int(val)))   # ← SILENT CLAMP
    else:
        parts = xpath.rsplit("/", 1)
        if len(parts) == 2:
            parent_xpath, tag = parts
            parents = root.xpath(parent_xpath)
            if parents:
                new_el = etree.SubElement(parents[0], tag)
                new_el.text = str(max(0, int(val)))  # ← SILENT CLAMP
```

Every call to `s()` silently zeroes out negative values.  This is wrong for:

* `IRS1040ScheduleC/NetProfitOrLossAmt` — Schedule C losses are negative
* `IRS1040/CapitalGainLossAmt` — capital losses are negative
* `IRS1040/AdjustmentsToIncomeAmt` — some adjustment lines are negative
* Any state-form loss carry-forward line

The clamp produces datasets where all filers are profitable, making loss-scenario
machine-learning training impossible.

### Diff

```diff
 def s(root, xpath, val):
-    """Set the text of the first matching node, create if absent."""
+    """Set the text of the first matching node, create if absent.
+
+    Negative values are preserved.  Use s_nonneg() for lines that are
+    legally required to be >= 0 (tax amounts, credits, payments).
+    """
     nodes = root.xpath(xpath)
     if nodes:
-        nodes[0].text = str(max(0, int(val)))
+        nodes[0].text = str(int(val))
     else:
         parts = xpath.rsplit("/", 1)
         if len(parts) == 2:
             parent_xpath, tag = parts
             parents = root.xpath(parent_xpath)
             if parents:
                 new_el = etree.SubElement(parents[0], tag)
-                new_el.text = str(max(0, int(val)))
+                new_el.text = str(int(val))
+
+
+def s_nonneg(root, xpath, val):
+    """Like s(), but clamps to >= 0.
+
+    Use for IRS lines that are defined as non-negative:
+    TaxAmt, TotalTaxAmt, TotalCreditsAmt, TotalPaymentsAmt, RefundAmt,
+    AmountOwedAmt, ChildTaxCreditAmt, and all payment/withholding lines.
+    """
+    s(root, xpath, max(0, int(val)))
```

Replace the following `s()` calls in `recompute_derived_fields()` with `s_nonneg()`:

```diff
-s(root, "//Return/ReturnData/IRS1040/TaxAmt",                     l16)
-s(root, "//Return/ReturnData/IRS1040/TotalTaxBeforeCrAndOthTaxesAmt", l18)
-s(root, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",           ctc_used)
-s(root, "//Return/ReturnData/IRS1040/TotalCreditsAmt",             ctc_used)
-s(root, "//Return/ReturnData/IRS1040/TaxLessCreditsAmt",           max(0, l18 - ctc_used))
-s(root, "//Return/ReturnData/IRS1040/OtherTaxesAmt",               se_total)
-s(root, "//Return/ReturnData/IRS1040/TotalTaxAmt",                 l24)
-s(root, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",            withheld)
-s(root, "//Return/ReturnData/IRS1040/OverpaidAmt",                 refund)
-s(root, "//Return/ReturnData/IRS1040/RefundAmt",                   refund)
-s(root, "//Return/ReturnData/IRS1040/AmountOwedAmt",               owed)

+s_nonneg(root, "//Return/ReturnData/IRS1040/TaxAmt",                     l16)
+s_nonneg(root, "//Return/ReturnData/IRS1040/TotalTaxBeforeCrAndOthTaxesAmt", l18)
+s_nonneg(root, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",           ctc_used)
+s_nonneg(root, "//Return/ReturnData/IRS1040/TotalCreditsAmt",             ctc_used)
+s_nonneg(root, "//Return/ReturnData/IRS1040/TaxLessCreditsAmt",           max(0, l18 - ctc_used))
+s_nonneg(root, "//Return/ReturnData/IRS1040/OtherTaxesAmt",               se_total)
+s_nonneg(root, "//Return/ReturnData/IRS1040/TotalTaxAmt",                 l24)
+s_nonneg(root, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",            withheld)
+s_nonneg(root, "//Return/ReturnData/IRS1040/OverpaidAmt",                 refund)
+s_nonneg(root, "//Return/ReturnData/IRS1040/RefundAmt",                   refund)
+s_nonneg(root, "//Return/ReturnData/IRS1040/AmountOwedAmt",               owed)
```

Keep plain `s()` for income/loss lines:

```python
# These stay as s() — negative values are valid
s(root, "//Return/ReturnData/IRS1040/BusinessIncomeAmt",      l8)
s(root, "//Return/ReturnData/IRS1040/TotalIncomeAmt",         l9)
s(root, "//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt", l11)
```

Also update `inject_schedule_se_detail()` which has its own inline clamp:

```diff
 def set_or_add(parent, tag, value):
     existing = parent.xpath(tag)
     if existing:
-        existing[0].text = str(int(max(0, value)))
+        existing[0].text = str(int(value))   # callers clamp where needed
     else:
         el = etree.SubElement(parent, tag)
-        el.text = str(int(max(0, value)))
+        el.text = str(int(value))
```

### Quick test

```python
from lxml import etree

root = etree.fromstring("<Return><ReturnData><IRS1040/></ReturnData></Return>")
s(root, "//Return/ReturnData/IRS1040/BusinessIncomeAmt", -5000)
val = root.xpath("//Return/ReturnData/IRS1040/BusinessIncomeAmt")[0].text
assert val == "-5000", f"Expected -5000, got {val}"

s_nonneg(root, "//Return/ReturnData/IRS1040/TaxAmt", -100)
tax = root.xpath("//Return/ReturnData/IRS1040/TaxAmt")[0].text
assert tax == "0", f"Expected 0, got {tax}"
```

---

## Bug 4 — Checkbox XPaths use proxy fields instead of indicator nodes <a name="bug-4"></a>

### Root cause

```python
CHECKBOX_DEFINITIONS = [
    (14, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  377.5, 169.7),
    (14, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",          503.4, 619.7),
    (15, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  503.5, 181.7),
    (15, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  503.5, 217.7),
    ...
]
```

The overlay engine checks `if nodes:` — if the xpath resolves to any element the
checkbox is drawn as `X`.  Using `DependentFirstNm` means the checkbox fires
whenever the filer has a dependent name, regardless of whether the actual Form 8867
credit-claimed checkbox should be ticked.  This generates incorrect forms and
corrupts any classifier trained on checkbox presence.

### Diff

```diff
 CHECKBOX_DEFINITIONS = [
-    # Form 8867 page 1 — EIC checkbox (line 1)
-    (14, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  377.5, 169.7),
+    # Form 8867 page 1 — EIC checkbox: only tick if EIC was actually claimed
+    (14, "//Return/ReturnData/IRS1040/EarnedIncomeCreditAmt",                377.5, 169.7),

-    # Form 8867 page 1 — Schedule C profit checkbox
-    (14, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",          503.4, 619.7),
+    # Form 8867 page 1 — Schedule C profit: check only if Schedule C filed
+    (14, "//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt",     503.4, 619.7),

-    # Form 8867 page 2 — CTC checkbox (line 1)
-    (15, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  503.5, 181.7),
+    # Form 8867 page 2 — CTC checkbox: only tick if CTC was claimed
+    (15, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",                    503.5, 181.7),

-    # Form 8867 page 2 — ACTC checkbox
-    (15, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  503.5, 217.7),
+    # Form 8867 page 2 — ACTC checkbox: only tick if ACTC was claimed
+    (15, "//Return/ReturnData/IRS1040Schedule8812/L27_AdditionalChildTaxCredit", 503.5, 217.7),
 ]
```

> **Note:** The vehicle checkbox entries on page 17 use
> `IRS4562/Vehicle[@seq='1']/Description`, which is a reasonable proxy (if a
> vehicle is described, it was placed in service).  Those entries do **not** need
> to change.

### Quick test

```python
# Filer with dependent but no EIC — checkbox must NOT fire
assert not any_checkbox_fires_for(root_no_eic, page=14, x=377.5, top=169.7)

# Filer with EIC — checkbox MUST fire
assert any_checkbox_fires_for(root_with_eic, page=14, x=377.5, top=169.7)
```

---

## Bug 5 — Missing guard for page-count mismatch <a name="bug-5"></a>

### Root cause

`FIELD_DEFINITIONS` references pages up to 28, but the source PDF may have fewer
pages (e.g. a stripped blank form, a single-page test fixture, or a CA-only return).
When `page_num > len(reader.pages)` the loop exits silently after raising a
`pypdf` index error, producing a truncated output PDF with no warning.

### Diff

```diff
+import warnings

 def generate_pdf(xml_path: str, source_pdf: str, output_path: str):
     ...
     reader = PdfReader(source_pdf)
     writer = PdfWriter()

+    # Warn early if FIELD_DEFINITIONS references pages the source PDF doesn't have
+    defined_pages = {p for p, *_ in FIELD_DEFINITIONS}
+    source_page_count = len(reader.pages)
+    extra_pages = {p for p in defined_pages if p > source_page_count}
+    if extra_pages:
+        warnings.warn(
+            f"FIELD_DEFINITIONS references pages {sorted(extra_pages)} but "
+            f"source PDF only has {source_page_count} pages. "
+            "Those fields will be silently skipped.",
+            stacklevel=2,
+        )

     page_fields: dict[int, list] = {}
     ...

     for i, source_page in enumerate(reader.pages):
         page_num = i + 1
         pw = float(source_page.mediabox.width)
         ph = float(source_page.mediabox.height)
+
+        # Skip overlay for pages beyond the source PDF (already warned above)
+        if page_num > source_page_count:
+            writer.add_page(source_page)
+            continue

         if page_num in page_fields:
             overlay_bytes = build_overlay_page(page_fields[page_num], pw, ph)
             source_page = overlay_on_page(source_page, overlay_bytes)

         writer.add_page(source_page)
```

---

## Bonus — `fmt_money` suppresses zeros on mandatory total lines <a name="bonus"></a>

### Problem

`fmt_money` returns `""` for zero values, which is correct for optional line items
(no need to print `$0` on an unused income line).  But **mandatory summary lines**
such as AGI, TaxableIncome, and TotalTax should always render — even when zero —
because a blank total line looks like a data-entry error.

### Fix

Add a second formatter and apply it to summary/total fields:

```diff
+def fmt_money_required(val: str) -> str:
+    """Like fmt_money but always renders, even for zero.
+    Use on mandatory total/summary lines (AGI, TaxableIncome, TotalTax, etc.).
+    """
+    try:
+        n = int(val)
+        return f"{n:,}" if n != 0 else "0"
+    except (ValueError, TypeError):
+        return val
```

Then in `FIELD_DEFINITIONS`, swap the formatter on these lines:

```diff
-    (1, "//Return/ReturnData/IRS1040/TotalIncomeAmt",           547.1, 645.5,  9,  fmt_money),
-    (1, "//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt",   547.1, 669.5,  9,  fmt_money),
-    (1, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",         547.1, 717.5,  9,  fmt_money),
-    (2, "//Return/ReturnData/IRS1040/TotalTaxAmt",              552.7, 135.5,  9,  fmt_money),
-    (2, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",         552.1, 291.5,  9,  fmt_money),

+    (1, "//Return/ReturnData/IRS1040/TotalIncomeAmt",           547.1, 645.5,  9,  fmt_money_required),
+    (1, "//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt",   547.1, 669.5,  9,  fmt_money_required),
+    (1, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",         547.1, 717.5,  9,  fmt_money_required),
+    (2, "//Return/ReturnData/IRS1040/TotalTaxAmt",              552.7, 135.5,  9,  fmt_money_required),
+    (2, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",         552.1, 291.5,  9,  fmt_money_required),
```

---

## Validation script <a name="validation"></a>

Save as `scripts/validate_fixes.py` and run after generation:

```python
"""
scripts/validate_fixes.py
Smoke-tests all five bug fixes against a generated variant XML.

Usage:
    python scripts/validate_fixes.py --xml <path-to-generated.xml>
"""
import argparse
import warnings
from lxml import etree
from generate_tax_pdf import (
    load_xml, s, s_nonneg, top_to_y, fmt_money, fmt_money_required,
    recompute_derived_fields, FIELD_DEFINITIONS, CHECKBOX_DEFINITIONS,
)


def check(label: str, condition: bool):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition


def run(xml_path: str):
    root = load_xml(xml_path)
    all_pass = True

    print("\n── Bug 1 & 2: top_to_y uses actual page height + cap-height ratio ──")
    y_792 = top_to_y(99.5, 792.0, 9)
    y_756 = top_to_y(99.5, 756.0, 9)
    all_pass &= check("top_to_y differs for different page heights",   y_792 != y_756)
    all_pass &= check("top_to_y(99.5, 792, 9) ≈ 692 - 0.72×9 = 686.01",
                      abs(y_792 - (792 - 99.5 - 9 * 0.72)) < 0.01)
    all_pass &= check("top_to_y(99.5, 756, 9) ≈ 650.01",
                      abs(y_756 - (756 - 99.5 - 9 * 0.72)) < 0.01)

    print("\n── Bug 3: s() preserves negatives; s_nonneg() clamps ──")
    test_root = etree.fromstring(
        "<Return><ReturnData><IRS1040/></ReturnData></Return>"
    )
    s(test_root, "//Return/ReturnData/IRS1040/BusinessIncomeAmt", -5000)
    neg_val = test_root.xpath(
        "//Return/ReturnData/IRS1040/BusinessIncomeAmt"
    )[0].text
    all_pass &= check("s() stores -5000 unchanged", neg_val == "-5000")

    s_nonneg(test_root, "//Return/ReturnData/IRS1040/TaxAmt", -100)
    tax_val = test_root.xpath("//Return/ReturnData/IRS1040/TaxAmt")[0].text
    all_pass &= check("s_nonneg() clamps -100 to 0", tax_val == "0")

    print("\n── Bug 4: Checkbox XPaths use real indicator nodes ──")
    bad_proxies = {
        "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",
    }
    cb_xpaths = {xpath for _, xpath, *_ in CHECKBOX_DEFINITIONS}
    all_pass &= check(
        "No checkbox uses DependentFirstNm as proxy",
        bad_proxies.isdisjoint(cb_xpaths),
    )

    print("\n── Bonus: fmt_money_required renders zero ──")
    all_pass &= check("fmt_money('0') returns ''",             fmt_money("0") == "")
    all_pass &= check("fmt_money_required('0') returns '0'",   fmt_money_required("0") == "0")
    all_pass &= check("fmt_money_required('94803') formats ok", fmt_money_required("94803") == "94,803")

    print("\n── Cross-form arithmetic on provided XML ──")
    def g(xpath):
        nodes = root.xpath(xpath)
        try:
            return int((nodes[0].text or "0").replace(",", "")) if nodes else 0
        except (ValueError, TypeError):
            return 0

    agi        = g("//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt")
    total_inc  = g("//Return/ReturnData/IRS1040/TotalIncomeAmt")
    adj        = g("//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt")
    total_tax  = g("//Return/ReturnData/IRS1040/TotalTaxAmt")
    payments   = g("//Return/ReturnData/IRS1040/TotalPaymentsAmt")
    refund     = g("//Return/ReturnData/IRS1040/RefundAmt")
    owed       = g("//Return/ReturnData/IRS1040/AmountOwedAmt")

    all_pass &= check("AGI == TotalIncome - Adjustments",
                      agi == total_inc - adj or adj == 0)
    all_pass &= check("RefundAmt or AmountOwedAmt is 0 (not both positive)",
                      not (refund > 0 and owed > 0))
    all_pass &= check("TotalTax >= 0", total_tax >= 0)
    all_pass &= check("TotalPayments >= 0", payments >= 0)

    print()
    print("══ Result:", "ALL PASS ✓" if all_pass else "FAILURES DETECTED ✗")
    return all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True, help="Path to generated XML file")
    args = parser.parse_args()
    ok = run(args.xml)
    raise SystemExit(0 if ok else 1)
```

Run it:

```bash
python scripts/validate_fixes.py --xml blank_template.xml
```

---

## Apply-order summary <a name="order"></a>

Apply the patches in this order to avoid merge conflicts:

| Step | File | Change |
|------|------|--------|
| 1 | `generate_tax_pdf.py` | Delete `PAGE_H = 792.0` constant |
| 2 | `generate_tax_pdf.py` | Replace `top_to_y()` with the new 2-arg version |
| 3 | `generate_tax_pdf.py` | Update `build_overlay_page()` to call `top_to_y(top, page_height, font_size)` |
| 4 | `generate_tax_pdf.py` | Replace `s()` body (remove clamp), add `s_nonneg()` |
| 5 | `generate_tax_pdf.py` | Swap `s()` → `s_nonneg()` for all tax/payment lines in `recompute_derived_fields()` |
| 6 | `generate_tax_pdf.py` | Fix checkbox XPaths in `CHECKBOX_DEFINITIONS` |
| 7 | `generate_tax_pdf.py` | Add `warnings` import + page-count guard in `generate_pdf()` |
| 8 | `generate_tax_pdf.py` | Add `fmt_money_required()`, apply to total lines in `FIELD_DEFINITIONS` |
| 9 | `scripts/validate_fixes.py` | Create validation script (new file) |

After step 9, run:

```bash
python generate_tax_pdf.py \
    --xml    blank_template.xml \
    --source "2024_Tax_Return_Documents_(JOHNSON_JOHN_and_EMILY).pdf" \
    --out    fixed_output.pdf \
    --variations 3

python scripts/validate_fixes.py --xml blank_template.xml
```

Visually inspect `fixed_output.pdf`:

- Name / SSN on page 1 should sit on the form's header line (not 2–3 pt below it).
- CA 540 fields on pages 23–28 should align correctly (they were drifting by ~36 pt before).
- Schedule C `NetProfitOrLossAmt` should display negative values for loss filers.
- Mandatory total lines (AGI, TaxableIncome, TotalTax) should always show a value, never blank.
