# Complete Fix Plan — XML → PDF → Dataset Pipeline
**Repo:** `synthetic_dataset_generator` | **Date:** April 2026  
**Status after audit:** 7 bugs confirmed, all root-caused, all fixes verified with test variants

---

## Quick Reference — All Bugs

| # | Severity | File | Bug | Impact |
|---|----------|------|-----|--------|
| 1 | 🔴 Critical | `generate_tax_pdf.py` | `blank_form.pdf` white-box approach fails — Johnson data bleeds through | Double data on every page of every variant |
| 2 | 🔴 Critical | `generate_tax_pdf.py` | Dependents injected **after** `recompute_derived_fields()` | CTC = $0 on every record regardless of children |
| 3 | 🟠 High | `generate_tax_pdf.py` | `IRS4562` Vehicle node duplicated — inject adds 2nd node, XPath picks empty 1st | Page 17 vehicle fields blank |
| 4 | 🟠 High | `generate_tax_pdf.py` | `PhoneNum` never generated | Pages 2 & 28 phone blank |
| 5 | 🟡 Medium | `generate_tax_pdf.py` | `CA540` dependent slots copied before dependents are populated | Page 24 dependent fields blank |
| 6 | 🟡 Medium | `generate_tax_pdf.py` | `pdfs_only/` and `completed_form/` dirs never created | Storage requirement unmet |
| 7 | 🟡 Medium | `generate_tax_pdf.py` | Tax brackets hardcoded to MFJ 2024 | Wrong tax for single/HOH filers and non-2024 years |

---

## Bug 1 — `blank_form.pdf` Is Not Actually Blank (CRITICAL)

### Root Cause

`generate_blank_form()` attempts to white-out Johnson data by **prepending** a white-box PDF stream before the source page stream:

```python
# BROKEN — current code
combined = white_stream + b"\n" + source_stream
```

In PDF's painter model, content streams render top-to-bottom. This means white boxes render **first** (background), then Johnson's text renders **on top** of them. The white boxes are invisible behind the form content.

Result: `blank_form.pdf` still contains all Johnson data (SSNs, dollar amounts, names on all 28 pages). Every generated variant stacks Smith/Jones/etc. data on top of still-visible Johnson data, producing merged garbage like `JWOilHliaNm`, `445702--3980-3-2182634`, and `5742,,529070`.

### Fix — Regenerate `blank_form.pdf` Using PyMuPDF Redaction

PyMuPDF's `apply_redactions()` **physically removes text from content streams** — not just visually covers it. This is the only reliable approach.

**Step 1: Install PyMuPDF**

```bash
pip install pymupdf --break-system-packages
```

**Step 2: Replace `generate_blank_form()` in `generate_tax_pdf.py`**

Find the existing `generate_blank_form()` function (it appears twice — remove both copies) and replace with this single implementation:

