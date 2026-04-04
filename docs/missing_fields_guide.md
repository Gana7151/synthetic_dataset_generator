# Missing Field Detection & Quant Model Imputation Guide

**For:** Synthetic Tax Return Dataset Generation Pipeline  
**Works with:** `generate_tax_pdf.py` + `johnson_2024_tax_return.xml`

---

## The Core Problem

When `generate_tax_pdf.py` runs, it places text at hard-coded `(x, top)` coordinates defined in `FIELD_DEFINITIONS`. If a field is missing in the output PDF, one of three things is happening:

1. **The XPath returns empty** — the value doesn't exist in the XML
2. **The coordinate is wrong** — the text is placed outside the visible area
3. **The value is blank/zero** — it was suppressed because `fmt_money("0")` returns `"0"` but the field logic skips empty strings

This guide covers how to catch all three, and how to use quant models to fill the gaps intelligently rather than using random noise.

---

## Step 1: Run the Missing Field Detector

Run this before generating any synthetic batch. It tells you exactly which XML paths are returning empty across the field map.

```bash
python3 - << 'EOF'
from lxml import etree
from generate_tax_pdf import FIELD_DEFINITIONS, CHECKBOX_DEFINITIONS, xget

root = etree.parse("johnson_2024_tax_return.xml").getroot()
missing = []

for (page, xpath, x, top, font_size, formatter) in FIELD_DEFINITIONS:
    val = xget(root, xpath)
    if not val:
        missing.append((page, xpath, x, top))

print(f"\n{'─'*60}")
print(f"MISSING FIELDS: {len(missing)} / {len(FIELD_DEFINITIONS)} total")
print(f"{'─'*60}")
for page, xpath, x, top in sorted(missing):
    print(f"  Page {page:>2}  x={x:<7.1f}  top={top:<7.1f}  {xpath}")
EOF
```

Save this output — it becomes your imputation task list.

---

## Step 2: Visual Coordinate Verification

For each field that *is* populated but not appearing in the output, the coordinate may be off. Use this to extract PNGs and check:

```bash
# Install poppler if needed: apt install poppler-utils
pdftoppm -r 150 output_synthetic.pdf /tmp/verify_pages

# Then open /tmp/verify_pages-01.ppm through -28.ppm
# and compare against the known-good original PDF
```

Or use the skill script:

```bash
python /mnt/skills/public/pdf/scripts/convert_pdf_to_images.py \
    output_synthetic.pdf /tmp/verify_images/
```

Then zoom into suspicious areas using ImageMagick:

```bash
# Crop around a specific coordinate region (x=480, top=430, width=120, height=20)
# PDF top coord → pixel: pixel_y = top * (image_height / page_height)
magick /tmp/verify_images/page_01.png \
    -crop 120x20+480+430 +repage /tmp/crop_check.png
```

For any field that is visually misaligned, update its `top` value in `FIELD_DEFINITIONS` in steps of ±2pt until it lands correctly.

---

## Step 3: Quant Model Imputation Strategy

Instead of filling missing/perturbed fields with random numbers (which creates unrealistic returns), use **constraint-based quant models** that respect IRS arithmetic identities.

### 3.1 — The Tax Identity Graph

Every line on a 1040 is connected. These are the hard constraints:

```
L9  = L1z + L2b + L3b + L4b + L5b + L6b + L7 + L8
L11 = L9 - L10
L14 = L12 + L13
L15 = L11 - L14
L18 = L16 + L17
L21 = L19 + L20
L22 = L18 - L21       (if > 0)
L24 = L22 + L23
L33 = L25d + L26 + L32
L34 = L33 - L24       (if L33 > L24)
L37 = L24 - L33       (if L24 > L33)
```

**Rule:** When you generate a synthetic variant, vary the *leaf inputs* (wages, business income, interest) and then recompute all derived fields using these identities. Never vary a derived field independently — it will create an arithmetically inconsistent return, which is detectable and useless for training.

### 3.2 — Recompute All Derived Fields in Python

Add this function to your synthetic variation pipeline. Call it after perturbing leaf inputs and before generating the PDF:

```python
def recompute_derived_fields(root):
    """
    Enforce IRS arithmetic identities across the XML tree.
    Call this after perturbing any leaf values.
    """
    def g(xpath):
        nodes = root.xpath(xpath)
        return int((nodes[0].text or "0").replace(",", "")) if nodes else 0

    def s(xpath, val):
        nodes = root.xpath(xpath)
        if nodes:
            nodes[0].text = str(max(0, val))

    # ── Form 1040 Income ──────────────────────────────────────
    w2         = g("//Form1040/Income/L1a_WagesW2")
    interest   = g("//Form1040/Income/L2b_TaxableInterest")
    dividends  = g("//Form1040/Income/L3b_OrdinaryDividends")
    biz_income = g("//Schedule1/Part1_AdditionalIncome/L3_BusinessIncomeScheduleC")
    cap_gain   = g("//Form1040/Income/L7_CapitalGainLoss")

    l1z  = w2
    l8   = biz_income
    l9   = l1z + interest + dividends + l8 + cap_gain

    s("//Form1040/Income/L1z_TotalWages",              l1z)
    s("//Form1040/Income/L8_AdditionalIncomeSchedule1", l8)
    s("//Form1040/Income/L9_TotalIncome",               l9)
    s("//Schedule1/Part1_AdditionalIncome/L10_TotalAdditionalIncome", l8)

    # ── Self-Employment Tax (Schedule SE) ─────────────────────
    se_net       = biz_income
    se_taxable   = int(se_net * 0.9235)
    se_ss_tax    = int(min(se_taxable, 168600) * 0.124)
    se_med_tax   = int(se_taxable * 0.029)
    se_total     = se_ss_tax + se_med_tax
    se_deduction = int(se_total * 0.50)

    s("//ScheduleSE/Part1_SelfEmploymentTax/L2_NetProfitScheduleC",   se_net)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L3_CombinedLines",        se_net)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L4a_Multiply_9235",       se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L4c_Combined",            se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L6_AddLines4c5b",         se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L9_Subtract8dFrom7",      se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L10_Multiply_124",        se_ss_tax)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L11_Multiply_029",        se_med_tax)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L12_SelfEmploymentTax",   se_total)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L13_DeductionHalfSETax",  se_deduction)
    s("//Schedule2/Part2_OtherTaxes/L4_SelfEmploymentTax",            se_total)
    s("//Schedule2/Part2_OtherTaxes/L21_TotalOtherTaxes",             se_total)
    s("//Schedule1/Part2_AdjustmentsToIncome/L15_SelfEmploymentTaxDeduction", se_deduction)
    s("//Schedule1/Part2_AdjustmentsToIncome/L26_TotalAdjustments",   se_deduction)

    # ── AGI ───────────────────────────────────────────────────
    l10 = se_deduction
    l11 = max(0, l9 - l10)
    s("//Form1040/AGI/L10_AdjustmentsSchedule1",    l10)
    s("//Form1040/AGI/L11_AdjustedGrossIncome",     l11)

    # ── QBI Deduction (Form 8995) ─────────────────────────────
    qbi_income      = int(biz_income * (se_taxable / se_net)) if se_net else 0
    qbi_component   = int(qbi_income * 0.20)
    standard_ded    = 29200  # MFJ 2024
    taxable_b4_qbi  = max(0, l11 - standard_ded)
    income_limit    = int(taxable_b4_qbi * 0.20)
    qbi_deduction   = min(qbi_component, income_limit)

    s("//Form8995/QBITrades/Trade[@seq='1']/QBIAmount",       qbi_income)
    s("//Form8995/L2_TotalQBI",                               qbi_income)
    s("//Form8995/L4_TotalQBIAfterCarryforward",              qbi_income)
    s("//Form8995/L5_QBIComponent_20pct",                     qbi_component)
    s("//Form8995/L10_QBIDeductionBeforeLimit",               qbi_component)
    s("//Form8995/L11_TaxableIncomeBeforeQBI",                l11)
    s("//Form8995/L13_L11MinusL12",                           taxable_b4_qbi)
    s("//Form8995/L14_IncomeLimitation",                      income_limit)
    s("//Form8995/L15_QBIDeduction",                          qbi_deduction)
    s("//Form1040/TaxableIncome/L13_QBIDeductionForm8995",    qbi_deduction)

    # ── Taxable Income ────────────────────────────────────────
    l12  = standard_ded
    l13  = qbi_deduction
    l14  = l12 + l13
    l15  = max(0, l11 - l14)

    s("//Form1040/TaxableIncome/L12_StandardOrItemizedDeduction", l12)
    s("//Form1040/TaxableIncome/L14_TotalDeductions",             l14)
    s("//Form1040/TaxableIncome/L15_TaxableIncome",               l15)

    # ── Federal Income Tax (2024 MFJ brackets) ───────────────
    def tax_mfj_2024(income: int) -> int:
        brackets = [
            (23200,   0.10),
            (94300,   0.12),
            (201050,  0.22),
            (383900,  0.24),
            (487450,  0.32),
            (731200,  0.35),
            (float("inf"), 0.37),
        ]
        tax, prev = 0, 0
        for limit, rate in brackets:
            taxable_in_bracket = min(income, limit) - prev
            if taxable_in_bracket <= 0:
                break
            tax += int(taxable_in_bracket * rate)
            prev = limit
        return tax

    l16  = tax_mfj_2024(l15)
    l17  = 0  # Schedule 2 Part I (AMT etc.) — 0 for most filers
    l18  = l16 + l17

    # CTC: $2,000 per qualifying child under 17, phaseout above $400,000 MFJ
    num_kids     = int(g("//Schedule8812/Part1_ChildTaxCredit/L4_QualifyingChildrenUnder17") or 0)
    num_other    = int(g("//Schedule8812/Part1_ChildTaxCredit/L6_OtherDependents") or 0)
    ctc_raw      = num_kids * 2000 + num_other * 500
    phaseout_exc = max(0, l11 - 400000)
    phaseout_red = int(((phaseout_exc + 999) // 1000) * 1000 * 0.05)
    ctc          = max(0, ctc_raw - phaseout_red)
    ctc_used     = min(ctc, l18)

    s("//Schedule8812/Part1_ChildTaxCredit/L5_Multiply2000",          num_kids * 2000)
    s("//Schedule8812/Part1_ChildTaxCredit/L7_Multiply500",           num_other * 500)
    s("//Schedule8812/Part1_ChildTaxCredit/L8_AddLines5_7",           ctc_raw)
    s("//Schedule8812/Part1_ChildTaxCredit/L12_CreditAfterPhaseout",  ctc)
    s("//Schedule8812/Part1_ChildTaxCredit/L14_ChildTaxCredit",       ctc_used)
    s("//Form1040/TaxAndCredits/L16_Tax",                             l16)
    s("//Form1040/TaxAndCredits/L18_TotalTax",                        l18)
    s("//Form1040/TaxAndCredits/L19_ChildTaxCreditSchedule8812",      ctc_used)
    s("//Form1040/TaxAndCredits/L21_TotalCredits",                    ctc_used)
    s("//Form1040/TaxAndCredits/L22_TaxAfterCredits",                 max(0, l18 - ctc_used))
    s("//Form1040/TaxAndCredits/L23_OtherTaxesSchedule2",             se_total)
    l24 = max(0, l18 - ctc_used) + se_total
    s("//Form1040/TaxAndCredits/L24_TotalTax",                        l24)

    # ── Payments & Refund ─────────────────────────────────────
    withheld = g("//Form1040/Payments/L25a_FederalWithheldW2")
    s("//Form1040/Payments/L25d_TotalFederalWithheld", withheld)
    s("//Form1040/Payments/L33_TotalPayments",         withheld)

    if withheld >= l24:
        refund = withheld - l24
        owed   = 0
    else:
        refund = 0
        owed   = l24 - withheld

    s("//Form1040/RefundOrOwed/L34_Overpaid",    refund)
    s("//Form1040/RefundOrOwed/L35a_RefundAmount", refund)
    s("//Form1040/RefundOrOwed/L37_AmountOwed",  owed)

    # ── 1040-V Payment Voucher ────────────────────────────────
    s("//Form1040V/PaymentAmount", owed)

    # ── CA 540 (simplified — real CA tax uses FTB tables) ────
    # CA standard deduction: MFJ = $11,080 (2024)
    ca_std  = 11080
    ca_agi  = l11
    ca_ti   = max(0, ca_agi - ca_std)
    # Rough CA tax (rate schedule, simplified):
    ca_brackets = [
        (20824,   0.01), (49368,   0.02), (77918,   0.04),
        (108162,  0.06), (136700,  0.08), (698274,  0.093),
        (float("inf"), 0.103),
    ]
    ca_tax, prev = 0, 0
    for limit, rate in ca_brackets:
        seg = min(ca_ti, limit) - prev
        if seg <= 0: break
        ca_tax += int(seg * rate)
        prev = limit

    ca_exempt = g("//CA540/L11_TotalExemptionCredits") or 1220
    ca_tax_after = max(0, ca_tax - ca_exempt)
    ca_withheld  = g("//CA540/Payments/L71_CAWithheld")
    ca_refund    = max(0, ca_withheld - ca_tax_after)
    ca_owed      = max(0, ca_tax_after - ca_withheld)

    s("//CA540/TaxableIncome/L13_FederalAGI",             ca_agi)
    s("//CA540/TaxableIncome/L15_AfterSubtractions",      ca_agi)
    s("//CA540/TaxableIncome/L17_CAAdjustedGrossIncome",  ca_agi)
    s("//CA540/TaxableIncome/L18_Deduction",              ca_std)
    s("//CA540/TaxableIncome/L19_TaxableIncome",          ca_ti)
    s("//CA540/Tax/L31_TaxFromTable",                     ca_tax)
    s("//CA540/Tax/L33_TaxAfterExemptionCredits",         ca_tax_after)
    s("//CA540/Tax/L35_TotalTax",                         ca_tax_after)
    s("//CA540/SpecialCredits/L48_TaxAfterCredits",       ca_tax_after)
    s("//CA540/OtherTaxes/L64_TotalTax",                  ca_tax_after)
    s("//CA540/Payments/L78_TotalPayments",               ca_withheld)
    s("//CA540/UseAndPenalty/L93_PaymentsAfterISR",       ca_withheld)
    s("//CA540/UseAndPenalty/L95_PaymentsBalance",        ca_withheld)
    s("//CA540/RefundOrOwed/L96_OverpaidTax",             ca_refund)
    s("//CA540/RefundOrOwed/L97_OverpaidTaxAvailable",    ca_refund)
    s("//CA540/RefundOrOwed/L99_RefundAvailable",         ca_refund)
    s("//CA540/AmountOwedOrRefund/L115_Refund",           ca_refund)
    s("//CA540/RefundOrOwed/L100_TaxDue",                 ca_owed)

    return root
```

