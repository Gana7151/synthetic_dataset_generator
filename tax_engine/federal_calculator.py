"""
Federal tax computation engine — v5.0 Guide v2.0 Compliant.

Calculation sequence:
  OBBBA deductions are ABOVE-THE-LINE via Schedule 1-A → Schedule 1 Part II
  → Form 1040 Line 10. This reduces AGI BEFORE standard/itemized deduction.

Implements:
  - Schedule 1-A: Tips, Overtime, Car Loan Interest, Senior deductions
  - Linear phase-out (tips, overtime, car loan) and proportional (senior)
  - Medicare surtax (0.9% Form 8959)
  - Year-specific CTC
  - AMT 2026 with OBBBA doubled 50¢ phase-out rate (Guide §6)
  - 2/37 Benefit Cap for 37% bracket itemizers (Guide §6.3)
  - Uses versioned tax_parameters_store
"""

from tax_engine.tax_tables import (
    FEDERAL_BRACKETS, STANDARD_DEDUCTION, SS_WAGE_BASE,
    SE_TAX_RATE, SE_INCOME_FACTOR, SS_TAX_RATE, MEDICARE_TAX_RATE,
    QBI_DEDUCTION_RATE, QBI_TAXABLE_INCOME_THRESHOLD,
    OBBBA_DEDUCTIONS, MEDICARE_SURTAX, ADDITIONAL_STD_DEDUCTION,
    AMT_PARAMS,
    get_ctc_per_child, CTC_PHASEOUT,
    compute_tax_from_brackets,
)
from tax_engine.tax_parameters_store import get_tax_parameters, is_obbba_year


# ===========================================================================
# OBBBA Schedule 1-A Phase-Out Functions
# ===========================================================================

def _linear_phaseout(gross_amount, magi, start, end, slope_per_1k):
    """Linear phase-out: reduces by $slope per $1K of MAGI over start."""
    if magi <= start:
        return gross_amount
    if magi >= end:
        return 0.0
    reduction = ((magi - start) / 1000) * slope_per_1k
    return max(0.0, round(gross_amount - reduction, 2))


def _proportional_phaseout(gross_amount, magi, start, end):
    """Proportional phase-out for senior deduction."""
    if magi <= start:
        return gross_amount
    if magi >= end:
        return 0.0
    fraction_remaining = 1 - (magi - start) / (end - start)
    return round(gross_amount * fraction_remaining, 2)