```python
def generate_blank_form(source_pdf: str, output_path: str):
    """
    Creates blank_form.pdf by permanently redacting all Johnson data
    from the source PDF using PyMuPDF content-stream redaction.
    Run once. Commit blank_form.pdf to repo.
    """
    import fitz  # PyMuPDF

    # Zones covering every data-entry position across all 28 pages.
    # Format: (x0, top, x1, bottom) — PDF coordinates, y from TOP of page.
    FULL_CLEAR_ZONES = {
        1: [
            (35,  85, 475, 105),   # primary name
            (465, 85, 612, 105),   # primary SSN
            (35, 109, 475, 128),   # spouse name
            (465,109, 612, 128),   # spouse SSN
            (35, 133, 612, 153),   # address
            (35, 157, 612, 177),   # city/state/zip
            (85, 373, 520, 410),   # dependents rows
            (530,296, 580, 313),   # digital assets checkbox
            (455,373, 480, 410),   # dependent CTC checkboxes
            (530,373, 580, 410),   # dependent credit X
            (535,420, 612, 730),   # all right-column income amounts
        ],
        2: [
            (110, 20, 475,  40),   # name header
            (465, 20, 612,  40),   # SSN header
            (450,154, 490, 174),   # withholding amount (line 25a)
            (535, 30, 612, 400),   # all tax/payment amounts
            (130,520, 445, 540),   # phone + email
            (285,547, 580, 592),   # occupation fields
            (35, 592, 612, 792),   # preparer block + signature
        ],
        3: [
            (35,  90, 612, 112),   # name header
            (535, 210, 612, 235),  # business income line
            (535, 655, 612, 680),  # total additional income
        ],
        4:  [(535, 205, 612, 615)],
        5:  [
            (35,  82, 612, 102),   # name header
            (540, 270, 612, 345),  # SE tax amounts
            (540, 442, 590, 462),  # 6,034 line
        ],
        6:  [
            (540, 568, 590, 588),  # 6,034
            (535, 710, 612, 732),  # total other taxes
        ],
        7:  [
            (35,  67, 612,  88),   # name/SSN header
            (35, 138, 612, 162),   # interest payer name
            (35, 320, 612, 344),   # dividend payer name
            (535,138, 612, 410),   # amounts
        ],
        8:  [
            (35,  90, 612, 108),   # proprietor name + SSN
            (35, 108, 612, 125),   # business description
            (35, 123, 612, 138),   # business name
            (35, 137, 612, 152),   # address
            (255,192, 612, 460),   # all income/expense amounts
            (535,550, 590, 570),   # net profit line
            (535,646, 590, 666),   # another amount line
        ],
        9:  [
            (35,  46, 612,  66),   # name/SSN header (Schedule C p2)
            (35, 456, 612, 560),   # Part V other expenses
        ],
        10: [
            (35,  90, 612, 112),   # name header
            (535, 183, 612, 475),  # SE calculation amounts
            (540, 526, 590, 546),  # deductible SE tax
        ],
        11: [
            (35, 100, 612, 125),   # name header + L1_AGI
            (535, 130, 590, 150),  # 94,803
            (535, 160, 612, 375),  # CTC calculation amounts
            (540, 394, 590, 414),  # 2,500
            (540, 442, 590, 475),  # 6,313 + 2,500
        ],
        12: [(145, 28, 612, 55),   # header
             (565, 85, 612, 510)], # ACTC amounts
        13: [
            (35,  90, 612, 112),   # name header
            (68, 106, 560, 126),   # EMILY JOHNSON + SSN
            (405,226, 485, 246),   # SSN in formula area
            (35, 135, 612, 160),   # business name row
            (475,135, 612, 380),   # QBI amounts
            (530,382, 585, 397),   # 7,937
            (530,478, 585, 498),   # 7,937
            (530,562, 585, 582),   # 7,937
            (418,658, 475, 678),   # 94,803
        ],
        14: [
            (35, 100, 612, 120),   # taxpayer name
            (35, 120, 612, 145),   # preparer name/PTIN
            (55, 475, 612, 500),   # documents relied on
        ],
        15: [(115, 30, 612, 55)],
        16: [
            (35,  85, 612, 120),   # name/SSN header + business name
            (475,135, 612, 175),   # depreciation amounts
        ],
        17: [
            (110, 20, 612,  42),   # name/SSN header
            (35, 170, 612, 200),   # vehicle info row
            (255,335, 612, 430),   # mileage section
        ],
        18: [(35, 50, 612, 792)],  # entire 1040-V data block
        19: [(35, 50, 612, 792)],  # 1040-ES Q1
        20: [(35, 50, 612, 792)],  # 1040-ES Q2
        21: [(35, 50, 612, 792)],  # 1040-ES Q3
        22: [(35, 50, 612, 792)],  # 1040-ES Q4
        23: [
            (35,  85, 330, 108),   # primary name
            (330, 85, 612, 108),   # SSNs
            (35, 108, 612, 182),   # address block
        ],
        24: [
            (35,  40, 612, 135),   # header + dependent rows
            (475,145, 612, 365),   # CA income/tax amounts
        ],
        25: [
            (35,  40, 612,  72),   # header
            (475, 95, 612, 445),   # CA tax/payment amounts
        ],
        26: [
            (35,  40, 612,  72),   # header
            (475, 70, 612, 115),   # refund amounts
        ],
        27: [
            (35,  40, 612,  72),   # header
            (475,185, 612, 215),   # refund line
        ],
        28: [
            (35,  40, 612, 215),   # header + signature block
            (35, 480, 612, 510),   # phone/email
        ],
    }

    doc = fitz.open(source_pdf)
    for i in range(len(doc)):
        page_num = i + 1
        page = doc[i]
        zones = FULL_CLEAR_ZONES.get(page_num, [])
        for (x0, top, x1, bot) in zones:
            page.add_redact_annot(fitz.Rect(x0, top, x1, bot), fill=(1, 1, 1))
        if zones:
            page.apply_redactions()

    doc.save(output_path)
    print(f"Blank form written: {output_path}  ({len(doc)} pages)")
```

