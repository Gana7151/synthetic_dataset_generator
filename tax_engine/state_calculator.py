"""
State tax computation — v5.0 Guide v2.0 Compliant.

Key features:
  - CA, NY, IL do NOT conform to OBBBA Schedule 1-A deductions.
    State AGI = Federal AGI + Schedule 1-A total (add-back).
  - CA CalEITC uses California-specific tables (Guide §10.2)
  - IL EITC uses year-specific rates (18%→40%).
  - IL Child Tax Credit: 40% of base IL EITC for children under 12.
  - NY: SALT flip detection for 2025 ($40K cap may trigger itemization).
  - NY: IT-2105 estimated tax voucher requirement check.
  - Uses versioned tax_parameters_store.
"""

from tax_engine.tax_tables import (
    CA_BRACKETS, CA_STANDARD_DEDUCTION, CA_PERSONAL_EXEMPTION,
    CA_DEPENDENT_EXEMPTION, CA_SDI_RATE, CA_SDI_WAGE_LIMIT,
    NY_BRACKETS, NY_STANDARD_DEDUCTION,
    IL_FLAT_RATE, IL_PERSONAL_EXEMPTION, IL_EITC_RATE, IL_CTC_RATE,
    NO_INCOME_TAX_STATES, SALT_CAP,
    compute_tax_from_brackets,
)
from tax_engine.tax_parameters_store import get_tax_parameters


def compute_state_tax(profile) -> dict:
    """Compute state tax liability with v4 OBBBA non-conformity."""
    state = profile.state

    if state in NO_INCOME_TAX_STATES:
        results = {
            "state": state,
            "has_income_tax": False,
            "state_tax": 0.0,
            "taxable_income": 0.0,
            "total_tax": 0.0,
            "payments": 0.0,
            "refund": 0.0,
            "amount_owed": 0.0,
        }
        profile.state_results = results
        return results

    if state == "CA":
        return _compute_ca_tax(profile)
    elif state == "NY":
        return _compute_ny_tax(profile)
    elif state == "IL":
        return _compute_il_tax(profile)
    else:
        raise ValueError(f"Unsupported state: {state}")


def _get_obbba_addback(profile) -> float:
    """Get the OBBBA Schedule 1-A total that must be added back for
    non-conforming states (CA, NY, IL)."""
    fed = profile.federal_results
    return fed.get("schedule_1a_total", 0)


# ===========================================================================
# CALIFORNIA (Form 540) — OBBBA Non-Conforming
# ===========================================================================

def _compute_ca_tax(profile) -> dict:
    """California state income tax.

    CA does NOT conform to OBBBA Schedule 1-A deductions.
    CA AGI = Federal AGI + OBBBA add-back.
    SDI: No wage cap for 2025.
    """
    status = profile.filing_status
    fed = profile.federal_results
    year = profile.tax_year

    results = {"state": "CA", "has_income_tax": True}

    # OBBBA non-conformity: add back Schedule 1-A deductions
    obbba_addback = _get_obbba_addback(profile)
    ca_agi = fed["agi"] + obbba_addback
    results["ca_agi"] = round(ca_agi, 2)
    results["obbba_addback"] = round(obbba_addback, 2)

    # Standard deduction (CA uses its own, not federal)
    std_ded = CA_STANDARD_DEDUCTION.get(status, CA_STANDARD_DEDUCTION["single"])
    results["standard_deduction"] = std_ded

    # Personal and dependent exemptions
    num_personal = 2 if status == "mfj" else 1
    personal_exemption = CA_PERSONAL_EXEMPTION.get(
        status, CA_PERSONAL_EXEMPTION["single"]) * num_personal
    dependent_exemption = CA_DEPENDENT_EXEMPTION * len(profile.dependents)
    total_exemptions = personal_exemption + dependent_exemption
    results["exemptions"] = round(total_exemptions, 2)

    # Taxable income
    taxable = max(0, ca_agi - std_ded - total_exemptions)
    results["taxable_income"] = round(taxable, 2)

    # Tax from brackets
    brackets = CA_BRACKETS.get(status, CA_BRACKETS["single"])
    ca_tax = compute_tax_from_brackets(taxable, brackets)

    # Mental Health Surcharge (1% on income over $1M)
    if taxable > 1000000:
        ca_tax += (taxable - 1000000) * 0.01

    results["state_tax"] = round(ca_tax, 2)

    # SDI (State Disability Insurance)
    total_wages = sum(w.wages for w in profile.w2_incomes)
    sdi_limit = CA_SDI_WAGE_LIMIT.get(year)
    if sdi_limit is None:
        sdi_wages = total_wages  # No cap for 2025
    else:
        sdi_wages = min(total_wages, sdi_limit)
    sdi = round(sdi_wages * CA_SDI_RATE, 2)
    results["sdi"] = sdi

    # Credits (CalEITC — Guide §10.2)
    credits = 0.0

    # CalEITC: uses California-specific tables, NOT federal EITC tables
    # Source: CA FTB Publication 3514
    earned_income = sum(w.wages for w in profile.w2_incomes)
    if profile.business_income:
        earned_income += max(0, profile.business_income.net_profit)
    num_children = len(profile.dependents)

    caleitc = _calculate_caleitc(earned_income, status, num_children)
    if caleitc > 0:
        results["caleitc"] = round(caleitc, 2)
        credits += caleitc

    # Young Child Tax Credit (YCTC) — children under 6
    qualifying_under_6 = sum(1 for d in profile.dependents if d.age < 6)
    if qualifying_under_6 > 0 and caleitc > 0 and ca_agi < 30000:
        yctc = qualifying_under_6 * 1117  # 2025 YCTC amount
        results["yctc"] = round(yctc, 2)
        credits += yctc

    # Renter's credit
    if ca_agi < 50000 and status == "single":
        credits += 60
    elif ca_agi < 100000 and status in ("mfj", "hoh"):
        credits += 120
    results["credits"] = round(credits, 2)

    # Total tax after credits
    total_tax = max(0, ca_tax - credits)
    results["total_tax"] = round(total_tax, 2)

    # Payments (state withholding from W-2)
    state_withheld = sum(w.state_withheld for w in profile.w2_incomes)
    results["payments"] = round(state_withheld, 2)

    # Refund or balance due
    if state_withheld >= total_tax:
        results["refund"] = round(state_withheld - total_tax, 2)
        results["amount_owed"] = 0.0
    else:
        results["refund"] = 0.0
        results["amount_owed"] = round(total_tax - state_withheld, 2)

    profile.state_results = results
    return results


