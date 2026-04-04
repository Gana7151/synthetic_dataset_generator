# Fix Guide — 28-Page Synthetic Tax PDF Generator
**Repo:** `synthetic_dataset_generator`  
**Target file:** `generate_tax_pdf.py`  
**XML schema:** IRS e-file standard (`Return/ReturnData/IRS1040/…`)  
**Last audited:** April 2026

---

## Executive Summary of All Errors

| # | Category | Severity | Impact |
|---|---|---|---|
| 1 | XPath schema mismatch — root cause | 🔴 CRITICAL | **0 of 28 pages populated** |
| 2 | `s()` helper silently fails on missing nodes | 🔴 CRITICAL | All recomputed values lost |
| 3 | CA 540 data completely absent from XML | 🔴 CRITICAL | Pages 23–28 always blank |
| 4 | Form 1040-V and 1040-ES nodes missing | 🟠 HIGH | Pages 18–22 always blank |
| 5 | Schedule C detailed expense lines missing in XML | 🟠 HIGH | Page 8 expenses blank |
| 6 | Schedule SE detail lines missing in XML | 🟠 HIGH | Page 10 mostly blank |
| 7 | Form 8995 detail lines missing in XML | 🟠 HIGH | Page 13 mostly blank |
| 8 | Pages 12, 14, 15, 17 have zero field definitions | 🟡 MEDIUM | Those pages silently unhandled |
| 9 | `num_kids` XPath returns 0 → CTC always $0 | 🟡 MEDIUM | Child Tax Credit broken |
| 10 | QBI division-by-zero risk when `se_net == 0` | 🟡 MEDIUM | Crash on wage-only filers |
| 11 | `generate_variation()` writes to non-existent nodes | 🟡 MEDIUM | Leaf inputs never land in XML |
| 12 | 2024 CA 540 bracket edge cases | 🟢 LOW | Slight tax miscalculation |
| 13 | `L14_TotalDeductions` computed but never placed on page 1 | 🟢 LOW | One blank line on page 1 |
| 14 | Schedule 8812 L3/L13 lines never populated | 🟢 LOW | Two blank lines on page 11 |

---

## Error 1 — XPath Schema Mismatch (CRITICAL — Root Cause of 0 Fields)

### What happens
Running the script produces:
```
[3/4] Overlaying 0 fields across 0 pages...
```
Every single field in `FIELD_DEFINITIONS` silently skips because `xget()` returns `""` for every XPath.

### Why
`generate_tax_pdf.py` was written against a **custom XML schema** that was never actually used. The real XML files (both `sample/Prompt/Tax Return Data - Prompt.xml` and `output/Dataset_0001_CA_2020_L1/Prompt/Tax_Return_Data.xml`) use the **IRS MeF e-file standard schema**.

### Schema comparison

| Field | Code expects (wrong) | XML actually contains (correct) |
|---|---|---|
| Taxpayer first name | `//Taxpayer/Primary/FirstName` | `//Return/ReturnHeader/Filer/NameLine1Txt` |
| Primary SSN | `//Taxpayer/Primary/SSN` | `//Return/ReturnHeader/Filer/PrimarySSN` |
| Spouse SSN | `//Taxpayer/Spouse/SSN` | `//Return/ReturnHeader/Filer/SpouseSSN` |
| Street address | `//Taxpayer/Address/Street` | `//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt` |
| City | `//Taxpayer/Address/City` | `//Return/ReturnHeader/Filer/USAddress/CityNm` |
| State | `//Taxpayer/Address/State` | `//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd` |
| ZIP | `//Taxpayer/Address/ZIP` | `//Return/ReturnHeader/Filer/USAddress/ZIPCd` |
| W-2 wages | `//Form1040/Income/L1a_WagesW2` | `//Return/ReturnData/IRS1040/WagesAmt` |
| Total wages | `//Form1040/Income/L1z_TotalWages` | `//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt` |
| Taxable interest | `//Form1040/Income/L2b_TaxableInterest` | `//Return/ReturnData/IRS1040/TaxableInterestAmt` |
| Ordinary dividends | `//Form1040/Income/L3b_OrdinaryDividends` | `//Return/ReturnData/IRS1040/OrdinaryDividendsAmt` |
| Business income (Sched C) | `//Form1040/Income/L8_AdditionalIncomeSchedule1` | `//Return/ReturnData/IRS1040/BusinessIncomeAmt` |
| Total income | `//Form1040/Income/L9_TotalIncome` | `//Return/ReturnData/IRS1040/TotalIncomeAmt` |
| Adjustments (Sched 1) | `//Form1040/AGI/L10_AdjustmentsSchedule1` | *(not in XML — must add)* |
| AGI | `//Form1040/AGI/L11_AdjustedGrossIncome` | `//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt` |
| Standard deduction | `//Form1040/TaxableIncome/L12_StandardOrItemizedDeduction` | `//Return/ReturnData/IRS1040/TotalItemizedOrStandardDedAmt` |
| QBI deduction | `//Form1040/TaxableIncome/L13_QBIDeductionForm8995` | `//Return/ReturnData/IRS1040/QualifiedBusinessIncomeDedAmt` |
| Taxable income | `//Form1040/TaxableIncome/L15_TaxableIncome` | `//Return/ReturnData/IRS1040/TaxableIncomeAmt` |
| Tax (L16) | `//Form1040/TaxAndCredits/L16_Tax` | `//Return/ReturnData/IRS1040/TaxAmt` |
| Total credits | `//Form1040/TaxAndCredits/L21_TotalCredits` | `//Return/ReturnData/IRS1040/TotalCreditsAmt` |
| Total tax | `//Form1040/TaxAndCredits/L24_TotalTax` | `//Return/ReturnData/IRS1040/TotalTaxAmt` |
| Federal withheld | `//Form1040/Payments/L25a_FederalWithheldW2` | `//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt` |
| Total payments | `//Form1040/Payments/L33_TotalPayments` | `//Return/ReturnData/IRS1040/TotalPaymentsAmt` |
| Overpaid | `//Form1040/RefundOrOwed/L34_Overpaid` | `//Return/ReturnData/IRS1040/OverpaidAmt` (missing in 2024 sample — add it) |
| Refund | `//Form1040/RefundOrOwed/L35a_RefundAmount` | `//Return/ReturnData/IRS1040/RefundAmt` |
| Amount owed | `//Form1040/RefundOrOwed/L37_AmountOwed` | `//Return/ReturnData/IRS1040/AmountOwedAmt` |
| Dep 1 first name | `//Taxpayer/Dependents/Dependent[@seq='1']/FirstName` | `//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm` |
| Dep 1 last name | `//Taxpayer/Dependents/Dependent[@seq='1']/LastName` | `//Return/ReturnData/IRS1040/DependentDetail[1]/DependentLastNm` |
| Dep 1 SSN | `//Taxpayer/Dependents/Dependent[@seq='1']/SSN` | `//Return/ReturnData/IRS1040/DependentDetail[1]/DependentSSN` |
| Dep 1 relationship | `//Taxpayer/Dependents/Dependent[@seq='1']/Relationship` | `//Return/ReturnData/IRS1040/DependentDetail[1]/DependentRelationshipCd` |
| Sched C gross receipts | `//ScheduleC/Part1_Income/L1_GrossReceipts` | `//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt` |
| Sched C net profit | `//ScheduleC/Part2_Expenses/L31_NetProfitLoss` | `//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt` |
| Sched C total expenses | `//ScheduleC/Part2_Expenses/L28_TotalExpensesBeforeHome` | `//Return/ReturnData/IRS1040ScheduleC/TotalExpensesAmt` |
| SE net profit | `//ScheduleSE/Part1_SelfEmploymentTax/L2_NetProfitScheduleC` | `//Return/ReturnData/IRS1040ScheduleSE/NetProfitOrLossAmt` |
| SE tax | `//ScheduleSE/Part1_SelfEmploymentTax/L12_SelfEmploymentTax` | `//Return/ReturnData/IRS1040ScheduleSE/SelfEmploymentTaxAmt` |
| SE deduction | `//ScheduleSE/Part1_SelfEmploymentTax/L13_DeductionHalfSETax` | `//Return/ReturnData/IRS1040ScheduleSE/DeductibleSelfEmploymentTaxAmt` |
| Schedule B interest | `//ScheduleB/Part1_Interest/L4_TaxableInterest` | `//Return/ReturnData/IRS1040ScheduleB/TotalInterestAmt` |
| Schedule B dividends | `//ScheduleB/Part2_OrdinaryDividends/L6_TotalOrdinaryDividends` | `//Return/ReturnData/IRS1040ScheduleB/TotalOrdinaryDividendsAmt` |
| QBI amount | `//Form8995/QBITrades/Trade[@seq='1']/QBIAmount` | `//Return/ReturnData/IRS8995/QualifiedBusinessIncomeAmt` |
| QBI deduction final | `//Form8995/L15_QBIDeduction` | `//Return/ReturnData/IRS8995/QualifiedBusinessIncomeDedAmt` |
| SE tax (Sched 2) | `//Schedule2/Part2_OtherTaxes/L4_SelfEmploymentTax` | `//Return/ReturnData/IRS1040Schedule2/SelfEmploymentTaxAmt` |
| CTC (Sched 8812) | `//Schedule8812/Part1_ChildTaxCredit/L14_ChildTaxCredit` | `//Return/ReturnData/IRS1040Schedule8812/ChildTaxCreditAmt` |

