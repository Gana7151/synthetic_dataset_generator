"""
Generates synthetic, internally-consistent taxpayer profiles.

v5.0 — Guide v2.0 Compliant:
  - IRS SOI filing status distribution weights (§13 Phase 2)
  - Triangular age distributions by filing status
  - OBBBA boolean flags calibrated to guide probabilities
  - CarLoanProfile with VIN validation
  - W-2 Box 7 tips, overtime pay fields
  - Year-specific CTC awareness
  - Senior (65+) DOB generation
  - Uses versioned tax_parameters_store
"""

import random
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import date
from faker import Faker
import numpy as np

from tax_engine.tax_tables import (
    SS_WAGE_BASE, STATE_WITHHOLDING_APPROX, FEDERAL_WITHHOLDING_APPROX,
    TIPPED_OCCUPATIONS, SS_RATE_EMPLOYEE,
)
from tax_engine.tax_parameters_store import get_tax_parameters, is_obbba_year

fake = Faker('en_US')

# ---------------------------------------------------------------------------
# IRS SOI Filing Status Distributions (Guide §13 Phase 2)
# Source: IRS SOI Individual Complete Report, Table 1.1
# ---------------------------------------------------------------------------

FILING_STATUS_DISTRIBUTION = {
    'single': 0.452,
    'mfj':    0.388,
    'hoh':    0.129,
    # MFS (2.2%) and QSS (0.9%) excluded — not in current scope
}

# Normalize to sum to 1.0 (since we excluded MFS/QSS)
_FILING_STATUSES = list(FILING_STATUS_DISTRIBUTION.keys())
_FILING_WEIGHTS = [v / sum(FILING_STATUS_DISTRIBUTION.values())
                   for v in FILING_STATUS_DISTRIBUTION.values()]

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class Dependent:
    first_name: str
    last_name: str
    ssn: str
    dob: str  # YYYY-MM-DD
    relationship: str
    age: int = 0


@dataclass
class W2Income:
    employer_name: str
    employer_ein: str
    employer_address: str
    employer_city: str
    employer_state: str
    employer_zip: str
    employee_name: str
    employee_ssn: str
    wages: float                    # Box 1
    federal_withheld: float         # Box 2
    ss_wages: float                 # Box 3
    ss_tax: float                   # Box 4
    medicare_wages: float           # Box 5
    medicare_tax: float             # Box 6
    box_7_tips: float = 0.0        # Box 7: Social security tips (OBBBA)
    state_wages: float = 0.0       # Box 16
    state_withheld: float = 0.0    # Box 17
    box_14_sdi: float = 0.0        # Box 14: CA SDI
    overtime_pay: float = 0.0      # OBBBA: FLSA premium portion


@dataclass
class InterestIncome:
    payer_name: str
    payer_ein: str
    amount: float


@dataclass
class DividendIncome:
    payer_name: str
    payer_ein: str
    ordinary_dividends: float
    qualified_dividends: float


@dataclass
class MortgageInterest:
    lender_name: str
    lender_ein: str
    principal: float
    interest_paid: float


@dataclass
class CapitalGainsIncome:
    payer_name: str
    payer_ein: str
    short_term_gains: float
    long_term_gains: float


@dataclass
class BusinessExpenses:
    advertising: float = 0.0
    car_and_truck: float = 0.0
    insurance: float = 0.0
    office_expense: float = 0.0
    rent_lease: float = 0.0
    supplies: float = 0.0
    taxes_licenses: float = 0.0
    utilities: float = 0.0
    other: float = 0.0

    @property
    def total(self):
        return round(sum([
            self.advertising, self.car_and_truck, self.insurance,
            self.office_expense, self.rent_lease, self.supplies,
            self.taxes_licenses, self.utilities, self.other
        ]), 2)


@dataclass
class BusinessIncome:
    business_name: str
    activity_code: str
    activity_desc: str
    gross_receipts: float
    expenses: BusinessExpenses
    net_profit: float = 0.0
    depreciation: float = 0.0
    rent_expense: float = 0.0
    deductible_meals: float = 0.0
    wages_paid: float = 0.0
    other_expense_items: List[tuple] = field(default_factory=list)
    material_participation: bool = True
    made_1099_payments: bool = False
    will_file_1099: bool = False
    vehicle: Optional[dict] = None
    depreciable_assets: List["DepreciableAsset"] = field(default_factory=list)

@dataclass
class PrepNotes:
    name: str = ""
    ptin: str = ""          # Format: P + 8 digits
    firm_name: str = ""
    firm_address: str = ""
    firm_ein: str = ""
    self_employed: bool = False