def _calculate_caleitc(earned_income: float, filing_status: str,
                       num_children: int) -> float:
    """CalEITC calculation using California-specific tables.

    Guide §10.2: CalEITC uses CA FTB Publication 3514 tables.
    Maximum credit phases in around $30,931 of earned income for 2025.
    These amounts differ from federal EITC and must NOT be conflated.
    """
    max_credits = {0: 285, 1: 1900, 2: 3137, 3: 3529}
    max_credit = max_credits.get(min(num_children, 3), 3529)

    if num_children == 0:
        phase_out_start = 15000
        phase_out_end = 30931
    elif num_children == 1:
        phase_out_start = 25000
        phase_out_end = 40931
    else:
        phase_out_start = 30000
        phase_out_end = 50000

    if earned_income <= 0:
        return 0.0
    elif earned_income <= phase_out_start:
        return max_credit * (earned_income / phase_out_start)
    elif earned_income <= phase_out_end:
        return max_credit
    else:
        excess = earned_income - phase_out_end
        reduction = max_credit * (excess / (phase_out_end - phase_out_start))
        return max(0.0, max_credit - reduction)


# ===========================================================================
# NEW YORK (IT-201) — OBBBA Non-Conforming
# ===========================================================================

def _compute_ny_tax(profile) -> dict:
    """New York state income tax.

    NY does NOT conform to OBBBA Schedule 1-A deductions.
    NY AGI = Federal AGI + OBBBA add-back.
    SALT flip: 2025 $40K SALT cap may trigger itemization.
    """
    status = profile.filing_status
    fed = profile.federal_results
    year = profile.tax_year

    results = {"state": "NY", "has_income_tax": True}

    # OBBBA non-conformity
    obbba_addback = _get_obbba_addback(profile)
    ny_agi = fed["agi"] + obbba_addback
    results["ny_agi"] = round(ny_agi, 2)
    results["obbba_addback"] = round(obbba_addback, 2)

    # Standard deduction
    std_ded = NY_STANDARD_DEDUCTION.get(status, NY_STANDARD_DEDUCTION["single"])
    results["standard_deduction"] = std_ded

    # SALT flip detection (Guide §10.3)
    # When 2025 $40K SALT cap triggers itemization at federal level,
    # NY requires state itemization too.
    salt_cap = SALT_CAP.get(year, 10000)
    total_salt_paid = sum(w.state_withheld for w in profile.w2_incomes)
    results["salt_flip_triggered"] = (year >= 2025 and total_salt_paid > salt_cap)

    # Taxable income
    taxable = max(0, ny_agi - std_ded)
    results["taxable_income"] = round(taxable, 2)

    # Tax from brackets
    brackets = NY_BRACKETS.get(status, NY_BRACKETS["single"])
    ny_tax = compute_tax_from_brackets(taxable, brackets)
    results["state_tax"] = round(ny_tax, 2)

    # Credits (simplified)
    credits = 0.0
    results["credits"] = round(credits, 2)

    # Total tax
    total_tax = max(0, ny_tax - credits)
    results["total_tax"] = round(total_tax, 2)

    # Payments
    state_withheld = sum(w.state_withheld for w in profile.w2_incomes)
    results["payments"] = round(state_withheld, 2)

    # IT-2105 estimated tax voucher check (Guide §10.3)
    # Required if projected tax liability − withholding > $300
    requires_it2105 = (total_tax - state_withheld) > 300
    results["requires_it2105"] = requires_it2105

    # Refund or balance due
    if state_withheld >= total_tax:
        results["refund"] = round(state_withheld - total_tax, 2)
        results["amount_owed"] = 0.0
    else:
        results["refund"] = 0.0
        results["amount_owed"] = round(total_tax - state_withheld, 2)

    profile.state_results = results
    return results