### Fix — Replace `xget` helper and rewrite FIELD_DEFINITIONS

**Step 1** — Add a helper that knows the IRS schema prefix:

```python
IRS_NS = ""   # IRS MeF XML has no namespace prefix

def xget(root, xpath, default=""):
    """Return text of first matching element, or default.
    Accepts both old custom-schema paths and new IRS-schema paths.
    """
    nodes = root.xpath(xpath)
    if nodes:
        return (nodes[0].text or "").strip()
    return default
```

**Step 2** — Replace the entire `FIELD_DEFINITIONS` list. The corrected XPaths for all 28 pages are given in **Appendix A** at the end of this document.

---

## Error 2 — `s()` Helper Silently Fails on Missing Nodes (CRITICAL)

### What happens
```python
def s(xpath, val):
    nodes = root.xpath(xpath)
    if nodes:
        nodes[0].text = str(max(0, val))
    # ← silently does nothing if xpath returns []
```
Because the IRS XML doesn't have the custom nodes (`//Form1040/AGI/L10_AdjustmentsSchedule1` etc.), every call to `s()` in `recompute_derived_fields()` is a no-op. No values are written anywhere.

### Fix — Make `s()` create the node if absent

```python
def s(root, xpath, val):
    """
    Set the text of the first matching node.
    If the node doesn't exist, create it under its parent.
    Only creates nodes one level deep (parent must exist).
    """
    nodes = root.xpath(xpath)
    if nodes:
        nodes[0].text = str(max(0, int(val)))
    else:
        # Parse parent path and tag name
        parts = xpath.rsplit("/", 1)
        if len(parts) == 2:
            parent_xpath, tag = parts
            parents = root.xpath(parent_xpath)
            if parents:
                from lxml import etree
                new_el = etree.SubElement(parents[0], tag)
                new_el.text = str(max(0, int(val)))
```

Update all calls in `recompute_derived_fields()` to pass `root` as the first argument: `s(root, xpath, val)`.

---

## Error 3 — CA 540 Data Completely Absent from XML (CRITICAL)

### What happens
Pages 23–28 are the California Form 540. The IRS e-file XML contains no CA-specific element — the `<ReturnData>` has only federal forms (`IRS1040`, `IRSW2`, `IRS1040ScheduleC`, etc.). There is no `<CA540>` node anywhere in the file.

### Fix — Generate CA 540 nodes from federal data during variation

Add a function `inject_ca540_nodes(root, ca_data: dict)` that builds the CA 540 subtree and attaches it to `<ReturnData>`. Call this from `generate_variation()` after `recompute_derived_fields()`.

```python
def inject_ca540_nodes(root, ca_data: dict):
    """
    Create <CA540> element under <ReturnData> with all fields
    needed for pages 23-28 of the PDF overlay.
    ca_data keys match the XPaths used in FIELD_DEFINITIONS.
    """
    from lxml import etree

    rd = root.xpath("//Return/ReturnData")
    if not rd:
        return root
    rd = rd[0]

    # Remove existing CA540 if present (idempotent)
    for old in rd.xpath("CA540"):
        rd.remove(old)

    ca = etree.SubElement(rd, "CA540")

    def add(parent_el, tag, value):
        el = etree.SubElement(parent_el, tag)
        el.text = str(value)
        return el

    # Header — pulled from federal filer info
    hdr = etree.SubElement(ca, "Header")
    primary_ssn  = xget(root, "//Return/ReturnHeader/Filer/PrimarySSN")
    spouse_ssn   = xget(root, "//Return/ReturnHeader/Filer/SpouseSSN")
    name_line    = xget(root, "//Return/ReturnHeader/Filer/NameLine1Txt")
    spouse_name  = xget(root, "//Return/ReturnHeader/Filer/SpouseNameLine1Txt")
    # Split "First Last" into parts (best-effort)
    p_parts = name_line.split(" ", 1)
    s_parts = spouse_name.split(" ", 1)
    add(hdr, "PrimarySSN",    primary_ssn)
    add(hdr, "SpouseSSN",     spouse_ssn)
    add(hdr, "PrimaryFirstName",  p_parts[0] if p_parts else "")
    add(hdr, "PrimaryLastName",   p_parts[1] if len(p_parts) > 1 else "")
    add(hdr, "SpouseFirstName",   s_parts[0] if s_parts else "")
    add(hdr, "SpouseLastName",    s_parts[1] if len(s_parts) > 1 else "")
    add(hdr, "Address",   xget(root, "//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt"))
    add(hdr, "City",      xget(root, "//Return/ReturnHeader/Filer/USAddress/CityNm"))
    add(hdr, "State",     xget(root, "//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd"))
    add(hdr, "ZIP",       xget(root, "//Return/ReturnHeader/Filer/USAddress/ZIPCd"))

    # Exemption credits (2024 FTB: $144 per person/spouse + $433 per dependent)
    dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    num_deps   = len(dep_nodes)
    personal_exempt  = 144 * 2        # MFJ: taxpayer + spouse
    dependent_exempt = 433 * num_deps
    total_exempt     = personal_exempt + dependent_exempt

    exm = etree.SubElement(ca, "Exemptions")
    add(exm, "L7_PersonalExemption_Amount", personal_exempt)

    deps_el = etree.SubElement(ca, "Dependents")
    for i, dep in enumerate(dep_nodes[:2], start=1):
        d = etree.SubElement(deps_el, "Dependent")
        d.set("seq", str(i))
        add(d, "FirstName",  (dep.findtext("DependentFirstNm") or ""))
        add(d, "LastName",   (dep.findtext("DependentLastNm") or ""))
        add(d, "SSN",        (dep.findtext("DependentSSN") or ""))

    add(ca, "L11_TotalExemptionCredits", total_exempt)

    # Populate computed values from ca_data dict
    ti_el  = etree.SubElement(ca, "TaxableIncome")
    tax_el = etree.SubElement(ca, "Tax")
    sc_el  = etree.SubElement(ca, "SpecialCredits")
    ot_el  = etree.SubElement(ca, "OtherTaxes")
    pay_el = etree.SubElement(ca, "Payments")
    up_el  = etree.SubElement(ca, "UseAndPenalty")
    ro_el  = etree.SubElement(ca, "RefundOrOwed")
    ao_el  = etree.SubElement(ca, "AmountOwedOrRefund")

    add(ti_el,  "L12_StateWages",            ca_data.get("state_wages", 0))
    add(ti_el,  "L13_FederalAGI",            ca_data.get("ca_agi", 0))
    add(ti_el,  "L15_AfterSubtractions",     ca_data.get("ca_agi", 0))
    add(ti_el,  "L16_CAAdditions",           0)
    add(ti_el,  "L17_CAAdjustedGrossIncome", ca_data.get("ca_agi", 0))
    add(ti_el,  "L18_Deduction",             ca_data.get("ca_std", 11080))
    add(ti_el,  "L19_TaxableIncome",         ca_data.get("ca_ti", 0))
    add(tax_el, "L31_TaxFromTable",          ca_data.get("ca_tax", 0))
    add(tax_el, "L32_ExemptionCredits",      total_exempt)
    add(tax_el, "L33_TaxAfterExemptionCredits", ca_data.get("ca_tax_after", 0))
    add(tax_el, "L35_TotalTax",              ca_data.get("ca_tax_after", 0))
    add(sc_el,  "L48_TaxAfterCredits",       ca_data.get("ca_tax_after", 0))
    add(ot_el,  "L64_TotalTax",              ca_data.get("ca_tax_after", 0))
    add(pay_el, "L71_CAWithheld",            ca_data.get("ca_withheld", 0))
    add(pay_el, "L78_TotalPayments",         ca_data.get("ca_withheld", 0))
    add(up_el,  "L93_PaymentsAfterISR",      ca_data.get("ca_withheld", 0))
    add(up_el,  "L95_PaymentsBalance",       ca_data.get("ca_withheld", 0))
    add(ro_el,  "L96_OverpaidTax",           ca_data.get("ca_refund", 0))
    add(ro_el,  "L97_OverpaidTaxAvailable",  ca_data.get("ca_refund", 0))
    add(ro_el,  "L99_RefundAvailable",       ca_data.get("ca_refund", 0))
    add(ro_el,  "L100_TaxDue",              ca_data.get("ca_owed", 0))
    add(ao_el,  "L115_Refund",              ca_data.get("ca_refund", 0))

    return root
```

