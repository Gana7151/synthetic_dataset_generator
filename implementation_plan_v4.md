# Synthetic Tax Dataset Engine — v4.0 Spec Implementation Plan

> **Definitive implementation plan** synthesized from `synthetic_tax_report_v4.docx`, the draft implementation plan, and review findings.  
> Scope: 2,000 synthetic individual tax datasets · 5 states (CA, TX, NY, IL, FL) · 6 tax years (2020–2025) · 3 complexity tiers  
> Delivery: 300–400 datasets/week · Each dataset: Client Summary PDF + 4–15 supporting docs + federal/state forms + Executive Summary + XML

---

## Table of Contents

1. [Error Resolution Summary](#1-error-resolution-summary)
2. [2026 Parameters — Scope Decision](#2-2026-parameters--scope-decision)
3. [Implementation Order](#3-implementation-order)
4. [Phase 1 — tax_tables.py](#4-phase-1--tax_tablespy)
5. [Phase 2 — vin_generator.py](#5-phase-2--vin_generatorpy)
6. [Phase 3 — profile_generator.py](#6-phase-3--profile_generatorpy)
7. [Phase 4 — federal_calculator.py](#7-phase-4--federal_calculatorpy)
8. [Phase 5 — state_calculator.py](#8-phase-5--state_calculatorpy)
9. [Phase 6 — validation.py](#9-phase-6--validationpy)
10. [Phase 7 — Generators](#10-phase-7--generators)
11. [Phase 8 — generate.py](#11-phase-8--generatepy)
12. [Phase 9 — Pilot Run](#12-phase-9--pilot-run)
13. [Phase 10 — Full Run](#13-phase-10--full-run)
14. [Reference: Verified Tax Parameter Matrix 2020–2026](#14-reference-verified-tax-parameter-matrix-20202026)
15. [Reference: Schedule 1-A OBBBA Deduction Table](#15-reference-schedule-1-a-obbba-deduction-table)
16. [Reference: Complete 15-Rule Validation Engine](#16-reference-complete-15-rule-validation-engine)

---

## 1. Error Resolution Summary

All 15 errors from v1–v3 are resolved in this plan. The table below is the authoritative correction log.

| ID | Category | Error (Prior Versions) | Correction (v4) | Affects |
|----|----------|------------------------|-----------------|---------|
| E-01 | Math | AGI example: $171,500 (wrong) | $150,000 + $18,500 = **$168,500** | federal_calculator.py |
| E-02 | Math | CTC $2,200 stated universally | Year-specific: $2K (2020/22–24), $3K–$3.6K (2021), **$2.2K (2025+)** | tax_tables.py, validation V-11 |
| E-03 | Classification | OBBBA deductions called below-the-line; wrong line ref (Line 13b) | Above-the-line: Schedule 1-A → Schedule 1 Part II → **Form 1040 Line 10** | federal_calculator.py |
| E-04 | Specification | Car loan phase-out listed as N/A | Phase-out: $100K/$200K MFJ start; $200 per $1K; ends $149K/$249K MFJ | tax_tables.py, federal_calculator.py |
| E-05 | Math | Cap gains 20% threshold used 2025 values for 2026 | 2025: $533,400/$600,050 · 2026: $545,500/$613,700 | tax_tables.py |
| E-06 | Specification | AMT phase-out range/rate change not documented | OBBBA reverts phase-out START; **doubles rate 25¢→50¢** (2026 only) | tax_tables.py (store), gate 2026 |
| E-07 | Specification | QBI $75K/$150K called phase-out start | $75K/$150K is the **width** of the phase-in range, not the start | federal_calculator.py |
| E-08 | Specification | Non-itemizer charitable deduction starts 2025 | Confirmed **starts 2026** ($1K single / $2K MFJ, permanent) | tax_tables.py (store), gate 2026 |
| E-09 | Specification | Medicare 0.9%: MFJ threshold omitted; employer logic incomplete | Single $200K (employer W/H trigger); MFJ $250K (Form 8959 reconciliation) | federal_calculator.py |
| E-10 | Specification | Validation table missing 7 of 15 rules | All 15 rules now defined: V-03, V-04, V-08, V-09, V-11, V-13, V-15 added | validation.py |
| E-11 | Omission | SALT 2026 cap implied flat at $40K | OBBBA mandates **1% annual increase**: 2025=$40K, 2026=$40,400, 2027=$40,804… | tax_tables.py |
| E-12 | Specification | Bonus depreciation date ambiguous (Jan 19 stated) | Correct date: **on or after January 20, 2025** (day after inauguration) | profile_generator.py |
| E-13 | Specification | Form 720 implied as individual obligation | Form 720 is a **business** excise form. Individuals: reduce disposable cash flow by 1% on qualifying remittances only | generators/input_documents.py |
| E-14 | Classification | 2/37 rule called "Pease limitation resurrection" | Different mechanism: caps **tax benefit** (not deduction) for 37% bracket itemizers at 35¢/$1, effective 2026 only | gate 2026 |
| E-15 | Omission | IL EITC rate stated as flat 40% | Year-specific: 18% (2020) → 20% (2021–23) → 30% (2024) → **40% (2025+)** | tax_tables.py, state_calculator.py |

---

## 2. 2026 Parameters — Scope Decision

**Decision: Store in `tax_tables.py`, gate all logic.**

2026 is explicitly out of the 2,000-dataset deliverable scope. All 2026 values are pre-loaded as table entries for engine forward-compatibility, but every 2026-specific computation is wrapped in a `if tax_year >= 2026` guard with a `# NOT IN DELIVERABLE SCOPE — DO NOT ACTIVATE` comment.

### What gets stored (data only)
- Standard deductions (Single $16,100 / MFJ $32,200 / HoH $24,150)
- Income tax brackets (Rev. Proc. 2025-32 values)
- Capital gains thresholds ($545,500 single / $613,700 MFJ)
- AMT exemptions ($90,100 single / $140,200 MFJ) and reverted phase-out starts ($500K single / $1M MFJ)
- SALT cap $40,400 (1% increment from $40,000)
- Non-itemizer charitable deduction ($1K single / $2K MFJ, permanent from 2026)
- QBI phase-in start thresholds ($201,775 single / $403,500 MFJ)

### What gets gated (logic stubs only)
- **AMT doubled phase-out rate** (50¢ per $1, reverted start at $500K single) — stub in `federal_calculator.py`
- **2/37 rule** (add `total_itemized × 0.02` to Line 16 for 37%-bracket itemizers) — stub in `federal_calculator.py`
- **Non-itemizer charitable deduction** — stub in `federal_calculator.py`
- **PMI deductibility** (2026 OBBBA provision, CA/NY do not conform) — stub in `state_calculator.py`

---

## 3. Implementation Order

```
1. tax_tables.py          → Mathematical foundation; everything depends on this
2. vin_generator.py       → Pure utility; must be NHTSA-validated before validation.py is wired
3. ny_zip_lookup.py       → Static data file; hard dependency for state_calculator.py (NY)
4. profile_generator.py   → Consumes tax_tables + vin_generator
5. federal_calculator.py  → Consumes tax_tables + profile
6. state_calculator.py    → Consumes federal output + ny_zip_lookup
7. validation.py          → Consumes all calculator outputs; all 15 rules
8. generators/ (all)      → Consume profile + calculator outputs
9. generate.py            → Orchestration; integrates validation (discard + re-seed logic)
10. Pilot run             → 20 datasets (4 per state, all 3 levels, mix of years)
11. Full run              → 2,000 datasets after pilot clears all 15 rules + manual QA
```

> **Gate rule**: Do not proceed to Step 7 (validation.py) until `vin_generator.py` passes NHTSA mod-11 unit tests. A VIN generator bug silently discards every car-loan dataset during the pilot with no visible error — the failure mode is invisible.

---

## 4. Phase 1 — `tax_tables.py`

**Role**: Single authoritative lookup for all year-specific and status-specific tax parameters. Every other module imports from here — no magic numbers anywhere else.

### 4.1 Standard Deductions (corrected)

```python
STANDARD_DEDUCTION = {
    2020: {"single": 12400, "mfj": 24800, "hoh": 18650, "mfs": 12400},
    2021: {"single": 12550, "mfj": 25100, "hoh": 18800, "mfs": 12550},
    2022: {"single": 12950, "mfj": 25900, "hoh": 19400, "mfs": 12950},
    2023: {"single": 13850, "mfj": 27700, "hoh": 20800, "mfs": 13850},
    2024: {"single": 14600, "mfj": 29200, "hoh": 21900, "mfs": 14600},
    2025: {"single": 15750, "mfj": 31500, "hoh": 23625, "mfs": 15750},  # E-01 fix
    2026: {"single": 16100, "mfj": 32200, "hoh": 24150, "mfs": 16100},  # forward-compat only
}
```

> **Prior error (E-01)**: Code used $15,000/$30,000 for 2025. Correct values per OBBBA: **$15,750/$31,500**.

### 4.2 Additional Standard Deduction (65+ or blind)

```python
ADDITIONAL_STANDARD_DEDUCTION = {
    # Per person; Single/MFS differs from MFJ
    2025: {"single_or_mfs": 2000, "mfj_per_person": 1600},
    2026: {"single_or_mfs": 2050, "mfj_per_person": 1650},
}
```

### 4.3 Child Tax Credit — Year-Specific (E-02 fix)

```python
CTC_PER_CHILD = {
    2020: 2000,
    2021: {"under_6": 3600, "age_6_to_17": 3000},  # ARPA expansion
    2022: 2000,
    2023: 2000,
    2024: 2000,
    2025: 2200,   # OBBBA increase
    2026: 2200,   # inflation too low to adjust
}

def get_ctc_per_child(tax_year: int, child_age: int = None) -> int:
    val = CTC_PER_CHILD[tax_year]
    if isinstance(val, dict):
        # 2021 only
        return val["under_6"] if child_age is not None and child_age < 6 else val["age_6_to_17"]
    return val
```

### 4.4 SALT Caps

```python
SALT_CAP = {
    **{year: 10000 for year in range(2020, 2025)},
    2025: 40000,   # OBBBA jump
    2026: 40400,   # 1% annual increment (E-11 fix)
    2027: 40804,
    2028: 41212,
    2029: 41624,
}

SALT_PHASEOUT_START = {
    **{year: None for year in range(2020, 2025)},  # no phase-out pre-2025
    2025: 500000,
    2026: 505000,
}
```

### 4.5 Income Tax Brackets

```python
# Format: list of (upper_bound, rate) tuples; final tuple upper_bound = None (top bracket)
TAX_BRACKETS = {
    2025: {
        "single": [
            (11925,  0.10),
            (48475,  0.12),
            (103350, 0.22),
            (197300, 0.24),
            (250525, 0.32),
            (626350, 0.35),
            (None,   0.37),
        ],
        "mfj": [
            (23850,  0.10),
            (96950,  0.12),
            (206700, 0.22),
            (394600, 0.24),
            (501050, 0.32),
            (751600, 0.35),
            (None,   0.37),
        ],
        # hoh, mfs follow same pattern
    },
    2026: { ... },  # Rev. Proc. 2025-32 values — stored, not executed in deliverable
}
```

### 4.6 Long-Term Capital Gains Thresholds

```python
LTCG_BRACKETS = {
    # Format: (0% upper, 15% upper); 20% applies above 15% threshold
    2020: {"single": (40000, 441450), "mfj": (80000, 496600)},
    2021: {"single": (40400, 445850), "mfj": (80800, 501600)},
    2022: {"single": (41675, 459750), "mfj": (83350, 517200)},
    2023: {"single": (44625, 492300), "mfj": (89250, 553850)},
    2024: {"single": (47025, 518900), "mfj": (94050, 583750)},
    2025: {"single": (48350, 533400), "mfj": (96700, 600050)},
    2026: {"single": (49450, 545500), "mfj": (98900, 613700)},  # E-05 fix; forward-compat
}
```

### 4.7 AMT Parameters

```python
AMT_PARAMS = {
    2024: {
        "exemption":      {"single": 85700,  "mfj": 133300},
        "phaseout_start": {"single": 609350, "mfj": 1218700},
        "phaseout_rate":  0.25,
    },
    2025: {
        "exemption":      {"single": 88100,  "mfj": 137000},
        "phaseout_start": {"single": 626350, "mfj": 1252700},
        "phaseout_rate":  0.25,
    },
    # 2026: OBBBA reverts start; doubles rate — stored for forward-compat (E-06 fix)
    2026: {
        "exemption":      {"single": 90100,  "mfj": 140200},
        "phaseout_start": {"single": 500000, "mfj": 1000000},  # OBBBA revert
        "phaseout_rate":  0.50,                                  # DOUBLED — gate this
    },
}
```

### 4.8 SS Wage Base

```python
SS_WAGE_BASE = {
    2020: 137700, 2021: 142800, 2022: 147000,
    2023: 160200, 2024: 168600, 2025: 176100,
    2026: 183000,  # estimated
}
SS_RATE_EMPLOYEE = 0.062
```

### 4.9 Medicare Surtax Thresholds (E-09 fix)

```python
MEDICARE_SURTAX = {
    "rate": 0.009,
    "employer_withholding_trigger": 200000,  # filing-status-blind
    "form_8959_threshold": {
        "single": 200000,
        "hoh":    200000,
        "mfs":    125000,
        "mfj":    250000,
    },
}
```

### 4.10 OBBBA Schedule 1-A Phase-Out Tables

```python
OBBBA_DEDUCTIONS = {
    "tips": {
        "max":          25000,
        "phaseout_start": {"single": 150000, "mfj": 300000},
        "phaseout_end":   {"single": 400000, "mfj": 550000},
        "slope_per_1k":  100,      # $100 reduction per $1,000 over start
        "valid_years":  range(2025, 2029),
    },
    "overtime": {
        "max":          {"single": 12500, "mfj": 25000},
        "phaseout_start": {"single": 150000, "mfj": 300000},
        "phaseout_end":   {"single": 400000, "mfj": 550000},
        "slope_per_1k":  100,
        "valid_years":  range(2025, 2029),
    },
    "car_loan_interest": {
        "max":          10000,     # all filing statuses
        "phaseout_start": {"single": 100000, "mfj": 200000},
        "phaseout_end":   {"single": 149000, "mfj": 249000},
        "slope_per_1k":  200,      # DOUBLE the tips/overtime rate — do not unify
        "valid_years":  range(2025, 2029),
    },
    "senior": {
        "max":          {"single": 6000, "mfj_both": 12000},  # $6K/person
        "phaseout_start": {"single": 75000,  "mfj": 150000},
        "phaseout_end":   {"single": 175000, "mfj": 250000},
        "slope_type":   "proportional",    # ratio over range, NOT per-$1K step — different logic
        "valid_years":  range(2025, 2029),
    },
}
```

> **Critical implementation note**: `car_loan_interest` uses a **$200/$1K slope** — double the tips/overtime slope. Do NOT pass all four deductions through the same generic `reduction = (MAGI - start) / 1000 * slope` call with a unified slope. Use the slope stored per deduction in this table. The senior deduction uses proportional reduction — a separate calculation path.

### 4.11 IL EITC Year-Specific Rates (E-15 fix)

```python
IL_EITC_RATE = {
    2020: 0.18,
    2021: 0.20,
    2022: 0.20,
    2023: 0.20,
    2024: 0.30,
    2025: 0.40,
    2026: 0.40,
}
```

### 4.12 QBI Phase-In Width

```python
QBI_PHASEOUT_WIDTH = {
    **{year: {"single": 50000, "mfj": 100000} for year in range(2020, 2025)},
    2025: {"single": 75000,  "mfj": 150000},  # OBBBA expansion
    2026: {"single": 75000,  "mfj": 150000},
}
# Phase-out STARTS at:
QBI_PHASEOUT_START = {
    2025: {"single": 197300, "mfj": 394600},
    2026: {"single": 201775, "mfj": 403500},  # (E-07: width above start, not start itself)
}
```

---

## 5. Phase 2 — `vin_generator.py`

**Role**: Generate ISO 3779-compliant VINs for car loan interest eligibility. Must pass NHTSA validation before `validation.py` is integrated.

### 5.1 Constraints

- 17 characters total
- Position 1 (WMI[0]) ∈ `['1', '4', '5']` — US-assembled vehicles only
- Position 9 = mod-11 check digit (ISO 3779 algorithm)
- Vehicle must be new (model year 2025 or 2024 for a 2025 loan)
- First-lien loan, post-2024 purchase date

### 5.2 Mod-11 Check Digit Algorithm

```python
TRANSLITERATION = {
    'A':1,'B':2,'C':3,'D':4,'E':5,'F':6,'G':7,'H':8,
    'J':1,'K':2,'L':3,'M':4,'N':5,      'P':7,'R':9,
         'S':2,'T':3,'U':4,'V':5,'W':6,'X':7,'Y':8,'Z':9,
    **{str(d): d for d in range(10)}
}
POSITION_WEIGHTS = [8,7,6,5,4,3,2,10,0,9,8,7,6,5,4,3,2]

def compute_check_digit(vin_without_check: str) -> str:
    """vin_without_check is 17 chars with position 9 as placeholder (any char)."""
    total = sum(
        TRANSLITERATION[c] * POSITION_WEIGHTS[i]
        for i, c in enumerate(vin_without_check)
        if i != 8
    )
    remainder = total % 11
    return 'X' if remainder == 10 else str(remainder)
```

### 5.3 Unit Tests (must pass before wiring validation.py)

```python
def test_vin_generator():
    for _ in range(1000):
        vin = generate_vin()
        assert len(vin) == 17
        assert vin[0] in ('1', '4', '5')
        assert vin[8] == compute_check_digit(vin)

def test_nhtsa_known_vins():
    # Use 5 known valid VINs from NHTSA database as ground truth
    known = ["1HGBH41JXMN109186", ...]
    for vin in known:
        assert compute_check_digit(vin) == vin[8]
```

---

## 6. Phase 3 — `ny_zip_lookup.py` (New Static File)

**Role**: ZIP-to-NYC-school-district mapping. Hard dependency for NY state calculations. Must exist before `state_calculator.py` is written.

This is a named deliverable — it must be committed to the repo as a static data file (JSON or Python dict) before Phase 5 (state_calculator.py) begins. Source: NY State Department of Taxation and Finance school district codes.

```python
# ny_zip_lookup.py
NYC_SCHOOL_DISTRICT_BY_ZIP = {
    "10001": {"district_code": "5600", "is_nyc": True,  "borough": "Manhattan"},
    "11201": {"district_code": "5600", "is_nyc": True,  "borough": "Brooklyn"},
    "10301": {"district_code": "5600", "is_nyc": True,  "borough": "Staten Island"},
    # ... full mapping
    "12601": {"district_code": "6215", "is_nyc": False, "borough": None},  # Poughkeepsie
}

def get_district(zip_code: str) -> dict:
    return NYC_SCHOOL_DISTRICT_BY_ZIP.get(zip_code[:5], {"district_code": "0000", "is_nyc": False})
```

NYC ZIP triggers: Form IT-201-ATT, NYC household credit, NYC school tax credit.

---

## 7. Phase 4 — `profile_generator.py`

### 7.1 New OBBBA Boolean Flags (2025+ profiles only)

```python
@dataclass
class TaxProfile:
    # ... existing fields ...

    # OBBBA flags — only set when tax_year >= 2025
    is_tipped_worker:    bool = False   # W-2 Box 7 populated
    overtime_eligible:   bool = False   # FLSA premium portion on W-2
    has_car_loan_2025:   bool = False   # new vehicle, post-2024, first-lien
    is_senior_65_plus:   bool = False   # DOB ≤ Dec 31 of (tax_year - 65)
    has_trump_account:   bool = False   # future use
```

### 7.2 New Income Fields

```python
@dataclass
class W2Income:
    box_1_wages:       float = 0.0
    box_3_ss_wages:    float = 0.0
    box_4_ss_tax:      float = 0.0
    box_7_tips:        float = 0.0    # NEW — populates for is_tipped_worker
    box_12_codes:      dict  = None   # HSA, 401k, etc.
    box_14_sdi:        float = 0.0    # CA only
    overtime_pay:      float = 0.0    # NEW — FLSA premium portion only
```

### 7.3 Car Loan Profile

```python
@dataclass
class CarLoanProfile:
    vin:                str   = ""     # generated by vin_generator.py
    annual_interest:    float = 0.0    # capped at $10K in calculator
    purchase_date:      date  = None   # must be >= 2025-01-01
    is_first_lien:      bool  = True
    is_new_vehicle:     bool  = True
```

### 7.4 Generation Logic

- **Level 1**: Wages only. OBBBA flags probabilistic (20% tips, 10% overtime, 5% car loan, 15% senior).
- **Level 2**: Wages + 1099-NEC SE income. Same OBBBA distribution.
- **Level 3**: Wages + SE + Schedule E rental income + investment income (Schedule B/D). OBBBA flags same. AMT exposure if income > $500K (2026 gate only).

---

## 8. Phase 5 — `federal_calculator.py`

### 8.1 Corrected Calculation Sequence

```
Step 1  Gross Income Aggregation          Form 1040 Lines 1a–8
Step 2  Above-the-Line Adjustments        Schedule 1 Part II → Form 1040 Line 10
        ├── Traditional (½ SE, HSA, IRA, student loan, educator)
        └── OBBBA Schedule 1-A (2025+): Tips + Overtime + Car Loan + Senior
Step 3  AGI                               Form 1040 Line 11
Step 4  Standard or Itemized Deduction   Form 1040 Line 12
        └── SALT cap: $10K (2020–24) / $40K (2025) / $40,400 (2026)
Step 5  QBI Deduction                    Form 1040 Line 13
        └── Phase-in width: $100K MFJ (2020–24) / $150K MFJ (2025+)
Step 6  Taxable Income                   Form 1040 Line 15
        └── NOTE: OBBBA already in AGI — do NOT subtract again here
Step 7  Income Tax                       Form 1040 Line 16
        └── Piecewise bracket function (year-specific from tax_tables)
        └── QDCGTW for qualified dividends + capital gains (3-bracket)
Step 8  AMT Check (Level 3 only)         Form 6251 → Schedule 2
        └── 2025: standard parameters
        └── 2026: gated stub (reverted start, 50¢ rate) — NOT IN DELIVERABLE SCOPE
Step 9  2/37 Rule (2026 only)            Form 1040 Line 16 adjustment — GATED
Step 10 Other Taxes                      Form 1040 Line 17
        ├── SE Tax (Schedule SE → Schedule 2)
        ├── NIIT Form 8960 (investment income > $200K single / $250K MFJ)
        └── Additional Medicare Tax Form 8959 (E-09 fix)
Step 11 Credits                          Form 1040 Lines 19–24
        └── CTC: get_ctc_per_child(tax_year, child_age)  [E-02 fix]
Step 12 Net Tax                          Form 1040 Line 24
Step 13 Payments & Refund                Form 1040 Lines 25–35
```

### 8.2 Schedule 1-A OBBBA Deduction Implementation

```python
def compute_schedule_1a(profile: TaxProfile, magi: float, tax_year: int) -> dict:
    if tax_year < 2025:
        return {"tips": 0, "overtime": 0, "car_loan": 0, "senior": 0, "total": 0}

    status = profile.filing_status
    result = {}

    # Tips
    if profile.is_tipped_worker and profile.w2.box_7_tips > 0:
        result["tips"] = _linear_phaseout(
            gross_amount = min(profile.w2.box_7_tips, 25000),
            magi         = magi,
            start        = OBBBA_DEDUCTIONS["tips"]["phaseout_start"][status],
            end          = OBBBA_DEDUCTIONS["tips"]["phaseout_end"][status],
            slope_per_1k = 100,
        )
    else:
        result["tips"] = 0

    # Overtime
    if profile.overtime_eligible and profile.w2.overtime_pay > 0:
        gross = min(profile.w2.overtime_pay, OBBBA_DEDUCTIONS["overtime"]["max"][status])
        result["overtime"] = _linear_phaseout(gross, magi,
            OBBBA_DEDUCTIONS["overtime"]["phaseout_start"][status],
            OBBBA_DEDUCTIONS["overtime"]["phaseout_end"][status],
            slope_per_1k=100,
        )
    else:
        result["overtime"] = 0

    # Car Loan Interest — slope is $200/$1K, NOT $100/$1K
    if profile.has_car_loan_2025 and _vin_eligible(profile.car_loan):
        gross = min(profile.car_loan.annual_interest, 10000)
        result["car_loan"] = _linear_phaseout(gross, magi,
            OBBBA_DEDUCTIONS["car_loan_interest"]["phaseout_start"][status],
            OBBBA_DEDUCTIONS["car_loan_interest"]["phaseout_end"][status],
            slope_per_1k=200,  # CRITICAL: double rate
        )
    else:
        result["car_loan"] = 0

    # Senior — proportional reduction (different from per-$1K step)
    if profile.is_senior_65_plus:
        gross = _senior_gross(profile, status)
        result["senior"] = _proportional_phaseout(gross, magi,
            start = OBBBA_DEDUCTIONS["senior"]["phaseout_start"][status],
            end   = OBBBA_DEDUCTIONS["senior"]["phaseout_end"][status],
        )
    else:
        result["senior"] = 0

    # Part VI: Limitation failsafe — cannot reduce taxable income below $0
    total = sum(result.values())
    result["total"] = total
    return result


def _linear_phaseout(gross_amount, magi, start, end, slope_per_1k):
    if magi <= start:
        return gross_amount
    if magi >= end:
        return 0.0
    reduction = ((magi - start) / 1000) * slope_per_1k
    return max(0.0, gross_amount - reduction)


def _proportional_phaseout(gross_amount, magi, start, end):
    if magi <= start:
        return gross_amount
    if magi >= end:
        return 0.0
    fraction_remaining = 1 - (magi - start) / (end - start)
    return gross_amount * fraction_remaining
```

### 8.3 Medicare Surtax (E-09 fix)

```python
def compute_medicare_surtax(profile: TaxProfile, wages: float, se_income: float) -> float:
    """
    Employer W-2 withholding triggers at $200K regardless of filing status.
    Final Form 8959 liability uses filing-status-specific thresholds.
    """
    threshold = MEDICARE_SURTAX["form_8959_threshold"][profile.filing_status]
    net_investment_equivalent = wages + se_income
    excess = max(0.0, net_investment_equivalent - threshold)
    return excess * 0.009
```

### 8.4 2026 Logic Stubs

```python
def _compute_2026_amt(taxable_income, filing_status):
    # NOT IN DELIVERABLE SCOPE — 2026 only
    # AMT phase-out reverted to $500K single / $1M MFJ; rate doubled to 50¢
    raise NotImplementedError("2026 AMT logic gated — not in deliverable scope")

def _compute_2_37_rule(total_itemized, filing_status, bracket):
    # NOT IN DELIVERABLE SCOPE — 2026 only
    # Adds total_itemized * 0.02 to Line 16 for 37%-bracket itemizers
    raise NotImplementedError("2/37 rule gated — not in deliverable scope")
```

---

## 9. Phase 6 — `state_calculator.py`

### 9.1 State Non-Conformity Architecture

All three non-conforming states (CA, NY, IL) use the same pattern:

```
State AGI = Federal AGI (Line 11) + OBBBA add-back
         = Federal AGI before Schedule 1-A deductions
```

Concretely: `state_agi = gross_income - traditional_schedule1_adjustments`  
(i.e., Schedule 1-A OBBBA deductions are NOT subtracted for state purposes)

### 9.2 California

```python
def compute_ca(profile, federal_result):
    # OBBBA add-back: CA does NOT conform to Schedule 1-A
    ca_agi = federal_result.agi + federal_result.schedule_1a_total

    # SDI (Box 14): flows to federal Schedule A as deductible state tax
    # Subject to $40,000 SALT cap for 2025
    # No SDI wage cap in 2025

    # CalEITC: CA-specific tables; max around $30,931 earned income (2025)
    # Do NOT use federal EITC tables

    # PMI: NOT deductible in CA for 2025 (CA does not conform to 2026 OBBBA PMI provision)

    # CA standard deduction: $5,202 single / $10,404 MFJ (2025 est.)
    # CA does NOT use federal standard deduction amounts
    ...
```

### 9.3 Illinois

```python
def compute_il(profile, federal_result, tax_year):
    # OBBBA add-back
    il_base_income = federal_result.agi + federal_result.schedule_1a_total

    # IL flat rate: 4.95%
    il_tax = il_base_income * 0.0495

    # IL EITC (year-specific — E-15 fix)
    federal_eitc = federal_result.eitc
    il_eitc_rate = IL_EITC_RATE[tax_year]
    il_eitc = federal_eitc * il_eitc_rate

    # IL Child Tax Credit: 40% of base IL EITC for children under age 12
    # (Sched IL-E/EITC Step 5 — separate from base EITC)
    qualifying_under_12 = sum(1 for c in profile.children if c.age < 12)
    il_ctc = il_eitc * 0.40 if qualifying_under_12 > 0 else 0

    # Property Tax Credit (Sched ICR): 5% of IL principal residence property tax
    # Generate synthetic county property tax bill with valid IL County Assessor EIN
    ...
```

### 9.4 New York

```python
def compute_ny(profile, federal_result, tax_year):
    from ny_zip_lookup import get_district

    # OBBBA add-back
    ny_agi = federal_result.agi + federal_result.schedule_1a_total

    # SALT flip detection (2025 only)
    # Many NY personas previously used standard deduction will now itemize
    # because $40K SALT cap lets them exceed NY standard deduction
    # NY requires state itemization if federal itemization is taken
    if tax_year == 2025 and federal_result.itemized:
        ny_itemized = True
        # Compute NY Schedule A (NY does not adopt federal SALT cap — uses actual SALT paid)

    # IT-2105 estimated tax vouchers
    # Required if projected NY tax exceeds withholding by > $300
    # Generate 4 quarterly vouchers for Level 3 personas with SE or investment income

    # School district lookup
    district = get_district(profile.address.zip_code)
    if district["is_nyc"]:
        # NYC household credit + NYC school tax credit
        # Triggers Form IT-201-ATT
        pass

    # NY does NOT conform to OBBBA deductions
    ...
```

### 9.5 Texas and Florida

```python
def compute_tx(profile, federal_result):
    # No state income tax
    # Generate Form 50-114 (Homestead Exemption) for homeowners
    # County property tax flows to federal Schedule A Line 5b
    # Subject to $40,000 SALT cap (2025)
    ...

def compute_fl(profile, federal_result):
    # No state income tax
    # Generate county TRIM notice + DR-501 ($25K + secondary $25K exemption)
    # Save Our Homes cap: assessed value increase capped at 3% or CPI
    # (relevant for multi-year longitudinal datasets)
    # PMI NOT deductible for 2025; deductible 2026+ (federal only, gate it)
    ...
```

---

## 10. Phase 7 — `validation.py`

### 10.1 All 15 Rules (corrected from draft plan)

> **Warning**: The draft implementation plan had V-02 and V-03 wrong. The table below reflects the v4 spec's actual rules.

```python
class ValidationEngine:

    def run_all(self, dataset: DatasetBundle) -> ValidationResult:
        rules = [
            self.v01_w2_wage_consistency,
            self.v02_ss_wage_base_cap,          # NOT "qualified dividends ≤ ordinary"
            self.v03_nec_to_schedule_c,         # NOT "std deduction matches table"
            self.v04_mortgage_interest_cap,
            self.v05_se_tax_arithmetic,
            self.v06_agi_consistency,
            self.v07_taxable_income_consistency,
            self.v08_interest_income_chain,
            self.v09_medicare_surtax_threshold,
            self.v10_salt_cap,
            self.v11_ctc_year_specific,
            self.v12_obbba_phaseout,
            self.v13_ssn_deduplication,
            self.v14_vin_validation,
            self.v15_file_existence,
        ]
        failures = []
        for rule in rules:
            ok, msg = rule(dataset)
            if not ok:
                failures.append(msg)
        return ValidationResult(passed=len(failures) == 0, failures=failures)
```

### 10.2 Rule Implementations

```python
def v01_w2_wage_consistency(self, d):
    total_w2 = sum(w2.box_1_wages for w2 in d.w2_forms)
    return (
        abs(total_w2 - d.form_1040.line_1a) < 0.01,
        f"V-01: W-2 wages {total_w2} ≠ Form 1040 Line 1a {d.form_1040.line_1a}"
    )

def v02_ss_wage_base_cap(self, d):
    base = SS_WAGE_BASE[d.tax_year]
    for w2 in d.w2_forms:
        if w2.box_3_ss_wages > base + 0.01:
            return False, f"V-02: Box 3 {w2.box_3_ss_wages} > SS wage base {base}"
        expected_box4 = round(min(w2.box_3_ss_wages, base) * SS_RATE_EMPLOYEE, 2)
        if abs(w2.box_4_ss_tax - expected_box4) > 0.02:
            return False, f"V-02: Box 4 {w2.box_4_ss_tax} ≠ expected {expected_box4}"
    return True, ""

def v03_nec_to_schedule_c(self, d):
    # V-03 uses ≤ (not ==) because cash income may supplement Schedule C
    # If generator does not synthesize cash income, assert == instead
    total_nec = sum(f.box_1 for f in d.forms_1099_nec)
    if total_nec > d.schedule_c.line_1_gross_receipts + 0.01:
        return False, f"V-03: 1099-NEC total {total_nec} > Schedule C Line 1 {d.schedule_c.line_1_gross_receipts}"
    return True, ""

def v04_mortgage_interest_cap(self, d):
    if not d.form_1098:
        return True, ""
    # Interest deductible only on first $750K of loan ($375K MFS)
    loan_cap = 375000 if d.profile.filing_status == "mfs" else 750000
    if d.form_1098.outstanding_balance > loan_cap + 0.01:
        deductible_fraction = loan_cap / d.form_1098.outstanding_balance
        deductible_interest = d.form_1098.box_1_interest * deductible_fraction
        if d.schedule_a.line_8a > deductible_interest + 0.01:
            return False, f"V-04: Schedule A Line 8a exceeds mortgage interest cap"
    return True, ""

def v05_se_tax_arithmetic(self, d):
    if not d.schedule_se:
        return True, ""
    expected = round(d.schedule_se.line_3_net_profit * 0.9235 * 0.153, 2)
    actual = d.schedule_se.line_12_se_tax
    return (
        abs(actual - expected) < 0.02,
        f"V-05: SE tax {actual} ≠ expected {expected}"
    )

def v06_agi_consistency(self, d):
    expected_agi = d.form_1040.line_9 - d.schedule_1_part2_total
    return (
        abs(d.form_1040.line_11_agi - expected_agi) < 0.01,
        f"V-06: AGI {d.form_1040.line_11_agi} ≠ Line 9 - Sched1 Part II {expected_agi}"
    )

def v07_taxable_income_consistency(self, d):
    expected = d.form_1040.line_11_agi - d.form_1040.line_12 - d.form_1040.line_13
    return (
        abs(d.form_1040.line_15_taxable - expected) < 0.01,
        f"V-07: Taxable income {d.form_1040.line_15_taxable} ≠ {expected}"
    )

def v08_interest_income_chain(self, d):
    total_1099_int = sum(f.box_1 for f in d.forms_1099_int)
    sched_b_total = d.schedule_b.part_1_total
    form_1040_line_2b = d.form_1040.line_2b
    if abs(total_1099_int - sched_b_total) > 0.01:
        return False, f"V-08: 1099-INT sum {total_1099_int} ≠ Schedule B {sched_b_total}"
    if abs(sched_b_total - form_1040_line_2b) > 0.01:
        return False, f"V-08: Schedule B {sched_b_total} ≠ Form 1040 Line 2b {form_1040_line_2b}"
    return True, ""

def v09_medicare_surtax_threshold(self, d):
    status = d.profile.filing_status
    threshold = MEDICARE_SURTAX["form_8959_threshold"][status]
    if d.form_8959:
        expected_excess = max(0, d.profile.total_wages_and_se - threshold)
        expected_tax = round(expected_excess * 0.009, 2)
        return (
            abs(d.form_8959.tax - expected_tax) < 0.02,
            f"V-09: Medicare surtax {d.form_8959.tax} ≠ expected {expected_tax} (threshold {threshold})"
        )
    return True, ""

def v10_salt_cap(self, d):
    cap = SALT_CAP[d.tax_year]
    if d.schedule_a and d.schedule_a.line_5e > cap + 0.01:
        return False, f"V-10: SALT {d.schedule_a.line_5e} > cap {cap} for {d.tax_year}"
    return True, ""

def v11_ctc_year_specific(self, d):
    children = d.profile.qualifying_children
    if not children:
        return True, ""
    expected = sum(get_ctc_per_child(d.tax_year, c.age) for c in children)
    return (
        abs(d.form_1040.ctc - expected) < 0.01,
        f"V-11: CTC {d.form_1040.ctc} ≠ year-specific expected {expected}"
    )

def v12_obbba_phaseout(self, d):
    if d.tax_year < 2025 or not d.schedule_1a:
        return True, ""
    for part_name, part_value in d.schedule_1a.items():
        expected = _recompute_obbba_part(d.profile, d.magi, d.tax_year, part_name)
        if abs(part_value - expected) > 0.02:
            return False, f"V-12: Schedule 1-A {part_name}: {part_value} ≠ expected {expected}"
    return True, ""

def v13_ssn_deduplication(self, d):
    ssn = d.profile.ssn
    if ssn in self._used_ssns:
        return False, f"V-13: Duplicate SSN {ssn}"
    self._used_ssns.add(ssn)
    return True, ""

def v14_vin_validation(self, d):
    if not d.profile.has_car_loan_2025:
        return True, ""
    vin = d.profile.car_loan.vin
    if len(vin) != 17:
        return False, f"V-14: VIN length {len(vin)} ≠ 17"
    if vin[0] not in ('1', '4', '5'):
        return False, f"V-14: VIN position 1 '{vin[0]}' not US-assembled"
    expected_check = compute_check_digit(vin)
    if vin[8] != expected_check:
        return False, f"V-14: VIN check digit '{vin[8]}' ≠ expected '{expected_check}'"
    return True, ""

def v15_file_existence(self, d):
    required = [
        "client_summary.pdf",
        "executive_summary.pdf",
        "form_1040.pdf",
        "w2.pdf",
        "xml_export.xml",
    ]
    if d.tax_year >= 2025:
        required.append("schedule_1a.pdf")
    if d.profile.has_car_loan_2025:
        required.append("car_loan_statement.pdf")
    missing = [f for f in required if not (d.output_dir / f).exists()]
    return (
        len(missing) == 0,
        f"V-15: Missing files: {missing}"
    )
```

### 10.3 V-03 Assertion Direction Decision

**Decide before implementation.** The spec uses `≤` (NEC ≤ Schedule C gross receipts) to allow for unreported cash income supplementing Schedule C. If your generator does not synthesize cash income, change to `==`. The code above implements `≤` as the spec states, but this comment must be resolved:

```python
# DECISION REQUIRED:
# If generator adds synthetic cash income to Schedule C beyond 1099-NEC:
#   Use: total_nec <= schedule_c.line_1  (current implementation)
# If generator makes Schedule C gross = exact sum of 1099-NEC only:
#   Use: abs(total_nec - schedule_c.line_1) < 0.01
```

---

## 11. Phase 8 — Generators

### 11.1 Files to Modify

| File | Changes |
|------|---------|
| `generators/xml_generator.py` | Add `<Schedule1A>` element with sub-elements for Tips, Overtime, CarLoan, Senior, VIN |
| `generators/tax_forms.py` | Add Schedule 1-A page rendering for 2025+ datasets; update Form 1040 line ref to Line 10 (not Line 13b) |
| `generators/executive_summary.py` | Add OBBBA deductions breakdown; add SALT cap info; add state non-conformity note for CA/NY/IL |
| `generators/client_summary.py` | Add OBBBA eligibility questionnaire for 2025+ profiles (tips occupation, overtime FLSA, car loan VIN, senior DOB) |
| `generators/input_documents.py` | Add 1099-NEC PDF for SE income (Level 2+); W-2 Box 7 tips rendering; car loan statement with VIN; W-2 with overtime pay labeled |

### 11.2 Form 720 Note (E-13 fix)

Do NOT generate Form 720 in individual dataset folders. For personas with qualifying cash/money-order remittances, reduce disposable cash flow by 1% only. Form 720 is a quarterly business excise tax form — individuals have zero obligation.

---

## 12. Phase 9 — `generate.py`

```python
MAX_RETRIES = 3

def generate_dataset(spec: DatasetSpec, used_ssns: set) -> DatasetBundle | None:
    validator = ValidationEngine(used_ssns=used_ssns)

    for attempt in range(1, MAX_RETRIES + 1):
        profile  = generate_profile(spec)
        federal  = compute_federal(profile)
        state    = compute_state(profile, federal)
        bundle   = generate_all_documents(profile, federal, state)

        result = validator.run_all(bundle)
        if result.passed:
            used_ssns.add(profile.ssn)
            return bundle
        else:
            log.warning(f"Dataset {spec.id} attempt {attempt} failed: {result.failures}")

    log.error(f"Dataset {spec.id} failed all {MAX_RETRIES} retries — hard alert")
    return None  # exclude from corpus; do not count toward 2,000

def main():
    used_ssns = set()
    corpus = []
    for spec in build_spec_list(target=2000):
        bundle = generate_dataset(spec, used_ssns)
        if bundle:
            corpus.append(bundle)
    write_validation_summary(corpus)
```

### Output: Validation Summary

Generate `validation_summary.json` after each batch:

```json
{
  "total_generated": 2000,
  "total_discarded": 17,
  "discard_rate": "0.85%",
  "rule_failure_breakdown": {
    "V-03": 8,
    "V-12": 5,
    "V-14": 4
  },
  "ssn_collision_count": 0
}
```

---

## 13. Phase 10 — Pilot Run (20 Datasets)

**Do not scale to 2,000 until the pilot passes all gates.**

### Pilot Composition

| State | Count | Level | Years |
|-------|-------|-------|-------|
| CA | 4 | 1, 2, 3, 3 | 2020, 2023, 2025, 2025 |
| TX | 4 | 1, 2, 3, 3 | 2021, 2024, 2025, 2025 |
| NY | 4 | 1, 2, 3, 3 | 2022, 2023, 2025, 2025 |
| IL | 4 | 1, 2, 3, 3 | 2020, 2024, 2025, 2025 |
| FL | 4 | 1, 2, 3, 3 | 2021, 2022, 2025, 2025 |

Include at least: 1 OBBBA tips persona, 1 car loan persona (VIN validated), 1 senior deduction persona, 1 NY SALT-flip persona, 1 IL year-specific EITC persona.

### Automated Gates

- All 15 validation rules pass on all 20 datasets
- Zero duplicate SSNs
- KS test: income distributions statistically consistent with target demographics

### Manual QA (5 randomly selected datasets)

- Verify OBBBA phase-outs match calculator by hand
- Verify CA/IL/NY state AGI = federal AGI + Schedule 1-A add-back
- Verify year-specific CTC matches `CTC_PER_CHILD[year]`
- Verify VIN mod-11 check digit against NHTSA

---

## 14. Reference: Verified Tax Parameter Matrix 2020–2026

| Parameter | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|-----------|------|------|------|------|------|------|------|
| Std Deduction Single | $12,400 | $12,550 | $12,950 | $13,850 | $14,600 | **$15,750** | $16,100 |
| Std Deduction MFJ | $24,800 | $25,100 | $25,900 | $27,700 | $29,200 | **$31,500** | $32,200 |
| CTC / child | $2,000 | $3,600/<6 $3,000/6–17 | $2,000 | $2,000 | $2,000 | **$2,200** | $2,200 |
| SS Wage Base | $137,700 | $142,800 | $147,000 | $160,200 | $168,600 | $176,100 | ~$183,000 |
| SALT Cap | $10,000 | $10,000 | $10,000 | $10,000 | $10,000 | **$40,000** | $40,400 |
| SALT Phase-Out Start | N/A | N/A | N/A | N/A | N/A | $500,000 | $505,000 |
| QBI Phase-In Width (MFJ) | $100K | $100K | $100K | $100K | $100K | **$150K** | $150K |
| Tips Deduction | N/A | N/A | N/A | N/A | N/A | up to $25K | up to $25K |
| Overtime Deduction | N/A | N/A | N/A | N/A | N/A | $25K MFJ | $25K MFJ |
| Car Loan Interest | N/A | N/A | N/A | N/A | N/A | up to $10K | up to $10K |
| Senior Deduction (65+) | N/A | N/A | N/A | N/A | N/A | $6K/person | $6K/person |
| IL EITC % of Federal | 18% | 20% | 20% | 20% | 30% | **40%** | 40% |
| AMT Phase-Out Start (Single) | $518,400 | $523,600 | $539,900 | $578,150 | $609,350 | $626,350 | $500,000* |
| Cap Gains 20% Start (Single) | $441,450 | $445,850 | $459,750 | $492,300 | $518,900 | $533,400 | $545,500* |

*\* 2026 values stored for forward-compatibility; logic gated.*

---

## 15. Reference: Schedule 1-A OBBBA Deduction Table

| Part | Deduction | Max | Phase-Out Start | Phase-Out End | Rate | Source Docs | Valid Years |
|------|-----------|-----|-----------------|---------------|------|-------------|-------------|
| II | Tips | $25,000 | $150K single / $300K MFJ | $400K / $550K | **$100 per $1K** | W-2 Box 7 or Form 4137 | 2025–2028 |
| III | Overtime | $12.5K single / $25K MFJ | $150K single / $300K MFJ | $400K / $550K | **$100 per $1K** | FLSA premium portion on W-2 | 2025–2028 |
| IV | Car Loan Interest | $10,000 (all statuses) | $100K single / $200K MFJ | $149K / $249K | **$200 per $1K** | VIN (US-assembled, post-2024, first-lien) | 2025–2028 |
| V | Senior (65+) | $6K/person ($12K MFJ both) | $75K single / $150K MFJ | $175K / $250K | **Proportional** | DOB ≤ Dec 31 of (tax_year − 65) | 2025–2028 |
| VI | Limitation Failsafe | Cannot reduce taxable income below $0 | — | — | — | Excess rolls forward | 2025–2028 |

**Form 1040 routing**: Schedule 1-A → Schedule 1 Part II → **Form 1040 Line 10**. There is no "Line 13b."

---

## 16. Reference: Complete 15-Rule Validation Engine

| Rule | Check / Assertion | Purpose |
|------|-------------------|---------|
| V-01 | `SUM(W-2 Box 1) == Form 1040 Line 1a` | Wage consistency across all input documents |
| V-02 | `W-2 Box 3 ≤ SS_Wage_Base[year]`; `Box 4 == Box 3 × 0.062` | SS withholding cap enforcement; 2025 max Box 4 = $10,918.20 |
| V-03 | `SUM(1099-NEC Box 1) ≤ Schedule C Line 1 (gross receipts)` | NEC income flows to Schedule C; ≤ allows for unreported cash |
| V-04 | `Form 1098 Box 1 applied to ≤ $750K loan balance on Schedule A Line 8a` | Mortgage interest deduction capped at $750K principal ($375K MFS) |
| V-05 | `Schedule SE Line 12 == (Line 3 × 0.9235) × 0.153` | SE tax arithmetic; ½ SE tax flows above-the-line |
| V-06 | `Form 1040 Line 11 == Line 9 − Schedule 1 Part II Total` | AGI correctly reduced by ALL adjustments including OBBBA |
| V-07 | `Form 1040 Line 15 == Line 11 − Line 12 − Line 13` | Taxable income = AGI − deduction − QBI; no double-counting OBBBA |
| V-08 | `SUM(1099-INT Box 1) == Schedule B Part I == Form 1040 Line 2b` | Three-document interest income chain must reconcile exactly |
| V-09 | `Form 8959: single/HOH = $200K threshold; MFJ = $250K threshold` | Filing-status-specific Medicare surtax; separate from employer withholding |
| V-10 | `Schedule A Line 5e ≤ SALT_cap[year]` | $10K (2020–24); $40,000 (2025); $40,400 (2026) |
| V-11 | `CTC == CTC_per_child[year] × qualifying_children` | Year-specific CTC: $2K (2020/22–24), $3K–$3.6K (2021), $2.2K (2025+) |
| V-12 | `phase_out_check(MAGI, part, start, end, slope)` for all Schedule 1-A parts | Linear (and proportional for Senior) reduction validation |
| V-13 | `SSN not in used_ssns; add on pass` | Zero duplicate SSNs across 2,000-dataset corpus |
| V-14 | `VIN[0] ∈ ['1','4','5']; len(VIN)==17; VIN[8]==mod11_check_digit(VIN)` | VIN eligibility for Schedule 1-A Part IV |
| V-15 | All required subdirectories and files exist before dataset is finalized | Catches partial generation failures before packaging |

---

*Sources: IRS Revenue Procedure 2025-32, Katten Muchin Rosenman private wealth analysis (2026), Tax Foundation 2026 bracket data, Kiplinger capital gains analysis (March 2026), IRS.gov OBBBA guidance, Shepherd Financial Partners (Sep 2025), H&R Block, EisnerAmper, Doeren Mayhew, CPA Practice Advisor.*
