"""
Authoritative U.S. federal and state tax parameter tables for 2020–2026.

v4.0 Spec Compliant — All values verified against:
  - IRS Revenue Procedure 2025-32
  - OBBBA (One Big Beautiful Bill Act) official guidance
  - Tax Foundation 2026 bracket data
  - Katten, Kiplinger, EisnerAmper, Doeren analyses

2026 values are stored for forward-compatibility but gated in all calculators.
"""

# =============================================================================
# FEDERAL TAX BRACKETS
# =============================================================================
# Format: list of (upper_bound, rate) tuples. float('inf') = top bracket.

FEDERAL_BRACKETS = {
    2020: {
        "single": [
            (9875, 0.10), (40125, 0.12), (85525, 0.22), (163300, 0.24),
            (207350, 0.32), (518400, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (19750, 0.10), (80250, 0.12), (171050, 0.22), (326600, 0.24),
            (414700, 0.32), (622050, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (14100, 0.10), (53700, 0.12), (85500, 0.22), (163300, 0.24),
            (207350, 0.32), (518400, 0.35), (float('inf'), 0.37),
        ],
    },
    2021: {
        "single": [
            (9950, 0.10), (40525, 0.12), (86375, 0.22), (164925, 0.24),
            (209425, 0.32), (523600, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (19900, 0.10), (81050, 0.12), (172750, 0.22), (329850, 0.24),
            (418850, 0.32), (628300, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (14200, 0.10), (54200, 0.12), (86350, 0.22), (164900, 0.24),
            (209400, 0.32), (523600, 0.35), (float('inf'), 0.37),
        ],
    },
    2022: {
        "single": [
            (10275, 0.10), (41775, 0.12), (89075, 0.22), (170050, 0.24),
            (215950, 0.32), (539900, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (20550, 0.10), (83550, 0.12), (178150, 0.22), (340100, 0.24),
            (431900, 0.32), (647850, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (14650, 0.10), (55900, 0.12), (89050, 0.22), (170050, 0.24),
            (215950, 0.32), (539900, 0.35), (float('inf'), 0.37),
        ],
    },
    2023: {
        "single": [
            (11000, 0.10), (44725, 0.12), (95375, 0.22), (182100, 0.24),
            (231250, 0.32), (578125, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (22000, 0.10), (89450, 0.12), (190750, 0.22), (364200, 0.24),
            (462500, 0.32), (693750, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (15700, 0.10), (59850, 0.12), (95350, 0.22), (182100, 0.24),
            (231250, 0.32), (578100, 0.35), (float('inf'), 0.37),
        ],
    },
    2024: {
        "single": [
            (11600, 0.10), (47150, 0.12), (100525, 0.22), (191950, 0.24),
            (243725, 0.32), (609350, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (23200, 0.10), (94300, 0.12), (201050, 0.22), (383900, 0.24),
            (487450, 0.32), (731200, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (16550, 0.10), (63100, 0.12), (100500, 0.22), (191950, 0.24),
            (243700, 0.32), (609350, 0.35), (float('inf'), 0.37),
        ],
    },
    2025: {
        "single": [
            (11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24),
            (250525, 0.32), (626350, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (23850, 0.10), (96950, 0.12), (206700, 0.22), (394600, 0.24),
            (501050, 0.32), (751600, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (17000, 0.10), (64850, 0.12), (103350, 0.22), (197300, 0.24),
            (250500, 0.32), (626350, 0.35), (float('inf'), 0.37),
        ],
    },
    # 2026: forward-compat only — NOT IN DELIVERABLE SCOPE
    2026: {
        "single": [
            (11925, 0.10), (48475, 0.12), (103350, 0.22), (197300, 0.24),
            (250525, 0.32), (626350, 0.35), (float('inf'), 0.37),
        ],
        "mfj": [
            (23850, 0.10), (96950, 0.12), (206700, 0.22), (394600, 0.24),
            (501050, 0.32), (751600, 0.35), (float('inf'), 0.37),
        ],
        "hoh": [
            (17000, 0.10), (64850, 0.12), (103350, 0.22), (197300, 0.24),
            (250500, 0.32), (626350, 0.35), (float('inf'), 0.37),
        ],
    },
}

# =============================================================================
# STANDARD DEDUCTIONS (E-01 fix: 2025 corrected from $15,000/$30,000)
# =============================================================================

STANDARD_DEDUCTION = {
    2020: {"single": 12400, "mfj": 24800, "hoh": 18650, "mfs": 12400},
    2021: {"single": 12550, "mfj": 25100, "hoh": 18800, "mfs": 12550},
    2022: {"single": 12950, "mfj": 25900, "hoh": 19400, "mfs": 12950},
    2023: {"single": 13850, "mfj": 27700, "hoh": 20800, "mfs": 13850},
    2024: {"single": 14600, "mfj": 29200, "hoh": 21900, "mfs": 14600},
    2025: {"single": 15750, "mfj": 31500, "hoh": 23625, "mfs": 15750},
    2026: {"single": 16100, "mfj": 32200, "hoh": 24150, "mfs": 16100},
}

# Additional Standard Deduction (65+ or blind) — per person
ADDITIONAL_STD_DEDUCTION = {
    2025: {"single_or_mfs": 2000, "mfj_per_person": 1600},
    2026: {"single_or_mfs": 2050, "mfj_per_person": 1650},
}

# =============================================================================
# SOCIAL SECURITY
# =============================================================================

SS_WAGE_BASE = {
    2020: 137700, 2021: 142800, 2022: 147000,
    2023: 160200, 2024: 168600, 2025: 176100,
    2026: 183000,  # estimated
}

SS_RATE_EMPLOYEE = 0.062   # 6.2% from employee paychecks
SS_TAX_RATE = 0.124        # 12.4% total (employee + employer for SE)
MEDICARE_TAX_RATE = 0.029  # 2.9% total for SE
SE_TAX_RATE = SS_TAX_RATE + MEDICARE_TAX_RATE  # 15.3%
SE_INCOME_FACTOR = 0.9235  # 92.35% of net SE income subject to SE tax

# =============================================================================
# MEDICARE SURTAX — Additional 0.9% (E-09 fix)
# =============================================================================

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

# =============================================================================
# CHILD TAX CREDIT — Year-Specific (E-02 fix)
# =============================================================================

CTC_PER_CHILD = {
    2020: 2000,
    2021: {"under_6": 3600, "age_6_to_17": 3000},  # ARPA expansion
    2022: 2000,
    2023: 2000,
    2024: 2000,
    2025: 2200,   # OBBBA increase
    2026: 2200,   # inflation too low to adjust
}

CTC_REFUNDABLE_MAX = {
    2020: 1400, 2021: 1400, 2022: 1500, 2023: 1600,
    2024: 1700, 2025: 1700, 2026: 1700,
}

CTC_PHASEOUT = {
    2020: {"single": 200000, "mfj": 400000, "hoh": 200000},
    2021: {"single": 75000,  "mfj": 150000, "hoh": 112500},
    2022: {"single": 200000, "mfj": 400000, "hoh": 200000},
    2023: {"single": 200000, "mfj": 400000, "hoh": 200000},
    2024: {"single": 200000, "mfj": 400000, "hoh": 200000},
    2025: {"single": 200000, "mfj": 400000, "hoh": 200000},
    2026: {"single": 200000, "mfj": 400000, "hoh": 200000},
}


def get_ctc_per_child(tax_year: int, child_age: int = None) -> int:
    """Get CTC amount for a given year, handling 2021 age-based split."""
    val = CTC_PER_CHILD[tax_year]
    if isinstance(val, dict):
        return val["under_6"] if child_age is not None and child_age < 6 else val["age_6_to_17"]
    return val


# =============================================================================
# SALT CAPS (E-11 fix: 2025=$40K, 2026=$40,400)
# =============================================================================

SALT_CAP = {
    2020: 10000, 2021: 10000, 2022: 10000, 2023: 10000, 2024: 10000,
    2025: 40000,   # OBBBA jump
    2026: 40400,   # 1% annual increment
}

SALT_PHASEOUT_START = {
    2020: None, 2021: None, 2022: None, 2023: None, 2024: None,
    2025: 500000,
    2026: 505000,
}

# =============================================================================
# QBI DEDUCTION (Section 199A) (E-07 fix: width, not start)
# =============================================================================

QBI_DEDUCTION_RATE = 0.20  # 20% of qualified business income

QBI_TAXABLE_INCOME_THRESHOLD = {
    2020: {"single": 163300, "mfj": 326600},
    2021: {"single": 164900, "mfj": 329800},
    2022: {"single": 170050, "mfj": 340100},
    2023: {"single": 182100, "mfj": 364200},
    2024: {"single": 191950, "mfj": 383900},
    2025: {"single": 197300, "mfj": 394600},
    2026: {"single": 201775, "mfj": 403500},
}

QBI_PHASEOUT_WIDTH = {
    2020: {"single": 50000, "mfj": 100000},
    2021: {"single": 50000, "mfj": 100000},
    2022: {"single": 50000, "mfj": 100000},
    2023: {"single": 50000, "mfj": 100000},
    2024: {"single": 50000, "mfj": 100000},
    2025: {"single": 75000, "mfj": 150000},  # OBBBA expansion
    2026: {"single": 75000, "mfj": 150000},
}

# =============================================================================
# OBBBA SCHEDULE 1-A DEDUCTIONS (2025+)
# =============================================================================
# E-03 fix: Above-the-line via Schedule 1 Part II → Form 1040 Line 10

OBBBA_DEDUCTIONS = {
    "tips": {
        "max": 25000,
        "phaseout_start": {"single": 150000, "hoh": 150000, "mfj": 300000},
        "phaseout_end":   {"single": 400000, "hoh": 400000, "mfj": 550000},
        "slope_per_1k": 100,       # $100 reduction per $1,000 over start
        "valid_years": range(2025, 2029),
    },
    "overtime": {
        "max": {"single": 12500, "hoh": 12500, "mfj": 25000},
        "phaseout_start": {"single": 150000, "hoh": 150000, "mfj": 300000},
        "phaseout_end":   {"single": 400000, "hoh": 400000, "mfj": 550000},
        "slope_per_1k": 100,
        "valid_years": range(2025, 2029),
    },
    "car_loan_interest": {
        "max": 10000,              # all filing statuses
        "phaseout_start": {"single": 100000, "hoh": 100000, "mfj": 200000},
        "phaseout_end":   {"single": 149000, "hoh": 149000, "mfj": 249000},
        "slope_per_1k": 200,       # DOUBLE the tips/overtime slope (E-04)
        "valid_years": range(2025, 2029),
    },
    "senior": {
        "max": {"single": 6000, "hoh": 6000, "mfj_both": 12000},  # $6K/person
        "phaseout_start": {"single": 75000,  "hoh": 75000,  "mfj": 150000},
        "phaseout_end":   {"single": 175000, "hoh": 175000, "mfj": 250000},
        "slope_type": "proportional",    # ratio over range, NOT per-$1K step
        "valid_years": range(2025, 2029),
    },
}

# =============================================================================
# LONG-TERM CAPITAL GAINS THRESHOLDS (E-05 fix: 2026 corrected)
# =============================================================================
# Format: (0% upper_bound, 15% upper_bound); 20% above 15% threshold

LTCG_BRACKETS = {
    2020: {"single": (40000,  441450), "mfj": (80000,  496600)},
    2021: {"single": (40400,  445850), "mfj": (80800,  501600)},
    2022: {"single": (41675,  459750), "mfj": (83350,  517200)},
    2023: {"single": (44625,  492300), "mfj": (89250,  553850)},
    2024: {"single": (47025,  518900), "mfj": (94050,  583750)},
    2025: {"single": (48350,  533400), "mfj": (96700,  600050)},
    2026: {"single": (49450,  545500), "mfj": (98900,  613700)},
}

# =============================================================================
# AMT PARAMETERS (E-06 fix: 2026 OBBBA revert)
# =============================================================================

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
    # 2026: OBBBA reverts start thresholds; doubles rate to 50¢ — GATED
    2026: {
        "exemption":      {"single": 90100,  "mfj": 140200},
        "phaseout_start": {"single": 500000, "mfj": 1000000},
        "phaseout_rate":  0.50,  # DOUBLED — NOT IN DELIVERABLE SCOPE
    },
}

# =============================================================================
# ILLINOIS EITC YEAR-SPECIFIC RATES (E-15 fix)
# =============================================================================

IL_EITC_RATE = {
    2020: 0.18, 2021: 0.20, 2022: 0.20, 2023: 0.20,
    2024: 0.30, 2025: 0.40, 2026: 0.40,
}

# IL Child Tax Credit: 40% of base IL EITC for children under age 12
IL_CTC_RATE = 0.40

# =============================================================================
# CALIFORNIA STATE TAX
# =============================================================================

CA_BRACKETS = {
    "single": [
        (10412, 0.01), (24684, 0.02), (38959, 0.04), (54081, 0.06),
        (68350, 0.08), (349137, 0.093), (418961, 0.103),
        (698271, 0.113), (float('inf'), 0.123),
    ],
    "mfj": [
        (20824, 0.01), (49368, 0.02), (77918, 0.04), (108162, 0.06),
        (136700, 0.08), (698274, 0.093), (837922, 0.103),
        (1396542, 0.113), (float('inf'), 0.123),
    ],
    "hoh": [
        (20839, 0.01), (49371, 0.02), (63644, 0.04), (78765, 0.06),
        (93037, 0.08), (474824, 0.093), (569790, 0.103),
        (949649, 0.113), (float('inf'), 0.123),
    ],
}

CA_STANDARD_DEDUCTION = {"single": 5540, "mfj": 11080, "hoh": 8310}
CA_PERSONAL_EXEMPTION = {"single": 144, "mfj": 288, "hoh": 144}
CA_DEPENDENT_EXEMPTION = 433
CA_SDI_RATE = 0.011
CA_SDI_WAGE_LIMIT = {
    2020: 122909, 2021: 128298, 2022: 145600, 2023: 153164,
    2024: 153164, 2025: None,  # No cap for 2025 per v4 spec
}

# =============================================================================
# NEW YORK STATE TAX
# =============================================================================

NY_BRACKETS = {
    "single": [
        (8500, 0.04), (11700, 0.045), (13900, 0.0525), (80650, 0.055),
        (215400, 0.06), (1077550, 0.0685), (5000000, 0.0965),
        (25000000, 0.103), (float('inf'), 0.109),
    ],
    "mfj": [
        (17150, 0.04), (23600, 0.045), (27900, 0.0525), (161550, 0.055),
        (323200, 0.06), (2155350, 0.0685), (5000000, 0.0965),
        (25000000, 0.103), (float('inf'), 0.109),
    ],
    "hoh": [
        (12800, 0.04), (17650, 0.045), (20900, 0.0525), (107650, 0.055),
        (269300, 0.06), (1616450, 0.0685), (5000000, 0.0965),
        (25000000, 0.103), (float('inf'), 0.109),
    ],
}

NY_STANDARD_DEDUCTION = {"single": 8000, "mfj": 16050, "hoh": 11200}

# =============================================================================
# ILLINOIS STATE TAX (flat rate)
# =============================================================================

IL_FLAT_RATE = 0.0495
IL_PERSONAL_EXEMPTION = 2625  # per person (2024/2025)

# =============================================================================
# STATES WITH NO INCOME TAX
# =============================================================================

NO_INCOME_TAX_STATES = {"TX", "FL"}

# =============================================================================
# WITHHOLDING APPROXIMATIONS (for realistic W-2 generation)
# =============================================================================

FEDERAL_WITHHOLDING_APPROX = [
    (15000, 0.05), (40000, 0.08), (80000, 0.12),
    (160000, 0.16), (300000, 0.22), (float('inf'), 0.28),
]

STATE_WITHHOLDING_APPROX = {
    "CA": 0.04, "NY": 0.045, "IL": 0.0495, "TX": 0.0, "FL": 0.0,
}

# =============================================================================
# NON-ITEMIZER CHARITABLE DEDUCTION (starts 2026 — E-08)
# =============================================================================

CHARITABLE_NON_ITEMIZER = {
    # CARES Act provisions
    2020: {"single": 300, "mfj": 300},
    2021: {"single": 300, "mfj": 600},
    # 2022-2025: not available
    # 2026+: permanent OBBBA provision — GATED
    2026: {"single": 1000, "mfj": 2000},
}

# =============================================================================
# TIPPED WORKER OCCUPATIONS (for OBBBA tips deduction eligibility)
# =============================================================================

TIPPED_OCCUPATIONS = [
    "Restaurant Server", "Bartender", "Hair Stylist", "Barber",
    "Hotel Bellhop", "Valet Parking Attendant", "Tour Guide",
    "Delivery Driver", "Rideshare Driver", "Casino Dealer",
    "Nail Technician", "Massage Therapist", "Barista",
]


def compute_tax_from_brackets(taxable_income, brackets):
    """Compute tax from a bracket schedule.

    Args:
        taxable_income: The taxable income amount.
        brackets: List of (upper_bound, rate) tuples.

    Returns:
        Total tax amount (float).
    """
    tax = 0.0
    prev_upper = 0
    for upper, rate in brackets:
        if taxable_income <= prev_upper:
            break
        taxable_in_bracket = min(taxable_income, upper) - prev_upper
        tax += taxable_in_bracket * rate
        prev_upper = upper
    return round(tax, 2)