@dataclass
class DepreciableAsset:
    description: str = ""
    placed_in_service: str = ""
    cost: float = 0.0
    recovery_period: int = 5
    method: str = "200DB"
    convention: str = "HY"
    depreciation_this_year: float = 0.0
    section_179_elected: float = 0.0
    prior_depreciation: float = 0.0


@dataclass
class CarLoanProfile:
    """Car loan details for OBBBA Schedule 1-A Part IV."""
    vin: str = ""
    annual_interest: float = 0.0
    purchase_date: str = ""         # YYYY-MM-DD
    is_first_lien: bool = True
    is_new_vehicle: bool = True


@dataclass
class TaxProfile:
    """Complete taxpayer profile for a single dataset."""
    # Meta
    dataset_id: str = ""
    tax_year: int = 2024
    state: str = "CA"
    level: int = 1

    # Primary taxpayer
    primary_first: str = ""
    primary_last: str = ""
    primary_ssn: str = ""
    primary_dob: str = ""
    primary_occupation: str = ""
    phone: str = ""
    email: str = ""
    preparer: Optional[PrepNotes] = None
    has_home_office: bool = False
    home_office_sqft: int = 0
    home_office_deduction: float = 0.0

    # Spouse (None fields if single/HoH)
    spouse_first: Optional[str] = None
    spouse_last: Optional[str] = None
    spouse_ssn: Optional[str] = None
    spouse_dob: Optional[str] = None
    spouse_occupation: Optional[str] = None

    # Address
    address: str = ""
    city: str = ""
    zip_code: str = ""

    # Filing
    filing_status: str = "single"  # single, mfj, hoh

    # Dependents
    dependents: List[Dependent] = field(default_factory=list)

    # Income sources
    w2_incomes: List[W2Income] = field(default_factory=list)
    interest_incomes: List[InterestIncome] = field(default_factory=list)
    dividend_incomes: List[DividendIncome] = field(default_factory=list)
    capital_gains: List[CapitalGainsIncome] = field(default_factory=list)
    mortgage_interests: List[MortgageInterest] = field(default_factory=list)
    business_income: Optional[BusinessIncome] = None

    # OBBBA flags (2025+ only)
    is_tipped_worker: bool = False
    overtime_eligible: bool = False
    has_car_loan: bool = False
    is_senior_65_plus: bool = False
    car_loan: Optional[CarLoanProfile] = None

    # Computed results (filled by calculators)
    federal_results: dict = field(default_factory=dict)
    state_results: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Reference data
# ---------------------------------------------------------------------------

STATE_CITIES = {
    "CA": [
        ("Sacramento", "95814"), ("Sacramento", "95816"),
        ("Los Angeles", "90012"), ("Los Angeles", "90045"),
        ("San Francisco", "94102"), ("San Francisco", "94110"),
        ("San Diego", "92101"), ("San Jose", "95112"),
        ("Fresno", "93721"), ("Oakland", "94612"),
    ],
    "TX": [
        ("Houston", "77001"), ("Houston", "77056"),
        ("Dallas", "75201"), ("Dallas", "75225"),
        ("Austin", "78701"), ("Austin", "78745"),
        ("San Antonio", "78201"), ("Fort Worth", "76102"),
        ("El Paso", "79901"), ("Plano", "75024"),
    ],
    "NY": [
        ("New York", "10001"), ("New York", "10019"),
        ("New York", "10028"), ("Brooklyn", "11201"),
        ("Buffalo", "14201"), ("Albany", "12207"),
        ("Rochester", "14604"), ("Syracuse", "13202"),
        ("Yonkers", "10701"), ("White Plains", "10601"),
    ],
    "IL": [
        ("Chicago", "60601"), ("Chicago", "60614"),
        ("Chicago", "60657"), ("Springfield", "62701"),
        ("Naperville", "60540"), ("Aurora", "60505"),
        ("Rockford", "61101"), ("Peoria", "61602"),
        ("Evanston", "60201"), ("Joliet", "60431"),
    ],
    "FL": [
        ("Miami", "33101"), ("Miami", "33139"),
        ("Orlando", "32801"), ("Tampa", "33602"),
        ("Jacksonville", "32202"), ("Fort Lauderdale", "33301"),
        ("St. Petersburg", "33701"), ("Naples", "34102"),
        ("Sarasota", "34236"), ("West Palm Beach", "33401"),
    ],
}

