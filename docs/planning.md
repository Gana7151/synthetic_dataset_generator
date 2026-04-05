# FIXI Synthetic Tax Dataset Generator — Technical Roadmap
**`planning.md` · Cross-reference: MISSING_FORMS_IMPLEMENTATION_GUIDE_v2.md vs codebase**

> Audit date: 2026-04-04  
> Repository: `Gana7151/synthetic_dataset_generator`  
> Reference PDF: `2024_Tax_Return_Documents__JOHNSON_JOHN_and_EMILY_.pdf`  
> Guide: `MISSING_FORMS_IMPLEMENTATION_GUIDE_v2.md`

---

## Executive Summary

The current codebase (`v5.0 / guide v2.0`) generates simplified table-based PDFs that diverge significantly from the exact IRS form layout shown in the reference PDF. The generator handles core federal tax arithmetic well but is missing: **9 complete form renderers** (Schedule 1 being the most critical), 7 validation rules (V-16–V-22), 8+ data model fields, 5 calculator functions, and the estimated-tax pipeline. The CA Form 540 renderer covers only ~10% of the actual 6-page form. All gaps are categorized below with priority, file locations, and exact implementation steps.

---

## Gap Analysis Matrix

| Area | Feature | Status | Guide §  | Priority |
|---|---|---|---|---|
| PDF Format | IRS-exact box/field layout (absolute positioning) | ❌ ABSENT | §1–15 | P0 |
| data model | `PrepNotes` dataclass | ❌ ABSENT | §1.5 | P1 |
| data model | `phone`, `email` on `TaxProfile` | ❌ ABSENT | §1.5 | P1 |
| data model | `RentExpense` dataclass | ❌ ABSENT | §10 | P1 |
| data model | `OtherExpenseItem` list on `BusinessIncome` | ❌ ABSENT | §10 | P1 |
| data model | `DepreciableAsset` dataclass | ❌ ABSENT | §9 | P1 |
| data model | `has_home_office`, `home_office_deduction` on `TaxProfile` | ❌ ABSENT | §10 | P2 |
| data model | `material_participation`, `made_1099_payments`, `will_file_1099` on `BusinessIncome` | ❌ ABSENT | §10 | P2 |
| calculators | Lines 1a–1z dict keys in `federal_results` | ❌ ABSENT | §1.2 | P1 |
| calculators | Lines 4a–6b stubs (IRA, pensions, SS) | ❌ ABSENT | §1.3 | P1 |
| calculators | Lines schedule_2_line_3, schedule_3_line_8, etc. | ❌ ABSENT | §1.4 | P1 |
| calculators | `compute_schedule_se()` as standalone function | ❌ ABSENT | §4 | P1 |
| calculators | `compute_schedule_2()` function | ❌ ABSENT | §5 | P1 |
| calculators | `compute_schedule_3()` function | ❌ ABSENT | §6 | P1 |
| calculators | `compute_schedule_8812()` with ACTC | ❌ ABSENT | §7 | P1 |
| calculators | `schedule_8995` dict in results | ❌ ABSENT | §8 | P1 |
| calculators | NIIT (Schedule 2 Line 12) | ❌ ABSENT | §5 | P1 |
| calculators | `compute_estimated_tax_next_year()` | ❌ ABSENT | §12 | P2 |
| tax_tables | `BONUS_DEPRECIATION_RATE` dict | ❌ ABSENT | §16.1 | P2 |
| tax_tables | `SECTION_179_MAX` + phaseout dict | ❌ ABSENT | §16.1 | P2 |
| tax_tables | `STANDARD_MILEAGE_RATE` dict | ❌ ABSENT | §9 | P2 |
| tax_tables | `HOME_OFFICE_RATE` dict | ❌ ABSENT | §10 | P2 |
| tax_tables | `MACRS_GDS_HY` tables | ❌ ABSENT | §9 | P2 |
| tax_tables | `get_salt_cap()` helper | ❌ ABSENT | §16.3 | P2 |
| tax_tables | OBBBA tips phaseout_end: $550K MFJ → **$700K** | ⚠️ WRONG | §2.1 | P0 |
| tax_tables | OBBBA overtime phaseout_end: $400K/$550K → **$275K/$550K** | ⚠️ WRONG | §2.1 | P0 |
| tax_tables | OBBBA car_loan phaseout_end: $149K/$249K → **$150K/$250K** | ⚠️ WRONG | §2.1 | P0 |
| tax_tables | OBBBA senior MFJ phaseout_end: $250K → **$350K** | ⚠️ WRONG | §2.1 | P0 |
| Form 1040 | DOBs, occupation, phone, email fields | ❌ ABSENT | §1.1 | P1 |
| Form 1040 | Presidential election fund / digital assets checkboxes | ❌ ABSENT | §1.1 | P1 |
| Form 1040 | Age/blindness checkboxes | ❌ ABSENT | §1.1 | P1 |
| Form 1040 | Lines 1a–1z income sub-breakdown | ❌ ABSENT | §1.2 | P1 |
| Form 1040 | Lines 4a–6b (IRA, pensions, SS) | ❌ ABSENT | §1.3 | P1 |
| Form 1040 | Preparer section (name, PTIN, firm, EIN) | ❌ ABSENT | §1.5 | P1 |
| **Schedule 1** | **Entire renderer — Part I (additional income) + Part II (adjustments)** | **❌ ABSENT** | §1–4 | **P0** |
| Form 1040 | Lines 17, 18, 21, 22 (intermediate tax calc lines) | ❌ ABSENT | §1.4 | P1 |
| Form 1040 | Lines 25a/25b/25c/25d withholding sub-breakdown | ❌ ABSENT | §1.4 | P1 |
| Form 1040 | Lines 31, 32 (Schedule 3 Line 15 + total other payments) | ❌ ABSENT | §1.4 | P1 |
| Form 1040 | Lines 35a–35d (direct deposit routing/account) | ❌ ABSENT | §1.4 | P2 |
| Form 1040 | Line 6c (SS lump-sum election checkbox) | ❌ ABSENT | §1.3 | P3 |
| Form 1040 | Third Party Designee section | ❌ ABSENT | §1.5 | P3 |
| Schedule B | Part III foreign accounts (checkboxes 7a, 7b, 8) | ❌ ABSENT | §3 | P2 |
| Schedule SE | Full line set (4b–13, SS wage base cap logic) | ⚠️ PARTIAL | §4 | P1 |
| Schedule 2 | Entire renderer | ❌ ABSENT | §5 | P1 |
| Schedule 3 | Entire renderer | ❌ ABSENT | §6 | P1 |
| Schedule 8812 | Entire renderer (Parts I, II-A, II-B, II-C) | ❌ ABSENT | §7 | P1 |
| Form 8995 | Entire renderer | ❌ ABSENT | §8 | P1 |
| Form 4562 | Entire renderer (Parts I–VI) | ❌ ABSENT | §9 | P2 |
| Schedule C | Lines 20b (rent/lease other prop), 24b (meals), 26 (wages) | ❌ ABSENT | §10 | P1 |
| Schedule C | Lines 10 (commissions), 11 (contract labor), 12 (depletion) | ❌ ABSENT | §10 | P2 |
| Schedule C | Lines 14 (emp benefits), 16a/16b (interest), 17 (legal/prof) | ❌ ABSENT | §10 | P2 |
| Schedule C | Lines 19 (pension), 20a (vehicle rent), 21 (repairs), 23 (taxes) | ❌ ABSENT | §10 | P2 |
| Schedule C | Lines 24a (travel), 30 (home office), 32a/32b (at-risk checkboxes) | ❌ ABSENT | §10 | P2 |
| Schedule C | Part III COGS (lines 33–42), Part IV vehicle (lines 43–47b) | ❌ ABSENT | §10 | P2 |
| Schedule C | Part V other expense itemization (line 48) | ❌ ABSENT | §10 | P2 |
| Form 1040-V | Entire generator | ❌ ABSENT | §11 | P1 |
| Form 1040-ES | Entire generator (4 vouchers) | ❌ ABSENT | §12 | P1 |
| CA Form 540 | **Side 1**: County, filing status codes 1–6, exemption lines 7–9 (×$149) | ❌ ABSENT | §13 | P1 |
| CA Form 540 | **Side 2**: Dep. exemptions L10 (×$461), L11, L12 state wages, L13–19 income/deduction chain | ❌ ABSENT | §13 | P1 |
| CA Form 540 | **Side 2**: Tax/credit lines 31–35, 40, 43, 44 | ❌ ABSENT | §13 | P1 |
| CA Form 540 | **Side 3**: Credits 45–48, AMT L61, Mental Health Svcs Tax L62, L63–64 total tax | ❌ ABSENT | §13 | P1 |
| CA Form 540 | **Side 3**: Payments L71–78, use tax L91, ISR penalty L92, balance lines L93–97 | ❌ ABSENT | §13 | P1 |
| CA Form 540 | **Side 4**: Lines 98–100, voluntary contributions codes 400–447, L110 | ❌ ABSENT | §13 | P2 |
| CA Form 540 | **Side 5**: Lines 111–116 (amount owed/refund), direct deposit, health care, voter info | ❌ ABSENT | §13 | P2 |
| CA Form 540 | **Side 6**: Signature block (preparer name, PTIN, firm address, FEIN) | ❌ ABSENT | §13 | P2 |
| Form 8867 | Entire generator (Parts I–VI) | ❌ ABSENT | §15 | P2 |
| Validation | V-16: ACTC arithmetic | ❌ ABSENT | §17 | P2 |
| Validation | V-17: Schedule 2 consistency | ❌ ABSENT | §17 | P2 |
| Validation | V-18: Estimated tax trigger | ❌ ABSENT | §17 | P2 |
| Validation | V-19: Form 4562 consistency | ❌ ABSENT | §17 | P2 |
| Validation | V-20: 1040-ES amount | ❌ ABSENT | §17 | P2 |
| Validation | V-21: Schedule B chain | ❌ ABSENT | §17 | P2 |
| Validation | V-22: Schedule SE arithmetic | ❌ ABSENT | §17 | P2 |
| generate.py | Estimated tax pipeline wired | ❌ ABSENT | §18 | P2 |
| generate.py | 1040-V / 1040-ES / 8867 generation calls | ❌ ABSENT | §18 | P2 |
| generate.py | V-15 file existence list updated | ❌ ABSENT | §15.5 | P2 |

