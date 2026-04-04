# Fix Plan: XML → PDF → Dataset Pipeline
**Repository:** `synthetic_dataset_generator`  
**Audit Date:** April 2026  
**Bugs Found:** 6 root-cause defects across 29 affected field positions  

---

## Executive Summary

The pipeline is structurally sound — `blank_form.pdf` exists and overlays render. However, a field-level audit exposes **29 empty/missing data positions** across the generated PDFs, a **CTC/dependent ordering bug** that silently zeroes child tax credits, a **duplicate Vehicle node collision** in `IRS4562`, two **missing storage directories**, and absent `PhoneNum` generation. All fixes are surgical edits to `generate_tax_pdf.py`.

---

## Bug Catalog

### Bug 1 — Dependent Data Injected After Tax Computation (Critical)

**File:** `generate_tax_pdf.py` → `generate_variation()`  
**Lines affected:** ~103 (recompute) vs ~109 (dependent loop)

**Root cause:** `recompute_derived_fields()` reads `EligibleForChildTaxCreditInd` from `DependentDetail` nodes to compute CTC. But the dependent population loop (`for i in range(min(target_kids, len(dep_nodes)))`) runs *after* `recompute_derived_fields()` is called — so dependents are always empty when the CTC is calculated, zeroing it every time.

**Impact:** CTC = `$0` for all generated records regardless of `target_kids`. Fields affected: `ChildTaxCreditAmt`, `TotalCreditsAmt`, `TaxLessCreditsAmt`, `TotalTaxAmt`, `RefundAmt` / `AmountOwedAmt`.

**Fix — Move dependent population before `recompute_derived_fields`:**

```python
# generate_variation() — BEFORE this block:
#   root, computed = recompute_derived_fields(root, ca_wh)

# ADD: populate dependents FIRST
target_kids = rng.choice([0, 1, 2])
dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
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

    _set_sub("DependentFirstNm",            c_first)
    _set_sub("DependentLastNm",             p_last)
    _set_sub("DependentSSN",                c_ssn)
    _set_sub("DependentRelationshipCd",     rng.choice(["DAUGHTER", "SON"]))
    _set_sub("EligibleForChildTaxCreditInd", "X")

num_kids  = target_kids
num_other = max(0, len(dep_nodes) - num_kids)

# THEN call recompute — it will now see the correct dependent data
root, computed = recompute_derived_fields(root, ca_wh)
```

**Also remove** the duplicate dependent loop that currently appears *after* `recompute_derived_fields` (lines ~109–126).

---

### Bug 2 — IRS4562 Vehicle Node Collision / Double-Creation (High)

**File:** `generate_tax_pdf.py` → `inject_form4562_detail()`

**Root cause:** `blank_template.xml` already contains a `<Vehicle seq="1">` node with empty child elements including `<Description/>`, `<DatePlacedInService/>`, `<BusinessUsePct/>`. `inject_form4562_detail()` calls `etree.SubElement(f4562, "Vehicle")` unconditionally, creating a *second* `<Vehicle>` node and then setting `seq="1"` on it. The `add()` helper appends *new* child elements to this second node. Result: two `Vehicle` nodes with `seq="1"`, the first with all-`None` text, the second with correct data — but XPath `[@seq='1']` returns the first (empty) one.

**Impact:** Fields `Description`, `BusinessUsePct`, `DepreciationAllowed` on page 17 are all blank.