EMPLOYERS = {
    "CA": [
        ("Pacific Health System Inc.", "Healthcare"),
        ("Golden State Tech Solutions", "Technology"),
        ("Bay Area Financial Group", "Finance"),
        ("Sierra Construction LLC", "Construction"),
        ("Valley Education Services", "Education"),
        ("CalCoast Logistics Inc.", "Logistics"),
        ("SunView Engineering Corp.", "Engineering"),
    ],
    "TX": [
        ("Lone Star Medical Center", "Healthcare"),
        ("TexTech Industries Inc.", "Technology"),
        ("Gulf Energy Partners LLC", "Energy"),
        ("Prairie Land Development", "Construction"),
        ("Bluebonnet School District", "Education"),
        ("Houston Freight Systems", "Logistics"),
        ("Rio Grande Engineering", "Engineering"),
    ],
    "NY": [
        ("Empire State Health Network", "Healthcare"),
        ("Manhattan Digital Labs Inc.", "Technology"),
        ("Hudson Valley Capital Group", "Finance"),
        ("Brooklyn Bridge Builders LLC", "Construction"),
        ("Metro Education Foundation", "Education"),
        ("Liberty Transport Corp.", "Logistics"),
        ("Gotham Engineering Solutions", "Engineering"),
    ],
    "IL": [
        ("Lakeside Medical Group", "Healthcare"),
        ("Midwest Software Systems", "Technology"),
        ("Prairie Capital Advisors", "Finance"),
        ("Lincoln Park Construction Co.", "Construction"),
        ("Great Plains School District", "Education"),
        ("Windy City Logistics Corp.", "Logistics"),
        ("Heartland Engineering Inc.", "Engineering"),
    ],
    "FL": [
        ("Sunshine Health Partners", "Healthcare"),
        ("Coastal Tech Innovations", "Technology"),
        ("Everglades Financial Group", "Finance"),
        ("Palm Harbor Builders LLC", "Construction"),
        ("Gulf Coast Academy", "Education"),
        ("Key West Shipping Inc.", "Logistics"),
        ("Atlantic Engineering Corp.", "Engineering"),
    ],
}

BUSINESS_TYPES = [
    ("Freelance Graphic & Web Design", "541430", "Graphic Design Services"),
    ("Photography Services", "541921", "Photography"),
    ("Consulting Services", "541611", "Management Consulting"),
    ("Home Repair & Maintenance", "236118", "Residential Remodeling"),
    ("Digital Marketing Solutions", "541810", "Advertising Services"),
    ("Tutoring & Education Services", "611691", "Tutoring"),
    ("Bookkeeping Services", "541219", "Bookkeeping"),
    ("Personal Training", "812990", "Personal Services"),
    ("Catering Services", "722320", "Catering"),
    ("Mobile App Development", "511210", "Software Publishing"),
    ("Content Creation & Writing", "711510", "Independent Writers"),
    ("Event Planning Services", "561920", "Convention Planning"),
]

BANKS = [
    "First National Bank", "Pacific Coast Credit Union",
    "Citizens Trust Bank", "Heritage Savings Bank",
    "Community Federal Bank", "Sunrise Credit Union",
    "Patriot National Bank", "Liberty Savings & Loan",
]

BROKERAGES = [
    ("Vanguard", "23-1945930"),
    ("Charles Schwab & Co.", "94-1737782"),
    ("Fidelity Investments", "04-3523567"),
    ("TD Ameritrade Inc.", "47-0533629"),
    ("E*TRADE Securities", "13-2961966"),
]

OCCUPATIONS = [
    "Registered Nurse", "Software Engineer", "Accountant",
    "Marketing Manager", "Teacher", "Sales Representative",
    "Project Manager", "Human Resources Specialist",
    "Financial Analyst", "Operations Manager",
    "Administrative Assistant", "Dental Hygienist",
    "Civil Engineer", "Graphic Designer", "Pharmacist",
    "Real Estate Agent", "Social Worker", "Paralegal",
    "Data Analyst", "Mechanical Engineer",
]

RELATIONSHIPS = ["Son", "Daughter"]


# ---------------------------------------------------------------------------
# SSN / EIN generators
# ---------------------------------------------------------------------------

_used_ssns = set()


def _generate_ssn():
    """Generate a unique synthetic SSN (9 digits, never starts with 9 or 000)."""
    while True:
        area = random.randint(100, 899)
        group = random.randint(1, 99)
        serial = random.randint(1, 9999)
        ssn = f"{area:03d}{group:02d}{serial:04d}"
        if ssn not in _used_ssns:
            _used_ssns.add(ssn)
            return ssn


def _generate_ein():
    """Generate a synthetic EIN."""
    prefix = random.choice([10, 12, 13, 20, 22, 23, 24, 27, 30, 32, 34,
                            36, 37, 38, 41, 42, 43, 45, 46, 47, 48, 51,
                            52, 53, 54, 55, 56, 58, 59, 61, 62, 63, 64,
                            65, 66, 68, 71, 72, 73, 74, 75, 76, 77, 81,
                            82, 83, 84, 85, 86, 87, 88, 91, 92, 93, 94, 95])
    serial = random.randint(1000000, 9999999)
    return f"{prefix:02d}{serial:07d}"


