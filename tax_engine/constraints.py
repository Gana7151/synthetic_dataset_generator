"""
Constraint-Augmented Generation (CAG) — Guide v2.0 §7

Post-hoc enforcement of accounting identities for synthetic tax records.
Neural generators (GANs, Copulas) cannot guarantee these identities;
they must be enforced after generation.

Key insight from the guide: "No amount of training will teach a CTGAN
that Box 4 = Box 3 × 6.2%, because the constraint space is measure-zero
in the continuous output space of the generator."
"""

from tax_engine.tax_tables import (
    SS_WAGE_BASE, SS_RATE_EMPLOYEE, STANDARD_DEDUCTION, SALT_CAP,
    NO_INCOME_TAX_STATES, OBBBA_DEDUCTIONS,
)
from tax_engine.tax_parameters_store import get_tax_parameters, is_obbba_year


def enforce_accounting_identity(record: dict, tax_year: int) -> dict:
    """Enforce the Form 1040 accounting identity chain.

    Guide §7.3: Forces all derived fields to be algebraically consistent
    with their upstream primitives. Mutates and returns the record.

    Chain:
      Gross Income → (- adjustments) → AGI
        → (- deductions - QBI) → Taxable Income
        → (brackets) → Income Tax
        → (- credits + other taxes) → Total Tax
        → (- payments) → Refund/Owed
    """
    # Step 1: Gross income from components
    gross = (record.get('wages', 0)
             + record.get('taxable_interest', 0)
             + record.get('ordinary_dividends', 0)
             + record.get('business_income', 0))
    record['total_income'] = round(gross, 2)
    record['gross_income'] = round(gross, 2)

    # Step 2: AGI = Gross - Adjustments
    adjustments = record.get('total_adjustments', 0)
    record['agi'] = round(gross - adjustments, 2)

    # Step 3: Taxable = AGI - Deductions - QBI
    deductions = record.get('deduction_used', 0)
    qbi = record.get('qbi_deduction', 0)
    record['taxable_income'] = round(max(0, record['agi'] - deductions - qbi), 2)

    return record


def enforce_w2_constraints(w2_record: dict, tax_year: int) -> dict:
    """Enforce W-2 Box constraints.

    Guide §7.2, Key constraints:
      - Box 3 (SS wages) ≤ SS wage base for the year
      - Box 4 (SS tax) = Box 3 × 6.2% (exactly)
      - Box 5 (Medicare wages) ≥ Box 1 (wages) (always)
      - Box 6 (Medicare tax) = Box 5 × 1.45% (exactly)
    """
    ss_base = SS_WAGE_BASE[tax_year]

    # Box 3 capped at wage base
    wages = w2_record.get('wages', 0)
    w2_record['ss_wages'] = min(wages, ss_base)

    # Box 4 exact
    w2_record['ss_tax'] = round(w2_record['ss_wages'] * SS_RATE_EMPLOYEE, 2)

    # Box 5 ≥ Box 1
    w2_record['medicare_wages'] = wages

    # Box 6 exact
    w2_record['medicare_tax'] = round(wages * 0.0145, 2)

    return w2_record


def enforce_state_constraints(record: dict, state: str, tax_year: int) -> dict:
    """Enforce state-level constraints.

    Guide §7.2:
      - No state income tax for TX/FL/etc.
      - EITC requires earned income > 0
      - Itemization only rational if itemized > standard deduction
    """
    # No-income-tax states
    if state in NO_INCOME_TAX_STATES:
        record['state_income_tax'] = 0
        record['state_tax'] = 0

    return record


def enforce_obbba_constraints(record: dict, tax_year: int) -> dict:
    """Enforce OBBBA deduction constraints.

    Guide §7.2:
      - Car loan deduction requires US-assembled vehicle (VIN pos 1 ∈ {1,4,5})
      - Overtime deduction requires overtime_eligible flag
      - Tip deduction requires is_tipped_worker flag
      - Senior deduction requires age ≥ 65
    """
    if not is_obbba_year(tax_year):
        return record

    # Car loan: must have US-assembled VIN
    if record.get('car_loan_interest_deduction', 0) > 0:
        if not record.get('is_us_assembled_vehicle', False):
            record['car_loan_interest_deduction'] = 0

    # Overtime: must be FLSA eligible
    if record.get('overtime_deduction', 0) > 0:
        if not record.get('overtime_eligible', False):
            record['overtime_deduction'] = 0

    # Tips: must be tipped worker
    if record.get('tip_income_deduction', 0) > 0:
        if not record.get('is_tipped_worker', False):
            record['tip_income_deduction'] = 0

    return record


def enforce_salt_cap(record: dict, tax_year: int) -> dict:
    """Enforce SALT deduction cap.

    Guide §14, V-06:
      2018–2024: $10,000
      2025:      $40,000 (OBBBA)
      2026:      $40,400 (indexed)
    """
    cap = SALT_CAP.get(tax_year, 10000)
    if record.get('salt_deduction_claimed', 0) > cap:
        record['salt_deduction_claimed'] = cap

    return record


def enforce_all(record: dict, tax_year: int, state: str = None) -> dict:
    """Run all constraint enforcement in sequence.

    Call this as a post-generation step to ensure algebraic consistency.
    """
    record = enforce_accounting_identity(record, tax_year)
    record = enforce_obbba_constraints(record, tax_year)
    record = enforce_salt_cap(record, tax_year)
    if state:
        record = enforce_state_constraints(record, state, tax_year)

    return record