Plug this into `generate_variation()` in `generate_tax_pdf.py`:

```python
# In generate_variation(), after perturbing leaf inputs, add:
root = recompute_derived_fields(root)
```

---

## Step 4: Fields That Still Need Quant Attention

These are the fields most likely to be blank or wrong after basic generation. They require domain-specific models, not simple arithmetic.

### 4.1 — Schedule C Expense Breakdown

The current generator perturbs `L1_GrossReceipts` but does NOT automatically re-scale individual expense lines. A real return has expenses that correlate with revenue.

**Fix — use expense ratio distributions from IRS Statistics of Income data:**

| Expense Category | Typical % of Gross Revenue | IRS SOI Reference |
|---|---|---|
| Advertising | 1–5% | SOI Table 3, NAICS 541510 |
| Rent/Lease | 10–30% | SOI Table 3 |
| Supplies | 1–3% | SOI Table 3 |
| Meals (deductible) | 0.5–2% | SOI Table 3 |
| Depreciation | 1–4% | SOI Table 3 |
| Other Expenses | 1–5% | SOI Table 3 |

```python
def generate_schedule_c_expenses(gross_revenue: int, rng: random.Random) -> dict:
    """Generate realistic correlated expense lines from gross revenue."""
    ratios = {
        "L8_Advertising":            rng.uniform(0.01, 0.05),
        "L18_OfficeExpense":         rng.uniform(0.02, 0.06),
        "L20b_RentLeaseOtherProperty": rng.uniform(0.10, 0.30),
        "L22_Supplies":              rng.uniform(0.01, 0.03),
        "L23_TaxesLicenses":         rng.uniform(0.005, 0.02),
        "L24b_DeductibleMeals":      rng.uniform(0.005, 0.015),
        "L13_DepreciationSection179": rng.uniform(0.01, 0.04),
    }
    expenses = {k: int(gross_revenue * v) for k, v in ratios.items()}
    expenses["L27a_OtherExpenses_Total"] = int(gross_revenue * rng.uniform(0.01, 0.05))
    expenses["L28_TotalExpensesBeforeHome"] = sum(expenses.values())
    expenses["L31_NetProfitLoss"] = max(0, gross_revenue - expenses["L28_TotalExpensesBeforeHome"])
    return expenses
```