def reset_ssn_pool():
    """Reset the used SSN pool (call between batch runs)."""
    global _used_ssns
    _used_ssns = set()

def _generate_ptin() -> str:
    return f"P{random.randint(10000000, 99999999)}"


# ---------------------------------------------------------------------------
# Profile Generator
# ---------------------------------------------------------------------------



# --- QUANTITATIVE MODELS ---

def sample_agi(filing_status: str, rng: np.random.Generator) -> int:
    MFS_PENALTY = 0.72
    HOH_PREMIUM = 0.85
    if rng.random() < 0.80:
        agi = rng.lognormal(mean=10.5, sigma=0.85)
    else:
        agi = rng.lognormal(mean=11.8, sigma=1.2)
    fs_upper = filing_status.upper()
    if fs_upper == "MFJ":
        agi *= 1.65
    elif fs_upper == "MFS":
        agi *= MFS_PENALTY
    elif fs_upper == "HOH":
        agi *= HOH_PREMIUM
    floor = {"S": 13_850, "MFJ": 27_700, "MFS": 5, "HOH": 20_800}.get(fs_upper, 13_850)
    return max(int(agi), floor)

def generate_income_split(agi: int, rng: np.random.Generator) -> dict:
    income_type = rng.choice(["wages_only", "mixed", "self_emp_only"], p=[0.68, 0.24, 0.08])
    if income_type == "wages_only":
        wages = int(agi * rng.uniform(0.88, 1.02))
        return {"wages": wages, "schedule_c": 0, "interest": int(agi * rng.beta(1.5, 20)), "dividends": int(agi * rng.beta(1.2, 25))}
    elif income_type == "self_emp_only":
        gross_revenue = int(agi * rng.uniform(1.3, 2.1))
        return {"wages": 0, "schedule_c": agi, "gross_revenue": gross_revenue, "interest": int(agi * rng.beta(1.0, 30)), "dividends": 0}
    else:
        wage_share = rng.beta(4, 3)
        return {"wages": int(agi * wage_share), "schedule_c": int(agi * (1 - wage_share) * rng.uniform(0.6, 1.0)), "interest": int(agi * rng.beta(1.2, 18)), "dividends": int(agi * rng.beta(1.0, 22)), "gross_revenue": int(agi * (1 - wage_share) * rng.uniform(1.3, 2.1))}

def generate_schedule_c_expenses(gross_revenue: int, industry_code: str, rng: np.random.Generator) -> dict:
    g = gross_revenue
    margins = {"541": (0.35, 0.60), "722": (0.05, 0.15), "621": (0.25, 0.50), "81": (0.20, 0.40)}
    prefix = industry_code[:3] if len(industry_code) >= 3 else "541"
    margin_range = margins.get(prefix, (0.25, 0.55))
    target_margin = rng.uniform(*margin_range)
    expenses = {
        "advertising": int(g * rng.uniform(0.005, 0.040)),
        "depreciation": int(g * rng.uniform(0.010, 0.080)),
        "office_expenses": int(g * rng.uniform(0.003, 0.025)),
        "rent_lease": int(g * rng.uniform(0.020, 0.120)),
        "supplies": int(g * rng.uniform(0.005, 0.050)),
        "taxes_licenses": int(g * rng.uniform(0.005, 0.030)),
        "meals": int(g * rng.uniform(0.002, 0.020)),
    }
    total_non_other = sum(expenses.values())
    target_total_expenses = int(g * (1 - target_margin))
    other_expenses = max(0, target_total_expenses - total_non_other)
    expenses["other_expenses"] = other_expenses
    expenses["total_expenses"] = sum(expenses.values())
    expenses["net_profit"] = g - expenses["total_expenses"]
    return expenses

def compute_se_tax(net_self_employment: int) -> dict:
    if net_self_employment <= 400: return {"se_tax": 0, "deductible_se_tax": 0, "se_taxable_income": 0}
    se_taxable = int(net_self_employment * 0.9235)
    ss_base = 168_600
    ss_portion = min(se_taxable, ss_base)
    medicare_portion = se_taxable
    se_tax = int(ss_portion * 0.124 + medicare_portion * 0.029)
    deductible_se_tax = se_tax // 2
    return {"se_tax": se_tax, "deductible_se_tax": deductible_se_tax, "se_taxable_income": se_taxable}