---

## Critical Bug: OBBBA Phase-Out Parameters

**File:** `tax_engine/tax_tables.py` · Lines 257–285

Four phase-out endpoints in `OBBBA_DEDUCTIONS` are wrong vs the v2 guide and the statutory source (Public Law 119-21).

```python
# CURRENT (WRONG) → CORRECT

# Tips
"phaseout_end": {"single": 400000, "hoh": 400000, "mfj": 550000},
# SHOULD BE:
"phaseout_end": {"single": 400000, "hoh": 400000, "mfj": 700000},
#   Derivation: $300K start + (($400K cap / $100 per $1K) × $1K) = $700K

# Overtime
"phaseout_end": {"single": 400000, "hoh": 400000, "mfj": 550000},
# SHOULD BE:
"phaseout_end": {"single": 275000, "hoh": 275000, "mfj": 550000},
#   Derivation: $150K start + ($12,500 cap / $100 per $1K × $1K) = $275K

# Car Loan Interest
"phaseout_end": {"single": 149000, "hoh": 149000, "mfj": 249000},
# SHOULD BE:
"phaseout_end": {"single": 150000, "hoh": 150000, "mfj": 250000},
#   Derivation: $100K start + ($10K cap / $200 per $1K × $1K) = $150K

# Senior — MFJ end
"phaseout_end": {"single": 175000, "hoh": 175000, "mfj": 250000},
# SHOULD BE:
"phaseout_end": {"single": 175000, "hoh": 175000, "mfj": 350000},
#   Source: Guide §2.1 table — $150K start + $200K range = $350K
```

**Fix:** Edit the four `phaseout_end` values before any other work. These affect downstream V-12 validation and the OBBBA deduction amounts in every generated dataset for 2025+.

---

## Phase 1 — Data Model

**File:** `tax_engine/profile_generator.py`

### 1.1 Add `PrepNotes` dataclass

```python
@dataclass
class PrepNotes:
    name: str = ""
    ptin: str = ""          # Format: P + 8 digits
    firm_name: str = ""
    firm_address: str = ""
    firm_ein: str = ""
    self_employed: bool = False

def _generate_ptin() -> str:
    return f"P{random.randint(10000000, 99999999)}"
```

Add to `generate_profile()` before return:

```python
profile.preparer = PrepNotes(
    name=fake.name(),
    ptin=_generate_ptin(),
    firm_name=f"{fake.last_name()} Tax Services LLC",
    firm_address=f"{random.randint(100,9999)} {fake.street_name()}, "
                 f"{fake.city()}, {fake.state_abbr()} {fake.zipcode()}",
    firm_ein=_generate_ein(),
    self_employed=False,
)
profile.phone = fake.phone_number()
profile.email  = fake.email()
```

### 1.2 Add fields to `TaxProfile`

```python
# Append to TaxProfile dataclass:
phone: str = ""
email: str = ""
preparer: Optional[PrepNotes] = None
has_home_office: bool = False
home_office_sqft: int = 0
home_office_deduction: float = 0.0
```

### 1.3 Extend `BusinessIncome` dataclass

```python
# Append to BusinessIncome dataclass:
rent_expense: float = 0.0           # Schedule C Line 20b (other business prop.)
deductible_meals: float = 0.0       # Schedule C Line 24b (50% limitation applied)
wages_paid: float = 0.0             # Schedule C Line 26
other_expense_items: List[tuple] = field(default_factory=list)
    # List of (description, amount) tuples for Part V
material_participation: bool = True
made_1099_payments: bool = False
will_file_1099: bool = False
vehicle: Optional[dict] = None      # See §1.4 below
depreciable_assets: List["DepreciableAsset"] = field(default_factory=list)
```

### 1.4 Add `DepreciableAsset` dataclass

```python
@dataclass
class DepreciableAsset:
    description: str
    placed_in_service: str      # MM/YYYY
    cost: float
    recovery_period: int        # years (5, 7, etc.)
    method: str                 # "200DB", "S/L"
    convention: str             # "HY", "MM", "MQ"
    depreciation_this_year: float
    section_179_elected: float = 0.0
    prior_depreciation: float = 0.0
```

### 1.5 Vehicle dict structure (for Part IV of Schedule C)

```python
vehicle = {
    "description": "2021 Honda Civic",
    "placed_in_service": "01/2022",
    "total_miles": 12000,
    "business_miles": 9600,
    "commuting_miles": 0,
    "other_miles": 2400,
    "available_personal": True,
    "another_vehicle": True,
    "written_evidence": True,
}
```

---

## Phase 2 — Calculators

**File:** `tax_engine/federal_calculator.py`

### 2.1 Add Lines 1a–1z to `compute_federal_tax()` results

After the wages computation block, add:

```python
results["line_1a"] = round(total_wages, 2)
results["line_1b"] = 0.0    # Household employee wages
results["line_1c"] = 0.0    # Tips not on W-2
results["line_1d"] = 0.0    # Medicaid waiver
results["line_1e"] = 0.0    # Taxable dependent care benefits
results["line_1f"] = 0.0    # Employer adoption benefits
results["line_1g"] = 0.0    # Form 8919 wages
results["line_1h"] = 0.0    # Other earned income
results["line_1i"] = 0.0    # Nontaxable combat pay (election)
results["line_1z"] = round(total_wages, 2)  # Sum 1a–1h
```

Add stub lines for unrealized income types:

```python
results["ira_distributions_total"]   = 0.0   # Line 4a
results["ira_distributions_taxable"] = 0.0   # Line 4b
results["pensions_total"]            = 0.0   # Line 5a
results["pensions_taxable"]          = 0.0   # Line 5b
results["ss_benefits_total"]         = 0.0   # Line 6a
results["ss_benefits_taxable"]       = 0.0   # Line 6b
results["capital_gains_line7"]       = 0.0   # Line 7 (stub; CG modeled via LTCG)
results["schedule_d_required"]       = False
```

Add Page 2 cross-reference stubs:

```python
results["schedule_2_line_3"]       = results.get("amt_excess", 0.0)
results["schedule_3_line_8"]       = 0.0
results["withholding_1099"]        = 0.0    # Line 25b
results["earned_income_credit"]    = 0.0    # Line 27
results["additional_ctc"]         = 0.0    # Line 28 (set by 8812 calc below)
results["aoc_refundable"]         = 0.0    # Line 29
results["estimated_tax_penalty"]   = 0.0   # Line 38
```

### 2.2 Add `compute_schedule_se()` as standalone function

Extract the current inline `_compute_se_tax()` into a full Schedule SE dict:

```python
def compute_schedule_se(profile, business_net: float,
                        ss_wage_base: float, w2_wages: float) -> dict:
    """Full Schedule SE computation — returns all lines for rendering."""
    se_data = {}
    se_data["line_2"]  = round(business_net, 2)           # Net profit from Sch C
    se_data["line_3"]  = round(business_net, 2)           # Combined

    se_earnings = business_net * 0.9235
    se_data["line_4a"] = round(se_earnings, 2)
    se_data["line_4b"] = 0.0                              # Optional method
    se_data["line_4c"] = round(se_earnings, 2)            # Combine 4a+4b

    se_data["line_6"]  = round(se_earnings, 2)            # (no church income)
    se_data["line_7"]  = ss_wage_base

    remaining_base = max(0.0, ss_wage_base - w2_wages)
    se_data["line_8a"] = round(w2_wages, 2)
    se_data["line_8b"] = 0.0
    se_data["line_8c"] = 0.0
    se_data["line_8d"] = round(w2_wages, 2)
    se_data["line_9"]  = round(remaining_base, 2)

    ss_tax     = round(min(se_earnings, remaining_base) * SS_TAX_RATE, 2)
    medicare   = round(se_earnings * MEDICARE_TAX_RATE, 2)
    se_tax     = round(ss_tax + medicare, 2)
    se_deduct  = round(se_tax * 0.50, 2)

    se_data["line_10"] = ss_tax
    se_data["line_11"] = medicare
    se_data["line_12_se_tax"]  = se_tax
    se_data["line_13_deduction"] = se_deduct

    return se_data
```

Wire into `compute_federal_tax()`:

```python
if business_net > 0:
    se_data = compute_schedule_se(profile, business_net, ss_base, total_wages)
    results["se_data"] = se_data
    results["se_tax"]  = se_data["line_12_se_tax"]
    results["se_tax_deduction"] = se_data["line_13_deduction"]
```

### 2.3 Add `compute_schedule_2()` function

```python
def compute_schedule_2(profile, income_tax: float, se_tax: float,
                       medicare_surtax: float, amt_excess: float) -> dict:
    """Schedule 2 — Additional Taxes."""
    s2 = {}
    s2["line_1z"] = 0.0              # Excess APTC repayment
    s2["part_i_total"] = round(amt_excess, 2)
    s2["line_3"]  = round(amt_excess, 2)   # AMT (→ Form 1040 Line 17)
    s2["line_4"]  = round(se_tax, 2)       # SE tax
    s2["line_5"]  = 0.0                    # Unreported tip SS/Medicare
    s2["line_6"]  = 0.0                    # Uncollected SS/Medicare wages
    s2["line_7"]  = 0.0                    # Sum 5+6
    s2["line_8"]  = 0.0                    # Additional tax on IRAs
    s2["line_11"] = round(medicare_surtax, 2)  # Additional Medicare
    s2["line_12"] = 0.0                    # NIIT (compute separately if needed)
    s2["part_ii_total"] = round(
        se_tax + medicare_surtax + s2["line_12"], 2)
    s2["line_21"] = s2["part_ii_total"]    # → Form 1040 Line 23
    return s2
```