### 4.2 — Interest and Dividend Amounts

These should scale with plausible portfolio size. A household earning $90–120K AGI typically holds $50K–$200K in taxable investments.

```python
def generate_investment_income(agi: int, rng: random.Random) -> dict:
    portfolio = agi * rng.uniform(0.5, 2.0)   # rough portfolio estimate
    interest  = int(portfolio * rng.uniform(0.005, 0.025))  # HYSA / CDs
    dividends = int(portfolio * rng.uniform(0.01, 0.03))    # equity funds
    return {
        "L2b_TaxableInterest": interest,
        "L3b_OrdinaryDividends": dividends,
    }
```

### 4.3 — Withholding Amounts

W-2 withholding should reflect the effective tax rate, not be arbitrary. A common pattern is under-withholding by 5–15% when there is self-employment income (since SE income has no withholding).

```python
def generate_withholding(w2_wages: int, expected_total_tax: int, rng: random.Random) -> int:
    # Employer withholds based on W-2 wages only
    w2_fraction = rng.uniform(0.85, 0.95)  # slight under-withholding
    estimated_w2_tax = int(w2_wages * 0.18)  # rough effective rate
    return int(estimated_w2_tax * w2_fraction)
```

### 4.4 — CA State Withholding

CA SDI + income tax withholding on W-2 wages. Rough estimate: 6–9% of W-2 wages for this income range.

