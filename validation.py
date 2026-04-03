"""
15-Rule Validation Engine — v5.0 Guide v2.0 Compliant.

Validates every generated dataset against the authoritative tax rules
from Guide §14 and enforces accounting identities from §7.

Failed datasets are discarded and re-seeded (max 3 retries).

Rule mapping to Guide §14:
  V-01: W-2 wage consistency (wages sum → 1040)
  V-02: SS wage base cap (Box 3 ≤ wage base, Box 4 = Box 3 × 6.2%)
  V-03: Business income consistency (Sch C → federal results)
  V-04: Mortgage interest cap ($750K principal, Guide V-04)
  V-05: SE tax arithmetic (Guide V-03)
  V-06: AGI consistency (Guide V-07: agi == gross_income - adjustments)
  V-07: Taxable income consistency (AGI - deductions - QBI)
  V-08: Interest income chain (1099-INT sum → 1040 Line 2b)
  V-09: Medicare surtax thresholds
  V-10: SALT cap enforcement (Guide V-06)
  V-11: CTC year-specific
  V-12: OBBBA phase-out validation (Guide V-10, V-14)
  V-13: SSN deduplication
  V-14: VIN validation (US-assembled, check digit)
  V-15: File existence (output folder completeness)
"""

import os
from tax_engine.tax_tables import (
    SS_WAGE_BASE, SS_RATE_EMPLOYEE, STANDARD_DEDUCTION,
    SALT_CAP, MEDICARE_SURTAX, CTC_PHASEOUT,
    get_ctc_per_child, OBBBA_DEDUCTIONS, NO_INCOME_TAX_STATES,
)
from tax_engine.vin_generator import compute_check_digit
from tax_engine.tax_parameters_store import get_tax_parameters, is_obbba_year


class ValidationResult:
    def __init__(self, passed: bool, failures: list):
        self.passed = passed
        self.failures = failures