**Fix — Replace unconditional SubElement with find-or-create pattern:**

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

    # FIX: find existing Vehicle[@seq='1'] or create it — never duplicate
    existing_veh = f4562.xpath("Vehicle[@seq='1']")
    if existing_veh:
        veh = existing_veh[0]
    else:
        veh = etree.SubElement(f4562, "Vehicle")
        veh.set("seq", "1")

    # Set child text directly on existing or new node
    def _veh_set(tag, val):
        el = veh.find(tag)
        if el is None:
            el = etree.SubElement(veh, tag)
        el.text = str(val)

    _veh_set("Description",       vehicle["description"])
    _veh_set("BusinessUsePct",    vehicle["business_pct"])
    _veh_set("DepreciationAllowed", vehicle["dep_allowed"])

    set_or_add(f4562, "L30_BusinessMiles",      vehicle["business_miles"])
    set_or_add(f4562, "L31_CommutingMiles",     vehicle["commute_miles"])
    set_or_add(f4562, "L32_OtherPersonalMiles", vehicle["personal_miles"])
    set_or_add(f4562, "L33_TotalMiles",         vehicle["total_miles"])
    set_or_add(f4562, "L28_TotalListedPropDep", vehicle["dep_allowed"])
    set_or_add(f4562, "DepreciationAmt",         vehicle["dep_allowed"])
    set_or_add(f4562, "TotalDepreciationAmt",    vehicle["dep_allowed"])

    return root
```

---

### Bug 3 — Missing `set_text()` Calls for Identity Fields (Medium)

**File:** `generate_tax_pdf.py` → `generate_variation()`

**Root cause:** Several fields defined in `FIELD_DEFINITIONS` require data that is never written to the XML in the variation loop. The `set_text()` calls either target an XPath that doesn't match (wrong element name) or are absent entirely.

**Fields affected and their fixes:**

| Page | Field XPath | Fix |
|------|-------------|-----|
| 8 | `IRS1040ScheduleC/ProprietorNm` | `set_text("//Return/ReturnData/IRS1040ScheduleC/ProprietorNm", f"{p_first} {p_last}")` — already present but runs AFTER inject; must run BEFORE |
| 8 | `IRS1040ScheduleC/PrincipalBusinessActivityDesc` | Same: `set_text(...)` before `inject_schedule_c_detail` |
| 8 | `IRS1040ScheduleC/PrincipalBusinessActivityCd` | Same |
| 8 | `IRS1040ScheduleC/BusinessName/BusinessNameLine1Txt` | Same |
| 8 | `IRS1040ScheduleC/BusinessAddressTxt` | Same |
| 2/28 | `ReturnHeader/Filer/PhoneNum` | Add: `set_text("//Return/ReturnHeader/Filer/PhoneNum", f"({rng.randint(200,999)}){rng.randint(200,999)}-{rng.randint(1000,9999)}")` |
| 7 | `IRS1040ScheduleB/InterestPayerName` | Already present but targets wrong node after inject; ensure set_text runs before inject_schedule_c_detail |
| 7 | `IRS1040ScheduleB/DividendPayerName` | Same |

**All `set_text()` identity calls for ScheduleC must run BEFORE `inject_schedule_c_detail()`** since inject uses `set_or_add()` which skips existing non-zero nodes — but text fields are empty strings (falsy), causing them to be skipped on re-inject. Move all these `set_text` calls to the identity block near the top of `generate_variation()`.

**Add PhoneNum generation (missing entirely):**
```python
# Add after EmailAddressTxt line
phone = f"({rng.randint(200,999)}){rng.randint(200,999)}-{rng.randint(1000,9999)}"
set_text("//Return/ReturnHeader/Filer/PhoneNum", phone)
```

---

### Bug 4 — CA540 Dependents Not Propagated (Medium)

**File:** `generate_tax_pdf.py` → `inject_ca540_nodes()`

**Root cause:** `inject_ca540_nodes()` reads `dep_nodes` from the XML at call time. Since the CA540 dependent block (`//Return/ReturnData/CA540/Dependents/Dependent[@seq='N']`) is built from the federal `DependentDetail` nodes, this only works correctly if dependents are already populated before `inject_ca540_nodes()` is called.

Due to Bug 1 (now fixed by moving dep population earlier), this will auto-resolve once the ordering is corrected. However, the CA540 dependent copy also fails silently when `dep.findtext()` returns `None` for empty template nodes — add a guard:

```python
# In inject_ca540_nodes(), the dependent loop:
for i, dep in enumerate(dep_nodes[:2], start=1):
    d = etree.SubElement(deps_el, "Dependent")
    d.set("seq", str(i))
    first = dep.findtext("DependentFirstNm") or ""
    last  = dep.findtext("DependentLastNm")  or ""
    ssn   = dep.findtext("DependentSSN")     or ""
    # FIX: only write non-empty values
    if first or last:                    # skip unpopulated template slots
        add(d, "FirstName",  first)
        add(d, "LastName",   last)
        add(d, "SSN",        ssn)
```

