import re

path = r"f:\\combined\\gana_combined\\validation.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

rules_list_old = """            ("V-14", self._v14_vin_validation),
            ("V-15", self._v15_file_existence),
        ]"""

rules_list_new = """            ("V-14", self._v14_vin_validation),
            ("V-15", self._v15_file_existence),
            ("V-16", self._v16_actc_arithmetic),
            ("V-17", self._v17_schedule_2_consistency),
            ("V-18", self._v18_estimated_tax_trigger),
            ("V-19", self._v19_form_4562_consistency),
            ("V-20", self._v20_estimated_amount_check),
        ]"""

content = content.replace(rules_list_old, rules_list_new)

new_rules = """
    # -----------------------------------------------------------------------
    # V-16: ACTC Arithmetic
    # -----------------------------------------------------------------------
    def _v16_actc_arithmetic(self, profile, _):
        fed = profile.federal_results
        sch = fed.get("schedule_8812", {})
        if not sch:
            return True, ""
        expected = round(min(sch.get("line_17", 0), sch.get("line_20", 0)), 2)
        actual = sch.get("line_27", 0)
        return (abs(actual - expected) < 0.01, f"ACTC {actual} ≠ expected {expected}")

    # -----------------------------------------------------------------------
    # V-17: Schedule 2 Consistency
    # -----------------------------------------------------------------------
    def _v17_schedule_2_consistency(self, profile, _):
        fed = profile.federal_results
        sch2 = fed.get("schedule_2", {})
        if not sch2:
            return True, ""
        tax2 = sch2.get("part_ii_total", 0)
        actual_other = fed.get("other_taxes", 0)
        return (abs(tax2 - actual_other) < 0.01, f"Sch 2 Part II {tax2} ≠ other_taxes {actual_other}")

    # -----------------------------------------------------------------------
    # V-18: Estimated Tax Trigger
    # -----------------------------------------------------------------------
    def _v18_estimated_tax_trigger(self, profile, _):
        fed = profile.federal_results
        est = fed.get("estimated_tax_data", {})
        if not est:
            return True, ""
        if profile.business_income is not None and est.get("annual_amount", 0) >= 1000:
            if not est.get("required"):
                return False, "EST tax required but flag is False"
        return True, ""

    # -----------------------------------------------------------------------
    # V-19: Form 4562 Consistency
    # -----------------------------------------------------------------------
    def _v19_form_4562_consistency(self, profile, _):
        if not profile.business_income:
            return True, ""
        total_depr = sum(a.depreciation_this_year for a in profile.business_income.depreciable_assets)
        actual = profile.business_income.depreciation
        if profile.business_income.depreciable_assets and abs(total_depr - actual) > 0.01:
             return False, f"4562 Depr {total_depr} ≠ Business Depr {actual}"
        return True, ""

    # -----------------------------------------------------------------------
    # V-20: Estimated Amount Check
    # -----------------------------------------------------------------------
    def _v20_estimated_amount_check(self, profile, _):
        fed = profile.federal_results
        est = fed.get("estimated_tax_data", {})
        if not est:
            return True, ""
        expected = round(est.get("annual_amount", 0) / 4.0, 2)
        actual = est.get("per_quarter", 0)
        return (abs(expected - actual) < 0.01, f"Quarterly {actual} ≠ expected {expected}")
"""
content += new_rules

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("done")