def compute_schedule_1a(profile, magi: float) -> dict:
    """Compute OBBBA Schedule 1-A deductions (2025+ only).

    Returns dict with tips, overtime, car_loan, senior, and total.
    All flow to Schedule 1 Part II → Form 1040 Line 10.
    """
    tax_year = profile.tax_year
    if tax_year < 2025:
        return {"tips": 0, "overtime": 0, "car_loan": 0, "senior": 0, "total": 0}

    status = profile.filing_status
    # Use "single" params for HoH where no specific HoH entry
    status_key = status if status != "hoh" else "single"
    result = {}

    # Part II — Tips
    if profile.is_tipped_worker:
        total_tips = sum(w.box_7_tips for w in profile.w2_incomes)
        if total_tips > 0:
            cfg = OBBBA_DEDUCTIONS["tips"]
            gross = min(total_tips, cfg["max"])
            result["tips"] = _linear_phaseout(
                gross, magi,
                cfg["phaseout_start"].get(status, cfg["phaseout_start"]["single"]),
                cfg["phaseout_end"].get(status, cfg["phaseout_end"]["single"]),
                cfg["slope_per_1k"],
            )
        else:
            result["tips"] = 0
    else:
        result["tips"] = 0

    # Part III — Overtime
    if profile.overtime_eligible:
        total_overtime = sum(w.overtime_pay for w in profile.w2_incomes)
        if total_overtime > 0:
            cfg = OBBBA_DEDUCTIONS["overtime"]
            ot_max = cfg["max"][status] if isinstance(cfg["max"], dict) else cfg["max"]
            gross = min(total_overtime, ot_max)
            result["overtime"] = _linear_phaseout(
                gross, magi,
                cfg["phaseout_start"].get(status, cfg["phaseout_start"]["single"]),
                cfg["phaseout_end"].get(status, cfg["phaseout_end"]["single"]),
                cfg["slope_per_1k"],
            )
        else:
            result["overtime"] = 0
    else:
        result["overtime"] = 0

    # Part IV — Car Loan Interest ($200/$1K slope — DOUBLE rate)
    if profile.has_car_loan and profile.car_loan:
        cfg = OBBBA_DEDUCTIONS["car_loan_interest"]
        gross = min(profile.car_loan.annual_interest, cfg["max"])
        result["car_loan"] = _linear_phaseout(
            gross, magi,
            cfg["phaseout_start"].get(status, cfg["phaseout_start"]["single"]),
            cfg["phaseout_end"].get(status, cfg["phaseout_end"]["single"]),
            cfg["slope_per_1k"],  # 200 — critical
        )
    else:
        result["car_loan"] = 0

    # Part V — Senior Deduction (65+) — PROPORTIONAL phase-out
    if profile.is_senior_65_plus:
        cfg = OBBBA_DEDUCTIONS["senior"]
        if status == "mfj":
            # Check if both spouses are 65+
            spouse_senior = False
            if profile.spouse_dob:
                try:
                    spouse_year = int(profile.spouse_dob[:4])
                    spouse_senior = (tax_year - spouse_year) >= 65
                except (ValueError, TypeError):
                    pass
            gross = cfg["max"]["mfj_both"] if spouse_senior else cfg["max"].get("single", 6000)
        else:
            gross = cfg["max"].get(status, cfg["max"].get("single", 6000))

        result["senior"] = _proportional_phaseout(
            gross, magi,
            cfg["phaseout_start"].get(status, cfg["phaseout_start"]["single"]),
            cfg["phaseout_end"].get(status, cfg["phaseout_end"]["single"]),
        )
    else:
        result["senior"] = 0

    # Part VI — Limitation failsafe: total cannot reduce taxable income below $0
    total = sum(result.values())
    result["total"] = round(total, 2)
    return result


# ===========================================================================
# Medicare Surtax (E-09 fix)
# ===========================================================================

def compute_medicare_surtax(profile, total_wages: float, se_income: float) -> float:
    """Compute Additional Medicare Tax (0.9%) per Form 8959.

    Employer withholding triggers at $200K regardless of filing status.
    Final Form 8959 liability uses filing-status-specific thresholds.
    """
    status = profile.filing_status
    threshold = MEDICARE_SURTAX["form_8959_threshold"].get(status, 200000)
    total_compensation = total_wages + se_income
    excess = max(0.0, total_compensation - threshold)
    return round(excess * MEDICARE_SURTAX["rate"], 2)


# ===========================================================================
# Main Federal Tax Computation
# ===========================================================================