### 2.4 Add `compute_schedule_8812()` with ACTC

```python
def compute_schedule_8812(profile, agi: float, income_tax: float,
                          total_credits_before: float) -> dict:
    """Schedule 8812 — CTC, ODC, and ACTC computation."""
    s = {}
    year = profile.tax_year
    status = profile.filing_status

    s["line_1"]  = round(agi, 2)

    qualifying_under_17 = [d for d in profile.dependents if d.age < 17]
    other_deps = [d for d in profile.dependents if d.age >= 17]

    from tax_engine.tax_tables import get_ctc_per_child
    ctc_per = get_ctc_per_child(year, 10)   # representative age
    s["line_4"] = len(qualifying_under_17)
    s["line_5"] = len(qualifying_under_17) * ctc_per
    s["line_6"] = len(other_deps)
    s["line_7"] = len(other_deps) * 500
    s["line_8"] = s["line_5"] + s["line_7"]

    threshold = {"mfj": 400000}.get(status, 200000)
    s["line_9"]  = threshold
    excess = max(0, agi - threshold)
    excess_rounded = (excess // 1000) * 1000 + (1000 if excess % 1000 else 0)
    s["line_10"] = excess_rounded
    s["line_11"] = round(excess_rounded * 0.05, 2)

    credit_limit = max(0, income_tax - total_credits_before)
    s["line_12"] = max(0, s["line_8"] - s["line_11"])
    s["line_13"] = credit_limit            # from Credit Limit Worksheet A
    s["line_14"] = min(s["line_12"], s["line_13"])

    # Part II-A: ACTC
    actc_max_per_child = 1700 if year >= 2024 else 1600
    s["line_15"] = max(0, s["line_12"] - s["line_14"])
    s["line_16a"] = s["line_4"] * actc_max_per_child
    s["line_16b"] = s["line_15"]
    s["line_17"]  = min(s["line_16a"], s["line_16b"])

    total_wages = sum(w.wages for w in profile.w2_incomes)
    s["line_18a"] = round(total_wages, 2)
    actc_earned = max(0, total_wages - 2500) * 0.15
    s["line_19"]  = round(max(0, total_wages - 2500), 2)
    s["line_20"]  = round(actc_earned, 2)
    s["line_27"]  = round(min(s["line_17"], s["line_20"]), 2)   # ACTC → Form 1040 L28

    return s
```

### 2.5 Add `compute_schedule_8995()` dict

Currently `qbi_deduction` is computed inline but not stored as a structured dict. Add:

```python
results["schedule_8995"] = {
    "line_1i_income": round(business_net, 2),
    "line_2":  round(total_net_qbi, 2),
    "line_4":  round(total_net_qbi, 2),
    "line_5":  round(business_net * QBI_DEDUCTION_RATE, 2),
    "line_11": round(agi - std_ded, 2),        # taxable income before QBI
    "line_12": round(total_qualified_div, 2),  # net capital gain
    "line_13": round(max(0, (agi - std_ded) - total_qualified_div), 2),
    "line_14": round(max(0, (agi - std_ded) - total_qualified_div)
                     * QBI_DEDUCTION_RATE, 2),
    "line_15": round(qbi_deduction, 2),
}
```

### 2.6 Add `compute_estimated_tax_next_year()` function

```python
def compute_estimated_tax_next_year(profile, current_year_tax: float,
                                     current_agi: float) -> dict:
    """Determine if estimated tax payments are required for next year.

    Safe harbor: 100% of prior year tax (110% if AGI > $150K).
    """
    safe_harbor_pct = 1.10 if current_agi > 150_000 else 1.00
    annual_est = round(current_year_tax * safe_harbor_pct, 2)
    per_quarter = round(annual_est / 4, 2)
    required = (
        profile.business_income is not None
        and current_year_tax > 1000
    )
    return {
        "required": required,
        "annual_amount": annual_est,
        "per_quarter": per_quarter,
        "safe_harbor_pct": safe_harbor_pct,
        "quarters": {
            1: {"due": f"{current_year_tax.__class__.__name__}", "amount": per_quarter},
        },
    }
```

---

## Phase 3 — Tax Tables

**File:** `tax_engine/tax_tables.py`

### 3.1 Fix OBBBA Phase-Out Endpoints (see Critical Bug section above)

### 3.2 Add Missing Constant Tables

Append after existing constants:

```python
# ─── Bonus Depreciation Rate ───────────────────────────────────────────────
BONUS_DEPRECIATION_RATE = {
    2020: 1.00, 2021: 1.00, 2022: 1.00,
    2023: 0.80, 2024: 0.60,
    2025: 1.00,   # ★ OBBBA restored
    2026: 1.00, 2027: 1.00, 2028: 1.00,
}

# ─── Section 179 Max & Phase-Out ───────────────────────────────────────────
SECTION_179_MAX = {
    2020: 1_040_000, 2021: 1_050_000, 2022: 1_080_000,
    2023: 1_160_000, 2024: 1_220_000,
    2025: 2_500_000,  # ★ OBBBA
    2026: 2_500_000,
}
SECTION_179_PHASEOUT_START = {
    2020: 2_590_000, 2021: 2_620_000, 2022: 2_700_000,
    2023: 2_890_000, 2024: 3_050_000,
    2025: 4_000_000,  # ★ OBBBA
    2026: 4_000_000,
}

# ─── Standard Mileage Rate ($/mile) ────────────────────────────────────────
STANDARD_MILEAGE_RATE = {
    2020: 0.575, 2021: 0.560, 2022: 0.585,
    2023: 0.655, 2024: 0.670, 2025: 0.700,
}

# ─── Home Office Simplified Rate ($/sqft) ──────────────────────────────────
HOME_OFFICE_RATE = {
    2020: 5.00, 2021: 5.00, 2022: 5.00,
    2023: 5.00, 2024: 5.00, 2025: 6.00,  # ★ OBBBA
}
HOME_OFFICE_MAX_SQFT = 300   # cap: 300 sqft

# ─── MACRS GDS Half-Year Convention Tables ─────────────────────────────────
# Percentage of cost deducted each year (200DB, HY convention)
# Index = year of recovery (1-based)
MACRS_GDS_HY = {
    "5-year":  [20.00, 32.00, 19.20, 11.52, 11.52, 5.76],
    "7-year":  [14.29, 24.49, 17.49, 12.49, 8.93, 8.92, 8.93, 4.46],
    "15-year": [5.00, 9.50, 8.55, 7.70, 6.93, 6.23, 5.90,
                5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 5.90, 5.91, 2.95],
}

# ─── SALT Cap helper ───────────────────────────────────────────────────────
def get_salt_cap(tax_year: int, filing_status: str, agi: float) -> float:
    """Return the applicable SALT cap for the year and AGI.

    2025+: OBBBA raised cap to $40K; phases out above $500K AGI ($50 per $1K),
    flooring at $10K.
    """
    if tax_year < 2025:
        return 10_000.0
    base = 40_000.0
    if agi > 500_000:
        reduction = ((agi - 500_000) / 1000) * 50
        base = max(10_000.0, base - reduction)
    return base
```

---

## Phase 2b — `compute_schedule_1()` Structured Dict

**File:** `tax_engine/federal_calculator.py`

Schedule 1 is the bridge between supplemental income/deductions and Form 1040. Currently, business income and SE deduction are computed inline without a structured `schedule_1` dict. Add:

```python
def compute_schedule_1(profile, business_net: float,
                       se_deduction: float, schedule_1a_total: float) -> dict:
    """Build the Schedule 1 line dict for rendering.

    Part I — Additional Income (flows to Form 1040 Line 8)
    Part II — Adjustments to Income (flows to Form 1040 Line 10)
    """
    s1 = {}

    # Part I — Additional Income
    s1["line_1"]  = 0.0          # Taxable refunds of state/local taxes
    s1["line_2a"] = 0.0          # Alimony received
    s1["line_3"]  = round(business_net, 2)   # Business income (Schedule C)
    s1["line_4"]  = 0.0          # Other gains (Form 4797)
    s1["line_5"]  = 0.0          # Rental/royalties/partnerships (Schedule E)
    s1["line_6"]  = 0.0          # Farm income (Schedule F)
    s1["line_7"]  = 0.0          # Unemployment compensation
    s1["line_8z"] = 0.0          # Other income (catch-all)
    s1["line_9"]  = 0.0          # Total other income (sum 8a–8z)
    # Line 10 = sum of lines 1–7 + line 9 → Form 1040 Line 8
    s1["line_10"] = round(
        s1["line_1"] + s1["line_2a"] + s1["line_3"] +
        s1["line_4"] + s1["line_5"] + s1["line_6"] +
        s1["line_7"] + s1["line_9"], 2)

    # Part II — Adjustments to Income
    s1["line_11"] = 0.0           # Educator expenses
    s1["line_12"] = 0.0           # Business expenses (reservists/artists)
    s1["line_13"] = 0.0           # HSA deduction (Form 8889)
    s1["line_14"] = 0.0           # Moving expenses (Armed Forces)
    s1["line_15"] = round(se_deduction, 2)    # ½ SE tax deduction
    s1["line_16"] = 0.0           # SEP/SIMPLE
    s1["line_17"] = 0.0           # Self-employed health insurance
    s1["line_18"] = 0.0           # Penalty on early withdrawal of savings
    s1["line_20"] = 0.0           # IRA deduction
    s1["line_21"] = 0.0           # Student loan interest
    s1["line_23"] = 0.0           # Archer MSA
    s1["line_25"] = 0.0           # Total other adjustments
    # OBBBA Schedule 1-A total flows into line 26 via "other adjustments"
    s1["line_26_obbba"] = round(schedule_1a_total, 2)
    # Line 26 = sum 11–23 + 25 + OBBBA → Form 1040 Line 10
    s1["line_26"] = round(
        s1["line_15"] + s1["line_26_obbba"], 2)

    return s1
```