def validate_and_enforce_constraints(profile: dict) -> dict:
    agi = profile.get("agi", 0)
    wages = profile.get("wages", 0)
    sched_c = profile.get("schedule_c_net", 0)
    interest = profile.get("interest", 0)
    dividends = profile.get("dividends", 0)
    income_sum = wages + sched_c + interest + dividends
    if abs(income_sum - agi) > 500:
        scale = agi / income_sum if income_sum > 0 else 1
        profile["wages"] = int(wages * scale)
        profile["interest"] = int(interest * scale)
        profile["dividends"] = int(dividends * scale)
    if sched_c > 400 and profile.get("se_tax", 0) == 0:
        se = compute_se_tax(sched_c)
        profile.update(se)
    elif sched_c <= 400:
        profile["se_tax"] = 0
        profile["deductible_se_tax"] = 0
    tax_liability = profile.get("gross_tax", 0)
    ctc = profile.get("ctc", 0)
    if ctc > tax_liability:
        profile["ctc"] = tax_liability
        profile["actc"] = max(0, ctc - tax_liability)
    if agi > 1_000_000 and profile.get("state") == "CA":
        if profile.get("ca_net_tax", 0) < int((agi - 1_000_000) * 0.01):
            profile["flag_high_income_ca"] = True
    gross_rev = profile.get("gross_revenue", 0)
    total_exp = profile.get("total_expenses", 0)
    if gross_rev > 0 and total_exp > gross_rev:
        profile["total_expenses"] = int(gross_rev * 0.98)
        profile["net_profit"] = gross_rev - profile["total_expenses"]
    return profile

def _generate_age_for_status(filing_status: str, tax_year: int,
                              force_senior: bool = False) -> int:
    """Generate age using triangular distribution per filing status.

    Guide §13 Phase 2: Age distributions matched to IRS SOI empirical data.
    """
    if force_senior:
        return random.randint(65, 82)

    if filing_status == 'single':
        return int(np.random.triangular(18, 32, 75))
    elif filing_status == 'mfj':
        return int(np.random.triangular(25, 45, 80))
    elif filing_status == 'hoh':
        return int(np.random.triangular(22, 38, 65))
    else:
        return int(np.random.triangular(30, 50, 80))