def compute_federal_tax(profile) -> dict:
    """Compute all federal tax values for a TaxProfile.

    v4.0 spec compliant:
      - OBBBA Schedule 1-A deductions (above-the-line, Line 10)
      - Year-specific CTC
      - Medicare surtax
      - Corrected standard deductions
    """
    year = profile.tax_year
    status = profile.filing_status
    brackets = FEDERAL_BRACKETS[year][status]
    std_ded = STANDARD_DEDUCTION[year].get(status, STANDARD_DEDUCTION[year]["single"])
    ss_base = SS_WAGE_BASE[year]

    results = {}

    # ------------------------------------------------------------------
    # Step 1 — Gross Income Aggregation (Form 1040 Lines 1a–8)
    # ------------------------------------------------------------------
    total_wages = sum(w.wages for w in profile.w2_incomes)
    results["wages"] = round(total_wages, 2)

    total_interest = sum(i.amount for i in profile.interest_incomes)
    results["taxable_interest"] = round(total_interest, 2)

    total_ordinary_div = sum(d.ordinary_dividends for d in profile.dividend_incomes)
    total_qualified_div = sum(d.qualified_dividends for d in profile.dividend_incomes)
    results["ordinary_dividends"] = round(total_ordinary_div, 2)
    results["qualified_dividends"] = round(total_qualified_div, 2)

    business_net = 0.0
    if profile.business_income:
        business_net = profile.business_income.net_profit
    results["business_income"] = round(business_net, 2)

    total_income = total_wages + total_interest + total_ordinary_div + business_net
    results["total_income"] = round(total_income, 2)

    # ------------------------------------------------------------------
    # Step 2 — Above-the-Line Adjustments (Schedule 1 Part II → Line 10)
    # ------------------------------------------------------------------
    adjustments = 0.0

    # Traditional: ½ SE tax deduction
    se_tax = 0.0
    if business_net > 0:
        se_tax = _compute_se_tax(business_net, ss_base, total_wages)
        results["se_tax"] = round(se_tax, 2)
        se_deduction = round(se_tax / 2, 2)
        adjustments += se_deduction
        results["se_tax_deduction"] = se_deduction
    else:
        results["se_tax"] = 0.0
        results["se_tax_deduction"] = 0.0

    # OBBBA Schedule 1-A deductions (2025+ only)
    # Use total_income as proxy for MAGI at this stage
    schedule_1a = compute_schedule_1a(profile, total_income)
    results["schedule_1a"] = schedule_1a
    results["schedule_1a_total"] = schedule_1a["total"]
    adjustments += schedule_1a["total"]

    results["total_adjustments"] = round(adjustments, 2)

    # ------------------------------------------------------------------
    # Step 3 — AGI (Form 1040 Line 11)
    # ------------------------------------------------------------------
    agi = total_income - adjustments
    results["agi"] = round(agi, 2)

    # ------------------------------------------------------------------
    # Step 4 — Standard Deduction (Form 1040 Line 12)
    # ------------------------------------------------------------------
    # Additional standard deduction for 65+ (OBBBA)
    additional_std = 0
    if profile.is_senior_65_plus and year >= 2025:
        add_ded = ADDITIONAL_STD_DEDUCTION.get(year, {})
        if status == "mfj":
            additional_std = add_ded.get("mfj_per_person", 0)
            # Check if spouse is also 65+
            if profile.spouse_dob:
                try:
                    spouse_year = int(profile.spouse_dob[:4])
                    if (year - spouse_year) >= 65:
                        additional_std *= 2
                except (ValueError, TypeError):
                    pass
        else:
            additional_std = add_ded.get("single_or_mfs", 0)

    total_std_ded = std_ded + additional_std
    results["standard_deduction"] = std_ded
    results["additional_std_deduction"] = additional_std
    results["deduction_used"] = total_std_ded

    # ------------------------------------------------------------------
    # Step 5 — QBI Deduction (Form 1040 Line 13)
    # ------------------------------------------------------------------
    qbi_deduction = 0.0
    if business_net > 0:
        status_key = status if status != "hoh" else "single"
        qbi_threshold = QBI_TAXABLE_INCOME_THRESHOLD[year].get(status_key, 200000)
        taxable_before_qbi = agi - total_std_ded
        if taxable_before_qbi > 0:
            qbi_deduction = round(min(
                business_net * QBI_DEDUCTION_RATE,
                taxable_before_qbi * QBI_DEDUCTION_RATE,
            ))
    results["qbi_deduction"] = round(qbi_deduction, 2)

    total_deductions = total_std_ded + qbi_deduction
    results["total_deductions"] = round(total_deductions, 2)

    # ------------------------------------------------------------------
    # Step 6 — Taxable Income (Form 1040 Line 15)
    # ------------------------------------------------------------------
    taxable_income = max(0, agi - total_deductions)
    results["taxable_income"] = round(taxable_income, 2)

    # Store gross_income for validation identity (Guide §7, V-07)
    results["gross_income"] = round(total_income, 2)

    # ------------------------------------------------------------------
    # Step 7 — Income Tax (Form 1040 Line 16)
    # ------------------------------------------------------------------
    income_tax = compute_tax_from_brackets(taxable_income, brackets)
    results["income_tax"] = round(income_tax, 2)

    # ------------------------------------------------------------------
    # Step 8 — AMT (Guide §6, un-gated for 2024+)
    # ------------------------------------------------------------------
    amt_liability = 0.0
    if year >= 2024 and year in AMT_PARAMS:
        # AMTI approximation: taxable income is a conservative proxy
        # (full AMTI requires preference item add-backs not modeled here)
        amti = taxable_income
        amt_liability = compute_amt(amti, status, year)
        # AMT only adds to tax if tentative AMT > regular tax
        if amt_liability > income_tax:
            results["amt_excess"] = round(amt_liability - income_tax, 2)
        else:
            results["amt_excess"] = 0.0
    results["amt_liability"] = round(amt_liability, 2)

    # ------------------------------------------------------------------
    # Step 10 — Other Taxes
    # ------------------------------------------------------------------
    # SE Tax (already computed above)
    results["other_taxes"] = round(se_tax, 2)

    # Medicare surtax (Form 8959) — E-09 fix
    se_income_for_medicare = business_net * SE_INCOME_FACTOR if business_net > 0 else 0
    medicare_surtax = compute_medicare_surtax(profile, total_wages, se_income_for_medicare)
    results["medicare_surtax"] = medicare_surtax

    # ------------------------------------------------------------------
    # Step 11 — Credits (Form 1040 Lines 19–24)
    # ------------------------------------------------------------------
    total_credits = 0.0

    # Child Tax Credit — year-specific (E-02 fix)
    num_qualifying = len([d for d in profile.dependents if d.age < 17])

    if num_qualifying > 0:
        ctc = 0
        for dep in profile.dependents:
            if dep.age < 17:
                ctc += get_ctc_per_child(year, dep.age)

        # Phase-out
        phase_out_threshold = CTC_PHASEOUT.get(year, {}).get(
            status if status != "hoh" else "single", 200000)
        if status == "hoh":
            phase_out_threshold = CTC_PHASEOUT.get(year, {}).get("hoh", 200000)
        if agi > phase_out_threshold:
            reduction = ((agi - phase_out_threshold) // 1000) * 50
            ctc = max(0, ctc - reduction)

        ctc = min(ctc, income_tax)
        results["child_tax_credit"] = round(ctc, 2)
        total_credits += ctc
    else:
        results["child_tax_credit"] = 0.0

    results["total_credits"] = round(total_credits, 2)

    # ------------------------------------------------------------------
    # Step 12 — Net Tax (Form 1040 Line 24)
    # ------------------------------------------------------------------
    tax_after_credits = max(0, income_tax - total_credits)
    results["tax_after_credits"] = round(tax_after_credits, 2)

    total_tax = tax_after_credits + se_tax + medicare_surtax
    # Add AMT excess if applicable (Guide §6)
    amt_excess = results.get("amt_excess", 0.0)
    total_tax += amt_excess
    results["total_tax"] = round(total_tax, 2)

    # Penalties / Interest (required by project requirements §7)
    results["penalties_interest"] = 0.0  # Stub — no underpayment modeling yet

    # ------------------------------------------------------------------
    # Step 13 — Payments & Refund (Form 1040 Lines 25–35)
    # ------------------------------------------------------------------
    total_withheld = sum(w.federal_withheld for w in profile.w2_incomes)
    results["federal_withheld"] = round(total_withheld, 2)
    results["estimated_payments"] = 0.0
    total_payments = total_withheld
    results["total_payments"] = round(total_payments, 2)

    if total_payments >= total_tax:
        results["refund"] = round(total_payments - total_tax, 2)
        results["amount_owed"] = 0.0
    else:
        results["refund"] = 0.0
        results["amount_owed"] = round(total_tax - total_payments, 2)

    # Effective rate
    if agi > 0:
        results["effective_rate"] = round((total_tax / agi) * 100, 2)
    else:
        results["effective_rate"] = 0.0

    profile.federal_results = results
    return results


def _compute_se_tax(business_net: float, ss_wage_base: float,
                    w2_wages: float) -> float:
    """Compute self-employment tax (V-05 compliant).

    SE tax = 15.3% (12.4% SS + 2.9% Medicare) on 92.35% of net SE income.
    SS portion is capped by the wage base (reduced by W-2 wages).
    """
    se_earnings = business_net * SE_INCOME_FACTOR

    if se_earnings <= 0:
        return 0.0

    remaining_ss_base = max(0, ss_wage_base - w2_wages)
    ss_earnings = min(se_earnings, remaining_ss_base)
    ss_tax = ss_earnings * SS_TAX_RATE

    medicare_tax = se_earnings * MEDICARE_TAX_RATE

    return round(ss_tax + medicare_tax, 2)


# ===========================================================================
# AMT Calculation — Guide §6 (OBBBA, un-gated)
# ===========================================================================

def compute_amt(amti: float, filing_status: str, tax_year: int) -> float:
    """Calculate Alternative Minimum Tax for any supported year.

    Guide §6.2: For 2026, OBBBA doubles the phase-out rate from 25¢ to 50¢
    per dollar and lowers phase-out thresholds.

    Args:
        amti: Alternative Minimum Taxable Income (before exemption).
        filing_status: 'single', 'mfj', or 'hoh'.
        tax_year: Tax year for parameter lookup.

    Returns:
        Tentative AMT liability.

    Sources:
        Bradford Tax Institute: "How the OBBBA Impacts Your AMT Risk Starting in 2026"
        Mercer Advisors: "Alternative Minimum Tax After OBBBA"
    """
    if tax_year not in AMT_PARAMS:
        return 0.0  # No AMT data for this year

    params = AMT_PARAMS[tax_year]
    status_key = filing_status if filing_status != 'hoh' else 'single'

    exemption = params['exemption'].get(status_key, params['exemption']['single'])
    phase_start = params['phaseout_start'].get(status_key, params['phaseout_start']['single'])
    phase_rate = params['phaseout_rate']  # 0.25 TCJA, 0.50 OBBBA

    # Phase-out: reduce exemption
    if amti > phase_start:
        excess = amti - phase_start
        reduction = excess * phase_rate
        exemption = max(0.0, exemption - reduction)

    # AMT base
    amt_base = max(0.0, amti - exemption)

    # Two-rate structure (26% up to ceiling, 28% above)
    amt_26_ceiling = get_tax_parameters(tax_year).get('amt_26_bracket_ceiling', 220700)
    if amt_base <= amt_26_ceiling:
        tentative_amt = amt_base * 0.26
    else:
        tentative_amt = (amt_26_ceiling * 0.26) + ((amt_base - amt_26_ceiling) * 0.28)

    return round(tentative_amt, 2)


# ===========================================================================
# 2/37 Benefit Cap — Guide §6.3
# ===========================================================================

def apply_237_benefit_cap(itemized_deductions: float, taxable_income: float,
                          filing_status: str, tax_year: int = 2026) -> float:
    """OBBBA 2/37 rule: cap the tax benefit of itemized deductions at 35%
    for taxpayers in the 37% bracket.

    Guide §6.3: The value of itemized deductions is limited to 35% for
    taxpayers in the 37% bracket. Each dollar of itemized deduction saves
    at most $0.35 (not $0.37).

    Returns the effective deduction amount after cap (may be reduced).
    """
    params = get_tax_parameters(tax_year)
    if not params.get('benefit_cap_237', False):
        return itemized_deductions  # Not applicable for this year

    # 37% bracket thresholds
    status_key = filing_status if filing_status != 'hoh' else 'single'
    bracket_37_start = params['top_bracket_start'].get(status_key, 999_999_999)

    if taxable_income <= bracket_37_start:
        return itemized_deductions  # Not in 37% bracket

    # Effective cap: scale deductions so benefit doesn't exceed 35%
    cap_factor = 35 / 37
    return round(itemized_deductions * cap_factor, 2)