Wire into `compute_federal_tax()` after SE deduction and Schedule 1-A calculations:

```python
schedule_1 = compute_schedule_1(
    profile, business_net, se_deduction, schedule_1a["total"])
results["schedule_1"] = schedule_1
# Ensure Form 1040 Line 8 and Line 10 use the Schedule 1 values
results["additional_income_sch1"] = schedule_1["line_10"]   # → F1040 L8
results["total_adjustments"] = schedule_1["line_26"]         # → F1040 L10
```

---

## Phase 2c — Form 1040 Intermediate Calculation Lines

Add these keys to `compute_federal_tax()` results for complete Form 1040 Page 2 rendering:

```python
# Line 17 = Schedule 2 Line 3 (AMT excess)
results["line_17_sch2_line3"] = results.get("amt_excess", 0.0)
# Line 18 = Line 16 + Line 17
results["line_18"] = round(results["income_tax"] + results.get("amt_excess", 0.0), 2)
# Line 21 = Line 19 (CTC) + Line 20 (Sch3 Line 8)
results["line_21"] = round(results["child_tax_credit"] + results.get("schedule_3_line_8", 0.0), 2)
# Line 22 = Line 18 - Line 21
results["line_22"] = round(max(0, results["line_18"] - results["line_21"]), 2)
# Lines 25a/25b/25c/25d — withholding breakdown
results["line_25a"] = results["federal_withheld"]   # W-2 withholding
results["line_25b"] = 0.0                           # 1099 withholding
results["line_25c"] = 0.0                           # Other
results["line_25d"] = results["federal_withheld"]   # Total 25a+25b+25c
# Line 32 = Lines 27 + 28 + 29 + 31
results["line_32"] = round(
    results.get("earned_income_credit", 0.0) +
    results.get("additional_ctc", 0.0) +
    results.get("aoc_refundable", 0.0) +
    results.get("schedule_3_line_15", 0.0), 2)
# Line 33 = Lines 25d + 26 + 32
results["line_33"] = round(
    results["line_25d"] +
    results.get("estimated_payments", 0.0) +
    results["line_32"], 2)
results["total_payments"] = results["line_33"]
```

---

## Phase 4 — PDF Rendering

**File:** `generators/tax_forms.py`

> **Architecture note:** The reference PDF uses exact IRS form layout with absolute-positioned text fields, checkboxes, and OCR scan lines. The current code uses ReportLab `Table` flowables, producing a visually distinct tabular report. To match the reference PDF format, the rendering approach must shift to **absolute-position coordinate-based drawing** using `canvas` calls rather than flowable elements.
>
> The recommended approach: create a `ReportLab Canvas`-based `_draw_field(canvas, x, y, value)` helper, then define per-form coordinate maps. This allows pixel-accurate reproduction of IRS box positions.

### 4.0 Add `_add_schedule_1_page()` ★ NEW — MISSING FROM ORIGINAL PLAN

Schedule 1 appears on pages 3–4 of the reference PDF and is the **most critical missing renderer**. It carries business income from Schedule C (line 3) and the SE tax deduction (line 15) into Form 1040.

```python
def _add_schedule_1_page(story, profile, styles):
    """Schedule 1 — Additional Income and Adjustments to Income.

    Part I:  Additional Income → sums to Line 10 → Form 1040 Line 8
    Part II: Adjustments to Income → sums to Line 26 → Form 1040 Line 10
    """
    fed = profile.federal_results
    s1  = fed.get("schedule_1", {})
    _form_header(story, styles, "Schedule 1 — Additional Income and Adjustments",
                 "Form 1040  |  OMB No. 1545-0074  |  Sequence No. 01",
                 profile.tax_year, profile)

    # Part I — Additional Income
    story.append(Paragraph("<b>Part I — Additional Income</b>", styles['SectionHeader']))
    p1_rows = [["Line", "Description", "Amount"]]
    p1_rows.append(_line_row("1",   "Taxable refunds of state/local taxes",     s1.get("line_1", 0)))
    p1_rows.append(_line_row("2a",  "Alimony received",                          s1.get("line_2a", 0)))
    p1_rows.append(_line_row("3",   "Business income or (loss) — Attach Sch C", s1.get("line_3", 0)))
    p1_rows.append(_line_row("4",   "Other gains or (losses) — Attach Form 4797",s1.get("line_4", 0)))
    p1_rows.append(_line_row("5",   "Rental real estate, royalties, partnerships",s1.get("line_5", 0)))
    p1_rows.append(_line_row("6",   "Farm income or (loss) — Attach Schedule F", s1.get("line_6", 0)))
    p1_rows.append(_line_row("7",   "Unemployment compensation",                 s1.get("line_7", 0)))
    p1_rows.append(_line_row("8z",  "Other income (see instructions)",           s1.get("line_8z", 0)))
    p1_rows.append(_line_row("9",   "Total other income (add lines 8a–8z)",      s1.get("line_9", 0)))
    p1_rows.append(_line_row("10",  "Additional income — enter on Form 1040 Line 8",
                              s1.get("line_10", 0)))
    story.append(_build_line_table(p1_rows, styles))
    story.append(Spacer(1, 12))

    # Part II — Adjustments to Income
    story.append(Paragraph("<b>Part II — Adjustments to Income</b>", styles['SectionHeader']))
    p2_rows = [["Line", "Description", "Amount"]]
    p2_rows.append(_line_row("11",  "Educator expenses",                         s1.get("line_11", 0)))
    p2_rows.append(_line_row("12",  "Certain business expenses (Form 2106)",     s1.get("line_12", 0)))
    p2_rows.append(_line_row("13",  "HSA deduction (Form 8889)",                 s1.get("line_13", 0)))
    p2_rows.append(_line_row("14",  "Moving expenses — Armed Forces (Form 3903)",s1.get("line_14", 0)))
    p2_rows.append(_line_row("15",  "Deductible part of self-employment tax",    s1.get("line_15", 0)))
    p2_rows.append(_line_row("16",  "Self-employed SEP, SIMPLE, qualified plans",s1.get("line_16", 0)))
    p2_rows.append(_line_row("17",  "Self-employed health insurance deduction",  s1.get("line_17", 0)))
    p2_rows.append(_line_row("18",  "Penalty on early withdrawal of savings",    s1.get("line_18", 0)))
    p2_rows.append(_line_row("20",  "IRA deduction",                             s1.get("line_20", 0)))
    p2_rows.append(_line_row("21",  "Student loan interest deduction",           s1.get("line_21", 0)))
    p2_rows.append(_line_row("23",  "Archer MSA deduction",                      s1.get("line_23", 0)))
    if s1.get("line_26_obbba", 0) > 0:
        p2_rows.append(_line_row("24z", "OBBBA Schedule 1-A deductions (tips/overtime/car/senior)",
                                  s1.get("line_26_obbba", 0)))
    p2_rows.append(_line_row("25",  "Total other adjustments",                   s1.get("line_25", 0)))
    p2_rows.append(_line_row("26",  "Adjustments — enter on Form 1040 Line 10", s1.get("line_26", 0)))
    story.append(_build_line_table(p2_rows, styles))
```

Wire into `generate_tax_forms()` — insert **before** Schedule C (Schedule 1 must come after Form 1040, before Schedule B):

```python
# Schedule 1 (always needed when business income or adjustments exist)
if fed.get("additional_income_sch1", 0) > 0 or fed.get("total_adjustments", 0) > 0:
    story.append(PageBreak())
    _add_schedule_1_page(story, profile, styles)
```

### 4.1 Coordinate-Based Drawing Infrastructure

Add at the top of `tax_forms.py`:

```python
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.pagesizes import letter

PAGE_W, PAGE_H = letter   # 612 × 792 pts

def _draw_text(c, x, y, text, size=9, bold=False):
    c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
    c.drawString(x, y, str(text))

def _draw_currency(c, x, y, amount, size=9):
    """Right-align a dollar amount at coordinate x."""
    s = f"{int(round(amount)):,}" if amount else ""
    c.setFont("Helvetica", size)
    c.drawRightString(x, y, s)

def _draw_checkbox(c, x, y, checked=True, size=8):
    c.rect(x, y, size, size)
    if checked:
        c.line(x, y, x+size, y+size)
        c.line(x+size, y, x, y+size)
```

### 4.2 Update `_add_form_1040_page()` — Missing Fields

Add the following renders after existing content:

**Identity block (Page 1 top):**
```python
# DOBs
_draw_text(c, 36, 730, f"DOB: {profile.primary_dob}")
if profile.filing_status == "mfj":
    _draw_text(c, 320, 730, f"Spouse DOB: {profile.spouse_dob}")

# Presidential Election Fund checkbox (always unchecked)
_draw_checkbox(c, 510, 722, checked=False)

# Digital assets checkbox (always No)
_draw_text(c, 36, 710, "Digital assets (crypto received/sold): ")
_draw_checkbox(c, 410, 708, checked=False)  # Yes
_draw_checkbox(c, 440, 708, checked=True)   # No

# Age / blindness
if profile.is_senior_65_plus:
    _draw_checkbox(c, 380, 695, checked=True)  # Born before Jan 2, 1960
```

**Income sub-lines (1a–1z):**
```python
lines_1 = [
    ("1a", "Total wages (W-2 Box 1)",      fed["line_1a"]),
    ("1b", "Household employee wages",     fed["line_1b"]),
    ("1c", "Tip income not on W-2",        fed["line_1c"]),
    ("1z", "Add lines 1a–1h",              fed["line_1z"]),
    ("2a", "Tax-exempt interest",          0),
    ("2b", "Taxable interest",             fed["taxable_interest"]),
    ("3a", "Qualified dividends",          fed["qualified_dividends"]),
    ("3b", "Ordinary dividends",           fed["ordinary_dividends"]),
    ("4a", "IRA distributions",            fed["ira_distributions_total"]),
    ("4b", "Taxable amount",               fed["ira_distributions_taxable"]),
    ("5a", "Pensions and annuities",       fed["pensions_total"]),
    ("5b", "Taxable amount",               fed["pensions_taxable"]),
    ("6a", "Social security benefits",     fed["ss_benefits_total"]),
    ("6b", "Taxable amount",               fed["ss_benefits_taxable"]),
    ("7",  "Capital gain or (loss)",       fed["capital_gains_line7"]),
]
```