# ===========================================================================
# ILLINOIS (IL-1040) — OBBBA Non-Conforming
# ===========================================================================

def _compute_il_tax(profile) -> dict:
    """Illinois state income tax — flat rate.

    IL does NOT conform to OBBBA Schedule 1-A deductions.
    IL EITC: year-specific rates (E-15 fix).
    IL Child Tax Credit: 40% of base IL EITC for children under 12.
    """
    status = profile.filing_status
    fed = profile.federal_results
    year = profile.tax_year

    results = {"state": "IL", "has_income_tax": True}

    # OBBBA non-conformity
    obbba_addback = _get_obbba_addback(profile)
    il_agi = fed["agi"] + obbba_addback
    results["il_agi"] = round(il_agi, 2)
    results["obbba_addback"] = round(obbba_addback, 2)

    # Personal exemptions
    num_exemptions = 1
    if status == "mfj":
        num_exemptions = 2
    num_exemptions += len(profile.dependents)
    total_exemption = IL_PERSONAL_EXEMPTION * num_exemptions
    results["exemptions"] = round(total_exemption, 2)

    # Taxable income
    taxable = max(0, il_agi - total_exemption)
    results["taxable_income"] = round(taxable, 2)

    # Flat rate tax
    il_tax = round(taxable * IL_FLAT_RATE, 2)
    results["state_tax"] = il_tax

    # IL EITC — year-specific rates (E-15 fix)
    il_eitc_rate = IL_EITC_RATE.get(year, 0.20)
    # Simplified: estimate federal EITC eligibility for lower incomes
    il_eitc = 0.0
    federal_agi = fed["agi"]
    earned_income = sum(w.wages for w in profile.w2_incomes)
    if profile.business_income:
        earned_income += max(0, profile.business_income.net_profit)

    # Basic EITC eligibility check (simplified — would need full EITC tables in production)
    num_children = len(profile.dependents)
    eitc_limit = {0: 17640, 1: 46560, 2: 52918, 3: 56838}.get(
        min(num_children, 3), 56838)
    if status == "mfj":
        eitc_limit += 7430

    if earned_income > 0 and federal_agi < eitc_limit:
        # Simplified federal EITC estimate
        eitc_rate = {0: 0.0765, 1: 0.34, 2: 0.40, 3: 0.45}.get(
            min(num_children, 3), 0.45)
        max_eitc = {0: 632, 1: 4213, 2: 6960, 3: 7830}.get(
            min(num_children, 3), 7830)
        federal_eitc = min(earned_income * eitc_rate, max_eitc)

        il_eitc = round(federal_eitc * il_eitc_rate, 2)
        results["federal_eitc_estimate"] = round(federal_eitc, 2)

        # IL Child Tax Credit: 40% of base IL EITC for children under 12
        qualifying_under_12 = sum(1 for d in profile.dependents if d.age < 12)
        if qualifying_under_12 > 0:
            il_ctc = round(il_eitc * IL_CTC_RATE, 2)
            results["il_child_tax_credit"] = il_ctc
            il_eitc += il_ctc

    results["il_eitc"] = round(il_eitc, 2)
    results["il_eitc_rate"] = il_eitc_rate

    # Credits (including EITC)
    credits = il_eitc
    results["credits"] = round(credits, 2)

    # Total tax
    total_tax = max(0, il_tax - credits)
    results["total_tax"] = round(total_tax, 2)

    # Payments
    state_withheld = sum(w.state_withheld for w in profile.w2_incomes)
    results["payments"] = round(state_withheld, 2)

    # Refund or balance due
    if state_withheld >= total_tax:
        results["refund"] = round(state_withheld - total_tax, 2)
        results["amount_owed"] = 0.0
    else:
        results["refund"] = 0.0
        results["amount_owed"] = round(total_tax - state_withheld, 2)

    profile.state_results = results
    return results