---

### Bug 5 — Missing Storage Directories (`pdfs_only/`, `completed_form/`) (Medium)

**File:** `generate_tax_pdf.py` — `generate_variation()` and `main()`

**Root cause:** Neither `pdfs_only/` nor `completed_form/` directories exist or are created anywhere in the codebase. The requirement specifies:
- `pdfs_only/` — intermediate per-record PDFs saved here
- `completed_form/` — final validated PDFs saved here

**Fix — Add auto-creation and dual-save to `generate_variation()`:**

```python
import os, shutil
from pathlib import Path

def generate_variation(source_pdf: str, output_path: str, seed: int,
                       pdfs_only_dir: str = "pdfs_only",
                       completed_dir:  str = "completed_form"):
    """
    ... existing docstring ...
    Saves intermediate PDF to pdfs_only/ and final copy to completed_form/.
    """
    os.makedirs(pdfs_only_dir, exist_ok=True)
    os.makedirs(completed_dir,  exist_ok=True)

    # ... all existing logic unchanged ...

    # At end, after generate_pdf(..., output_path):
    filename = Path(output_path).name

    # Save to pdfs_only/ (post-overlay, pre-validation copy)
    pdfs_only_path = os.path.join(pdfs_only_dir, filename)
    shutil.copy2(output_path, pdfs_only_path)

    # Save to completed_form/ (final validated copy)
    completed_path = os.path.join(completed_dir, filename)
    shutil.copy2(output_path, completed_path)

    print(f"  ✓ pdfs_only/   → {pdfs_only_path}")
    print(f"  ✓ completed_form/ → {completed_path}")
```

**Also update `main()` to pass directories through:**
```python
if args.variations > 0:
    for i in range(args.variations):
        variant_path = out_path / f"test_output_variant_{i+1:03d}.pdf"
        generate_variation(
            args.source, str(variant_path), seed=args.seed + i,
            pdfs_only_dir=str(out_path / "pdfs_only"),
            completed_dir=str(out_path / "completed_form"),
        )
```

---

### Bug 6 — Quant Consistency: `recompute_derived_fields` Uses Hardcoded MFJ Brackets (Low/Correctness)

**File:** `generate_tax_pdf.py` → `recompute_derived_fields()`

**Root cause:** `tax_mfj_2024()` inside `recompute_derived_fields` is hardcoded for Married Filing Jointly 2024 standard deduction ($29,200) and brackets. When generating multi-year or non-MFJ profiles this produces incorrect tax amounts, breaking numerical parity between the XML dataset values and the overlaid PDF fields.

**Fix — Parameterise by filing status and tax year:**

```python
TAX_PARAMS = {
    2024: {
        "mfj":    {"std_ded": 29200, "brackets": [(23200,0.10),(94300,0.12),(201050,0.22),(383900,0.24),(487450,0.32),(731200,0.35),(float("inf"),0.37)]},
        "single": {"std_ded": 14600, "brackets": [(11600,0.10),(47150,0.12),(100525,0.22),(191950,0.24),(243725,0.32),(609350,0.35),(float("inf"),0.37)]},
        "hoh":    {"std_ded": 21900, "brackets": [(16550,0.10),(63100,0.12),(100500,0.22),(191950,0.24),(243700,0.32),(609350,0.35),(float("inf"),0.37)]},
    },
    2023: {
        "mfj":    {"std_ded": 27700, "brackets": [(22000,0.10),(89075,0.12),(190750,0.22),(364200,0.24),(462500,0.32),(693750,0.35),(float("inf"),0.37)]},
        "single": {"std_ded": 13850, "brackets": [(11000,0.10),(44725,0.12),(95375,0.22),(182050,0.24),(231250,0.32),(578125,0.35),(float("inf"),0.37)]},
        "hoh":    {"std_ded": 20800, "brackets": [(15700,0.10),(59850,0.12),(95350,0.22),(182050,0.24),(231250,0.32),(578100,0.35),(float("inf"),0.37)]},
    },
}

def _apply_brackets(income, brackets):
    tax, prev = 0, 0
    for limit, rate in brackets:
        seg = min(income, limit) - prev
        if seg <= 0:
            break
        tax += int(seg * rate)
        prev = limit
    return tax
```