**Preparer section (Page 2 bottom):**
```python
prep = getattr(profile, "preparer", None)
if prep:
    _draw_text(c, 36,  100, prep.name)
    _draw_text(c, 240, 100, prep.ptin)
    _draw_text(c, 36,  88,  prep.firm_name)
    _draw_text(c, 36,  76,  prep.firm_address)

# Sign Here block
_draw_text(c, 36, 118, f"{profile.primary_occupation}")
if profile.filing_status == "mfj":
    _draw_text(c, 310, 106, f"{profile.spouse_occupation}")
_draw_text(c, 36, 64, getattr(profile, "phone", ""))
_draw_text(c, 240, 64, getattr(profile, "email", ""))
```

### 4.3 Complete Schedule SE Renderer

Current renderer has only 5 lines. Add the full line set:

```python
def _add_schedule_se_page(story, profile, styles):
    se = profile.federal_results.get("se_data", {})
    biz = profile.business_income
    # ...header...
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("2",   "Net profit from Schedule C",        se.get("line_2", 0)))
    rows.append(_line_row("3",   "Combined net earnings",             se.get("line_3", 0)))
    rows.append(_line_row("4a",  "92.35% of line 3",                  se.get("line_4a", 0)))
    rows.append(_line_row("4c",  "Combine 4a and 4b",                 se.get("line_4c", 0)))
    rows.append(_line_row("6",   "SE income (less church employee)",  se.get("line_6", 0)))
    rows.append(_line_row("7",   "Max SS wage base",                  se.get("line_7", 0)))
    rows.append(_line_row("8a",  "Social security wages (W-2)",       se.get("line_8a", 0)))
    rows.append(_line_row("8d",  "Add 8a, 8b, 8c",                   se.get("line_8d", 0)))
    rows.append(_line_row("9",   "Subtract 8d from 7",                se.get("line_9", 0)))
    rows.append(_line_row("10",  "SS tax (12.4%)",                    se.get("line_10", 0)))
    rows.append(_line_row("11",  "Medicare tax (2.9%)",               se.get("line_11", 0)))
    rows.append(_line_row("12",  "Self-employment tax (add 10+11)",   se.get("line_12_se_tax", 0)))
    rows.append(_line_row("13",  "SE tax deduction (50%)",            se.get("line_13_deduction", 0)))
```

### 4.4 Add `_add_schedule_2_page()`

```python
def _add_schedule_2_page(story, profile, styles):
    """Schedule 2 — Additional Taxes (Part I: AMT; Part II: SE, Medicare)."""
    fed = profile.federal_results
    s2  = fed.get("schedule_2", {})
    _form_header(story, styles, "Schedule 2 — Additional Taxes", ...)
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("1z", "Total other additions to tax",    s2.get("line_1z", 0)))
    rows.append(_line_row("2",  "Alternative minimum tax",         s2.get("line_3", 0)))
    rows.append(_line_row("3",  "Add 1z + 2 (→ Form 1040 L17)",   s2.get("line_3", 0)))
    rows.append(_line_row("4",  "Self-employment tax (Sch SE)",    s2.get("line_4", 0)))
    rows.append(_line_row("11", "Additional Medicare Tax (8959)",  s2.get("line_11", 0)))
    rows.append(_line_row("12", "Net investment income tax (8960)",s2.get("line_12", 0)))
    rows.append(_line_row("21", "Total other taxes (→ Form 1040 L23)", s2.get("line_21", 0)))
    story.append(_build_line_table(rows, styles))
```

Call this from `generate_tax_forms()`:

```python
story.append(PageBreak())
_add_schedule_2_page(story, profile, styles)
```

### 4.5 Add `_add_schedule_3_page()`

```python
def _add_schedule_3_page(story, profile, styles):
    """Schedule 3 — Additional Credits & Payments."""
    fed = profile.federal_results
    _form_header(story, styles, "Schedule 3 — Additional Credits and Payments", ...)
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("8",  "Total additional credits (→ Form 1040 L20)", 0))
    rows.append(_line_row("11", "Adoption credit",                             0))
    rows.append(_line_row("15", "Total other payments/refundable credits",     0))
    story.append(_build_line_table(rows, styles))
```

### 4.6 Add `_add_schedule_8812_page()`

```python
def _add_schedule_8812_page(story, profile, styles):
    """Schedule 8812 — Credits for Qualifying Children and Other Dependents."""
    fed = profile.federal_results
    s   = fed.get("schedule_8812", {})
    _form_header(story, styles, "Schedule 8812 — Child Tax Credit / ACTC", ...)

    # Part I — CTC & ODC
    story.append(Paragraph("<b>Part I — Child Tax Credit and Credit for Other Dependents</b>", styles['SectionHeader']))
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("1",  "AGI (Form 1040 Line 11)",               s.get("line_1", 0)))
    rows.append(_line_row("4",  "Qualifying children under 17",          s.get("line_4", 0)))
    rows.append(_line_row("5",  "CTC amount (line 4 × $2,000)",          s.get("line_5", 0)))
    rows.append(_line_row("6",  "Other dependents",                      s.get("line_6", 0)))
    rows.append(_line_row("7",  "ODC amount (line 6 × $500)",            s.get("line_7", 0)))
    rows.append(_line_row("8",  "Total CTC + ODC",                       s.get("line_8", 0)))
    rows.append(_line_row("9",  "Phase-out threshold",                   s.get("line_9", 0)))
    rows.append(_line_row("11", "Phase-out reduction",                   s.get("line_11", 0)))
    rows.append(_line_row("12", "Credit after phase-out",                s.get("line_12", 0)))
    rows.append(_line_row("14", "Child tax credit (→ Form 1040 L19)",   s.get("line_14", 0)))
    story.append(_build_line_table(rows, styles))
    story.append(Spacer(1, 10))

    # Part II-A — ACTC
    story.append(Paragraph("<b>Part II-A — Additional Child Tax Credit</b>", styles['SectionHeader']))
    rows2 = [["Line", "Description", "Amount"]]
    rows2.append(_line_row("15", "Excess of line 12 over line 14",       s.get("line_15", 0)))
    rows2.append(_line_row("16a", "Qualifying children × $1,700",        s.get("line_16a", 0)))
    rows2.append(_line_row("16b", "Smaller of 15 or 16a",                s.get("line_16b", 0)))
    rows2.append(_line_row("18a", "Earned income",                       s.get("line_18a", 0)))
    rows2.append(_line_row("20", "15% of earned income over $2,500",     s.get("line_20", 0)))
    rows2.append(_line_row("27", "ACTC (→ Form 1040 Line 28)",           s.get("line_27", 0)))
    story.append(_build_line_table(rows2, styles))
```

### 4.7 Add `_add_form_8995_page()`

```python
def _add_form_8995_page(story, profile, styles):
    """Form 8995 — Qualified Business Income Deduction (Simplified)."""
    fed = profile.federal_results
    s   = fed.get("schedule_8995", {})
    biz = profile.business_income
    _form_header(story, styles, "Form 8995 — QBI Deduction (Simplified Computation)", ...)

    # Business table
    biz_rows = [["Trade/Business Name", "Tax ID", "QBI or (Loss)"]]
    biz_rows.append([
        biz.business_name if biz else "—",
        format_ssn(profile.primary_ssn),
        format_currency_int(s.get("line_1i_income", 0)),
    ])
    story.append(_build_line_table(biz_rows, styles))
    story.append(Spacer(1, 8))

    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("2",  "Total QBI",                                s.get("line_2", 0)))
    rows.append(_line_row("4",  "Total qualified business income",          s.get("line_4", 0)))
    rows.append(_line_row("5",  "QBI component (line 4 × 20%)",            s.get("line_5", 0)))
    rows.append(_line_row("11", "Taxable income before QBI deduction",     s.get("line_11", 0)))
    rows.append(_line_row("12", "Net capital gain",                         s.get("line_12", 0)))
    rows.append(_line_row("13", "Line 11 minus line 12",                   s.get("line_13", 0)))
    rows.append(_line_row("14", "Income limitation (line 13 × 20%)",       s.get("line_14", 0)))
    rows.append(_line_row("15", "QBI deduction (→ Form 1040 L13)",         s.get("line_15", 0)))
    story.append(_build_line_table(rows, styles))
```

### 4.8 Add `_add_form_4562_page()`

```python
def _add_form_4562_page(story, profile, styles):
    """Form 4562 — Depreciation and Amortization."""
    biz = profile.business_income
    _form_header(story, styles, "Form 4562 — Depreciation and Amortization", ...)

    rows = [["Line", "Description", "Amount"]]
    # Part I — Section 179
    rows.append(_line_row("1",  "Maximum §179 amount",                    0))
    rows.append(_line_row("5",  "Dollar limitation for tax year",         0))
    rows.append(_line_row("12", "§179 expense deduction",                 0))

    # Part II — Bonus Depreciation
    rows.append(_line_row("14", "Special depreciation allowance",         0))

    # Part III — MACRS (assets placed in service during year)
    if biz and biz.depreciable_assets:
        for asset in biz.depreciable_assets:
            rows.append(_line_row(
                "19",
                f"{asset.description} ({asset.recovery_period}-yr, {asset.method})",
                asset.depreciation_this_year
            ))

    rows.append(_line_row("22", "Total depreciation (→ Schedule C L13)",
                          biz.depreciation if biz else 0))
    story.append(_build_line_table(rows, styles))

    # Part IV — Vehicle info (if applicable)
    if biz and biz.vehicle:
        v = biz.vehicle
        story.append(Spacer(1, 10))
        story.append(Paragraph("<b>Part V — Listed Property (Vehicle)</b>", styles['SectionHeader']))
        v_rows = [
            ["Field", "Value"],
            ["Vehicle", v.get("description", "")],
            ["Date placed in service", v.get("placed_in_service", "")],
            ["Total miles", str(v.get("total_miles", 0))],
            ["Business miles", str(v.get("business_miles", 0))],
            ["Business use %", f"{v.get('business_miles', 0) / max(1, v.get('total_miles', 1)) * 100:.1f}%"],
        ]
        story.append(Table(v_rows, colWidths=[3*inch, 4.2*inch]))
```