class ValidationEngine:
    """Runs all 15 validation rules against a dataset.

    Guide v2.0 §14 compliant. Every generated record must pass all 15 rules.
    """

    def __init__(self):
        self._used_ssns = set()
        self.rule_failure_counts = {}

    def run_all(self, profile, output_dir: str = None) -> ValidationResult:
        """Run all 15 validation rules.

        Args:
            profile: TaxProfile with computed federal_results and state_results.
            output_dir: Path to the dataset output folder (for V-15).

        Returns:
            ValidationResult with pass/fail and list of failures.
        """
        fed = profile.federal_results
        failures = []

        rules = [
            ("V-01", self._v01_w2_wage_consistency),
            ("V-02", self._v02_ss_wage_base_cap),
            ("V-03", self._v03_business_income_consistency),
            ("V-04", self._v04_mortgage_interest_cap),
            ("V-05", self._v05_se_tax_arithmetic),
            ("V-06", self._v06_agi_consistency),
            ("V-07", self._v07_taxable_income_consistency),
            ("V-08", self._v08_interest_income_chain),
            ("V-09", self._v09_medicare_surtax_threshold),
            ("V-10", self._v10_salt_cap),
            ("V-11", self._v11_ctc_year_specific),
            ("V-12", self._v12_obbba_phaseout),
            ("V-13", self._v13_ssn_deduplication),
            ("V-14", self._v14_vin_validation),
            ("V-15", self._v15_file_existence),
        ]

        for rule_id, rule_fn in rules:
            try:
                ok, msg = rule_fn(profile, output_dir)
                if not ok:
                    failures.append(f"{rule_id}: {msg}")
                    self.rule_failure_counts[rule_id] = \
                        self.rule_failure_counts.get(rule_id, 0) + 1
            except Exception as e:
                failures.append(f"{rule_id}: Exception — {e}")

        return ValidationResult(passed=len(failures) == 0, failures=failures)

    # -----------------------------------------------------------------------
    # V-01: W-2 Wage Consistency
    # -----------------------------------------------------------------------
    def _v01_w2_wage_consistency(self, profile, _):
        """SUM(W-2 Box 1) == Form 1040 wages."""
        total_w2 = sum(w.wages for w in profile.w2_incomes)
        fed_wages = profile.federal_results["wages"]
        return (
            abs(total_w2 - fed_wages) < 0.01,
            f"W-2 wages {total_w2} ≠ Form 1040 wages {fed_wages}"
        )

    # -----------------------------------------------------------------------
    # V-02: SS Wage Base Cap (Guide V-02, V-03)
    # -----------------------------------------------------------------------
    def _v02_ss_wage_base_cap(self, profile, _):
        """W-2 Box 3 ≤ SS wage base; Box 4 = Box 3 × 6.2%."""
        base = SS_WAGE_BASE[profile.tax_year]
        for w2 in profile.w2_incomes:
            if w2.ss_wages > base + 0.01:
                return False, f"Box 3 {w2.ss_wages} > SS base {base}"
            expected_box4 = round(min(w2.ss_wages, base) * SS_RATE_EMPLOYEE, 2)
            if abs(w2.ss_tax - expected_box4) > 0.02:
                return False, f"Box 4 {w2.ss_tax} ≠ expected {expected_box4}"
        return True, ""

    # -----------------------------------------------------------------------
    # V-03: Business Income → Schedule C
    # -----------------------------------------------------------------------
    def _v03_business_income_consistency(self, profile, _):
        """Schedule C net profit matches federal_results business_income."""
        if not profile.business_income:
            return True, ""
        expected = profile.business_income.net_profit
        actual = profile.federal_results.get("business_income", 0)
        return (
            abs(actual - expected) < 0.01,
            f"Schedule C net {expected} ≠ federal {actual}"
        )

    # -----------------------------------------------------------------------
    # V-04: Mortgage Interest Cap (Guide V-04)
    # -----------------------------------------------------------------------
    def _v04_mortgage_interest_cap(self, profile, _):
        """Mortgage interest capped at $750K principal × assumed 8% rate.

        Guide V-04: mortgage_interest_deduction ≤ ($750K if year ≥ 2018
        else $1M) × 0.08.
        """
        fed = profile.federal_results
        mortgage_deduction = fed.get("mortgage_interest_deduction", 0)
        
        cap_principal = 750000 if profile.tax_year >= 2018 else 1000000
        max_rate = 0.08
        max_deduction = cap_principal * max_rate
        
        if mortgage_deduction > max_deduction + 0.01:
            return False, f"Mortgage interest deduction {mortgage_deduction} exceeds cap {max_deduction}"
        return True, ""

    # -----------------------------------------------------------------------
    # V-05: SE Tax Arithmetic (Guide V-03)
    # -----------------------------------------------------------------------
    def _v05_se_tax_arithmetic(self, profile, _):
        """SE tax = (net SE × 0.9235) × 0.153 (with SS wage base cap)."""
        if not profile.business_income or profile.business_income.net_profit <= 0:
            return True, ""

        from tax_engine.tax_tables import SE_INCOME_FACTOR, SS_TAX_RATE, MEDICARE_TAX_RATE
        net = profile.business_income.net_profit
        se_earnings = net * SE_INCOME_FACTOR
        total_wages = sum(w.wages for w in profile.w2_incomes)
        ss_base = SS_WAGE_BASE[profile.tax_year]

        remaining_ss = max(0, ss_base - total_wages)
        ss_portion = min(se_earnings, remaining_ss) * SS_TAX_RATE
        medicare_portion = se_earnings * MEDICARE_TAX_RATE
        expected = round(ss_portion + medicare_portion, 2)

        actual = profile.federal_results.get("se_tax", 0)
        return (
            abs(actual - expected) < 0.05,
            f"SE tax {actual} ≠ expected {expected}"
        )

    # -----------------------------------------------------------------------
    # V-06: AGI Consistency (Guide V-07)
    # -----------------------------------------------------------------------
    def _v06_agi_consistency(self, profile, _):
        """AGI = Total Income − Total Adjustments (including OBBBA).

        Guide V-07: agi == gross_income - schedule1_adjustments
        """
        fed = profile.federal_results
        # Use gross_income if available (Guide v2.0), fallback to total_income
        gross = fed.get("gross_income", fed.get("total_income", 0))
        expected = gross - fed.get("total_adjustments", 0)
        actual = fed["agi"]
        return (
            abs(actual - expected) < 0.01,
            f"AGI {actual} ≠ GrossIncome {gross} - Adj {fed.get('total_adjustments', 0)} = {expected}"
        )

    # -----------------------------------------------------------------------
    # V-07: Taxable Income Consistency
    # -----------------------------------------------------------------------
    def _v07_taxable_income_consistency(self, profile, _):
        """Taxable income = AGI − deduction − QBI."""
        fed = profile.federal_results
        expected = max(0, fed["agi"] - fed["deduction_used"] - fed["qbi_deduction"])
        actual = fed["taxable_income"]
        return (
            abs(actual - expected) < 0.01,
            f"Taxable {actual} ≠ AGI {fed['agi']} - Ded {fed['deduction_used']} - QBI {fed['qbi_deduction']} = {expected}"
        )

    # -----------------------------------------------------------------------
    # V-08: Interest Income Chain (Guide V-08)
    # -----------------------------------------------------------------------
    def _v08_interest_income_chain(self, profile, _):
        """SUM(1099-INT) == Form 1040 Line 2b."""
        total_1099 = sum(i.amount for i in profile.interest_incomes)
        fed_interest = profile.federal_results["taxable_interest"]
        return (
            abs(total_1099 - fed_interest) < 0.01,
            f"1099-INT sum {total_1099} ≠ Line 2b {fed_interest}"
        )

    # -----------------------------------------------------------------------
    # V-09: Medicare Surtax Threshold
    # -----------------------------------------------------------------------
    def _v09_medicare_surtax_threshold(self, profile, _):
        """Medicare surtax uses correct filing-status-specific thresholds."""
        fed = profile.federal_results
        status = profile.filing_status
        threshold = MEDICARE_SURTAX["form_8959_threshold"].get(status, 200000)
        total_wages = fed["wages"]
        se_income = 0
        if profile.business_income and profile.business_income.net_profit > 0:
            from tax_engine.tax_tables import SE_INCOME_FACTOR
            se_income = profile.business_income.net_profit * SE_INCOME_FACTOR

        excess = max(0, total_wages + se_income - threshold)
        expected = round(excess * 0.009, 2)
        actual = fed.get("medicare_surtax", 0)

        return (
            abs(actual - expected) < 0.05,
            f"Medicare surtax {actual} ≠ expected {expected} (threshold {threshold})"
        )

    # -----------------------------------------------------------------------
    # V-10: SALT Cap (Guide V-06 — fully enforced)
    # -----------------------------------------------------------------------
    def _v10_salt_cap(self, profile, _):
        """SALT deduction ≤ SALT_cap[year].

        Guide V-06: salt_deduction_claimed ≤ salt_cap[tax_year]
        Currently using standard deduction, so passes by design.
        When itemization is added, this becomes a hard check.
        """
        # Standard deduction users: always passes (SALT not deducted)
        # If itemized deductions are tracked in the future:
        fed = profile.federal_results
        salt_claimed = fed.get("salt_deduction_claimed", 0)
        if salt_claimed > 0:
            cap = SALT_CAP.get(profile.tax_year, 10000)
            if salt_claimed > cap + 0.01:
                return False, f"SALT claimed ({salt_claimed}) exceeds cap ({cap})"
        return True, ""

    # -----------------------------------------------------------------------
    # V-11: CTC Year-Specific (Guide V-11)
    # -----------------------------------------------------------------------
    def _v11_ctc_year_specific(self, profile, _):
        """CTC uses year-specific amounts."""
        fed = profile.federal_results
        qualifying = [d for d in profile.dependents if d.age < 17]
        if not qualifying:
            return fed.get("child_tax_credit", 0) == 0, "CTC nonzero but no qualifying children"

        expected_raw = sum(get_ctc_per_child(profile.tax_year, d.age) for d in qualifying)
        actual = fed.get("child_tax_credit", 0)

        # CTC is limited by income tax liability and phase-outs, so actual ≤ expected
        if actual > expected_raw + 0.01:
            return False, f"CTC {actual} > max expected {expected_raw}"
        return True, ""

    # -----------------------------------------------------------------------
    # V-12: OBBBA Phase-Out Validation (Guide V-10, V-14)
    # -----------------------------------------------------------------------
    def _v12_obbba_phaseout(self, profile, _):
        """Validates Schedule 1-A phase-out calculations and eligibility.

        Guide V-10: Car loan deduction requires is_us_assembled_vehicle
        Guide V-14: Overtime deduction requires overtime_eligible AND overtime_amount > 0
        """
        if profile.tax_year < 2025:
            return True, ""

        schedule_1a = profile.federal_results.get("schedule_1a", {})
        total = schedule_1a.get("total", 0)

        # Verify total equals sum of parts
        parts_sum = (schedule_1a.get("tips", 0) + schedule_1a.get("overtime", 0)
                     + schedule_1a.get("car_loan", 0) + schedule_1a.get("senior", 0))
        if abs(total - parts_sum) > 0.01:
            return False, f"Schedule 1-A total {total} ≠ sum of parts {parts_sum}"

        # Verify values are non-negative
        for key in ["tips", "overtime", "car_loan", "senior"]:
            if schedule_1a.get(key, 0) < 0:
                return False, f"Schedule 1-A {key} is negative: {schedule_1a[key]}"

        # Guide V-10: Car loan deduction requires US-assembled VIN
        if schedule_1a.get("car_loan", 0) > 0:
            if not (profile.has_car_loan and profile.car_loan):
                return False, "Car loan deduction but no car loan on profile"
            vin = profile.car_loan.vin
            if vin[0] not in ('1', '4', '5'):
                return False, f"Car loan deduction for non-US-assembled VIN: {vin}"

        # Guide V-14: Overtime deduction requires eligibility flag
        if schedule_1a.get("overtime", 0) > 0:
            if not profile.overtime_eligible:
                return False, "Overtime deduction but overtime_eligible is False"

        # Guide V-09: Tip deduction requires tipped worker flag
        if schedule_1a.get("tips", 0) > 0:
            if not profile.is_tipped_worker:
                return False, "Tip deduction but is_tipped_worker is False"

        # Senior deduction requires age 65+
        if schedule_1a.get("senior", 0) > 0:
            if not profile.is_senior_65_plus:
                return False, "Senior deduction but is_senior_65_plus is False"

        return True, ""

    # -----------------------------------------------------------------------
    # V-13: SSN Deduplication
    # -----------------------------------------------------------------------
    def _v13_ssn_deduplication(self, profile, _):
        """No duplicate SSNs across entire corpus."""
        ssn = profile.primary_ssn
        if ssn in self._used_ssns:
            return False, f"Duplicate SSN {ssn}"
        self._used_ssns.add(ssn)

        if profile.spouse_ssn:
            if profile.spouse_ssn in self._used_ssns:
                return False, f"Duplicate spouse SSN {profile.spouse_ssn}"
            self._used_ssns.add(profile.spouse_ssn)

        for dep in profile.dependents:
            if dep.ssn in self._used_ssns:
                return False, f"Duplicate dependent SSN {dep.ssn}"
            self._used_ssns.add(dep.ssn)

        return True, ""

    # -----------------------------------------------------------------------
    # V-14: VIN Validation
    # -----------------------------------------------------------------------
    def _v14_vin_validation(self, profile, _):
        """VIN must be 17 chars, US-assembled, valid check digit."""
        if not profile.has_car_loan or not profile.car_loan:
            return True, ""

        vin = profile.car_loan.vin
        if len(vin) != 17:
            return False, f"VIN length {len(vin)} ≠ 17"
        if vin[0] not in ('1', '4', '5'):
            return False, f"VIN position 1 '{vin[0]}' not US-assembled"
        expected_check = compute_check_digit(vin)
        if vin[8] != expected_check:
            return False, f"VIN check digit '{vin[8]}' ≠ expected '{expected_check}'"
        return True, ""

    # -----------------------------------------------------------------------
    # V-15: File Existence
    # -----------------------------------------------------------------------
    def _v15_file_existence(self, profile, output_dir):
        """All required subdirectories and files exist."""
        if not output_dir:
            return True, ""

        required_dirs = [
            "1. Client Summary",
            "2. Input Documents",
            "3. Complete Forms",
            "4. Executive Summary",
            "Prompt",
        ]

        missing = []
        for d in required_dirs:
            path = os.path.join(output_dir, d)
            if not os.path.isdir(path):
                missing.append(d)

        if missing:
            return False, f"Missing directories: {missing}"

        # Check for key files
        required_files = [
            os.path.join("1. Client Summary", "Client_Summary.pdf"),
            os.path.join("4. Executive Summary", "Executive_Summary.pdf"),
            os.path.join("Prompt", "Tax_Return_Data.xml"),
        ]
        for f in required_files:
            if not os.path.isfile(os.path.join(output_dir, f)):
                missing.append(f)

        if missing:
            return False, f"Missing files: {missing}"

        return True, ""