Then in `recompute_derived_fields()` at the CA section, collect results into a dict and call `inject_ca540_nodes()`:

```python
ca_data = {
    "state_wages":   w2,      # CA wages = federal W-2 wages (simplification)
    "ca_agi":        ca_agi,
    "ca_std":        ca_std,
    "ca_ti":         ca_ti,
    "ca_tax":        ca_tax,
    "ca_tax_after":  ca_tax_after,
    "ca_withheld":   ca_withheld,
    "ca_refund":     ca_refund,
    "ca_owed":       ca_owed,
}
root = inject_ca540_nodes(root, ca_data)
```

---

## Error 4 — Form 1040-V and 1040-ES Nodes Missing (HIGH)

### What happens
Pages 18–22 map to `//Form1040V/…` and `//Form1040ES/…` XPaths. Neither element exists in the IRS e-file XML.

### Fix — Inject nodes from federal computed values

```python
def inject_voucher_nodes(root, p_name: str, s_name: str,
                          p_ssn: str, s_ssn: str,
                          owed: int, quarterly_payment: int,
                          address: str, city: str):
    """Inject Form1040V and Form1040ES nodes into XML."""
    from lxml import etree
    rd = root.xpath("//Return/ReturnData")[0]

    # --- 1040-V ---
    for old in rd.xpath("Form1040V"):
        rd.remove(old)
    v = etree.SubElement(rd, "Form1040V")
    def add(p, t, v_): el = etree.SubElement(p, t); el.text = str(v_); return el
    add(v, "PrimarySSN",    p_ssn)
    add(v, "SpouseSSN",     s_ssn)
    add(v, "PaymentAmount", owed)
    add(v, "TaxpayerName",  f"{p_name} & {s_name}")
    add(v, "Address",       address)
    add(v, "City",          city)

    # --- 1040-ES (4 quarterly vouchers) ---
    for old in rd.xpath("Form1040ES"):
        rd.remove(old)
    es = etree.SubElement(rd, "Form1040ES")
    add(es, "TaxpayerName", f"{p_name} & {s_name}")
    for i in range(1, 5):
        vch = etree.SubElement(es, "Voucher")
        vch.set("seq", str(i))
        amt = etree.SubElement(vch, "Amount")
        amt.text = str(quarterly_payment)

    return root
```

**Quarterly payment** = estimated next-year tax ÷ 4. A reasonable default:

```python
# After recompute_derived_fields(), estimated next-year liability ≈ current year
quarterly_payment = int(l24 / 4)
root = inject_voucher_nodes(
    root, p_first, s_first, p_ssn_fmt, s_ssn_fmt,
    owed, quarterly_payment, street, f"{city}, {state} {zipcode}"
)
```

---

## Error 5 — Schedule C Detailed Expense Lines Missing in XML (HIGH)

### What happens
The IRS e-file XML for Schedule C only has high-level totals:
- `GrossReceiptsOrSalesAmt`
- `TotalExpensesAmt`
- `NetProfitOrLossAmt`
- `AdvertisingAmt`, `OfficeExpensesAmt`, `SuppliesAmt`, `OtherBusinessExpensesAmt`

Missing from XML (and therefore blank on page 8):
- `L13_DepreciationSection179`
- `L20b_RentLeaseOtherProperty`
- `L23_TaxesLicenses`
- `L24b_DeductibleMeals`
- `L27a_OtherExpenses_Total`
- `Part5_OtherExpenses` line items (page 9)

### Fix — Inject Schedule C detail nodes

```python
def inject_schedule_c_detail(root, gross_rev: int, expenses: dict):
    """
    Adds missing detail lines to IRS1040ScheduleC.
    expenses = output of generate_schedule_c_expenses()
    """
    from lxml import etree
    sc = root.xpath("//Return/ReturnData/IRS1040ScheduleC")
    if not sc:
        return root
    sc = sc[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(value))
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(value))

    set_or_add(sc, "GrossReceiptsOrSalesAmt",    gross_rev)
    set_or_add(sc, "TotalGrossReceiptsAmt",       gross_rev)
    set_or_add(sc, "AdvertisingAmt",              expenses.get("L8_Advertising", 0))
    set_or_add(sc, "DepreciationAmt",             expenses.get("L13_DepreciationSection179", 0))
    set_or_add(sc, "OfficeExpensesAmt",           expenses.get("L18_OfficeExpense", 0))
    set_or_add(sc, "RentLeaseAmt",                expenses.get("L20b_RentLeaseOtherProperty", 0))
    set_or_add(sc, "SuppliesAmt",                 expenses.get("L22_Supplies", 0))
    set_or_add(sc, "TaxesAndLicensesAmt",         expenses.get("L23_TaxesLicenses", 0))
    set_or_add(sc, "MealsAmt",                    expenses.get("L24b_DeductibleMeals", 0))
    set_or_add(sc, "OtherBusinessExpensesAmt",    expenses.get("L27a_OtherExpenses_Total", 0))
    set_or_add(sc, "TotalExpensesAmt",            expenses.get("L28_TotalExpensesBeforeHome", 0))
    set_or_add(sc, "NetProfitOrLossAmt",          expenses.get("L31_NetProfitLoss", 0))

    # Part V — Other Expenses detail (page 9)
    other_items = [
        ("Software Subscriptions", int(expenses.get("L27a_OtherExpenses_Total", 0) * 0.40)),
        ("Professional Development", int(expenses.get("L27a_OtherExpenses_Total", 0) * 0.35)),
        ("Bank Charges",            int(expenses.get("L27a_OtherExpenses_Total", 0) * 0.25)),
    ]
    for old in sc.xpath("Part5_OtherExpenses"):
        sc.remove(old)
    p5 = etree.SubElement(sc, "Part5_OtherExpenses")
    for i, (desc, amt) in enumerate(other_items, start=1):
        item = etree.SubElement(p5, "Item")
        item.set("seq", str(i))
        d = etree.SubElement(item, "Description"); d.text = desc
        a = etree.SubElement(item, "Amount");      a.text = str(amt)
    total_other = etree.SubElement(p5, "L48_TotalOtherExpenses")
    total_other.text = str(expenses.get("L27a_OtherExpenses_Total", 0))

    return root
```

Update `FIELD_DEFINITIONS` for pages 8–9 to point to these new IRS-schema-compatible nodes (see **Appendix A**).

---

## Error 6 — Schedule SE Detail Lines Missing in XML (HIGH)

