import re
import os

path = r"f:\\combined\\gana_combined\\tax_engine\\federal_calculator.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# Replace block 1 (Gross income)
b1_old = """    total_wages = sum(w.wages for w in profile.w2_incomes)
    results["wages"] = round(total_wages, 2)

    total_interest = sum(i.amount for i in profile.interest_incomes)
    results["taxable_interest"] = round(total_interest, 2)

    total_ordinary_div = sum(d.ordinary_dividends for d in profile.dividend_incomes)
    total_qualified_div = sum(d.qualified_dividends for d in profile.dividend_incomes)
    results["ordinary_dividends"] = round(total_ordinary_div, 2)
    results["qualified_dividends"] = round(total_qualified_div, 2)

    total_short_term = sum(cg.short_term_gains for cg in getattr(profile, 'capital_gains', []))
    total_long_term = sum(cg.long_term_gains for cg in getattr(profile, 'capital_gains', []))
    results["short_term_gains"] = round(total_short_term, 2)
    results["long_term_gains"] = round(total_long_term, 2)

    business_net = 0.0
    if profile.business_income:
        business_net = profile.business_income.net_profit
    results["business_income"] = round(business_net, 2)

    total_income = total_wages + total_interest + total_ordinary_div + total_short_term + total_long_term + business_net
    results["total_income"] = round(total_income, 2)"""

b1_new = """    total_wages = sum(w.wages for w in profile.w2_incomes)
    results["wages"] = round(total_wages, 2)
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

    total_interest = sum(i.amount for i in profile.interest_incomes)
    results["taxable_interest"] = round(total_interest, 2)
    
    results["ira_distributions_total"]   = 0.0   # Line 4a
    results["ira_distributions_taxable"] = 0.0   # Line 4b
    results["pensions_total"]            = 0.0   # Line 5a
    results["pensions_taxable"]          = 0.0   # Line 5b
    results["ss_benefits_total"]         = 0.0   # Line 6a
    results["ss_benefits_taxable"]       = 0.0   # Line 6b

    total_ordinary_div = sum(d.ordinary_dividends for d in profile.dividend_incomes)
    total_qualified_div = sum(d.qualified_dividends for d in profile.dividend_incomes)
    results["ordinary_dividends"] = round(total_ordinary_div, 2)
    results["qualified_dividends"] = round(total_qualified_div, 2)

    total_short_term = sum(cg.short_term_gains for cg in getattr(profile, 'capital_gains', []))
    total_long_term = sum(cg.long_term_gains for cg in getattr(profile, 'capital_gains', []))
    results["short_term_gains"] = round(total_short_term, 2)
    results["long_term_gains"] = round(total_long_term, 2)
    
    results["schedule_d_required"] = len(getattr(profile, 'capital_gains', [])) > 0 and \
        any(cg.short_term_gains != 0 for cg in getattr(profile, 'capital_gains', []))
    results["capital_gains_line7"] = round(total_short_term + total_long_term, 2) if results["schedule_d_required"] else round(total_long_term, 2)

    business_net = 0.0
    if profile.business_income:
        business_net = profile.business_income.net_profit
    results["business_income"] = round(business_net, 2)

    total_income = total_wages + total_interest + total_ordinary_div + total_short_term + total_long_term + business_net
    results["total_income"] = round(total_income, 2)"""

content = content.replace(b1_old, b1_new)


# Replace block 2 (Adjustments)
b2_old = """    # Traditional: ½ SE tax deduction
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

    results["total_adjustments"] = round(adjustments, 2)"""

b2_new = """    # Traditional: ½ SE tax deduction
    se_tax = 0.0
    se_deduction = 0.0
    if business_net > 0:
        se_data = compute_schedule_se(profile, business_net, ss_base, total_wages)
        results["se_data"] = se_data
        se_tax = se_data["line_12_se_tax"]
        results["se_tax"] = round(se_tax, 2)
        se_deduction = se_data["line_13_deduction"]
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
    
    schedule_1 = compute_schedule_1(profile, business_net, se_deduction, schedule_1a["total"])
    results["schedule_1"] = schedule_1
    results["additional_income_sch1"] = schedule_1["line_10"]
    
    adjustments += schedule_1a["total"]
    results["total_adjustments"] = schedule_1["line_26"]"""