### 4.9 Update `_add_schedule_c_page()` — Missing Expense Lines

In the expense rendering block, add after existing `exp.utilities`:

```python
if biz.rent_expense and biz.rent_expense > 0:
    rows.append(_line_row("20b", "Rent or lease — other business property", biz.rent_expense))
if biz.deductible_meals and biz.deductible_meals > 0:
    rows.append(_line_row("24b", "Deductible meals (50% limitation applied)", biz.deductible_meals))
if biz.wages_paid and biz.wages_paid > 0:
    rows.append(_line_row("26",  "Wages (less employment credits)",          biz.wages_paid))

# Part V — Other Expenses detail
if biz.other_expense_items:
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Part V — Other Expenses</b>", styles['SectionHeader']))
    oe_rows = [["Description", "Amount"]]
    for desc, amt in biz.other_expense_items:
        oe_rows.append([desc, format_currency_int(amt)])
    oe_rows.append(["Total other expenses (→ Line 27a)", format_currency_int(exp.other)])
    story.append(Table(oe_rows, colWidths=[5.5*inch, 1.7*inch]))

# Part IV — Vehicle (if vehicle dict present)
if biz.vehicle:
    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Part IV — Vehicle Information</b>", styles['SectionHeader']))
```

### 4.10 Add `generate_1040v()` — Payment Voucher

```python
def generate_1040v(profile, output_path: str):
    """Generate Form 1040-V Payment Voucher as a standalone PDF."""
    fed = profile.federal_results
    amount_owed = fed.get("amount_owed", 0)
    if amount_owed <= 0:
        return  # No voucher needed

    from reportlab.pdfgen import canvas as rl_canvas
    c = rl_canvas.Canvas(output_path, pagesize=letter)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(36, 740, "Form 1040-V (2024) — Payment Voucher")
    c.setFont("Helvetica", 10)
    c.drawString(36, 716, f"Taxpayer: {profile.primary_first} {profile.primary_last}")
    c.drawString(36, 702, f"SSN: {format_ssn(profile.primary_ssn)}")
    if profile.spouse_ssn:
        c.drawString(300, 702, f"Spouse SSN: {format_ssn(profile.spouse_ssn)}")
    c.drawString(36, 688, f"Amount: ${amount_owed:,.2f}")
    c.drawString(36, 660, "Make check payable to: United States Treasury")
    c.drawString(36, 646, f"Write '2024 Form 1040' and SSN on payment.")
    c.drawString(36, 620, "Mail to: Internal Revenue Service")
    c.drawString(36, 606, "P.O. Box 931000, Louisville, KY 40293-1000")
    c.save()
```

### 4.11 Add `generate_1040es()` — Estimated Tax Vouchers (×4)

```python
ESTIMATED_TAX_DUE_DATES = {
    1: "April 15, {next_year}",
    2: "June 16, {next_year}",
    3: "September 15, {next_year}",
    4: "January 15, {year_after}",
}

def generate_1040es(profile, est_tax_data: dict, output_path: str):
    """Generate 4 × Form 1040-ES estimated tax vouchers."""
    if not est_tax_data.get("required"):
        return

    from reportlab.pdfgen import canvas as rl_canvas
    c = rl_canvas.Canvas(output_path, pagesize=letter)
    per_q = est_tax_data["per_quarter"]
    next_year = profile.tax_year + 1
    year_after = profile.tax_year + 2

    voucher_y = 760
    for q in range(1, 5):
        due = ESTIMATED_TAX_DUE_DATES[q].format(
            next_year=next_year, year_after=year_after)
        c.setFont("Helvetica-Bold", 11)
        c.drawString(36, voucher_y,
            f"Form 1040-ES Voucher {q} — Due {due}")
        c.setFont("Helvetica", 9)
        c.drawString(36, voucher_y - 14,
            f"Taxpayer: {profile.primary_first} {profile.primary_last}  "
            f"SSN: {format_ssn(profile.primary_ssn)}")
        c.drawString(36, voucher_y - 28,
            f"Amount: ${per_q:,.2f}")
        c.drawString(36, voucher_y - 42,
            "Make check payable to: United States Treasury")
        c.line(36, voucher_y - 58, 576, voucher_y - 58)
        voucher_y -= 80

    c.save()
```

### 4.12 Add Full CA Form 540 Multi-Page Renderer ★ EXPANDED

The reference PDF shows CA Form 540 with 6 sides (pages). The current `_add_state_form_page()` renders a minimal 6-line table. Replace entirely with the full line-accurate renderer:

```python
def _add_ca_form_540(story, profile, styles):
    """CA Form 540 — Full 6-page renderer matching IRS layout structure."""
    sr  = profile.state_results
    fed = profile.federal_results

    # ── Side 1 ─────────────────────────────────────────────────────────────
    _form_header(story, styles, "CA Form 540 (2024) — California Resident Income Tax Return",
                 "Franchise Tax Board  |  Taxable Year 2024",
                 profile.tax_year, profile)

    filing_map = {"single": "1 — Single", "mfj": "2 — Married/RDP Filing Jointly",
                  "hoh":    "4 — Head of Household"}
    story.append(Paragraph(
        f"Filing Status: <b>{filing_map.get(profile.filing_status, '1 — Single')}</b>",
        styles['FieldValue']))
    story.append(Paragraph(
        f"County: {profile.city.title()}  |  "
        f"Address: {profile.address}, {profile.city}, CA {profile.zip_code}",
        styles['FieldValue']))
    story.append(Spacer(1, 6))

    # Exemption lines 7–9 (×$149 each)
    num_personal = 2 if profile.filing_status == "mfj" else 1
    num_senior   = 1 if profile.is_senior_65_plus else 0
    ex_rows = [["Line", "Description", "Count", "Rate", "Amount"]]
    ex_rows.append(["7",  "Personal exemption",  str(num_personal), "$149",
                    format_currency_int(num_personal * 149)])
    ex_rows.append(["8",  "Blind exemption",     "0", "$149", format_currency_int(0)])
    ex_rows.append(["9",  "Senior (65+) exemption", str(num_senior), "$149",
                    format_currency_int(num_senior * 149)])
    t = Table(ex_rows, colWidths=[0.4*inch, 3.4*inch, 0.7*inch, 0.8*inch, 1.4*inch])
    t.setStyle(TableStyle([('GRID',(0,0),(-1,-1),0.5,BORDER_COLOR),
                           ('BACKGROUND',(0,0),(-1,0),HEADER_BG),
                           ('TEXTCOLOR',(0,0),(-1,0),WHITE),
                           ('FONTSIZE',(0,0),(-1,-1),9),
                           ('TOPPADDING',(0,0),(-1,-1),4),
                           ('BOTTOMPADDING',(0,0),(-1,-1),4),]))
    story.append(t)
    story.append(PageBreak())

    # ── Side 2 ─────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>CA Form 540 — Side 2</b>", styles['SectionHeader']))

    # Dependents (Line 10 — ×$461 each)
    dep_exemption_total = len(profile.dependents) * 461
    if profile.dependents:
        dep_rows = [["First Name", "Last Name", "SSN", "Relationship"]]
        for d in profile.dependents[:3]:   # Form has 3 columns max
            dep_rows.append([d.first_name, d.last_name, format_ssn(d.ssn), d.relationship])
        story.append(Table(dep_rows, colWidths=[1.5*inch,1.5*inch,1.5*inch,1.7*inch]))
        story.append(Spacer(1, 6))

    exemption_total = (num_personal * 149) + dep_exemption_total + (num_senior * 149)

    # Income / tax chain (Lines 10–44)
    s2_rows = [["Line", "Description", "Amount"]]
    s2_rows.append(_line_row("10",  f"Dependent exemptions ({len(profile.dependents)} × $461)",
                              dep_exemption_total))
    s2_rows.append(_line_row("11",  "Total exemptions (lines 7–10)",            exemption_total))
    s2_rows.append(_line_row("12",  "CA wages (from W-2 Box 16)",
                              sum(w.state_wages for w in profile.w2_incomes)))
    s2_rows.append(_line_row("13",  "Federal adjusted gross income (Form 1040 Line 11)",
                              fed["agi"]))
    s2_rows.append(_line_row("14",  "CA adjustments — subtractions",            sr.get("ca_subtractions", 0)))
    s2_rows.append(_line_row("15",  "Subtract line 14 from line 13",
                              round(fed["agi"] - sr.get("ca_subtractions", 0), 2)))
    obbba_addback = sr.get("obbba_addback", 0)
    s2_rows.append(_line_row("16",  "CA adjustments — additions (OBBBA add-back)",  obbba_addback))
    ca_agi = sr.get("ca_agi", fed["agi"])
    s2_rows.append(_line_row("17",  "CA adjusted gross income",                 ca_agi))
    s2_rows.append(_line_row("18",  "CA standard deduction",                    sr.get("standard_deduction", 0)))
    s2_rows.append(_line_row("19",  "CA taxable income (line 17 – 18)",         sr.get("taxable_income", 0)))
    s2_rows.append(_line_row("31",  "CA income tax",                            sr.get("state_tax", 0)))
    s2_rows.append(_line_row("32",  "Exemption credits (line 11)",              exemption_total))
    s2_rows.append(_line_row("33",  "Subtract line 32 from line 31",
                              max(0, round(sr.get("state_tax", 0) - exemption_total, 2))))
    s2_rows.append(_line_row("35",  "Total CA tax",                             sr.get("state_tax", 0)))
    story.append(_build_line_table(s2_rows, styles))
    story.append(PageBreak())

    # ── Side 3 ─────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>CA Form 540 — Side 3 (Credits, Taxes, Payments)</b>",
                           styles['SectionHeader']))
    s3_rows = [["Line", "Description", "Amount"]]
    credits = sr.get("credits", 0)
    s3_rows.append(_line_row("47",  "Total credits",                            credits))
    s3_rows.append(_line_row("48",  "Subtract line 47 from line 35",
                              max(0, round(sr.get("state_tax", 0) - credits, 2))))
    s3_rows.append(_line_row("61",  "Alternative Minimum Tax",                  0))
    s3_rows.append(_line_row("62",  "Mental Health Services Tax (1% over $1M)", 0))
    s3_rows.append(_line_row("63",  "Other taxes",                              0))
    s3_rows.append(_line_row("64",  "Total CA tax (line 48 + 61 + 62 + 63)",   sr.get("total_tax", 0)))
    s3_rows.append(_line_row("71",  "CA income tax withheld (W-2 Box 17)",
                              sum(w.state_withheld for w in profile.w2_incomes)))
    sdi_total = sum(w.box_14_sdi for w in profile.w2_incomes)
    s3_rows.append(_line_row("74",  "CA SDI withheld (W-2 Box 14)",            round(sdi_total, 2)))
    total_ca_payments = round(
        sum(w.state_withheld for w in profile.w2_incomes) + sdi_total, 2)
    s3_rows.append(_line_row("78",  "Total payments",                           total_ca_payments))
    s3_rows.append(_line_row("91",  "Use tax (CA CDTFA)",                       0))
    s3_rows.append(_line_row("92",  "ISR Penalty",                              0))
    if total_ca_payments > sr.get("total_tax", 0):
        s3_rows.append(_line_row("97", "Overpaid tax",
                                  round(total_ca_payments - sr.get("total_tax", 0), 2)))
    else:
        s3_rows.append(_line_row("97", "Overpaid tax",                          0))
    story.append(_build_line_table(s3_rows, styles))
    story.append(PageBreak())

    # ── Side 4 ─────────────────────────────────────────────────────────────
    story.append(Paragraph("<b>CA Form 540 — Side 4 (Overpaid / Amount Due)</b>",
                           styles['SectionHeader']))
    s4_rows = [["Line", "Description", "Amount"]]
    s4_rows.append(_line_row("98",  "Amount of line 97 applied to 2025 estimated tax", 0))
    s4_rows.append(_line_row("99",  "Overpaid tax available this year",         sr.get("refund", 0)))
    s4_rows.append(_line_row("100", "Tax due",                                  sr.get("amount_owed", 0)))
    s4_rows.append(_line_row("110", "Total voluntary contributions",            0))
    story.append(_build_line_table(s4_rows, styles))
    story.append(PageBreak())

    # ── Sides 5 & 6 ────────────────────────────────────────────────────────
    story.append(Paragraph("<b>CA Form 540 — Side 5 (Refund / Amount Owed)</b>",
                           styles['SectionHeader']))
    s5_rows = [["Line", "Description", "Amount"]]
    s5_rows.append(_line_row("111", "Amount you owe (line 100 + 110 + penalties)", sr.get("amount_owed", 0)))
    if sr.get("refund", 0) > 0:
        s5_rows.append(_line_row("115", "Refund",                               sr.get("refund", 0)))
    story.append(_build_line_table(s5_rows, styles))
    story.append(Spacer(1, 10))
    story.append(Paragraph(
        "Health care coverage: All household members had full-year qualifying coverage. "
        "Voter registration: See sos.ca.gov/elections.", styles['FieldValue']))

    # Signature block (Side 6)
    story.append(PageBreak())
    story.append(Paragraph("<b>CA Form 540 — Side 6 (Signatures)</b>", styles['SectionHeader']))
    prep = getattr(profile, "preparer", None)
    if prep:
        sig_info = [
            ["Firm Name", prep.firm_name],
            ["Firm Address", prep.firm_address],
            ["PTIN", prep.ptin],
            ["Firm FEIN", prep.firm_ein],
        ]
        story.append(Table(sig_info, colWidths=[1.5*inch, 5.7*inch]))
    story.append(Paragraph(
        f"Taxpayer email: {getattr(profile, 'email', '')}  "
        f"|  Phone: {getattr(profile, 'phone', '')}",
        styles['FieldValue']))
```