def generate_profile(dataset_id: str, state: str, tax_year: int, level: int, seed: int = None) -> TaxProfile:
    """Generate a complete, internally-consistent taxpayer profile.

    v5.0 — Guide v2.0 compliant:
      - IRS SOI filing status distribution
      - Triangular age distributions
      - Calibrated OBBBA flag probabilities
    """

    if seed is None:
        seed = hash(dataset_id) & 0xFFFFFFFF
    rng = np.random.default_rng(seed)
    random.seed(seed)
    profile = TaxProfile(
        dataset_id=dataset_id,
        tax_year=tax_year,
        state=state,
        level=level,
    )

    # --- Filing status (IRS SOI weighted) & dependents ---
    # Level still influences dependent count and complexity,
    # but filing status uses realistic SOI distribution.
    if level == 1:
        # Level 1: bias toward simpler statuses but still use SOI weights
        status_choices = ['single', 'mfj']
        status_weights = [0.55, 0.45]  # slight bias to single for simplicity
        profile.filing_status = random.choices(status_choices, weights=status_weights, k=1)[0]
        num_dependents = random.choice([0, 0, 0, 1])
    elif level == 2:
        # Level 2: full SOI distribution
        profile.filing_status = random.choices(_FILING_STATUSES, weights=_FILING_WEIGHTS, k=1)[0]
        num_dependents = random.randint(1, 3)
    else:
        # Level 3: full SOI distribution
        profile.filing_status = random.choices(_FILING_STATUSES, weights=_FILING_WEIGHTS, k=1)[0]
        num_dependents = random.randint(0, 4)

    if profile.filing_status == "hoh" and num_dependents == 0:
        num_dependents = 1

    # --- OBBBA flags (2025+ only, Guide-calibrated probabilities) ---
    is_obbba = is_obbba_year(tax_year)
    if is_obbba:
        profile.is_tipped_worker = random.random() < 0.12   # Guide: 12%
        profile.overtime_eligible = random.random() < 0.35   # Guide: 35%
        profile.has_car_loan = random.random() < 0.18        # Guide: 18%
        # Senior: age-based, not flat probability
        # Will be set after age generation below

    # --- Primary taxpayer ---
    if is_obbba and profile.is_tipped_worker:
        profile.primary_occupation = random.choice(TIPPED_OCCUPATIONS)
    else:
        profile.primary_occupation = random.choice(OCCUPATIONS)

    profile.primary_first = fake.first_name()
    profile.primary_last = fake.last_name()
    profile.primary_ssn = _generate_ssn()

    # DOB: Use triangular distribution per filing status (Guide §13)
    primary_age = _generate_age_for_status(profile.filing_status, tax_year)

    # For OBBBA years, senior status is age-based (65+), not flat probability
    if is_obbba and primary_age >= 65:
        profile.is_senior_65_plus = True
    elif is_obbba:
        # Small chance of being placed as senior even if age distribution
        # didn't naturally produce 65+ (ensures minimum senior representation)
        if random.random() < 0.08:
            primary_age = random.randint(65, 82)
            profile.is_senior_65_plus = True
        else:
            profile.is_senior_65_plus = False

    birth_year = tax_year - primary_age
    profile.primary_dob = f"{birth_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

    # --- Spouse (if MFJ) ---
    if profile.filing_status == "mfj":
        profile.spouse_first = fake.first_name()
        profile.spouse_last = profile.primary_last
        profile.spouse_ssn = _generate_ssn()
        if profile.is_senior_65_plus and random.random() < 0.6:
            spouse_birth_year = tax_year - random.randint(65, 80)
        else:
            spouse_age = _generate_age_for_status('mfj', tax_year)
            spouse_birth_year = tax_year - spouse_age
        profile.spouse_dob = f"{spouse_birth_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}"
        profile.spouse_occupation = random.choice(OCCUPATIONS)

    # --- Address ---
    city, zip_code = random.choice(STATE_CITIES[state])
    street_num = random.randint(100, 9999)
    street_name = fake.street_name()
    profile.address = f"{street_num} {street_name}".upper()
    profile.city = city.upper()
    profile.zip_code = zip_code

    # --- Dependents ---
    for i in range(num_dependents):
        dep_age = random.randint(1, 16)
        dep_birth_year = tax_year - dep_age
        dep = Dependent(
            first_name=fake.first_name(),
            last_name=profile.primary_last,
            ssn=_generate_ssn(),
            dob=f"{dep_birth_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            relationship=random.choice(RELATIONSHIPS),
            age=dep_age,
        )
        profile.dependents.append(dep)

    # --- Car loan (OBBBA) ---
    if profile.has_car_loan and is_obbba:
        from tax_engine.vin_generator import generate_vin
        model_year = random.choice([2024, 2025])
        profile.car_loan = CarLoanProfile(
            vin=generate_vin(model_year),
            annual_interest=round(random.uniform(1500, 9500), 2),
            purchase_date=f"{tax_year}-{random.randint(1,12):02d}-{random.randint(1,28):02d}",
            is_first_lien=True,
            is_new_vehicle=True,
        )

    # --- Income generation ---
    
    # QUANT MODELS
    agi = sample_agi(profile.filing_status, rng)
    income_dict = generate_income_split(agi, rng)
    profile.federal_results["wages"] = income_dict["wages"]
    profile.federal_results["schedule_c_net"] = income_dict.get("schedule_c", 0)
    profile.federal_results["interest"] = income_dict.get("interest", 0)
    profile.federal_results["dividends"] = income_dict.get("dividends", 0)
    profile.federal_results["agi"] = agi
    profile.federal_results["gross_revenue"] = income_dict.get("gross_revenue", 0)

    _generate_income(profile, state, tax_year, level, income_dict, rng)

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
    profile.email = fake.email()

    return profile