content = content.replace(b2_old, b2_new)


# Replace Block 3 (QBI)
b3_old = """    qbi_deduction = 0.0
    if business_net > 0:
        status_key = status if status != "hoh" else "single"
        qbi_threshold = QBI_TAXABLE_INCOME_THRESHOLD[year].get(status_key, 200000)
        taxable_before_qbi = agi - deduction_to_use
        if taxable_before_qbi > 0:
            qbi_deduction = round(min(
                business_net * QBI_DEDUCTION_RATE,
                taxable_before_qbi * QBI_DEDUCTION_RATE,
            ))
    results["qbi_deduction"] = round(qbi_deduction, 2)"""

b3_new = """    qbi_deduction = 0.0
    if business_net > 0:
        status_key = status if status != "hoh" else "single"
        qbi_threshold = QBI_TAXABLE_INCOME_THRESHOLD[year].get(status_key, 200000)
        taxable_before_qbi = agi - deduction_to_use
        if taxable_before_qbi > 0:
            qbi_deduction = round(min(
                max(0, business_net - results.get("se_tax_deduction", 0.0)) * QBI_DEDUCTION_RATE,
                taxable_before_qbi * QBI_DEDUCTION_RATE,
            ))
            
    results["schedule_8995"] = {
        "line_1i_income": round(business_net, 2),
        "line_2":  round(max(0, business_net - results.get("se_tax_deduction", 0.0)), 2),
        "line_4":  round(max(0, business_net - results.get("se_tax_deduction", 0.0)), 2),
        "line_5":  round(max(0, business_net - results.get("se_tax_deduction", 0.0)) * QBI_DEDUCTION_RATE, 2),
        "line_11": round(agi - deduction_to_use, 2),        # taxable income before QBI
        "line_12": round(total_qualified_div + total_long_term, 2),  # net capital gain
        "line_13": round(max(0, (agi - deduction_to_use) - (total_qualified_div + total_long_term)), 2),
        "line_14": round(max(0, (agi - deduction_to_use) - (total_qualified_div + total_long_term)) * QBI_DEDUCTION_RATE, 2),
        "line_15": round(qbi_deduction, 2),
    }
            
    results["qbi_deduction"] = round(qbi_deduction, 2)"""

content = content.replace(b3_old, b3_new)

# Block 4 (Credits down to end)
b4_old = """    # ------------------------------------------------------------------
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


def _compute_se_tax"""