```python
def generate_ca_withholding(w2_wages: int, rng: random.Random) -> int:
    rate = rng.uniform(0.06, 0.09)
    return int(w2_wages * rate)
```

---

## Step 5: Realistic Variation Boundaries

These are hard limits — going outside them creates detectable synthetic artifacts:

| Field | Realistic Range | Why |
|---|---|---|
| W-2 Wages | $30,000 – $300,000 | SOI wage distribution |
| Schedule C Gross Revenue | $20,000 – $500,000 | SOI self-employment |
| Net Profit Margin (Sched C) | 30% – 70% | SOI profit ratios by NAICS |
| AGI | W-2 + SE net – SE deduction | Must follow identity |
| Federal effective rate | 8% – 28% | Bracket math |
| CA effective rate | 3% – 10% | CA bracket math |
| CTC per child | $0 – $2,000 | Phaseout above $400K MFJ |
| SE tax rate on net SE | ~14.13% | Fixed by law |

---

## Step 6: Full Pipeline Integration

After completing the above, your full synthetic generation loop looks like:

```python
from generate_tax_pdf import load_xml, generate_pdf
# from your_recompute_module import recompute_derived_fields

for i in range(N_VARIANTS):
    root = load_xml("johnson_2024_tax_return.xml")

    # 1. Randomise identity fields (names, SSN, address)
    root = randomise_identity(root, seed=i)

    # 2. Generate correlated leaf inputs
    w2        = random.randint(30000, 150000)
    gross_rev = random.randint(30000, 200000)
    root      = set_leaf_inputs(root, w2, gross_rev)

    # 3. Recompute ALL derived fields using tax math
    root = recompute_derived_fields(root)

    # 4. Write XML → generate PDF
    save_xml(root, f"/tmp/variant_{i}.xml")
    generate_pdf(f"/tmp/variant_{i}.xml", "source_template.pdf", f"output/variant_{i:04d}.pdf")
```

---

## Quick Reference: Which Fields Are Derived vs. Leaf

### Leaf Inputs (vary these, never the derived fields)

- `//Form1040/Income/L1a_WagesW2` — W-2 wages
- `//ScheduleC/Part1_Income/L1_GrossReceipts` — business revenue
- `//Form1040/Income/L2b_TaxableInterest` — bank interest
- `//Form1040/Income/L3b_OrdinaryDividends` — dividends
- `//CA540/Payments/L71_CAWithheld` — CA withholding
- `//Form1040/Payments/L25a_FederalWithheldW2` — federal withholding
- Individual Schedule C expense lines (L8, L18, L20b, L22, L23, L24b)

### Derived Fields (always recompute, never perturb directly)

All other fields in Form 1040 lines 1z, 8–15, 16–24, 25d, 33–37.  
All Schedule SE lines 3, 4a, 4c, 6, 9, 10, 11, 12, 13.  
All Schedule 1 lines 10, 26.  
All Form 8995 lines 2, 4, 5, 10, 13, 14, 15.  
All Schedule 8812 lines 5, 7, 8, 12, 14.  
All CA 540 lines 15, 17, 18, 19, 31, 33, 35, 48, 64, 78, 93, 95, 96, 97, 99, 115.

---

## Checklist Before Running Batch

- [ ] Run missing field detector (Step 1) — fix all empty XPaths in `FIELD_DEFINITIONS`
- [ ] Run visual check on single output (Step 2) — fix misaligned coordinates  
- [ ] Plug `recompute_derived_fields()` into `generate_variation()` (Step 3)
- [ ] Set Schedule C expense ratios using `generate_schedule_c_expenses()` (Step 4.1)
- [ ] Set withholding using `generate_withholding()` (Step 4.3)
- [ ] Confirm all output amounts stay within realistic boundaries (Step 5)
- [ ] Verify 3–5 sample PDFs visually before generating full batch