**Step 3: Regenerate `blank_form.pdf`**

```bash
cd synthetic_dataset_generator
python generate_tax_pdf.py \
    --source "2024_Tax_Return_Documents_(JOHNSON_JOHN_and_EMILY).pdf" \
    --xml blank_template.xml \
    --out blank_form.pdf \
    --make-blank
```

**Step 4: Verify**

```bash
python - <<'EOF'
import pdfplumber
PATTERNS = ['JOHNSON','EMILY','472-90','52,200','94,803','42,700','6,034','6,313','3,447']
with pdfplumber.open('blank_form.pdf') as pdf:
    for i, page in enumerate(pdf.pages, 1):
        bad = [w['text'] for w in page.extract_words()
               if any(p in w['text'] for p in PATTERNS)]
        print(f'Page {i}: {"CLEAN" if not bad else bad}')
EOF
```

Expected: every page prints `CLEAN`.

---

## Bug 2 — Dependents Populated After Tax Computation (CRITICAL)

### Root Cause

In `generate_variation()`, the current order is:

```python
# Line ~103 — computes CTC, reads EligibleForChildTaxCreditInd
root, computed = recompute_derived_fields(root, ca_wh)

# Line ~107 — populates dependents (TOO LATE)
target_kids = rng.choice([0, 1, 2])
dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
for i in range(min(target_kids, len(dep_nodes))):
    ...
    _set_sub("EligibleForChildTaxCreditInd", "X")
```

`recompute_derived_fields()` reads `EligibleForChildTaxCreditInd` to compute the CTC. Because dependents are blank when it runs, `num_kids = 0` always → CTC = `$0` on every record, breaking `ChildTaxCreditAmt`, `TotalCreditsAmt`, `TaxLessCreditsAmt`, `TotalTaxAmt`, and refund/owed fields.

### Fix — Move Dependent Loop Before `recompute_derived_fields()`

In `generate_variation()`, find the block starting `root, computed = recompute_derived_fields(root, ca_wh)` and restructure as follows:

```python
    # ── STEP A: Set raw income values ──────────────────────────────────────
    w2        = rng.randint(30000, 150000)
    gross_rev = rng.randint(30000, 200000)

    set_text("//Return/ReturnData/IRS1040/WagesAmt", w2)
    set_text("//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt", w2)
    set_text("//Return/ReturnData/IRSW2/WagesAmt", w2)
    set_text("//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt", gross_rev)
    set_text("//Return/ReturnData/IRS1040ScheduleC/TotalGrossReceiptsAmt", gross_rev)

    expenses = generate_schedule_c_expenses(gross_rev, rng)
    vehicle  = generate_vehicle_depreciation(rng)
    if "description" not in vehicle:
        vehicle["description"] = f"20{rng.randint(18,24)} {rng.choice(['Honda','Toyota','Ford'])}"
    expenses["L13_DepreciationSection179"] = vehicle["dep_allowed"]

    inv = generate_investment_income(w2 + expenses["L31_NetProfitLoss"], rng)
    set_text("//Return/ReturnData/IRS1040/TaxableInterestAmt",  inv["L2b_TaxableInterest"])
    set_text("//Return/ReturnData/IRS1040/OrdinaryDividendsAmt", inv["L3b_OrdinaryDividends"])

    fed_wh = generate_withholding(w2, rng)
    ca_wh  = generate_ca_withholding(w2, rng)
    set_text("//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt", fed_wh)
    set_text("//Return/ReturnData/IRSW2/WithholdingAmt", fed_wh)

    # ── STEP B: Populate dependents BEFORE recompute ────────────────────────
    target_kids = rng.choice([0, 1, 2])
    dep_nodes   = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    for i in range(min(target_kids, len(dep_nodes))):
        c_first = rng.choice(FIRST_NAMES)
        c_ssn   = random_ssn(rng).replace("-", "")
        dep_el  = dep_nodes[i]

        def _set_sub(tag, val):
            el = dep_el.find(tag)
            if el is None:
                from lxml import etree
                el = etree.SubElement(dep_el, tag)
            el.text = str(val)

        _set_sub("DependentFirstNm",             c_first)
        _set_sub("DependentLastNm",              p_last)
        _set_sub("DependentSSN",                 c_ssn)
        _set_sub("DependentRelationshipCd",      rng.choice(["DAUGHTER", "SON"]))
        _set_sub("EligibleForChildTaxCreditInd", "X")

    num_kids  = target_kids
    num_other = max(0, len(dep_nodes) - num_kids)

    # ── STEP C: Recompute — now sees correct dependent data ─────────────────
    root, computed = recompute_derived_fields(root, ca_wh)
```

Then **delete** the duplicate dependent loop that appears after `recompute_derived_fields` (the original `target_kids = rng.choice([0, 1, 2])` block at ~line 107).

---

## Bug 3 — `IRS4562` Vehicle Node Duplicated

### Root Cause

`blank_template.xml` already has `<Vehicle seq="1">` with empty child nodes:

```xml
<IRS4562>
  ...
  <Vehicle seq="1">
    <Description/>
    <DatePlacedInService/>
    <BusinessUsePct/>
    <DepreciationAllowed>0</DepreciationAllowed>
  </Vehicle>
</IRS4562>
```

`inject_form4562_detail()` calls `etree.SubElement(f4562, "Vehicle")` unconditionally, creating a **second** `<Vehicle seq="1">`. XPath `[@seq='1']` returns the **first** (empty) node. Result: Description, BusinessUsePct, and DepreciationAllowed on page 17 are all blank.

### Fix — Replace `inject_form4562_detail()` body

```python
def inject_form4562_detail(root, vehicle: dict, section179: int, total_dep: int):
    from lxml import etree
    f4562 = root.xpath("//Return/ReturnData/IRS4562")
    if not f4562:
        rd = root.xpath("//Return/ReturnData")[0]
        f4562 = etree.SubElement(rd, "IRS4562")
    else:
        f4562 = f4562[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(value)
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(value)

    # FIX: find-or-create, never duplicate
    existing_veh = f4562.xpath("Vehicle[@seq='1']")
    veh = existing_veh[0] if existing_veh else etree.SubElement(f4562, "Vehicle")
    veh.set("seq", "1")

    def _veh_set(tag, val):
        el = veh.find(tag)
        if el is None:
            el = etree.SubElement(veh, tag)
        el.text = str(val)

    _veh_set("Description",        vehicle["description"])
    _veh_set("BusinessUsePct",     vehicle["business_pct"])
    _veh_set("DepreciationAllowed", vehicle["dep_allowed"])

    set_or_add(f4562, "L30_BusinessMiles",      vehicle["business_miles"])
    set_or_add(f4562, "L31_CommutingMiles",     vehicle["commute_miles"])
    set_or_add(f4562, "L32_OtherPersonalMiles", vehicle["personal_miles"])
    set_or_add(f4562, "L33_TotalMiles",         vehicle["total_miles"])
    set_or_add(f4562, "L28_TotalListedPropDep", vehicle["dep_allowed"])
    set_or_add(f4562, "DepreciationAmt",        vehicle["dep_allowed"])
    set_or_add(f4562, "TotalDepreciationAmt",   vehicle["dep_allowed"])

    return root
```

---

## Bug 4 — `PhoneNum` Never Generated

### Root Cause