Update `generate_tax_forms()` to call `_add_ca_form_540()` instead of `_add_state_form_page()` for CA:

```python
if profile.state not in NO_INCOME_TAX_STATES:
    story.append(PageBreak())
    if profile.state == "CA":
        _add_ca_form_540(story, profile, styles)
    else:
        _add_state_form_page(story, profile, styles)
```

### 4.13 Add `generate_form_8867()` — Paid Preparer Due Diligence

```python
def generate_form_8867(profile, fed: dict, output_path: str):
    """Form 8867 — Paid Preparer's Due Diligence Checklist (CTC/ACTC/ODC)."""
    from reportlab.pdfgen import canvas as rl_canvas
    prep = getattr(profile, "preparer", None)
    c = rl_canvas.Canvas(output_path, pagesize=letter)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(36, 750, "Form 8867 (Rev. 11-2024) — Paid Preparer's Due Diligence")

    c.setFont("Helvetica", 9)
    c.drawString(36, 730, f"Taxpayer: {profile.primary_first} {profile.primary_last}")
    c.drawString(36, 718, f"SSN: {format_ssn(profile.primary_ssn)}")
    if prep:
        c.drawString(300, 730, f"Preparer: {prep.name}")
        c.drawString(300, 718, f"PTIN: {prep.ptin}")

    # Credits claimed checkboxes
    y = 695
    c.drawString(36, y, "Credits claimed (check all that apply):")
    has_ctc = fed.get("child_tax_credit", 0) > 0 or fed.get("additional_ctc", 0) > 0
    _draw_field = lambda label, val, cx, cy: (
        c.rect(cx, cy, 8, 8),
        c.line(cx, cy, cx+8, cy+8) if val else None,
        c.drawString(cx + 12, cy, label)
    )
    c.rect(36, y-16, 8, 8)
    if has_ctc: c.line(36, y-16, 44, y-8)
    c.drawString(48, y-14, "CTC/ACTC/ODC")

    # Part I — Due Diligence Questions (all Yes for a compliant preparer)
    y -= 40
    questions = [
        ("1",  "Return based on information provided?",         True),
        ("2",  "Applicable worksheets completed?",              True),
        ("3",  "Knowledge requirement satisfied?",              True),
        ("4",  "No incorrect/inconsistent info?",               True),
        ("5",  "Record retention requirement met?",             True),
        ("6",  "Asked taxpayer for documentation?",             True),
        ("7",  "Credits previously disallowed?",                False),
        ("8",  "Schedule C questions asked (if SE income)?",
               profile.business_income is not None),
    ]
    for line, text, answer in questions:
        c.drawString(36, y, f"Q{line}. {text}")
        c.rect(430, y-2, 8, 8)
        if answer: c.line(430, y-2, 438, y+6)
        c.drawString(442, y, "Yes")
        c.rect(470, y-2, 8, 8)
        if not answer: c.line(470, y-2, 478, y+6)
        c.drawString(482, y, "No")
        y -= 16

    # Part VI — Certification
    y -= 10
    c.setFont("Helvetica-Bold", 9)
    c.drawString(36, y, "Part VI — I certify all answers are true, correct, and complete.")
    c.rect(36, y-16, 8, 8)
    c.line(36, y-16, 44, y-8)   # checked Yes
    c.drawString(48, y-14, "Yes")
    c.save()
```

---

## Phase 5 — Validation Rules V-16 through V-22

**File:** `validation.py`

Add the following methods to `ValidationEngine` class after `_v15_file_existence`:

```python
def _v16_actc_arithmetic(self, profile, _):
    """V-16: ACTC = min(line_16a, max(0, (earned_income - 2500) × 0.15))."""
    s = profile.federal_results.get("schedule_8812", {})
    if not s:
        return []
    actc = s.get("line_27", 0)
    earned = s.get("line_18a", 0)
    expected = min(s.get("line_16a", 0), max(0, (earned - 2500) * 0.15))
    if abs(actc - round(expected, 2)) > 1.00:
        return [f"V-16 ACTC mismatch: computed={actc}, expected≈{expected:.2f}"]
    return []

def _v17_schedule_2_consistency(self, profile, _):
    """V-17: Schedule 2 Part II total == SE + medicare_surtax + NIIT."""
    fed = profile.federal_results
    s2  = fed.get("schedule_2", {})
    if not s2:
        return []
    expected = round(
        fed.get("se_tax", 0) +
        fed.get("medicare_surtax", 0) +
        s2.get("line_12", 0), 2)
    actual = s2.get("part_ii_total", 0)
    if abs(actual - expected) > 0.01:
        return [f"V-17 Sch2 mismatch: actual={actual}, expected={expected}"]
    return []

def _v18_estimated_tax_trigger(self, profile, _):
    """V-18: If SE income > 0 and amount_owed > $1,000, est_tax required."""
    fed = profile.federal_results
    est = fed.get("est_tax_data", {})
    if (profile.business_income
            and fed.get("amount_owed", 0) > 1000
            and not est.get("required", False)):
        return ["V-18 Estimated tax should be required (amount_owed > $1,000 with SE income)"]
    return []

def _v19_form_4562_consistency(self, profile, _):
    """V-19: Sum of asset depreciation == biz.depreciation."""
    biz = profile.business_income
    if not biz or not biz.depreciable_assets:
        return []
    asset_total = sum(a.depreciation_this_year for a in biz.depreciable_assets)
    if abs(asset_total - biz.depreciation) > 0.01:
        return [f"V-19 Form 4562 mismatch: asset sum={asset_total}, biz.depreciation={biz.depreciation}"]
    return []

def _v20_1040es_amount(self, profile, _):
    """V-20: per_quarter × 4 ≈ annual_estimated (within $1)."""
    est = profile.federal_results.get("est_tax_data", {})
    if not est.get("required"):
        return []
    annual = est.get("annual_amount", 0)
    per_q  = est.get("per_quarter", 0)
    if abs(per_q * 4 - annual) > 1.00:
        return [f"V-20 1040-ES: per_quarter×4={per_q*4:.2f} ≠ annual={annual:.2f}"]
    return []

def _v21_schedule_b_chain(self, profile, _):
    """V-21: Sum of Sch B payers == federal_results interest/dividend totals."""
    fed = profile.federal_results
    interest_sum = sum(i.amount for i in profile.interest_incomes)
    if abs(interest_sum - fed.get("taxable_interest", 0)) > 0.01:
        return [f"V-21 Sch B interest chain: sum={interest_sum}, fed={fed.get('taxable_interest')}"]
    div_sum = sum(d.ordinary_dividends for d in profile.dividend_incomes)
    if abs(div_sum - fed.get("ordinary_dividends", 0)) > 0.01:
        return [f"V-21 Sch B dividend chain: sum={div_sum}, fed={fed.get('ordinary_dividends')}"]
    return []

def _v22_schedule_se_arithmetic(self, profile, _):
    """V-22: SE tax arithmetic internal consistency."""
    se = profile.federal_results.get("se_data", {})
    if not se:
        return []
    errors = []
    se_tax = se.get("line_12_se_tax", 0)
    ss = se.get("line_10", 0)
    med = se.get("line_11", 0)
    if abs(se_tax - round(ss + med, 2)) > 0.01:
        errors.append(f"V-22a SE tax: {ss}+{med}≠{se_tax}")
    ded = se.get("line_13_deduction", 0)
    expected_ded = round(se_tax * 0.50, 2)
    if abs(ded - expected_ded) > 0.01:
        errors.append(f"V-22b SE deduction: {ded}≠{expected_ded}")
    fed_se = profile.federal_results.get("se_tax", 0)
    if abs(fed_se - se_tax) > 0.01:
        errors.append(f"V-22c SE tax vs federal_results: {fed_se}≠{se_tax}")
    return errors
```

Register all new rules in `run_all()`:

```python
self._validators = [
    # ... existing V-01 through V-15 ...
    self._v16_actc_arithmetic,
    self._v17_schedule_2_consistency,
    self._v18_estimated_tax_trigger,
    self._v19_form_4562_consistency,
    self._v20_1040es_amount,
    self._v21_schedule_b_chain,
    self._v22_schedule_se_arithmetic,
]
```

Update `_v15_file_existence()` required files:

```python
required_files = [
    os.path.join("1. Client Summary", "Client_Summary.pdf"),
    os.path.join("4. Executive Summary", "Executive_Summary.pdf"),
    os.path.join("Prompt", "Tax_Return_Data.xml"),
    os.path.join("3. Complete Forms", "Form_8867.pdf"),   # ← NEW
]
```

---

## Phase 6 — Wire into `generate_single_dataset()`

**File:** `generate.py`

Update the pipeline in `generate_single_dataset()`:

```python
# After compute_federal_tax(profile):
from tax_engine.federal_calculator import (
    compute_schedule_se, compute_schedule_2, compute_schedule_8812,
    compute_estimated_tax_next_year,
)

# Schedule SE (standalone dict)
if profile.business_income and fed.get("se_tax", 0) > 0:
    se_data = compute_schedule_se(
        profile,
        profile.business_income.net_profit,
        SS_WAGE_BASE[year],
        sum(w.wages for w in profile.w2_incomes),
    )
    profile.federal_results["se_data"] = se_data

# Schedule 2
s2 = compute_schedule_2(
    profile,
    fed["income_tax"],
    fed.get("se_tax", 0),
    fed.get("medicare_surtax", 0),
    fed.get("amt_excess", 0),
)
profile.federal_results["schedule_2"] = s2

# Schedule 8812 (CTC/ACTC)
s8812 = compute_schedule_8812(
    profile, fed["agi"], fed["income_tax"], 0)
profile.federal_results["schedule_8812"] = s8812
profile.federal_results["additional_ctc"] = s8812["line_27"]

# Estimated tax for next year
est_data = compute_estimated_tax_next_year(
    profile, fed["total_tax"], fed["agi"])
profile.federal_results["est_tax_data"] = est_data

# ... then existing document generation calls ...

# 1040-V (if balance due)
from generators.tax_forms import generate_1040v, generate_1040es, generate_form_8867
if fed.get("amount_owed", 0) > 0:
    generate_1040v(
        profile,
        os.path.join(dirs["forms"], "Form_1040V.pdf"))

# 1040-ES (if estimated tax required)
if est_data.get("required"):
    generate_1040es(
        profile, est_data,
        os.path.join(dirs["forms"], "Form_1040ES.pdf"))

# Form 8867 (always — paid preparer checklist)
generate_form_8867(
    profile, fed,
    os.path.join(dirs["forms"], "Form_8867.pdf"))
```

---

## PDF Format Alignment with Reference Document

The reference PDF (`2024_Tax_Return_Documents__JOHNSON_JOHN_and_EMILY_.pdf`) uses exact IRS form styling:

| Aspect | Reference PDF | Current Output | Gap |
|---|---|---|---|
| Layout engine | Absolute coordinate boxes | ReportLab flowable `Table` | Architecture mismatch |
| Form numbers | Printed in top-right corner with OMB number | Not present | Missing |
| Line labels | Left-aligned with dotted leaders | Truncated descriptions | Cosmetic |
| Amount fields | Right-aligned in fixed-width boxes | Right-aligned in table column | Close match |
| Checkboxes | Rendered SVG-style boxes with X marks | Not rendered | Missing |
| SSN format | `XXX-XX-XXXX` displayed | `format_ssn()` exists | ✅ Present |
| EIN format | `XX-XXXXXXX` displayed | `format_ein()` exists | ✅ Present |
| Page 2 items | Tax table, credits, payments, refund, signature blocks | Partially rendered | Partial |
| OCR scan line | Bottom barcode-style text | Not present | Low priority |
| Preparer block | Name, PTIN, firm, EIN, date | Not rendered | Missing |

**Recommended approach for format alignment:** For each major form, create a coordinate map dict that maps IRS official form field positions (in ReportLab points, bottom-left origin) to result keys. Use `canvas.drawString(x, y, value)` calls placed against a background PNG of the blank IRS form (or hand-coded box-drawing). This would require adding blank IRS form images as assets.

---

## Implementation Priority Order

```
CRITICAL (fix before any new generation run):
  1. Fix OBBBA phase-out endpoints in tax_tables.py            (Phase 3.1)

HIGH (required for accurate output matching reference PDF):
  2. Add compute_schedule_1() and structured dict              (Phase 2b)
  3. Add lines 1a–1z, 4a–6b, preparer fields to data model    (Phase 1)
  4. Add Form 1040 intermediate lines 17,18,21,22,25a–d,32,33 (Phase 2c)
  5. Add compute_schedule_se() standalone                       (Phase 2.2)
  6. Add compute_schedule_2() and wire into results            (Phase 2.3)
  7. Add compute_schedule_8812() with ACTC                     (Phase 2.4)
  8. Add _add_schedule_1_page() renderer                       (Phase 4.0) ★ NEW
  9. Update Form 1040 renderer with all missing fields          (Phase 4.2)
  10. Complete Schedule SE renderer (all lines)                 (Phase 4.3)
  11. Add Schedule 2 renderer                                   (Phase 4.4)
  12. Add Schedule 8812 renderer                               (Phase 4.6)
  13. Add Form 8995 renderer                                   (Phase 4.7)
  14. Add Form 1040-V generator                                (Phase 4.10)
  15. Add Form 1040-ES generator                               (Phase 4.11)
  16. Replace CA state renderer with full 6-page Form 540      (Phase 4.12) ★ EXPANDED
  17. Wire all new calculators into generate_single_dataset()  (Phase 6)

MEDIUM (completeness and data integrity):
  18. Add missing tax_tables constants                          (Phase 3.2)
  19. Add DepreciableAsset dataclass + Form 4562 renderer      (Phases 1.4, 4.8)
  20. Add RentExpense + Schedule C missing lines (all 15 lines)(Phases 1.3, 4.9)
  21. Add Schedule 3 renderer                                   (Phase 4.5)
  22. Add Form 8867 generator                                   (Phase 4.13)
  23. Add validation rules V-16 through V-22                   (Phase 5)
  24. Update V-15 file existence list                           (Phase 5)

LOW (cosmetic / format precision):
  25. Coordinate-based absolute positioning for IRS form layout
  26. Schedule B Part III (foreign accounts checkboxes 7a, 7b, 8)
  27. Form 1040 Lines 35a–35d (direct deposit routing/account)
  28. Form 1040 Third Party Designee section
  29. CA Form 540 voluntary contributions (codes 400–447)
```

---

## Estimated Effort

| Phase | Files Changed | New Lines of Code (est.) | Complexity |
|---|---|---|---|
| Critical Bug Fix | `tax_tables.py` | ~4 | Low |
| Phase 1 — Data Model | `profile_generator.py` | ~80 | Low |
| Phase 2 — Calculators | `federal_calculator.py` | ~220 | Medium |
| Phase 3 — Tax Tables | `tax_tables.py` | ~60 | Low |
| Phase 4 — PDF Rendering | `generators/tax_forms.py` | ~650 | High |
| Phase 5 — Validation | `validation.py` | ~100 | Medium |
| Phase 6 — Wiring | `generate.py` | ~40 | Low |
| **Total** | **6 files** | **~1,154** | **Medium-High** |

---

*Sources: IRS.gov Form 1040 instructions (2024), MISSING_FORMS_IMPLEMENTATION_GUIDE_v2.md,  
Public Law 119-21 (OBBBA, July 4, 2025), IRS FS-2025-03, FS-2026-01.*