Replace the hardcoded `tax_mfj_2024(l15)` call with:
```python
year           = int(xget(root, "//Return/ReturnHeader/TaxYr") or "2024")
filing_cd      = xget(root, "//Return/ReturnData/IRS1040/IndividualReturnFilingStatusCd") or "2"
filing_key     = {"1": "single", "2": "mfj", "4": "hoh"}.get(filing_cd, "mfj")
params         = TAX_PARAMS.get(year, TAX_PARAMS[2024]).get(filing_key, TAX_PARAMS[2024]["mfj"])
standard_ded   = params["std_ded"]
l16            = _apply_brackets(l15, params["brackets"])
```

---

## Corrected Execution Order in `generate_variation()`

```
1.  Load blank_template.xml
2.  Set identity fields (names, SSNs, address, phone, email)          ← Bug 3 fix
3.  Set ScheduleC identity fields (ProprietorNm, BusinessName, etc.)  ← Bug 3 fix
4.  Set ScheduleB payer names
5.  Set IRSW2 identity fields + occupation
6.  Populate dependent nodes (DependentDetail loop)                   ← Bug 1 fix (moved up)
7.  Set raw income values (W2, gross_rev, withholding)
8.  Call recompute_derived_fields()  → now sees correct dep data       ← Bug 1 fix
9.  inject_schedule_c_detail()
10. inject_schedule_se_detail()
11. inject_form8995_detail()
12. inject_schedule8812_detail()
13. inject_schedule8812_part2()
14. inject_ca540_nodes()             → now sees correct dep data       ← Bug 4 auto-fix
15. inject_voucher_nodes()
16. inject_form4562_detail()         → find-or-create Vehicle node     ← Bug 2 fix
17. inject_preparer_node()
18. Write temp XML → generate_pdf() → output PDF
19. Copy to pdfs_only/ and completed_form/                             ← Bug 5 fix
```

---

## Validation Checklist (Post-Fix)

Run after applying all fixes:

```bash
python generate_tax_pdf.py \
  --source blank_form.pdf \
  --xml    blank_template.xml \
  --out    /tmp/test_single.pdf

python generate_tax_pdf.py \
  --source blank_form.pdf \
  --out    ./output_test \
  --variations 3 \
  --seed 42
```

Expected outcomes:
- [ ] `pdfs_only/` and `completed_form/` directories created automatically
- [ ] 3 PDFs generated with zero empty fields in the 29 previously failing positions
- [ ] CTC > 0 for records with `target_kids ≥ 1`
- [ ] Page 17 vehicle description renders correctly
- [ ] Phone number visible on pages 2 and 28
- [ ] CA540 dependents on page 24 match federal Form 1040 dependents
- [ ] `TotalTaxAmt = TaxAmt + OtherTaxesAmt - TotalCreditsAmt + ACTC` (verified numerically)

---

## File Change Summary

| File | Change Type | Scope |
|------|-------------|-------|
| `generate_tax_pdf.py` | Move code block | Dependent loop before `recompute_derived_fields()` |
| `generate_tax_pdf.py` | Rewrite function | `inject_form4562_detail()` — find-or-create Vehicle |
| `generate_tax_pdf.py` | Add lines | `PhoneNum` generation in `generate_variation()` |
| `generate_tax_pdf.py` | Add guard | `inject_ca540_nodes()` — skip empty dep slots |
| `generate_tax_pdf.py` | Add dirs + copy | `generate_variation()` — pdfs_only/ + completed_form/ |
| `generate_tax_pdf.py` | Add constants | `TAX_PARAMS`, `_apply_brackets()` for multi-year support |
| `generate_tax_pdf.py` | Replace call | `tax_mfj_2024(l15)` → `_apply_brackets(l15, params["brackets"])` |