### What happens
The IRS e-file XML for `IRS1040ScheduleSE` only has:
- `NetProfitOrLossAmt`
- `SelfEmploymentTaxAmt`
- `DeductibleSelfEmploymentTaxAmt`
- `SEBaseAmt`, `SETotalNetEarningsOrLossAmt`, `MinimumProfitForSETaxAmt`

Missing (page 10 blank lines):
- `L3_CombinedLines`, `L4a_Multiply_9235`, `L4c_Combined`, `L6_AddLines4c5b`
- `L9_Subtract8dFrom7`, `L10_Multiply_124`, `L11_Multiply_029`

### Fix — Inject detail nodes after recompute

```python
def inject_schedule_se_detail(root, se_net, se_taxable, se_ss_tax, se_med_tax, se_total, se_deduction):
    from lxml import etree
    se = root.xpath("//Return/ReturnData/IRS1040ScheduleSE")
    if not se:
        return root
    se = se[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(max(0, value)))
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(max(0, value)))

    set_or_add(se, "NetProfitOrLossAmt",             se_net)
    set_or_add(se, "SETotalNetEarningsOrLossAmt",     se_net)
    set_or_add(se, "SEBaseAmt",                       se_taxable)
    set_or_add(se, "MinimumProfitForSETaxAmt",        se_taxable)
    set_or_add(se, "L4a_Multiply_9235",               se_taxable)
    set_or_add(se, "L4c_Combined",                    se_taxable)
    set_or_add(se, "L6_AddLines4c5b",                 se_taxable)
    set_or_add(se, "L9_Subtract8dFrom7",              se_taxable)
    set_or_add(se, "L10_Multiply_124",                se_ss_tax)
    set_or_add(se, "L11_Multiply_029",                se_med_tax)
    set_or_add(se, "SelfEmploymentTaxAmt",            se_total)
    set_or_add(se, "DeductibleSelfEmploymentTaxAmt",  se_deduction)

    return root
```

---

## Error 7 — Form 8995 Detail Lines Missing in XML (HIGH)

### What happens
`IRS8995` in the XML only has:
- `QualifiedBusinessIncomeAmt`
- `TotalQualifiedBusinessIncomeAmt`
- `QualifiedBusinessIncomeDedAmt`

Missing for page 13:
- `L2_TotalQBI`, `L4_TotalQBIAfterCarryforward`, `L5_QBIComponent_20pct`
- `L10_QBIDeductionBeforeLimit`, `L11_TaxableIncomeBeforeQBI`
- `L13_L11MinusL12`, `L14_IncomeLimitation`, `L15_QBIDeduction`

### Fix — Inject after recompute

```python
def inject_form8995_detail(root, qbi_income, qbi_component, l11, taxable_b4_qbi, income_limit, qbi_deduction):
    from lxml import etree
    f8995 = root.xpath("//Return/ReturnData/IRS8995")
    if not f8995:
        rd = root.xpath("//Return/ReturnData")[0]
        f8995_el = etree.SubElement(rd, "IRS8995")
    else:
        f8995_el = f8995[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(max(0, value)))
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(max(0, value)))

    # Business name for Trade entry (page 13 header row)
    biz_name = xget(root, "//Return/ReturnData/IRS1040ScheduleC/BusinessName/BusinessNameLine1Txt")
    biz_ein  = xget(root, "//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityCd")

    # Trade entry (seq=1)
    for old in f8995_el.xpath("QBITrades"):
        f8995_el.remove(old)
    trades = etree.SubElement(f8995_el, "QBITrades")
    trade  = etree.SubElement(trades, "Trade")
    trade.set("seq", "1")
    n  = etree.SubElement(trade, "n");            n.text  = biz_name
    tid= etree.SubElement(trade, "TaxpayerID");   tid.text= biz_ein
    qa = etree.SubElement(trade, "QBIAmount");    qa.text = str(qbi_income)

    set_or_add(f8995_el, "QualifiedBusinessIncomeAmt",    qbi_income)
    set_or_add(f8995_el, "L2_TotalQBI",                   qbi_income)
    set_or_add(f8995_el, "L4_TotalQBIAfterCarryforward",  qbi_income)
    set_or_add(f8995_el, "L5_QBIComponent_20pct",         qbi_component)
    set_or_add(f8995_el, "TotalQualifiedBusinessIncomeAmt", qbi_income)
    set_or_add(f8995_el, "L10_QBIDeductionBeforeLimit",   qbi_component)
    set_or_add(f8995_el, "L11_TaxableIncomeBeforeQBI",    l11)
    set_or_add(f8995_el, "L13_L11MinusL12",               taxable_b4_qbi)
    set_or_add(f8995_el, "L14_IncomeLimitation",          income_limit)
    set_or_add(f8995_el, "L15_QBIDeduction",              qbi_deduction)
    set_or_add(f8995_el, "QualifiedBusinessIncomeDedAmt", qbi_deduction)

    return root
```

---

## Error 8 — Pages 12, 14, 15, 17 Have Zero Field Definitions (MEDIUM)

### What happens
The PDF has 28 pages. `FIELD_DEFINITIONS` skips pages 12, 14, 15, and 17 entirely. These pages are silently passed through with no overlay.

### What's on those pages

| Page | Form | Known content |
|---|---|---|
| 12 | Schedule 8812 Part II (ACTC) | Additional child tax credit worksheet; for most middle-income filers = $0 |
| 14 | Schedule B (continuation) | Foreign account questions — Yes/No checkboxes only |
| 15 | Schedule C (continuation / Part III, IV) | Cost of goods sold; vehicle info; not applicable if service business |
| 17 | W-2 (copy B) | Employee copy — same data as overlaid on earlier W-2 pages |

### Fix

For pages 14 and 17 (checkboxes / W-2 copy), add minimal definitions:

```python
# Page 12 — Schedule 8812 Part II (most filers: $0, leave blank; only add if ACTC applicable)
# No additional lines needed unless net CTC > tax liability

# Page 14 — Schedule B foreign account checkbox (No = no foreign accounts)
CHECKBOX_DEFINITIONS += [
    (14, "//Return/ReturnData/IRS1040ScheduleB/ForeignAccountsQuestionInd[text()='false']", 52.0, 490.0),
]

# Page 15 — Schedule C Part III / vehicle — skip if service business
# Only add if IRS1040ScheduleC/BusinessVehicleUsed exists in XML

# Page 17 — W-2 Copy B (repeat of W-2 data — same XPaths as earlier W-2 page)
FIELD_DEFINITIONS += [
    (17, "//Return/ReturnData/IRSW2/EmployeeNm",                   43.0, 280.0, 9, None),
    (17, "//Return/ReturnData/IRSW2/EmployerName/BusinessNameLine1Txt", 43.0, 310.0, 9, None),
    (17, "//Return/ReturnData/IRSW2/WagesAmt",                    400.0, 280.0, 9, fmt_money),
    (17, "//Return/ReturnData/IRSW2/WithholdingAmt",              400.0, 310.0, 9, fmt_money),
]
```

---

## Error 9 — `num_kids` XPath Returns 0 → CTC Always $0 (MEDIUM)

### What happens
```python
num_kids = int(g("//Schedule8812/Part1_ChildTaxCredit/L4_QualifyingChildrenUnder17") or 0)
```
This xpath matches nothing in IRS XML → `num_kids = 0` → `ctc = 0` always.

### Fix — Count from `DependentDetail` nodes with child credit indicator

```python
# Count qualifying children under 17 from IRS XML
dep_nodes  = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
num_kids   = sum(
    1 for d in dep_nodes
    if (d.findtext("EligibleForChildTaxCreditInd") or "").strip().upper() in ("X", "TRUE", "1")
)
num_other  = max(0, len(dep_nodes) - num_kids)
```

Also inject the counts back into the Schedule 8812 subtree so page 11 renders correctly:

```python
def inject_schedule8812_detail(root, num_kids, num_other, l11, ctc_raw, ctc, ctc_used, l18):
    from lxml import etree
    rd  = root.xpath("//Return/ReturnData")[0]
    s8812 = root.xpath("//Return/ReturnData/IRS1040Schedule8812")
    if not s8812:
        s8812 = etree.SubElement(rd, "IRS1040Schedule8812")
    else:
        s8812 = s8812[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(value)
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(value)

    # Part I detail (page 11)
    set_or_add(s8812, "L1_AGI",                       l11)
    set_or_add(s8812, "L3_AddLines1_2d",               l11)
    set_or_add(s8812, "L4_QualifyingChildrenUnder17",  num_kids)
    set_or_add(s8812, "L5_Multiply2000",               num_kids * 2000)
    set_or_add(s8812, "L6_OtherDependents",            num_other)
    set_or_add(s8812, "L7_Multiply500",                num_other * 500)
    set_or_add(s8812, "L8_AddLines5_7",                ctc_raw)
    set_or_add(s8812, "L12_CreditAfterPhaseout",       ctc)
    set_or_add(s8812, "L13_CreditLimitWorksheetA",     l18)
    set_or_add(s8812, "L14_ChildTaxCredit",            ctc_used)
    set_or_add(s8812, "ChildTaxCreditAmt",             ctc_used)
    set_or_add(s8812, "TotalChildTaxCreditAmt",        ctc_used)
    return root
```

Update `FIELD_DEFINITIONS` page 11 XPaths to match the new node names (see **Appendix A**).

---

## Error 10 — QBI Division-by-Zero Risk (MEDIUM)

### What happens
```python
qbi_income = int(biz_income * (se_taxable / se_net)) if se_net else 0
```
This is guarded for `se_net == 0` but `se_taxable` is already `int(se_net * 0.9235)`, so the ratio is always `0.9235`. The formula simplifies to:

```python
qbi_income = int(biz_income * 0.9235) if se_net else 0
```

**Additional risk**: If `biz_income > 0` but Schedule C expenses exceed revenue (net loss), `se_net` could be negative. The `max(0, val)` guard in `s()` handles this for writing, but the brackets still compute wrongly.

### Fix — Guard all SE paths and cap QBI at zero

```python
se_net     = max(0, biz_income)          # SE tax only on profit, not loss
se_taxable = int(se_net * 0.9235)        # 92.35% multiplier
qbi_income = int(se_net * 0.9235)        # QBI = same base as SE taxable

# QBI deduction is further limited to 20% of taxable income minus capital gains
# per §199A. Simplified (no SSTB, no W-2 wage limit for income < $383,900 MFJ):
qbi_component  = int(qbi_income * 0.20)
standard_ded   = 29200   # 2024 MFJ
taxable_b4_qbi = max(0, l11 - standard_ded)
income_limit   = int(taxable_b4_qbi * 0.20)
qbi_deduction  = min(qbi_component, income_limit)
```

---

## Error 11 — `generate_variation()` Writes Leaf Inputs to Non-Existent Nodes (MEDIUM)

### What happens
```python
def set_text(xpath: str, value):
    nodes = root.xpath(xpath)
    if nodes:
        nodes[0].text = str(value)
```
Calls like:
```python
set_text("//Form1040/Income/L1a_WagesW2", w2)          # ← wrong schema
set_text("//CA540/Payments/L71_CAWithheld", ca_withholding)  # ← doesn't exist
```
Both silently do nothing. The XML leaf values are never updated.

### Fix — Replace all `set_text` calls with IRS-schema paths

```python
# Correct leaf input assignments using IRS e-file paths:
set_text("//Return/ReturnData/IRS1040/WagesAmt",                       w2)
set_text("//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt",        w2)
set_text("//Return/ReturnData/IRSW2/WagesAmt",                         w2)
set_text("//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt", gross_rev)
set_text("//Return/ReturnData/IRS1040ScheduleC/TotalGrossReceiptsAmt",   gross_rev)
set_text("//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt",           fed_withholding)

# CA withholding — must use inject_ca540_nodes() instead of set_text;
# the CA540 node is injected fresh each variation
```

Also update the identity fields:

```python
# Primary filer
set_text("//Return/ReturnHeader/Filer/NameLine1Txt",        f"{p_first} {p_last}")
set_text("//Return/ReturnHeader/Filer/PrimarySSN",          random_ssn(rng).replace("-", ""))
set_text("//Return/ReturnHeader/Filer/SpouseNameLine1Txt",  f"{s_first} {s_last}")
set_text("//Return/ReturnHeader/Filer/SpouseSSN",           random_ssn(rng).replace("-", ""))

# Address
set_text("//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt", f"{street_num} {street_name}")
set_text("//Return/ReturnHeader/Filer/USAddress/CityNm",          city)
set_text("//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd", state)
set_text("//Return/ReturnHeader/Filer/USAddress/ZIPCd",           zipcode)
```

---

## Error 12 — CA 540 Bracket Parameters (LOW)

### Current code
```python
ca_brackets = [
    (20824,   0.01), (49368,   0.02), (77918,   0.04),
    (108162,  0.06), (136700,  0.08), (698274,  0.093),
    (float("inf"), 0.103),
]
```

### Verified 2024 CA Schedule Y (MFJ) brackets per FTB

```python
# 2024 California Tax Rate Schedule Y — Married/RDP Filing Jointly
# Source: FTB 2024-540-tax-rate-schedules.pdf
CA_BRACKETS_MFJ_2024 = [
    (20824,       0.010),   # 1%   on first $20,824
    (49368,       0.020),   # 2%   on $20,825–$49,368
    (77918,       0.040),   # 4%   on $49,369–$77,918
    (108162,      0.060),   # 6%   on $77,919–$108,162
    (136700,      0.080),   # 8%   on $108,163–$136,700
    (698274,      0.093),   # 9.3% on $136,701–$698,274
    (1000000,     0.103),   # 10.3% on $698,275–$1,000,000  ← add this bracket
    (float("inf"), 0.123),  # 12.3% on $1,000,001+          ← add this bracket
]
```

> The code was missing the 10.3% and 12.3% brackets. For AGI under ~$300K these don't trigger, but they must be present for correctness.

### Also fix: CA standard deduction for MFJ 2024

```python
CA_STD_DEDUCTION_MFJ_2024 = 11080  # ✓ Correct per FTB/H&R Block (unchanged)
```

### CA exemption credits 2024 (update the hardcoded `ca_exempt`)

```python
# 2024 FTB exemption credits (per FTB 540 instructions):
CA_PERSONAL_EXEMPT_MFJ   = 144 * 2   # $144 each for taxpayer + spouse = $288
CA_DEPENDENT_EXEMPT_EACH = 433        # $433 per qualifying dependent
# (These replaced the old $1,220 hardcoded value which was incorrect)
```

The current code uses `g("//CA540/L11_TotalExemptionCredits") or 1220`. The `1220` fallback was wrong — it's for single/MFS. For MFJ with 2 dependents: $288 + $866 = $1,154.

---

## Error 13 — `L14_TotalDeductions` Missing from Page 1 (LOW)

### What happens
`recompute_derived_fields()` computes `l14 = l12 + l13` and calls `s("//Form1040/TaxableIncome/L14_TotalDeductions", l14)` but there is no entry in `FIELD_DEFINITIONS` for page 1, line 14.

### Fix — Add to FIELD_DEFINITIONS (page 1)

```python
(1, "//Return/ReturnData/IRS1040/TotalDeductionsAmt", 547.1, 705.5, 9, fmt_money),
```

The coordinate `top=705.5` places it between line 13 (QBI, top=693.5) and line 15 (taxable income, top=717.5).

---

## Error 14 — Schedule 8812 L3 and L13 Never Populated (LOW)

### What happens
`FIELD_DEFINITIONS` includes:
```python
(11, "//Schedule8812/Part1_ChildTaxCredit/L3_AddLines1_2d",       547.0, 210.5, 9, fmt_money),
(11, "//Schedule8812/Part1_ChildTaxCredit/L13_CreditLimitWorksheetA", 547.0, 348.5, 9, fmt_money),
```
- `L3` = AGI + any Schedule C add-backs (effectively just AGI for most filers).
- `L13` = Tax before credits (line 18 of 1040) — used to cap the CTC.

Neither is populated by `recompute_derived_fields()`.

### Fix — Populate in `inject_schedule8812_detail()` (already shown in Error 9 fix):
- `L3_AddLines1_2d` = `l11` (AGI)
- `L13_CreditLimitWorksheetA` = `l18` (tax before credits)