b4_new = """    # ------------------------------------------------------------------
    # Step 10 — Other Taxes
    # ------------------------------------------------------------------
    # SE Tax (already computed above)
    se_income_for_medicare = business_net * SE_INCOME_FACTOR if business_net > 0 else 0
    medicare_surtax = compute_medicare_surtax(profile, total_wages, se_income_for_medicare)
    results["medicare_surtax"] = medicare_surtax

    schedule_2_data = compute_schedule_2(profile, income_tax, se_tax, medicare_surtax, results.get("amt_excess", 0.0), total_interest, total_ordinary_div, total_short_term, total_long_term, agi)
    results["schedule_2"] = schedule_2_data
    results["other_taxes"] = schedule_2_data["part_ii_total"]
    
    results["line_17_sch2_line3"] = schedule_2_data["part_i_total"]
    results["line_18"] = round(results["income_tax"] + results["line_17_sch2_line3"], 2)

    # ------------------------------------------------------------------
    # Step 11 — Credits (Form 1040 Lines 19–24)
    # ------------------------------------------------------------------
    total_credits = 0.0

    schedule_8812 = compute_schedule_8812(profile, agi, income_tax, 0.0)
    results["schedule_8812"] = schedule_8812
    results["child_tax_credit"] = schedule_8812.get("line_14", 0.0)
    results["additional_ctc"] = schedule_8812.get("line_27", 0.0)
    total_credits += schedule_8812.get("line_14", 0.0)
    results["total_credits"] = round(total_credits, 2)
    
    results["schedule_3_line_8"] = 0.0
    results["line_21"] = round(results["child_tax_credit"] + results.get("schedule_3_line_8", 0.0), 2)

    # ------------------------------------------------------------------
    # Step 12 — Net Tax (Form 1040 Line 24)
    # ------------------------------------------------------------------
    results["line_22"] = round(max(0, results["line_18"] - results["line_21"]), 2)
    tax_after_credits = results["line_22"]
    results["tax_after_credits"] = round(tax_after_credits, 2)

    total_tax = tax_after_credits + results.get("other_taxes", 0.0)
    results["total_tax"] = round(total_tax, 2)

    # Penalties / Interest
    results["penalties_interest"] = 0.0
    results["estimated_tax_penalty"] = 0.0

    # ------------------------------------------------------------------
    # Step 13 — Payments & Refund (Form 1040 Lines 25–35)
    # ------------------------------------------------------------------
    total_withheld = sum(w.federal_withheld for w in profile.w2_incomes)
    results["federal_withheld"] = round(total_withheld, 2)
    results["line_25a"] = results["federal_withheld"]
    results["line_25b"] = 0.0
    results["line_25c"] = 0.0
    results["line_25d"] = results["federal_withheld"]
    
    results["estimated_payments"] = 0.0
    results["earned_income_credit"] = 0.0
    results["aoc_refundable"] = 0.0
    
    # Schedule 3 Part II (excess SS)
    total_ss_withheld = sum(w.ss_tax for w in profile.w2_incomes)
    ss_base_expected = SS_WAGE_BASE[year]
    max_ss = round(ss_base_expected * 0.062, 2)
    excess_ss = max(0.0, round(total_ss_withheld - max_ss, 2))
    results["excess_ss_withheld"] = excess_ss
    results["schedule_3_line_15"] = excess_ss
    
    results["line_32"] = round(
        results.get("earned_income_credit", 0.0) +
        results.get("additional_ctc", 0.0) +
        results.get("aoc_refundable", 0.0) +
        results.get("schedule_3_line_15", 0.0), 2)
        
    results["line_33"] = round(
        results["line_25d"] +
        results.get("estimated_payments", 0.0) +
        results["line_32"], 2)
        
    total_payments = results["line_33"]
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

    est_tax_data = compute_estimated_tax_next_year(profile, total_tax, agi)
    results["estimated_tax_data"] = est_tax_data

    profile.federal_results = results
    return results


def compute_schedule_8812(profile, agi: float, income_tax: float,
                          total_credits_before: float) -> dict:
    s = {}
    year = profile.tax_year
    status = profile.filing_status

    s["line_1"]  = round(agi, 2)

    qualifying_under_17 = [d for d in profile.dependents if d.age < 17]
    other_deps = [d for d in profile.dependents if d.age >= 17]

    ctc_per = get_ctc_per_child(year, 10)
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
    s["line_13"] = credit_limit
    s["line_14"] = min(s["line_12"], s["line_13"])

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
    s["line_27"]  = round(min(s["line_17"], s["line_20"]), 2)

    return s


def compute_schedule_se"""

content = content.replace(b4_old, b4_new)

# Block 5 (Replace _compute_se_tax content and add the rest of missing functions)
b5_old = """def _compute_se_tax(business_net: float, ss_wage_base: float,
                    w2_wages: float) -> float:
    \"\"\"Compute self-employment tax (V-05 compliant).

    SE tax = 15.3% (12.4% SS + 2.9% Medicare) on 92.35% of net SE income.
    SS portion is capped by the wage base (reduced by W-2 wages).
    \"\"\"
    se_earnings = business_net * SE_INCOME_FACTOR

    if se_earnings <= 0:
        return 0.0

    remaining_ss_base = max(0, ss_wage_base - w2_wages)
    ss_earnings = min(se_earnings, remaining_ss_base)
    ss_tax = ss_earnings * SS_TAX_RATE

    medicare_tax = se_earnings * MEDICARE_TAX_RATE

    return round(ss_tax + medicare_tax, 2)
"""