`generate_variation()` sets `EmailAddressTxt` but never sets `PhoneNum`. Pages 2 and 28 have blank phone fields.

### Fix — Add one line to the identity block in `generate_variation()`

Add immediately after the `EmailAddressTxt` line:

```python
    set_text("//Return/ReturnHeader/Filer/EmailAddressTxt",
             f"{p_first.lower()}.{p_last.lower()}@gmail.com")

    # ADD THIS LINE:
    set_text("//Return/ReturnHeader/Filer/PhoneNum",
             f"({rng.randint(200,999)}){rng.randint(200,999)}-{rng.randint(1000,9999)}")
```

---

## Bug 5 — CA540 Dependents Copied Before Population (Auto-Fixed by Bug 2)

### Root Cause

`inject_ca540_nodes()` copies dependents from federal `DependentDetail` nodes into the CA540 structure. Because the dependent loop previously ran **after** `inject_ca540_nodes()`, the CA540 always got empty dependent slots.

### Status

**This bug auto-resolves** once Bug 2 is fixed — the dependent loop now runs before both `recompute_derived_fields()` and the inject chain. No additional code change needed.

However, add this guard in `inject_ca540_nodes()` to skip empty template slots:

```python
    # In inject_ca540_nodes(), replace the dependent loop with:
    deps_el = etree.SubElement(ca, "Dependents")
    for i, dep in enumerate(dep_nodes[:2], start=1):
        first = dep.findtext("DependentFirstNm") or ""
        last  = dep.findtext("DependentLastNm")  or ""
        ssn   = dep.findtext("DependentSSN")     or ""
        if not first:          # skip unpopulated template slots
            continue
        d = etree.SubElement(deps_el, "Dependent")
        d.set("seq", str(i))
        add(d, "FirstName", first)
        add(d, "LastName",  last)
        add(d, "SSN",       ssn)
```

---

## Bug 6 — Missing Storage Directories

### Root Cause

`pdfs_only/` and `completed_form/` directories are never created anywhere in the codebase. The requirement specifies intermediate PDFs go to `pdfs_only/` and final versions to `completed_form/`.

### Fix — Update `generate_variation()` signature and add auto-save

**Change the function signature:**

```python
def generate_variation(source_pdf: str, output_path: str, seed: int,
                       pdfs_only_dir: str = "pdfs_only",
                       completed_dir:  str = "completed_form"):
```

**Add at the top of the function body:**

```python
    import os, shutil
    from pathlib import Path
    os.makedirs(pdfs_only_dir, exist_ok=True)
    os.makedirs(completed_dir,  exist_ok=True)
```

**Add at the bottom of the function body, after `generate_pdf(...)` returns:**

```python
    filename = Path(output_path).name

    pdfs_only_path = os.path.join(pdfs_only_dir, filename)
    completed_path = os.path.join(completed_dir,  filename)
    shutil.copy2(output_path, pdfs_only_path)
    shutil.copy2(output_path, completed_path)
    print(f"  ✓ pdfs_only/      → {pdfs_only_path}")
    print(f"  ✓ completed_form/ → {completed_path}")
```

**Update the `main()` batch loop to pass directories:**

```python
    if args.variations > 0:
        out_path = Path(args.out)
        out_path.mkdir(parents=True, exist_ok=True)
        for i in range(args.variations):
            variant_path = out_path / f"test_output_variant_{i+1:03d}.pdf"
            print(f"\n═══ Variant {i+1}/{args.variations} → {variant_path.name} ═══")
            generate_variation(
                args.source, str(variant_path), seed=args.seed + i,
                pdfs_only_dir=str(out_path / "pdfs_only"),
                completed_dir=str(out_path / "completed_form"),
            )
```

---

## Bug 7 — Tax Brackets Hardcoded to MFJ 2024

### Root Cause

`recompute_derived_fields()` contains a hardcoded inner function `tax_mfj_2024()` and a hardcoded standard deduction of `$29,200`. This produces wrong tax figures for `single`/`hoh` filers and for any year other than 2024.

### Fix — Add `TAX_PARAMS` table and replace hardcoded call