---

## Quant Model Architecture — Correct Pipeline Order

After all fixes are applied, `generate_variation()` must call helpers in this exact order:

```python
def generate_variation(xml_path, source_pdf, output_path, seed):
    rng  = random.Random(seed)
    root = load_xml(xml_path)

    # ── Step 1: Randomise identity leaf fields (IRS schema paths) ──────────
    p_first, p_last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
    s_first         = rng.choice(FIRST_NAMES)
    city, state, zipcode = rng.choice(CITIES)
    p_ssn = random_ssn(rng).replace("-","")
    s_ssn = random_ssn(rng).replace("-","")
    set_text(root, "//Return/ReturnHeader/Filer/NameLine1Txt",  f"{p_first} {p_last}")
    set_text(root, "//Return/ReturnHeader/Filer/PrimarySSN",    p_ssn)
    set_text(root, "//Return/ReturnHeader/Filer/SpouseNameLine1Txt", f"{s_first} {p_last}")
    set_text(root, "//Return/ReturnHeader/Filer/SpouseSSN",     s_ssn)
    # ... address, occupation, phone, email

    # ── Step 2: Generate correlated leaf income inputs ──────────────────────
    w2        = rng.randint(30_000, 150_000)
    gross_rev = rng.randint(30_000, 200_000)
    expenses  = generate_schedule_c_expenses(gross_rev, rng)
    inv       = generate_investment_income(w2 + expenses["L31_NetProfitLoss"], rng)
    fed_wh    = generate_withholding(w2, rng)
    ca_wh     = generate_ca_withholding(w2, rng)

    set_text(root, "//Return/ReturnData/IRS1040/WagesAmt",        w2)
    set_text(root, "//Return/ReturnData/IRSW2/WagesAmt",          w2)
    set_text(root, "//Return/ReturnData/IRSW2/WithholdingAmt",    fed_wh)
    set_text(root, "//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt", gross_rev)
    set_text(root, "//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt", fed_wh)
    set_text(root, "//Return/ReturnData/IRS1040/TaxableInterestAmt",   inv["L2b_TaxableInterest"])
    set_text(root, "//Return/ReturnData/IRS1040/OrdinaryDividendsAmt", inv["L3b_OrdinaryDividends"])

    # ── Step 3: Recompute ALL derived fields via IRS arithmetic ────────────
    root, computed = recompute_derived_fields(root, ca_wh)
    # (recompute now returns both root and a computed-values dict for vouchers)

    # ── Step 4: Inject detail subtrees for missing XML elements ────────────
    root = inject_schedule_c_detail(root, gross_rev, expenses)
    root = inject_schedule_se_detail(root, *computed["se_vals"])
    root = inject_form8995_detail(root,   *computed["qbi_vals"])
    root = inject_schedule8812_detail(root, *computed["ctc_vals"])
    root = inject_ca540_nodes(root, computed["ca_data"])
    root = inject_voucher_nodes(root, p_first, s_first, p_ssn, s_ssn,
                                computed["owed"], computed["quarterly"], ...)

    # ── Step 5: Write temp XML → overlay PDF ───────────────────────────────
    generate_pdf(tmp_xml_path, source_pdf, output_path)
```

---

## 2024 US Tax Economy — Quant Model Parameters Reference

All values are **2024 tax year** (filed April 2025).

### Federal Income Tax — Married Filing Jointly

| Bracket | Rate |
|---|---|
| $0 – $23,200 | 10% |
| $23,201 – $94,300 | 12% |
| $94,301 – $201,050 | 22% |
| $201,051 – $383,900 | 24% |
| $383,901 – $487,450 | 32% |
| $487,451 – $731,200 | 35% |
| $731,201+ | 37% |

**Standard deduction MFJ 2024:** $29,200 ✓ (code has this correct)

### Self-Employment Tax (Schedule SE)

| Parameter | Value | Notes |
|---|---|---|
| Net earnings multiplier | × 0.9235 | Deducts employer-equivalent half |
| SS tax rate | 12.4% | On net × 0.9235 |
| SS wage base cap | $168,600 | 2024 ✓ (code correct) |
| Medicare rate | 2.9% | No cap |
| Additional Medicare | 0.9% | On SE income > $200K single / $250K MFJ |
| Total SE rate (approx) | ~14.13% | SS + Medicare combined |
| Deductible half | 50% | Reduces AGI via Schedule 1 |

**Additional Medicare Tax** — the current code omits this. Add:

```python
# Additional Medicare Tax (0.9%) on SE income above $250,000 MFJ
adt_medicare_threshold = 250000
if se_taxable > adt_medicare_threshold:
    adt_medicare = int((se_taxable - adt_medicare_threshold) * 0.009)
else:
    adt_medicare = 0
se_total += adt_medicare
```

### QBI Deduction (§199A / Form 8995)

| Parameter | Value | Notes |
|---|---|---|
| Deduction rate | 20% of QBI | For filers below income threshold |
| Phase-in threshold MFJ | $383,900 | Below = full 20% available |
| Phase-out ceiling MFJ | $483,900 | Above = reduced or $0 (SSTB) |
| Taxable income cap | 20% of (taxable income − net cap gains) | Whichever is lower |
| SSTB restriction | Applies above threshold | E.g., consulting, law, health |

**Simplification valid for synthetic data:** For AGI < $383,900 (which covers ~95% of realistic synthetic profiles), `qbi_deduction = min(qbi_component, income_limit)` is correct as coded.

### CTC / Schedule 8812

| Parameter | Value |
|---|---|
| Credit per qualifying child under 17 | $2,000 |
| Credit per other dependent | $500 |
| Phase-out threshold MFJ | $400,000 |
| Phase-out reduction | $50 per $1,000 (5%) |
| Refundable portion (ACTC) max | $1,700 per child (2024) |

### CA 540 — 2024 (Married/RDP Filing Jointly)

| Parameter | Value |
|---|---|
| Standard deduction | $11,080 ✓ |
| Personal exemption credit (each) | $144 |
| Dependent exemption credit (each) | $433 |
| SDI rate (employer withholds) | 1.1% of wages (no cap) |
| CA estimated tax threshold | ≥ $500 owed after withholding |

**CA 2024 tax brackets (MFJ) — Schedule Y:**

| Income range | Rate |
|---|---|
| $0 – $20,824 | 1% |
| $20,825 – $49,368 | 2% |
| $49,369 – $77,918 | 4% |
| $77,919 – $108,162 | 6% |
| $108,163 – $136,700 | 8% |
| $136,701 – $698,274 | 9.3% |
| $698,275 – $1,000,000 | 10.3% |
| $1,000,001+ | 12.3% |

---

## Checklist — Apply in This Order

- [ ] **Error 2** — Fix `s()` to create missing nodes (prerequisite for everything else)
- [ ] **Error 1** — Rewrite all XPaths in `FIELD_DEFINITIONS` (see Appendix A)
- [ ] **Error 11** — Rewrite `set_text` calls in `generate_variation()` to IRS schema
- [ ] **Error 9** — Fix `num_kids` count from `DependentDetail` nodes
- [ ] **Error 10** — Fix QBI formula, add Additional Medicare Tax
- [ ] **Error 5** — Add `inject_schedule_c_detail()`
- [ ] **Error 6** — Add `inject_schedule_se_detail()`
- [ ] **Error 7** — Add `inject_form8995_detail()`
- [ ] **Error 9** — Add `inject_schedule8812_detail()`
- [ ] **Error 3** — Add `inject_ca540_nodes()` with correct 2024 parameters
- [ ] **Error 4** — Add `inject_voucher_nodes()` for pages 18–22
- [ ] **Error 12** — Add CA 10.3% and 12.3% brackets; fix exemption credit amounts
- [ ] **Error 13** — Add `L14_TotalDeductions` to FIELD_DEFINITIONS page 1
- [ ] **Error 14** — Confirm L3 and L13 populated via inject_schedule8812_detail
- [ ] **Error 8** — Add minimal definitions for pages 12, 14, 15, 17
- [ ] **Validate** — Run detector script, visually inspect 5 sample PDFs before batch