def _generate_income(profile: TaxProfile, state: str, tax_year: int, level: int, income_dict: dict, rng: np.random.Generator):
    """Generate income sources appropriate for the complexity level."""
    ss_base = SS_WAGE_BASE[tax_year]

    # --- W-2 income ---
    if level == 1:
        num_w2 = 1
        wage_range = (25000, 85000)
    elif level == 2:
        num_w2 = random.choice([1, 1, 2])
        wage_range = (30000, 120000)
    else:
        num_w2 = random.choice([1, 2])
        wage_range = (40000, 200000)

    w2_recipients = []
    if profile.filing_status == "mfj" and num_w2 >= 2:
        w2_recipients = ["primary", "spouse"]
    elif profile.filing_status == "mfj" and num_w2 == 1:
        w2_recipients = [random.choice(["primary", "spouse"])]
    else:
        w2_recipients = ["primary"]

    for recipient in w2_recipients:
        
        if income_dict["wages"] > 0:
            wages = income_dict["wages"]
        else:
            wages = 0
            continue # skip if no wages 

        employer_info = random.choice(EMPLOYERS[state])
        emp_city, emp_zip = random.choice(STATE_CITIES[state])

        # Tips (OBBBA — Box 7)
        tip_income = 0.0
        if profile.is_tipped_worker and recipient == "primary":
            tip_income = round(random.uniform(5000, 25000), 2)
            wages += tip_income  # tips are included in Box 1

        # Overtime pay (OBBBA)
        overtime_pay = 0.0
        if profile.overtime_eligible and recipient == "primary":
            overtime_pay = round(random.uniform(3000, 20000), 2)
            wages += overtime_pay  # overtime included in Box 1

        # Compute withholdings
        fed_rate = 0.10
        for threshold, rate in FEDERAL_WITHHOLDING_APPROX:
            if wages <= threshold:
                fed_rate = rate
                break
        federal_withheld = round(wages * fed_rate)

        ss_wages = min(wages, ss_base)
        ss_tax = round(ss_wages * SS_RATE_EMPLOYEE, 2)
        medicare_tax = round(wages * 0.0145, 2)

        state_rate = STATE_WITHHOLDING_APPROX.get(state, 0)
        state_withheld = round(wages * state_rate)

        # CA SDI
        sdi = 0.0
        if state == "CA":
            from tax_engine.tax_tables import CA_SDI_RATE, CA_SDI_WAGE_LIMIT
            sdi_limit = CA_SDI_WAGE_LIMIT.get(tax_year)
            sdi_wages = wages if sdi_limit is None else min(wages, sdi_limit)
            sdi = round(sdi_wages * CA_SDI_RATE, 2)

        if recipient == "primary":
            emp_name = f"{profile.primary_first} {profile.primary_last}"
            emp_ssn = profile.primary_ssn
        else:
            emp_name = f"{profile.spouse_first} {profile.spouse_last}"
            emp_ssn = profile.spouse_ssn

        w2 = W2Income(
            employer_name=employer_info[0],
            employer_ein=_generate_ein(),
            employer_address=f"{random.randint(100,9999)} {fake.street_name()}",
            employer_city=emp_city,
            employer_state=state,
            employer_zip=emp_zip,
            employee_name=emp_name,
            employee_ssn=emp_ssn,
            wages=wages,
            federal_withheld=federal_withheld,
            ss_wages=ss_wages,
            ss_tax=ss_tax,
            medicare_wages=wages,
            medicare_tax=medicare_tax,
            box_7_tips=tip_income,
            state_wages=wages,
            state_withheld=state_withheld,
            box_14_sdi=sdi,
            overtime_pay=overtime_pay,
        )
        profile.w2_incomes.append(w2)

    # --- Interest income (Level 2+ or 30% chance for Level 1) ---
    if level >= 2 or (level == 1 and random.random() < 0.3):
        bank = random.choice(BANKS)
        interest_amt = round(random.uniform(50, 800), 2)
        profile.interest_incomes.append(InterestIncome(
            payer_name=bank,
            payer_ein=_generate_ein(),
            amount=interest_amt,
        ))

    # --- Dividend income (Level 2+) ---
    if level >= 2:
        brokerage_name, brokerage_ein = random.choice(BROKERAGES)
        ordinary_div = round(random.uniform(100, 2000), 2)
        qualified_div = round(ordinary_div * random.uniform(0.5, 0.9), 2)
        profile.dividend_incomes.append(DividendIncome(
            payer_name=brokerage_name,
            payer_ein=brokerage_ein,
            ordinary_dividends=ordinary_div,
            qualified_dividends=qualified_div,
        ))

    # --- Self-employment / Schedule C (Level 2+) ---
    if level >= 2:
        
        biz_name, biz_code, biz_desc = random.choice(BUSINESS_TYPES)
        gross = income_dict.get("gross_revenue", 0)
        if gross == 0:
            gross = round(random.uniform(20000, 80000) / 100) * 100

        expense_data = generate_schedule_c_expenses(gross, biz_code, rng)
        total_expenses = expense_data["total_expenses"]

        expenses = BusinessExpenses(
            advertising=expense_data["advertising"],
            car_and_truck=expense_data["depreciation"],
            office_expense=expense_data["office_expenses"],
            rent_lease=expense_data["rent_lease"],
            supplies=expense_data["supplies"],
            taxes_licenses=expense_data["taxes_licenses"],
            other=expense_data["other_expenses"],
        )

        depreciation = expense_data["depreciation"]
        net = expense_data["net_profit"]


        if random.random() < 0.3:
            biz_name = f"{profile.primary_last}'s {biz_name}"

        biz_income = BusinessIncome(
            business_name=biz_name,
            activity_code=biz_code,
            activity_desc=biz_desc,
            gross_receipts=gross,
            expenses=expenses,
            net_profit=net,
            depreciation=depreciation,
        )

        if random.random() < 0.40:
            monthly = random.choice([800, 900, 1000, 1200, 1500, 1800, 2000, 2500])
            annual_rent = monthly * random.randint(6, 12)
            biz_income.rent_expense = float(annual_rent)
            biz_income.net_profit -= biz_income.rent_expense
            
        if level == 3 and random.random() < 0.30:
            total_meals = round(random.uniform(1000, 4000), 0)
            biz_income.deductible_meals = round(total_meals * 0.50)
            biz_income.expenses.other += round(random.uniform(500, 3000), 0) # travel in other
            biz_income.net_profit -= biz_income.deductible_meals

        if level == 3 and random.random() < 0.10:
            biz_income.wages_paid = round(random.uniform(15000, 50000), 0)
            biz_income.net_profit -= biz_income.wages_paid

        n = random.randint(2, 4)
        cat_options = ["Software subscriptions", "Professional memberships & dues", "Bank charges", "Postage & shipping", "Cloud storage & hosting", "Professional development", "Client entertainment", "Business insurance riders"]
        cats = random.sample(cat_options, n)
        rem = expenses.other
        items = []
        for i, cat in enumerate(cats):
            if i < n - 1:
                amt = round(rem * random.uniform(0.20, 0.60))
                rem -= amt
            else:
                amt = round(rem)
            if amt > 0:
                items.append((cat, amt))
        biz_income.other_expense_items = items

        if biz_income.depreciation > 0:
            cost = round(biz_income.depreciation / 0.20)
            asset = DepreciableAsset(
                description="Computer Equipment",
                placed_in_service=f"01/15/{tax_year}",
                cost=cost,
                recovery_period=5,
                convention="HY",
                method="200DB",
                depreciation_this_year=biz_income.depreciation,
            )
            biz_income.depreciable_assets.append(asset)

        if biz_income.expenses.car_and_truck > 0:
            total_business_miles = round(biz_income.expenses.car_and_truck / 0.67)
            total_miles = round(total_business_miles / random.uniform(0.60, 0.85))
            personal_miles = total_miles - total_business_miles
            vehicle_year = tax_year - random.randint(1, 4)
            vehicle_makes = ["Honda Civic", "Toyota Camry", "Ford F-150", "Chevrolet Malibu", "Nissan Altima"]
            biz_income.vehicle = {
                "description": f"{vehicle_year} {random.choice(vehicle_makes)}",
                "placed_in_service": f"01/01/{tax_year - random.randint(1,3)}",
                "total_miles": total_miles,
                "business_miles": total_business_miles,
                "commuting_miles": 0,
                "other_miles": personal_miles,
                "available_personal": True,
                "another_vehicle": True,
                "written_evidence": True,
            }

        profile.business_income = biz_income
        
        if random.random() < 0.35:
            profile.has_home_office = True
            profile.home_office_sqft = random.randint(80, 300)
            rate = 6 if tax_year >= 2025 else 5
            profile.home_office_deduction = round(min(profile.home_office_sqft, 300) * rate, 2)

    # --- Additional Level 3 income ---
    if level == 3 and random.random() < 0.5:
        second_brokerage = random.choice(BROKERAGES)
        profile.dividend_incomes.append(DividendIncome(
            payer_name=second_brokerage[0],
            payer_ein=second_brokerage[1],
            ordinary_dividends=round(random.uniform(200, 3000), 2),
            qualified_dividends=round(random.uniform(100, 1500), 2),
        ))

    if level == 3:
        profile.interest_incomes.append(InterestIncome(
            payer_name=random.choice(BANKS),
            payer_ein=_generate_ein(),
            amount=round(random.uniform(100, 2000), 2),
        ))

    # --- Mortgage Interest (Level 2+) ---
    if level >= 2 and random.random() < 0.4:
        # Occasionally generate principal > $750k to trigger V-04 limit
        if random.random() < 0.2:
            principal = round(random.uniform(800000, 1500000) / 1000) * 1000
        else:
            principal = round(random.uniform(150000, 600000) / 1000) * 1000
            
        rate = random.uniform(0.03, 0.07)
        interest_paid = round(principal * rate, 2)
        bank = random.choice(BANKS)
        profile.mortgage_interests.append(MortgageInterest(
            lender_name=bank,
            lender_ein=_generate_ein(),
            principal=principal,
            interest_paid=interest_paid,
        ))

    # --- Capital Gains (Level 2+) ---
    if level >= 2 and random.random() < 0.3:
        brokerage = random.choice(BROKERAGES)
        short_term = round(random.uniform(0, 5000), 2) if random.random() < 0.5 else 0.0
        long_term = round(random.uniform(500, 20000), 2)
        profile.capital_gains.append(CapitalGainsIncome(
            payer_name=brokerage[0],
            payer_ein=brokerage[1],
            short_term_gains=short_term,
            long_term_gains=long_term,
        ))