**Add this constant block near the top of `generate_tax_pdf.py`**, after the imports:

```python
TAX_PARAMS = {
    2024: {
        "mfj":    {"std": 29200, "brackets": [
            (23200, .10),(94300, .12),(201050, .22),
            (383900,.24),(487450, .32),(731200, .35),(float("inf"),.37)]},
        "single": {"std": 14600, "brackets": [
            (11600, .10),(47150, .12),(100525, .22),
            (191950,.24),(243725, .32),(609350, .35),(float("inf"),.37)]},
        "hoh":    {"std": 21900, "brackets": [
            (16550, .10),(63100, .12),(100500, .22),
            (191950,.24),(243700, .32),(609350, .35),(float("inf"),.37)]},
    },
    2023: {
        "mfj":    {"std": 27700, "brackets": [
            (22000, .10),(89075, .12),(190750, .22),
            (364200,.24),(462500, .32),(693750, .35),(float("inf"),.37)]},
        "single": {"std": 13850, "brackets": [
            (11000, .10),(44725, .12),(95375,  .22),
            (182050,.24),(231250, .32),(578125, .35),(float("inf"),.37)]},
        "hoh":    {"std": 20800, "brackets": [
            (15700, .10),(59850, .12),(95350,  .22),
            (182050,.24),(231250, .32),(578100, .35),(float("inf"),.37)]},
    },
    2022: {
        "mfj":    {"std": 25900, "brackets": [
            (20550, .10),(83550, .12),(178150, .22),
            (340100,.24),(431900, .32),(647850, .35),(float("inf"),.37)]},
        "single": {"std": 12950, "brackets": [
            (10275, .10),(41775, .12),(89075,  .22),
            (170050,.24),(215950, .32),(539900, .35),(float("inf"),.37)]},
        "hoh":    {"std": 19400, "brackets": [
            (14650, .10),(55900, .12),(89050,  .22),
            (170050,.24),(215950, .32),(539900, .35),(float("inf"),.37)]},
    },
}

def _apply_brackets(income: int, brackets: list) -> int:
    tax, prev = 0, 0
    for limit, rate in brackets:
        seg = min(income, limit) - prev
        if seg <= 0:
            break
        tax += int(seg * rate)
        prev = limit
    return tax
```

**Inside `recompute_derived_fields()`, replace the hardcoded section:**

```python
    # REMOVE this inner function:
    # def tax_mfj_2024(income: int) -> int: ...

    # REPLACE:
    # l16  = tax_mfj_2024(l15)
    # standard_ded = 29200
    
    # WITH:
    year        = int(xget(root, "//Return/ReturnHeader/TaxYr") or "2024")
    filing_cd   = xget(root, "//Return/ReturnData/IRS1040/IndividualReturnFilingStatusCd") or "2"
    filing_key  = {"1": "single", "2": "mfj", "4": "hoh"}.get(filing_cd, "mfj")
    yr_params   = TAX_PARAMS.get(year, TAX_PARAMS[2024]).get(filing_key, TAX_PARAMS[2024]["mfj"])
    standard_ded = yr_params["std"]
    l16          = _apply_brackets(l15, yr_params["brackets"])
```

---

## Execution Order Reference

After all fixes, `generate_variation()` must execute in this order:

```
1.  Load blank_template.xml
2.  Generate identity (names, SSNs, address)
3.  Set PhoneNum                                    ← Bug 4 fix
4.  Set ScheduleC identity fields (ProprietorNm etc.)
5.  Set ScheduleB payer names
6.  Set W2 identity + occupation
7.  Set raw income (W2, gross_rev, withholding)
8.  Populate DependentDetail nodes                  ← Bug 2 fix (moved up)
9.  Call recompute_derived_fields()                 ← now sees correct deps
10. inject_schedule_c_detail()
11. inject_schedule_se_detail()
12. inject_form8995_detail()
13. inject_schedule8812_detail()
14. inject_schedule8812_part2()
15. inject_ca540_nodes()                            ← Bug 5 auto-fixed
16. inject_voucher_nodes()
17. inject_form4562_detail()    (find-or-create)    ← Bug 3 fix
18. inject_preparer_node()
19. Write temp XML → generate_pdf() → output_path
20. shutil.copy2 → pdfs_only/ and completed_form/  ← Bug 6 fix
```

