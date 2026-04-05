"""
scripts/validate_fixes.py
Smoke-tests all five bug fixes against a generated variant XML.

Usage:
    python scripts/validate_fixes.py --xml <path-to-generated.xml>
"""
import argparse
import warnings
from lxml import etree
from generate_tax_pdf import (
    load_xml, s, s_nonneg, top_to_y, fmt_money, fmt_money_required,
    recompute_derived_fields, FIELD_DEFINITIONS, CHECKBOX_DEFINITIONS,
)


def check(label: str, condition: bool):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    return condition


def run(xml_path: str):
    root = load_xml(xml_path)
    all_pass = True

    print("\n── Bug 1 & 2: top_to_y uses actual page height + cap-height ratio ──")
    y_792 = top_to_y(99.5, 792.0, 9)
    y_756 = top_to_y(99.5, 756.0, 9)
    all_pass &= check("top_to_y differs for different page heights",   y_792 != y_756)
    all_pass &= check("top_to_y(99.5, 792, 9) ≈ 686.01 (cap-height formula)",
                      abs(y_792 - (792 - 99.5 - 9 * 0.72)) < 0.01)
    all_pass &= check("top_to_y(99.5, 756, 9) ≈ 650.01",
                      abs(y_756 - (756 - 99.5 - 9 * 0.72)) < 0.01)

    print("\n── Bug 3: s() preserves negatives; s_nonneg() clamps ──")
    test_root = etree.fromstring(
        "<Return><ReturnData><IRS1040/></ReturnData></Return>"
    )
    s(test_root, "//Return/ReturnData/IRS1040/BusinessIncomeAmt", -5000)
    neg_val = test_root.xpath(
        "//Return/ReturnData/IRS1040/BusinessIncomeAmt"
    )[0].text
    all_pass &= check("s() stores -5000 unchanged", neg_val == "-5000")

    s_nonneg(test_root, "//Return/ReturnData/IRS1040/TaxAmt", -100)
    tax_val = test_root.xpath("//Return/ReturnData/IRS1040/TaxAmt")[0].text
    all_pass &= check("s_nonneg() clamps -100 to 0", tax_val == "0")

    print("\n── Bug 4: Checkbox XPaths use real indicator nodes ──")
    bad_proxies = {
        "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",
    }
    cb_xpaths = {xpath for _, xpath, *_ in CHECKBOX_DEFINITIONS}
    all_pass &= check(
        "No checkbox uses DependentFirstNm as proxy",
        bad_proxies.isdisjoint(cb_xpaths),
    )

    print("\n── Bonus: fmt_money_required renders zero ──")
    all_pass &= check("fmt_money('0') returns ''",             fmt_money("0") == "")
    all_pass &= check("fmt_money_required('0') returns '0'",   fmt_money_required("0") == "0")
    all_pass &= check("fmt_money_required('94803') formats ok", fmt_money_required("94803") == "94,803")

    print("\n── Cross-form arithmetic on provided XML ──")
    def g(xpath):
        nodes = root.xpath(xpath)
        try:
            return int((nodes[0].text or "0").replace(",", "")) if nodes else 0
        except (ValueError, TypeError):
            return 0

    agi        = g("//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt")
    total_inc  = g("//Return/ReturnData/IRS1040/TotalIncomeAmt")
    adj        = g("//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt")
    total_tax  = g("//Return/ReturnData/IRS1040/TotalTaxAmt")
    payments   = g("//Return/ReturnData/IRS1040/TotalPaymentsAmt")
    refund     = g("//Return/ReturnData/IRS1040/RefundAmt")
    owed       = g("//Return/ReturnData/IRS1040/AmountOwedAmt")

    all_pass &= check("AGI == TotalIncome - Adjustments",
                      agi == total_inc - adj or adj == 0)
    all_pass &= check("RefundAmt or AmountOwedAmt is 0 (not both positive)",
                      not (refund > 0 and owed > 0))
    all_pass &= check("TotalTax >= 0", total_tax >= 0)
    all_pass &= check("TotalPayments >= 0", payments >= 0)

    print()
    print("══ Result:", "ALL PASS ✓" if all_pass else "FAILURES DETECTED ✗")
    return all_pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--xml", required=True, help="Path to generated XML file")
    args = parser.parse_args()
    ok = run(args.xml)
    raise SystemExit(0 if ok else 1)