b5_new = """def compute_schedule_se(profile, business_net: float,
                        ss_wage_base: float, w2_wages: float) -> dict:
    \"\"\"Full Schedule SE computation — returns all lines for rendering.\"\"\"
    se_data = {}
    se_data["line_2"]  = round(business_net, 2)
    se_data["line_3"]  = round(business_net, 2)

    se_earnings = business_net * 0.9235
    se_data["line_4a"] = round(se_earnings, 2)
    se_data["line_4b"] = 0.0
    se_data["line_4c"] = round(se_earnings, 2)

    se_data["line_6"]  = round(se_earnings, 2)
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

def compute_schedule_1(profile, business_net: float,
                       se_deduction: float, schedule_1a_total: float) -> dict:
    s1 = {}
    s1["line_1"]  = 0.0
    s1["line_2a"] = 0.0
    s1["line_3"]  = round(business_net, 2)
    s1["line_4"]  = 0.0
    s1["line_5"]  = 0.0
    s1["line_6"]  = 0.0
    s1["line_7"]  = 0.0
    s1["line_8z"] = 0.0
    s1["line_9"]  = 0.0
    s1["line_10"] = round(s1["line_3"], 2)

    s1["line_11"] = 0.0
    s1["line_12"] = 0.0
    s1["line_13"] = 0.0
    s1["line_14"] = 0.0
    s1["line_15"] = round(se_deduction, 2)
    s1["line_16"] = 0.0
    s1["line_17"] = 0.0
    s1["line_18"] = 0.0
    s1["line_20"] = 0.0
    s1["line_21"] = 0.0
    s1["line_23"] = 0.0
    s1["line_25"] = 0.0
    s1["line_26_obbba"] = round(schedule_1a_total, 2)
    s1["line_26"] = round(s1["line_15"] + s1["line_26_obbba"], 2)
    return s1

def compute_schedule_2(profile, income_tax: float, se_tax: float,
                       medicare_surtax: float, amt_excess: float,
                       taxable_interst: float, ord_div: float,
                       st_gains: float, lt_gains: float, agi: float) -> dict:
    s2 = {}
    s2["line_1z"] = 0.0
    s2["part_i_total"] = round(amt_excess, 2)
    s2["line_3"]  = round(amt_excess, 2)
    s2["line_4"]  = round(se_tax, 2)
    s2["line_5"]  = 0.0
    s2["line_6"]  = 0.0
    s2["line_7"]  = 0.0
    s2["line_8"]  = 0.0
    s2["line_11"] = round(medicare_surtax, 2)
    
    NIIT_THRESHOLDS = {"single": 200000, "mfj": 250000, "hoh": 200000}
    net_inv = taxable_interst + ord_div + st_gains + lt_gains
    threshold = NIIT_THRESHOLDS.get(profile.filing_status, 200000)
    excess_magi = max(0, agi - threshold)
    s2["line_12"] = round(min(net_inv, excess_magi) * 0.038, 2)

    s2["part_ii_total"] = round(se_tax + medicare_surtax + s2["line_12"], 2)
    s2["line_21"] = s2["part_ii_total"]
    return s2

def compute_estimated_tax_next_year(profile, current_year_tax: float,
                                     current_agi: float) -> dict:
    safe_harbor_pct = 1.10 if current_agi > 150_000 else 1.00
    annual_est = round(current_year_tax * safe_harbor_pct, 2)
    
    w2_withholding = sum(w.federal_withheld for w in profile.w2_incomes)
    net_estimated = max(0.0, round(annual_est - w2_withholding, 2))
    
    per_quarter = round(net_estimated / 4, 2)
    required = (
        profile.business_income is not None
        and net_estimated >= 1000
    )
    return {
        "required": required,
        "annual_amount": net_estimated,
        "per_quarter": per_quarter,
        "safe_harbor_pct": safe_harbor_pct,
        "next_tax_year": profile.tax_year + 1,
    }
"""

content = content.replace(b5_old, b5_new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("done")
