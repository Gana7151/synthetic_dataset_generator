import sys

path = r"f:\combined\gana_combined\generate_tax_pdf.py"

with open(path, "r", encoding="utf-8") as f:
    content = f.read()

marker = "# ─────────────────────────────────────────────────────────────────────────────\n# SYNTHETIC VARIATION ENGINE"
if marker not in content:
    print("Marker not found.")
    sys.exit(1)

pre_content = content.split(marker)[0]

new_engine = """# ─────────────────────────────────────────────────────────────────────────────
# SYNTHETIC VARIATION ENGINE
# ─────────────────────────────────────────────────────────────────────────────

FIRST_NAMES = [
    "James", "Robert", "Michael", "William", "David", "Richard", "Joseph",
    "Thomas", "Mary", "Patricia", "Jennifer", "Linda", "Barbara", "Susan",
    "Jessica", "Karen", "Sarah", "Lisa", "Nancy", "Sandra"
]
LAST_NAMES = [
    "Smith", "Jones", "Williams", "Brown", "Davis", "Miller", "Wilson",
    "Moore", "Taylor", "Anderson", "Jackson", "Martin", "Lee", "Garcia",
    "Thompson", "White", "Lopez", "Harris", "Clark", "Lewis"
]
CITIES = [
    ("Sacramento", "CA", "95816"), ("Fresno", "CA", "93720"),
    ("Oakland", "CA", "94601"), ("San Jose", "CA", "95101"),
    ("Los Angeles", "CA", "90001"), ("San Diego", "CA", "92101"),
    ("Bakersfield", "CA", "93301"), ("Stockton", "CA", "95201"),
    ("Riverside", "CA", "92501"), ("Irvine", "CA", "92618"),
]
OCCUPATIONS_P = ["Graphic Designer", "Software Engineer", "Teacher",
                  "Accountant", "Marketing Manager", "Architect"]
OCCUPATIONS_S = ["Nurse", "Doctor", "Pharmacist", "Physical Therapist",
                  "Teacher", "Social Worker"]


def random_ssn(rng: random.Random) -> str:
    a = rng.randint(200, 899)
    b = rng.randint(10, 99)
    c = rng.randint(1000, 9999)
    return f"{a:03d}-{b:02d}-{c:04d}"


def generate_schedule_c_expenses(gross_revenue: int, rng: random.Random) -> dict:
    \"\"\"Generate realistic correlated expense lines from gross revenue.\"\"\"
    ratios = {
        "L8_Advertising":            rng.uniform(0.01, 0.05),
        "L18_OfficeExpense":         rng.uniform(0.02, 0.06),
        "L20b_RentLeaseOtherProperty": rng.uniform(0.10, 0.30),
        "L22_Supplies":              rng.uniform(0.01, 0.03),
        "L23_TaxesLicenses":         rng.uniform(0.005, 0.02),
        "L24b_DeductibleMeals":      rng.uniform(0.005, 0.015),
        "L13_DepreciationSection179": rng.uniform(0.01, 0.04),
    }
    expenses = {k: int(gross_revenue * v) for k, v in ratios.items()}
    expenses["L27a_OtherExpenses_Total"] = int(gross_revenue * rng.uniform(0.01, 0.05))
    expenses["L28_TotalExpensesBeforeHome"] = sum(expenses.values())
    expenses["L31_NetProfitLoss"] = max(0, gross_revenue - expenses["L28_TotalExpensesBeforeHome"])
    return expenses

def generate_investment_income(agi: int, rng: random.Random) -> dict:
    portfolio = agi * rng.uniform(0.5, 2.0)   # rough portfolio estimate
    interest  = int(portfolio * rng.uniform(0.005, 0.025))  # HYSA / CDs
    dividends = int(portfolio * rng.uniform(0.01, 0.03))    # equity funds
    return {
        "L2b_TaxableInterest": interest,
        "L3b_OrdinaryDividends": dividends,
    }

def generate_withholding(w2_wages: int, rng: random.Random) -> int:
    w2_fraction = rng.uniform(0.85, 0.95)  # slight under-withholding
    estimated_w2_tax = int(w2_wages * 0.18)  # rough effective rate
    return int(estimated_w2_tax * w2_fraction)

def generate_ca_withholding(w2_wages: int, rng: random.Random) -> int:
    rate = rng.uniform(0.06, 0.09)
    return int(w2_wages * rate)

def recompute_derived_fields(root):
    \"\"\"
    Enforce IRS arithmetic identities across the XML tree.
    Call this after perturbing any leaf values.
    \"\"\"
    def g(xpath):
        nodes = root.xpath(xpath)
        return int((nodes[0].text or "0").replace(",", "")) if nodes and nodes[0].text else 0

    def s(xpath, val):
        nodes = root.xpath(xpath)
        if nodes:
            nodes[0].text = str(max(0, val))

    # ── Form 1040 Income ──────────────────────────────────────
    w2         = g("//Form1040/Income/L1a_WagesW2")
    interest   = g("//Form1040/Income/L2b_TaxableInterest")
    dividends  = g("//Form1040/Income/L3b_OrdinaryDividends")
    biz_income = g("//Schedule1/Part1_AdditionalIncome/L3_BusinessIncomeScheduleC")
    cap_gain   = g("//Form1040/Income/L7_CapitalGainLoss")

    l1z  = w2
    l8   = biz_income
    l9   = l1z + interest + dividends + l8 + cap_gain

    s("//Form1040/Income/L1z_TotalWages",              l1z)
    s("//Form1040/Income/L8_AdditionalIncomeSchedule1", l8)
    s("//Form1040/Income/L9_TotalIncome",               l9)
    s("//Schedule1/Part1_AdditionalIncome/L10_TotalAdditionalIncome", l8)

    # ── Self-Employment Tax (Schedule SE) ─────────────────────
    se_net       = biz_income
    se_taxable   = int(se_net * 0.9235)
    se_ss_tax    = int(min(se_taxable, 168600) * 0.124)
    se_med_tax   = int(se_taxable * 0.029)
    se_total     = se_ss_tax + se_med_tax
    se_deduction = int(se_total * 0.50)

    s("//ScheduleSE/Part1_SelfEmploymentTax/L2_NetProfitScheduleC",   se_net)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L3_CombinedLines",        se_net)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L4a_Multiply_9235",       se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L4c_Combined",            se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L6_AddLines4c5b",         se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L9_Subtract8dFrom7",      se_taxable)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L10_Multiply_124",        se_ss_tax)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L11_Multiply_029",        se_med_tax)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L12_SelfEmploymentTax",   se_total)
    s("//ScheduleSE/Part1_SelfEmploymentTax/L13_DeductionHalfSETax",  se_deduction)
    s("//Schedule2/Part2_OtherTaxes/L4_SelfEmploymentTax",            se_total)
    s("//Schedule2/Part2_OtherTaxes/L21_TotalOtherTaxes",             se_total)
    s("//Schedule1/Part2_AdjustmentsToIncome/L15_SelfEmploymentTaxDeduction", se_deduction)
    s("//Schedule1/Part2_AdjustmentsToIncome/L26_TotalAdjustments",   se_deduction)

    # ── AGI ───────────────────────────────────────────────────
    l10 = se_deduction
    l11 = max(0, l9 - l10)
    s("//Form1040/AGI/L10_AdjustmentsSchedule1",    l10)
    s("//Form1040/AGI/L11_AdjustedGrossIncome",     l11)

    # ── QBI Deduction (Form 8995) ─────────────────────────────
    qbi_income      = int(biz_income * (se_taxable / se_net)) if se_net else 0
    qbi_component   = int(qbi_income * 0.20)
    standard_ded    = 29200  # MFJ 2024
    taxable_b4_qbi  = max(0, l11 - standard_ded)
    income_limit    = int(taxable_b4_qbi * 0.20)
    qbi_deduction   = min(qbi_component, income_limit)

    s("//Form8995/QBITrades/Trade[@seq='1']/QBIAmount",       qbi_income)
    s("//Form8995/L2_TotalQBI",                               qbi_income)
    s("//Form8995/L4_TotalQBIAfterCarryforward",              qbi_income)
    s("//Form8995/L5_QBIComponent_20pct",                     qbi_component)
    s("//Form8995/L10_QBIDeductionBeforeLimit",               qbi_component)
    s("//Form8995/L11_TaxableIncomeBeforeQBI",                l11)
    s("//Form8995/L13_L11MinusL12",                           taxable_b4_qbi)
    s("//Form8995/L14_IncomeLimitation",                      income_limit)
    s("//Form8995/L15_QBIDeduction",                          qbi_deduction)
    s("//Form1040/TaxableIncome/L13_QBIDeductionForm8995",    qbi_deduction)

    # ── Taxable Income ────────────────────────────────────────
    l12  = standard_ded
    l13  = qbi_deduction
    l14  = l12 + l13
    l15  = max(0, l11 - l14)

    s("//Form1040/TaxableIncome/L12_StandardOrItemizedDeduction", l12)
    s("//Form1040/TaxableIncome/L14_TotalDeductions",             l14)
    s("//Form1040/TaxableIncome/L15_TaxableIncome",               l15)

    # ── Federal Income Tax (2024 MFJ brackets) ───────────────
    def tax_mfj_2024(income: int) -> int:
        brackets = [
            (23200,   0.10),
            (94300,   0.12),
            (201050,  0.22),
            (383900,  0.24),
            (487450,  0.32),
            (731200,  0.35),
            (float("inf"), 0.37),
        ]
        tax, prev = 0, 0
        for limit, rate in brackets:
            taxable_in_bracket = min(income, limit) - prev
            if taxable_in_bracket <= 0:
                break
            tax += int(taxable_in_bracket * rate)
            prev = limit
        return tax

    l16  = tax_mfj_2024(l15)
    l17  = 0  # Schedule 2 Part I (AMT etc.) — 0 for most filers
    l18  = l16 + l17

    # CTC: $2,000 per qualifying child under 17, phaseout above $400,000 MFJ
    num_kids     = int(g("//Schedule8812/Part1_ChildTaxCredit/L4_QualifyingChildrenUnder17") or 0)
    num_other    = int(g("//Schedule8812/Part1_ChildTaxCredit/L6_OtherDependents") or 0)
    ctc_raw      = num_kids * 2000 + num_other * 500
    phaseout_exc = max(0, l11 - 400000)
    phaseout_red = int(((phaseout_exc + 999) // 1000) * 1000 * 0.05)
    ctc          = max(0, ctc_raw - phaseout_red)
    ctc_used     = min(ctc, l18)

    s("//Schedule8812/Part1_ChildTaxCredit/L5_Multiply2000",          num_kids * 2000)
    s("//Schedule8812/Part1_ChildTaxCredit/L7_Multiply500",           num_other * 500)
    s("//Schedule8812/Part1_ChildTaxCredit/L8_AddLines5_7",           ctc_raw)
    s("//Schedule8812/Part1_ChildTaxCredit/L12_CreditAfterPhaseout",  ctc)
    s("//Schedule8812/Part1_ChildTaxCredit/L14_ChildTaxCredit",       ctc_used)
    s("//Form1040/TaxAndCredits/L16_Tax",                             l16)
    s("//Form1040/TaxAndCredits/L18_TotalTax",                        l18)
    s("//Form1040/TaxAndCredits/L19_ChildTaxCreditSchedule8812",      ctc_used)
    s("//Form1040/TaxAndCredits/L21_TotalCredits",                    ctc_used)
    s("//Form1040/TaxAndCredits/L22_TaxAfterCredits",                 max(0, l18 - ctc_used))
    s("//Form1040/TaxAndCredits/L23_OtherTaxesSchedule2",             se_total)
    l24 = max(0, l18 - ctc_used) + se_total
    s("//Form1040/TaxAndCredits/L24_TotalTax",                        l24)

    # ── Payments & Refund ─────────────────────────────────────
    withheld = g("//Form1040/Payments/L25a_FederalWithheldW2")
    s("//Form1040/Payments/L25d_TotalFederalWithheld", withheld)
    s("//Form1040/Payments/L33_TotalPayments",         withheld)

    if withheld >= l24:
        refund = withheld - l24
        owed   = 0
    else:
        refund = 0
        owed   = l24 - withheld

    s("//Form1040/RefundOrOwed/L34_Overpaid",    refund)
    s("//Form1040/RefundOrOwed/L35a_RefundAmount", refund)
    s("//Form1040/RefundOrOwed/L37_AmountOwed",  owed)

    # ── 1040-V Payment Voucher ────────────────────────────────
    s("//Form1040V/PaymentAmount", owed)

    # ── CA 540 (simplified — real CA tax uses FTB tables) ────
    # CA standard deduction: MFJ = $11,080 (2024)
    ca_std  = 11080
    ca_agi  = l11
    ca_ti   = max(0, ca_agi - ca_std)
    # Rough CA tax (rate schedule, simplified):
    ca_brackets = [
        (20824,   0.01), (49368,   0.02), (77918,   0.04),
        (108162,  0.06), (136700,  0.08), (698274,  0.093),
        (float("inf"), 0.103),
    ]
    ca_tax, prev = 0, 0
    for limit, rate in ca_brackets:
        seg = min(ca_ti, limit) - prev
        if seg <= 0: break
        ca_tax += int(seg * rate)
        prev = limit

    ca_exempt = g("//CA540/L11_TotalExemptionCredits") or 1220
    ca_tax_after = max(0, ca_tax - ca_exempt)
    ca_withheld  = g("//CA540/Payments/L71_CAWithheld")
    ca_refund    = max(0, ca_withheld - ca_tax_after)
    ca_owed      = max(0, ca_tax_after - ca_withheld)

    s("//CA540/TaxableIncome/L13_FederalAGI",             ca_agi)
    s("//CA540/TaxableIncome/L15_AfterSubtractions",      ca_agi)
    s("//CA540/TaxableIncome/L17_CAAdjustedGrossIncome",  ca_agi)
    s("//CA540/TaxableIncome/L18_Deduction",              ca_std)
    s("//CA540/TaxableIncome/L19_TaxableIncome",          ca_ti)
    s("//CA540/Tax/L31_TaxFromTable",                     ca_tax)
    s("//CA540/Tax/L33_TaxAfterExemptionCredits",         ca_tax_after)
    s("//CA540/Tax/L35_TotalTax",                         ca_tax_after)
    s("//CA540/SpecialCredits/L48_TaxAfterCredits",       ca_tax_after)
    s("//CA540/OtherTaxes/L64_TotalTax",                  ca_tax_after)
    s("//CA540/Payments/L78_TotalPayments",               ca_withheld)
    s("//CA540/UseAndPenalty/L93_PaymentsAfterISR",       ca_withheld)
    s("//CA540/UseAndPenalty/L95_PaymentsBalance",        ca_withheld)
    s("//CA540/RefundOrOwed/L96_OverpaidTax",             ca_refund)
    s("//CA540/RefundOrOwed/L97_OverpaidTaxAvailable",    ca_refund)
    s("//CA540/RefundOrOwed/L99_RefundAvailable",         ca_refund)
    s("//CA540/AmountOwedOrRefund/L115_Refund",           ca_refund)
    s("//CA540/RefundOrOwed/L100_TaxDue",                 ca_owed)

    return root

def generate_variation(xml_path: str, source_pdf: str, output_path: str, seed: int):
    \"\"\"Generate a randomised synthetic variant from the base XML using the Quant Model.\"\"\"
    rng = random.Random(seed)
    root = load_xml(xml_path)

    def set_text(xpath: str, value: Any):
        nodes = root.xpath(xpath)
        if nodes:
            nodes[0].text = str(value)

    # 1. Randomise identities
    p_first = rng.choice(FIRST_NAMES)
    p_last  = rng.choice(LAST_NAMES)
    s_first = rng.choice(FIRST_NAMES)
    s_last  = p_last  # spouse takes same last name
    city, state, zipcode = rng.choice(CITIES)
    street_num = rng.randint(100, 9999)
    street_names = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd",
                    "Elm St", "Washington Blvd", "Park Ave"]

    set_text("//Taxpayer/Primary/FirstName", p_first)
    set_text("//Taxpayer/Primary/LastName",  p_last)
    set_text("//Taxpayer/Primary/SSN",       random_ssn(rng))
    set_text("//Taxpayer/Primary/Email",     f"{p_first.lower()}.{p_last.lower()}@gmail.com")
    set_text("//Taxpayer/Primary/Occupation", rng.choice(OCCUPATIONS_P))

    set_text("//Taxpayer/Spouse/FirstName", s_first)
    set_text("//Taxpayer/Spouse/LastName",  s_last)
    set_text("//Taxpayer/Spouse/SSN",       random_ssn(rng))
    set_text("//Taxpayer/Spouse/Occupation", rng.choice(OCCUPATIONS_S))

    set_text("//Taxpayer/Address/Street",
             f"{street_num} {rng.choice(street_names)}")
    set_text("//Taxpayer/Address/City",  city)
    set_text("//Taxpayer/Address/State", state)
    set_text("//Taxpayer/Address/ZIP",   zipcode)

    # 2. Generate correlated leaf inputs
    w2        = rng.randint(30000, 150000)
    gross_rev = rng.randint(30000, 200000)
    
    set_text("//Form1040/Income/L1a_WagesW2", w2)
    set_text("//ScheduleC/Part1_Income/L1_GrossReceipts", gross_rev)
    set_text("//ScheduleC/Part1_Income/L7_GrossIncome", gross_rev)

    # Generate business expenses derived from gross revenue
    expenses = generate_schedule_c_expenses(gross_rev, rng)
    for field, amount in expenses.items():
        set_text(f"//ScheduleC/Part2_Expenses/{field}", amount)
        
    set_text("//Schedule1/Part1_AdditionalIncome/L3_BusinessIncomeScheduleC", expenses["L31_NetProfitLoss"])

    # Rough estimate of AGI temporarily for investment correlation
    estimated_agi = w2 + expenses["L31_NetProfitLoss"]
    inv_income = generate_investment_income(estimated_agi, rng)
    for field, amount in inv_income.items():
        set_text(f"//Form1040/Income/{field}", amount)

    # Withholdings
    fed_withholding = generate_withholding(w2, rng)
    ca_withholding = generate_ca_withholding(w2, rng)
    
    set_text("//Form1040/Payments/L25a_FederalWithheldW2", fed_withholding)
    set_text("//CA540/Payments/L71_CAWithheld", ca_withholding)

    # 3. Recompute ALL derived fields using tax math
    root = recompute_derived_fields(root)

    # 4. Write modified XML to temp file, then generate PDF
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="wb") as tmp:
        tree = root.getroottree()
        tree.write(tmp, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        tmp_path = tmp.name

    try:
        generate_pdf(tmp_path, source_pdf, output_path)
    finally:
        os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic tax return PDFs from XML data"
    )
    parser.add_argument("--xml",    required=True,  help="Path to tax return XML file")
    parser.add_argument("--source", required=True,  help="Path to original/blank PDF (layout template)")
    parser.add_argument("--out",    required=True,  help="Output PDF path")
    parser.add_argument("--variations", type=int, default=0,
                        help="If > 0, generate N synthetic variants instead of exact reproduction")
    parser.add_argument("--seed",   type=int, default=42,
                        help="Base random seed for synthetic variants")
    args = parser.parse_args()

    if args.variations > 0:
        out_path = Path(args.out)
        stem = out_path.stem
        suffix = out_path.suffix
        parent = out_path.parent
        for i in range(args.variations):
            variant_path = str(parent / f"{stem}_variant_{i+1:03d}{suffix}")
            print(f"\\n═══ Variant {i+1}/{args.variations} → {variant_path} ═══")
            generate_variation(args.xml, args.source, variant_path, seed=args.seed + i)
    else:
        generate_pdf(args.xml, args.source, args.out)


if __name__ == "__main__":
    main()
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(pre_content + new_engine)

print("done")