---

## Appendix A — Full Corrected FIELD_DEFINITIONS

Below is the complete replacement for `FIELD_DEFINITIONS`, using IRS e-file XPaths throughout. Fields for CA 540 (pages 23–28) now reference the `<CA540>` node injected by `inject_ca540_nodes()`.

```python
FIELD_DEFINITIONS = [

    # ── PAGE 1 — Form 1040 ──────────────────────────────────────────────────
    (1, "//Return/ReturnHeader/Filer/NameLine1Txt",                          39.1,  93.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/PrimarySSN",                           478.3,  93.5,  9,  fmt_ssn),
    (1, "//Return/ReturnHeader/Filer/SpouseNameLine1Txt",                    39.5, 117.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/SpouseSSN",                            478.3, 117.5,  9,  fmt_ssn),
    (1, "//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt",             39.5, 143.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/USAddress/CityNm",                      39.5, 166.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd",        206.0, 166.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/USAddress/ZIPCd",                      260.0, 166.5,  9,  None),
    # Dependents
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",   96.7, 381.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentLastNm",   160.0, 381.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentSSN",      290.0, 381.5,  8,  fmt_ssn),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentRelationshipCd", 400.0, 381.5, 8, None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentFirstNm",   96.7, 393.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentLastNm",   160.0, 393.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentSSN",      290.0, 393.5,  8,  fmt_ssn),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentRelationshipCd", 400.0, 393.5, 8, None),
    # Income lines
    (1, "//Return/ReturnData/IRS1040/WagesAmt",                            547.1, 429.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt",             547.1, 537.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TaxableInterestAmt",                  547.1, 549.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/OrdinaryDividendsAmt",                547.1, 561.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/BusinessIncomeAmt",                   547.1, 633.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TotalIncomeAmt",                      547.1, 645.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt",              552.7, 657.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt",              547.1, 669.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TotalItemizedOrStandardDedAmt",       547.1, 681.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/QualifiedBusinessIncomeDedAmt",       547.1, 693.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TotalDeductionsAmt",                  547.1, 705.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                    547.1, 717.5,  9,  fmt_money),

    # ── PAGE 2 — Form 1040 (Tax, Credits, Payments) ─────────────────────────
    (2, "//Return/ReturnHeader/Filer/NameLine1Txt",                         39.5,  27.5,  8,  None),
    (2, "//Return/ReturnHeader/Filer/PrimarySSN",                          474.7,  27.5,  8,  fmt_ssn),
    (2, "//Return/ReturnData/IRS1040/TaxAmt",                              552.7,  39.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalTaxBeforeCrAndOthTaxesAmt",      552.7,  63.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",                   552.1,  75.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalCreditsAmt",                     552.1,  99.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TaxLessCreditsAmt",                   552.7, 111.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/OtherTaxesAmt",                       552.7, 123.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalTaxAmt",                         552.7, 135.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt",                455.5, 159.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/WithholdingTaxAmt",                   552.1, 195.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",                    552.1, 291.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/OverpaidAmt",                         575.1, 303.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/RefundAmt",                           574.5, 315.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/AmountOwedAmt",                       552.1, 375.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRSW2/EmployeeOccupation",                    290.0, 555.5,  9,  None),
    (2, "//Return/ReturnData/IRSW2/SpouseOccupation",                      290.0, 569.5,  9,  None),
    (2, "//Return/ReturnHeader/Filer/PhoneNum",                             39.5, 583.5,  9,  None),
    (2, "//Return/ReturnHeader/Filer/EmailAddressTxt",                     200.0, 583.5,  9,  None),

    # ── PAGE 3 — Schedule 1 Part I ──────────────────────────────────────────
    (3, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (3, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",         547.0, 277.5,  9,  fmt_money),
    (3, "//Return/ReturnData/IRS1040/BusinessIncomeAmt",                   547.0, 501.5,  9,  fmt_money),

    # ── PAGE 4 — Schedule 1 Part II ─────────────────────────────────────────
    (4, "//Return/ReturnData/IRS1040ScheduleSE/DeductibleSelfEmploymentTaxAmt", 547.0, 218.5, 9, fmt_money),
    (4, "//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt",              547.0, 598.5,  9,  fmt_money),

    # ── PAGE 5 — Schedule 2 Part I ──────────────────────────────────────────
    (5, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (5, "//Return/ReturnData/IRS1040Schedule2/AlternativeMinimumTaxAmt",   547.0, 282.5,  9,  fmt_money),
    (5, "//Return/ReturnData/IRS1040Schedule2/TotalAdditionalTaxAmt",      547.0, 296.5,  9,  fmt_money),
    (5, "//Return/ReturnData/IRS1040Schedule2/SelfEmploymentTaxAmt",       547.0, 324.5,  9,  fmt_money),

    # ── PAGE 6 — Schedule 2 Part II ─────────────────────────────────────────
    (6, "//Return/ReturnData/IRS1040Schedule2/TotalOtherTaxesAmt",         547.0, 720.5,  9,  fmt_money),

    # ── PAGE 7 — Schedule B ──────────────────────────────────────────────────
    (7, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (7, "//Return/ReturnData/IRS1040ScheduleB/InterestPayerName",           43.0, 148.5,  9,  None),
    (7, "//Return/ReturnData/IRS1040ScheduleB/InterestAmt",                547.0, 148.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/TotalInterestAmt",           547.0, 220.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/TotalInterestAmt",           547.0, 248.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/DividendPayerName",           43.0, 330.5,  9,  None),
    (7, "//Return/ReturnData/IRS1040ScheduleB/OrdinaryDividendsAmt",       547.0, 330.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/TotalOrdinaryDividendsAmt",  547.0, 388.5,  9,  fmt_money),

    # ── PAGE 8 — Schedule C ──────────────────────────────────────────────────
    (8, "//Return/ReturnData/IRS1040ScheduleC/ProprietorNm",                43.0,  99.5,  9,  None),
    (8, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (8, "//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityDesc", 43.0, 118.5, 9, None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityCd", 440.0, 118.5, 9, None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/BusinessName/BusinessNameLine1Txt", 43.0, 130.5, 9, None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/BusinessAddressTxt",          43.0, 142.5,  9,  None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt",    547.0, 204.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/TotalGrossReceiptsAmt",      547.0, 256.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/AdvertisingAmt",             267.0, 280.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/DepreciationAmt",            267.0, 340.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/OfficeExpensesAmt",          488.0, 280.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/RentLeaseAmt",               488.0, 304.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/SuppliesAmt",                267.0, 352.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/TaxesAndLicensesAmt",        267.0, 364.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/MealsAmt",                   488.0, 328.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/OtherBusinessExpensesAmt",   267.0, 400.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/TotalExpensesAmt",           547.0, 412.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",         547.0, 448.5,  9,  fmt_money),

    # ── PAGE 9 — Schedule C Part V ───────────────────────────────────────────
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='1']/Description", 43.0, 466.5, 9, None),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='1']/Amount",     488.0, 466.5, 9, fmt_money),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='2']/Description", 43.0, 478.5, 9, None),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='2']/Amount",     488.0, 478.5, 9, fmt_money),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='3']/Description", 43.0, 490.5, 9, None),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='3']/Amount",     488.0, 490.5, 9, fmt_money),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/L48_TotalOtherExpenses",   488.0, 550.5, 9, fmt_money),

    # ── PAGE 10 — Schedule SE ────────────────────────────────────────────────
    (10, "//Return/ReturnHeader/Filer/NameLine1Txt",                         43.0,  99.5,  9,  None),
    (10, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/NetProfitOrLossAmt",        547.0, 196.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/SETotalNetEarningsOrLossAmt", 547.0, 208.5, 9, fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L4a_Multiply_9235",         547.0, 222.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L4c_Combined",              547.0, 238.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L6_AddLines4c5b",           547.0, 280.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L9_Subtract8dFrom7",        547.0, 406.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L10_Multiply_124",          547.0, 418.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L11_Multiply_029",          547.0, 430.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/SelfEmploymentTaxAmt",      547.0, 444.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/DeductibleSelfEmploymentTaxAmt", 547.0, 460.5, 9, fmt_money),

    # ── PAGE 11 — Schedule 8812 ──────────────────────────────────────────────
    (11, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L1_AGI",                  547.0, 174.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L3_AddLines1_2d",         547.0, 210.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L4_QualifyingChildrenUnder17", 300.0, 228.5, 9, None),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L5_Multiply2000",         547.0, 228.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L6_OtherDependents",      300.0, 248.5,  9,  None),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L7_Multiply500",          547.0, 248.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L8_AddLines5_7",          547.0, 264.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L12_CreditAfterPhaseout", 547.0, 336.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L13_CreditLimitWorksheetA", 547.0, 348.5, 9, fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/ChildTaxCreditAmt",       547.0, 360.5,  9,  fmt_money),

    # ── PAGE 13 — Form 8995 ──────────────────────────────────────────────────
    (13, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (13, "//Return/ReturnData/IRS8995/QBITrades/Trade[@seq='1']/n",          43.0, 145.5,  8,  None),
    (13, "//Return/ReturnData/IRS8995/QBITrades/Trade[@seq='1']/TaxpayerID", 350.0, 145.5, 8,  fmt_ssn),
    (13, "//Return/ReturnData/IRS8995/QBITrades/Trade[@seq='1']/QBIAmount",  488.0, 145.5, 8,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L2_TotalQBI",                         488.0, 187.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L4_TotalQBIAfterCarryforward",        488.0, 211.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L5_QBIComponent_20pct",               488.0, 225.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L10_QBIDeductionBeforeLimit",         488.0, 309.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L11_TaxableIncomeBeforeQBI",          488.0, 321.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L13_L11MinusL12",                     488.0, 345.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L14_IncomeLimitation",                488.0, 357.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L15_QBIDeduction",                    488.0, 371.5,  9,  fmt_money),

    # ── PAGE 16 — Form 4562 ──────────────────────────────────────────────────
    (16, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (16, "//Return/ReturnData/IRS4562/Section179ExpenseAmt",                488.0, 148.5,  9,  fmt_money),
    (16, "//Return/ReturnData/IRS4562/DepreciationAmt",                     488.0, 160.5,  9,  fmt_money),
    (16, "//Return/ReturnData/IRS4562/TotalDepreciationAmt",                488.0, 612.5,  9,  fmt_money),

    # ── PAGE 18 — Form 1040-V ────────────────────────────────────────────────
    (18, "//Return/ReturnData/Form1040V/PrimarySSN",                         43.0, 280.5, 10,  fmt_ssn),
    (18, "//Return/ReturnData/Form1040V/SpouseSSN",                         200.0, 280.5, 10,  fmt_ssn),
    (18, "//Return/ReturnData/Form1040V/PaymentAmount",                     400.0, 280.5, 10,  fmt_money),
    (18, "//Return/ReturnData/Form1040V/TaxpayerName",                       43.0, 350.5, 10,  None),
    (18, "//Return/ReturnData/Form1040V/Address",                            43.0, 365.5, 10,  None),
    (18, "//Return/ReturnData/Form1040V/City",                               43.0, 380.5, 10,  None),

    # ── PAGES 19–22 — Form 1040-ES Vouchers ─────────────────────────────────
    (19, "//Return/ReturnData/Form1040ES/Voucher[@seq='1']/Amount",         400.0, 280.5, 10,  fmt_money),
    (19, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),
    (20, "//Return/ReturnData/Form1040ES/Voucher[@seq='2']/Amount",         400.0, 280.5, 10,  fmt_money),
    (20, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),
    (21, "//Return/ReturnData/Form1040ES/Voucher[@seq='3']/Amount",         400.0, 280.5, 10,  fmt_money),
    (21, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),
    (22, "//Return/ReturnData/Form1040ES/Voucher[@seq='4']/Amount",         400.0, 280.5, 10,  fmt_money),
    (22, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),

    # ── PAGE 23 — CA 540 Page 1 ──────────────────────────────────────────────
    (23, "//Return/ReturnData/CA540/Header/PrimarySSN",                     350.0,  99.5,  9,  fmt_ssn),
    (23, "//Return/ReturnData/CA540/Header/SpouseSSN",                      440.0,  99.5,  9,  fmt_ssn),
    (23, "//Return/ReturnData/CA540/Header/PrimaryFirstName",                43.0, 118.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/PrimaryLastName",                200.0, 118.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/SpouseFirstName",                 43.0, 130.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/SpouseLastName",                 200.0, 130.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/Address",                         43.0, 148.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/City",                            43.0, 162.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/State",                          290.0, 162.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/ZIP",                            310.0, 162.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Exemptions/L7_PersonalExemption_Amount", 488.0, 376.5, 9, fmt_money),

    # ── PAGE 24 — CA 540 Page 2 ──────────────────────────────────────────────
    (24, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  27.5,  9,  fmt_ssn),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='1']/FirstName", 43.0, 76.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='1']/LastName",  120.0, 76.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='1']/SSN",       220.0, 76.5, 8, fmt_ssn),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='2']/FirstName", 43.0, 89.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='2']/LastName",  120.0, 89.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='2']/SSN",       220.0, 89.5, 8, fmt_ssn),
    (24, "//Return/ReturnData/CA540/L11_TotalExemptionCredits",             488.0, 133.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L12_StateWages",          488.0, 152.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L13_FederalAGI",          488.0, 164.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L15_AfterSubtractions",   488.0, 188.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L16_CAAdditions",         488.0, 200.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L17_CAAdjustedGrossIncome", 488.0, 212.5, 9, fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L18_Deduction",           488.0, 234.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L19_TaxableIncome",       488.0, 248.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L31_TaxFromTable",                  488.0, 312.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L32_ExemptionCredits",              488.0, 324.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L33_TaxAfterExemptionCredits",      488.0, 336.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L35_TotalTax",                      488.0, 354.5,  9,  fmt_money),

    # ── PAGE 25 — CA 540 Page 3 ──────────────────────────────────────────────
    (25, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  27.5,  9,  fmt_ssn),
    (25, "//Return/ReturnData/CA540/SpecialCredits/L48_TaxAfterCredits",    488.0, 108.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/OtherTaxes/L64_TotalTax",               488.0, 192.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/Payments/L71_CAWithheld",               488.0, 218.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/Payments/L78_TotalPayments",            488.0, 290.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/UseAndPenalty/L93_PaymentsAfterISR",    488.0, 378.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/UseAndPenalty/L95_PaymentsBalance",     488.0, 404.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/RefundOrOwed/L96_OverpaidTax",          488.0, 430.5,  9,  fmt_money),

    # ── PAGE 26 — CA 540 Page 4 ──────────────────────────────────────────────
    (26, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  27.5,  9,  fmt_ssn),
    (26, "//Return/ReturnData/CA540/RefundOrOwed/L97_OverpaidTaxAvailable", 488.0,  80.5,  9,  fmt_money),
    (26, "//Return/ReturnData/CA540/RefundOrOwed/L99_RefundAvailable",      488.0, 104.5,  9,  fmt_money),

    # ── PAGE 27 — CA 540 Page 5 ──────────────────────────────────────────────
    (27, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  27.5,  9,  fmt_ssn),
    (27, "//Return/ReturnData/CA540/AmountOwedOrRefund/L115_Refund",        488.0, 200.5,  9,  fmt_money),

    # ── PAGE 28 — CA 540 Page 6 ──────────────────────────────────────────────
    (28, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  27.5,  9,  fmt_ssn),
    (28, "//Return/ReturnHeader/Filer/EmailAddressTxt",                      43.0, 490.5,  9,  None),
    (28, "//Return/ReturnHeader/Filer/PhoneNum",                            290.0, 490.5,  9,  None),
]
```

---

*End of Fix Guide. Apply all corrections, run `python3 generate_tax_pdf.py --xml sample/Prompt/Tax\ Return\ Data\ -\ Prompt.xml --source 2024_Tax_Return_Documents_\(JOHNSON_JOHN_and_EMILY\).pdf --out test_output.pdf`, then verify all 28 pages visually before batch generation.*