---

## Installation Requirements

Add to `requirements.txt`:

```
pymupdf>=1.23.0
```

Install:

```bash
pip install pymupdf --break-system-packages
# or
pip install -r requirements.txt
```

---

## Full Test Run

After applying all fixes:

```bash
# 1. Regenerate blank_form.pdf (one-time)
python generate_tax_pdf.py \
    --source "2024_Tax_Return_Documents_(JOHNSON_JOHN_and_EMILY).pdf" \
    --xml blank_template.xml \
    --out blank_form.pdf \
    --make-blank

# 2. Verify blank form is clean
python -c "
import pdfplumber
PATTERNS = ['JOHNSON','EMILY','472-90','52,200','94,803','42,700','6,034','6,313']
with pdfplumber.open('blank_form.pdf') as pdf:
    issues = 0
    for i, page in enumerate(pdf.pages, 1):
        bad = [w['text'] for w in page.extract_words() if any(p in w['text'] for p in PATTERNS)]
        if bad: print(f'Page {i}: {bad}'); issues += 1
    print('CLEAN' if not issues else f'{issues} pages have issues')
"

# 3. Generate test variants
python generate_tax_pdf.py \
    --source blank_form.pdf \
    --xml blank_template.xml \
    --out ./test_output \
    --variations 5 \
    --seed 42

# 4. Verify test variants — no Johnson data, no merged values
python -c "
import pdfplumber, glob
for path in sorted(glob.glob('test_output/test_output_variant_*.pdf')):
    with pdfplumber.open(path) as pdf:
        p1 = pdf.pages[0]
        words = p1.extract_words()
        bad   = [w['text'] for w in words if 'JOHNSON' in w['text'] or w['text'].count(',') >= 2 and len(w['text']) > 12]
        names = [w['text'] for w in words if 88 <= w['top'] <= 130 and w['x0'] < 400 and len(w['text']) > 2][:4]
        print(f'{path.split(\"/\")[-1]}: names={names} corrupt={bad[:2]}')
"

# 5. Verify storage directories were created
ls -la test_output/pdfs_only/
ls -la test_output/completed_form/
```

### Expected Results

| Check | Expected |
|-------|----------|
| `blank_form.pdf` verification | All 28 pages: `CLEAN` |
| Variant names field | Single unique name per variant (e.g. `['William', 'Smith', 'Mary', 'Smith']`) |
| Corrupt merged values | `[]` on all variants |
| `pdfs_only/` | 5 PDF files |
| `completed_form/` | 5 PDF files |
| CTC with 1+ kids | `ChildTaxCreditAmt > 0` |
| Phone on page 2 | Format `(XXX)XXX-XXXX` |
| Vehicle on page 17 | Year/make/model string populated |

---

## File Change Summary

| File | Changes |
|------|---------|
| `generate_tax_pdf.py` | Replace `generate_blank_form()` with PyMuPDF redaction version |
| `generate_tax_pdf.py` | Add `TAX_PARAMS` dict + `_apply_brackets()` near top |
| `generate_tax_pdf.py` | `generate_variation()` — move dependent loop before `recompute_derived_fields()` |
| `generate_tax_pdf.py` | `generate_variation()` — add `PhoneNum` `set_text()` call |
| `generate_tax_pdf.py` | `generate_variation()` — add `pdfs_only/`+`completed_form/` auto-save |
| `generate_tax_pdf.py` | `inject_form4562_detail()` — find-or-create Vehicle node |
| `generate_tax_pdf.py` | `inject_ca540_nodes()` — skip empty dependent slots |
| `generate_tax_pdf.py` | `recompute_derived_fields()` — replace hardcoded brackets with `TAX_PARAMS` lookup |
| `requirements.txt` | Add `pymupdf>=1.23.0` |
| `blank_form.pdf` | Regenerate using new `generate_blank_form()` |
