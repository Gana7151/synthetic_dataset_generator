import re

with open(r"f:\combined\gana_combined\generate_tax_pdf.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update xget and s
new_xget_s = """IRS_NS = ""   # IRS MeF XML has no namespace prefix

def xget(root, xpath, default=""):
    \"\"\"Return text of first matching element, or default.\"\"\"
    nodes = root.xpath(xpath)
    if nodes:
        return (nodes[0].text or "").strip()
    return default

def s(root, xpath, val):
    \"\"\"Set the text of the first matching node, create if absent.\"\"\"
    nodes = root.xpath(xpath)
    if nodes:
        nodes[0].text = str(max(0, int(val)))
    else:
        parts = xpath.rsplit("/", 1)
        if len(parts) == 2:
            parent_xpath, tag = parts
            parents = root.xpath(parent_xpath)
            if parents:
                from lxml import etree
                new_el = etree.SubElement(parents[0], tag)
                new_el.text = str(max(0, int(val)))
"""
code = re.sub(r'def xget.*?return default', new_xget_s, code, flags=re.DOTALL)

# 2. Extract FIELD_DEFINITIONS from FIX_GUIDE_28PAGE_PDF.md and FIX_GUIDE_PAGES_12_14_15_17_SUPPLEMENT.md
with open(r"f:\combined\gana_combined\FIX_GUIDE_28PAGE_PDF.md", "r", encoding="utf-8") as f:
    guide1 = f.read()

with open(r"f:\combined\gana_combined\FIX_GUIDE_PAGES_12_14_15_17_SUPPLEMENT.md", "r", encoding="utf-8") as f:
    guide2 = f.read()

field_defs_1 = re.search(r'FIELD_DEFINITIONS = \[(.*?)\]\n```', guide1, flags=re.DOTALL).group(1)
field_defs_2 = re.search(r'    # ── PAGE 12(.*?)(?=\n```)', guide2, flags=re.DOTALL).group(0)

new_field_defs = "FIELD_DEFINITIONS = [" + field_defs_1 + "\n" + field_defs_2 + "\n]"
code = re.sub(r'FIELD_DEFINITIONS = \[.*?\]\n\n', new_field_defs + "\n\n", code, flags=re.DOTALL)

# 3. Update CHECKBOX_DEFINITIONS
new_checkbox = """CHECKBOX_DEFINITIONS = [
    (14, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  377.5, 169.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.5, 193.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.6, 241.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.6, 313.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     532.4, 349.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.4, 463.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.4, 559.7),
    (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.4, 571.7),
    (14, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",          503.4, 619.7),
    (15, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  503.5, 181.7),
    (15, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",  503.5, 217.7),
    (15, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     532.4, 613.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 312.7,  97.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 521.5,  97.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 262.3, 433.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 233.5, 457.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 233.5, 469.7),
]
"""
code = re.sub(r'CHECKBOX_DEFINITIONS = \[.*?\]\n\n', new_checkbox + "\n\n", code, flags=re.DOTALL)

ca540 = re.search(r'def inject_ca540_nodes.*?return root', guide1, flags=re.DOTALL).group(0)
voucher = re.search(r'def inject_voucher_nodes.*?return root', guide1, flags=re.DOTALL).group(0)
schedc = re.search(r'def inject_schedule_c_detail.*?return root', guide1, flags=re.DOTALL).group(0)
schedse = re.search(r'def inject_schedule_se_detail.*?return root', guide1, flags=re.DOTALL).group(0)
form8995 = re.search(r'def inject_form8995_detail.*?return root', guide1, flags=re.DOTALL).group(0)
sched8812 = re.search(r'def inject_schedule8812_detail.*?return root', guide1, flags=re.DOTALL).group(0)

actc_comp = re.search(r'def compute_actc.*?return \{.*?\}', guide2, flags=re.DOTALL).group(0)
actc_inj = re.search(r'def inject_schedule8812_part2.*?return root', guide2, flags=re.DOTALL).group(0)
prep_names = re.search(r'PREPARER_NAMES = \[.*?\]', guide2, flags=re.DOTALL).group(0)
prep_inj = re.search(r'def inject_preparer_node.*?return root', guide2, flags=re.DOTALL).group(0)
veh_pool = re.search(r'VEHICLE_POOL = \[.*?\]\n\nLUXURY_AUTO_CAPS = \{.*?\}', guide2, flags=re.DOTALL).group(0)
veh_gen = re.search(r'def generate_vehicle_depreciation.*?return \{.*?\}', guide2, flags=re.DOTALL).group(0)
veh_inj = re.search(r'def inject_form4562_detail.*?return root', guide2, flags=re.DOTALL).group(0)

new_recompute = """def recompute_derived_fields(root, ca_withheld=0):
    def g(xpath):
        nodes = root.xpath(xpath)
        return int((nodes[0].text or "0").replace(",", "")) if nodes and nodes[0].text else 0

    w2         = g("//Return/ReturnData/IRS1040/WagesAmt")
    interest   = g("//Return/ReturnData/IRS1040/TaxableInterestAmt")
    dividends  = g("//Return/ReturnData/IRS1040/OrdinaryDividendsAmt")
    biz_income = g("//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt") - g("//Return/ReturnData/IRS1040ScheduleC/TotalExpensesAmt")
    cap_gain   = g("//Return/ReturnData/IRS1040/CapitalGainLossAmt")

    l1z  = w2
    l8   = biz_income
    l9   = l1z + interest + dividends + l8 + cap_gain

    s(root, "//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt", l1z)
    s(root, "//Return/ReturnData/IRS1040/BusinessIncomeAmt", l8)
    s(root, "//Return/ReturnData/IRS1040/TotalIncomeAmt", l9)

    se_net       = max(0, biz_income)
    se_taxable   = int(se_net * 0.9235)
    se_ss_tax    = int(min(se_taxable, 168600) * 0.124)
    se_med_tax   = int(se_taxable * 0.029)
    se_total     = se_ss_tax + se_med_tax
    
    adt_medicare_threshold = 250000
    if se_taxable > adt_medicare_threshold:
        adt_medicare = int((se_taxable - adt_medicare_threshold) * 0.009)
    else:
        adt_medicare = 0
    se_total += adt_medicare
    
    se_deduction = int(se_total * 0.50)

    l10 = se_deduction
    l11 = max(0, l9 - l10)
    s(root, "//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt", l10)
    s(root, "//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt", l11)

    qbi_income     = int(se_net * 0.9235)
    qbi_component  = int(qbi_income * 0.20)
    standard_ded   = 29200
    taxable_b4_qbi = max(0, l11 - standard_ded)
    income_limit   = int(taxable_b4_qbi * 0.20)
    qbi_deduction  = min(qbi_component, income_limit)

    l12  = standard_ded
    l13  = qbi_deduction
    l14  = l12 + l13
    l15  = max(0, l11 - l14)

    s(root, "//Return/ReturnData/IRS1040/TotalItemizedOrStandardDedAmt", l12)
    s(root, "//Return/ReturnData/IRS1040/QualifiedBusinessIncomeDedAmt", l13)
    s(root, "//Return/ReturnData/IRS1040/TotalDeductionsAmt", l14)
    s(root, "//Return/ReturnData/IRS1040/TaxableIncomeAmt", l15)

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
    l17  = 0
    l18  = l16 + l17

    dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    num_kids  = sum(1 for d in dep_nodes if (d.findtext("EligibleForChildTaxCreditInd") or "").strip().upper() in ("X", "TRUE", "1"))
    num_other = max(0, len(dep_nodes) - num_kids)
    ctc_raw   = num_kids * 2000 + num_other * 500
    phaseout_exc = max(0, l11 - 400000)
    phaseout_red = int(((phaseout_exc + 999) // 1000) * 1000 * 0.05) if phaseout_exc > 0 else 0
    ctc          = max(0, ctc_raw - phaseout_red)
    ctc_used     = min(ctc, l18)

    l24 = max(0, l18 - ctc_used) + se_total
    withheld = g("//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt")

    if withheld >= l24:
        refund = withheld - l24
        owed   = 0
    else:
        refund = 0
        owed   = l24 - withheld

    s(root, "//Return/ReturnData/IRS1040/TaxAmt", l16)
    s(root, "//Return/ReturnData/IRS1040/TotalTaxBeforeCrAndOthTaxesAmt", l18)
    s(root, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt", ctc_used)
    s(root, "//Return/ReturnData/IRS1040/TotalCreditsAmt", ctc_used)
    s(root, "//Return/ReturnData/IRS1040/TaxLessCreditsAmt", max(0, l18 - ctc_used))
    s(root, "//Return/ReturnData/IRS1040/OtherTaxesAmt", se_total)
    s(root, "//Return/ReturnData/IRS1040/TotalTaxAmt", l24)
    s(root, "//Return/ReturnData/IRS1040/TotalPaymentsAmt", withheld)
    s(root, "//Return/ReturnData/IRS1040/OverpaidAmt", refund)
    s(root, "//Return/ReturnData/IRS1040/RefundAmt", refund)
    s(root, "//Return/ReturnData/IRS1040/AmountOwedAmt", owed)

    ca_std  = 11080
    ca_agi  = l11
    ca_ti   = max(0, ca_agi - ca_std)
    ca_brackets = [
        (20824,   0.01), (49368,   0.02), (77918,   0.04),
        (108162,  0.06), (136700,  0.08), (698274,  0.093),
        (1000000, 0.103), (float("inf"), 0.123),
    ]
    ca_tax, prev = 0, 0
    for limit, rate in ca_brackets:
        seg = min(ca_ti, limit) - prev
        if seg <= 0: break
        ca_tax += int(seg * rate)
        prev = limit

    ca_exempt = (144 * 2) + (433 * len(dep_nodes))
    ca_tax_after = max(0, ca_tax - ca_exempt)
    ca_refund    = max(0, ca_withheld - ca_tax_after)
    ca_owed      = max(0, ca_tax_after - ca_withheld)

    ca_data = {
        "state_wages":   w2,
        "ca_agi":        ca_agi,
        "ca_std":        ca_std,
        "ca_ti":         ca_ti,
        "ca_tax":        ca_tax,
        "ca_tax_after":  ca_tax_after,
        "ca_withheld":   ca_withheld,
        "ca_refund":     ca_refund,
        "ca_owed":       ca_owed,
    }

    computed = {
        "se_vals": (se_net, se_taxable, se_ss_tax, se_med_tax, se_total, se_deduction),
        "qbi_vals": (qbi_income, qbi_component, l11, taxable_b4_qbi, income_limit, qbi_deduction),
        "ctc_vals": (l11, ctc_raw, ctc, ctc_used, l18),
        "ca_data": ca_data,
        "owed": owed,
        "l24": l24,
        "l18": l18,
        "ctc_used": ctc_used,
        "quarterly": int(l24/4),
    }

    return root, computed
"""
code = re.sub(r'def recompute_derived_fields.*?return root\n\n', new_recompute + "\n\n", code, flags=re.DOTALL)

new_generate = """def generate_variation(xml_path: str, source_pdf: str, output_path: str, seed: int):
    rng = random.Random(seed)
    root = load_xml(xml_path)

    def set_text(xpath: str, value: Any):
        nodes = root.xpath(xpath)
        if nodes:
            nodes[0].text = str(value)
        else:
            parts = xpath.rsplit("/", 1)
            if len(parts) == 2:
                parent_xpath, tag = parts
                parents = root.xpath(parent_xpath)
                if parents:
                    from lxml import etree
                    new_el = etree.SubElement(parents[0], tag)
                    new_el.text = str(value)

    p_first = rng.choice(FIRST_NAMES)
    p_last  = rng.choice(LAST_NAMES)
    s_first = rng.choice(FIRST_NAMES)
    s_last  = p_last
    p_ssn   = random_ssn(rng).replace("-", "")
    s_ssn   = random_ssn(rng).replace("-", "")
    city, state, zipcode = rng.choice(CITIES)
    street_num = rng.randint(100, 9999)
    street_names = ["Main St", "Oak Ave", "Maple Dr", "Cedar Ln", "Pine Rd",
                    "Elm St", "Washington Blvd", "Park Ave"]
    street = f"{street_num} {rng.choice(street_names)}"

    set_text("//Return/ReturnHeader/Filer/NameLine1Txt", f"{p_first} {p_last}")
    set_text("//Return/ReturnHeader/Filer/PrimarySSN", p_ssn)
    set_text("//Return/ReturnHeader/Filer/SpouseNameLine1Txt", f"{s_first} {s_last}")
    set_text("//Return/ReturnHeader/Filer/SpouseSSN", s_ssn)
    set_text("//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt", street)
    set_text("//Return/ReturnHeader/Filer/USAddress/CityNm", city)
    set_text("//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd", state)
    set_text("//Return/ReturnHeader/Filer/USAddress/ZIPCd", zipcode)
    
    set_text("//Return/ReturnHeader/Filer/EmailAddressTxt", f"{p_first.lower()}.{p_last.lower()}@gmail.com")
    set_text("//Return/ReturnData/IRSW2/EmployeeOccupation", rng.choice(OCCUPATIONS_P))
    set_text("//Return/ReturnData/IRSW2/SpouseOccupation", rng.choice(OCCUPATIONS_S))

    w2        = rng.randint(30000, 150000)
    gross_rev = rng.randint(30000, 200000)
    
    set_text("//Return/ReturnData/IRS1040/WagesAmt", w2)
    set_text("//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt", w2)
    set_text("//Return/ReturnData/IRSW2/WagesAmt", w2)
    set_text("//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt", gross_rev)
    set_text("//Return/ReturnData/IRS1040ScheduleC/TotalGrossReceiptsAmt", gross_rev)

    expenses = generate_schedule_c_expenses(gross_rev, rng)
    vehicle = generate_vehicle_depreciation(rng)
    expenses["L13_DepreciationSection179"] = vehicle["dep_allowed"]

    inv = generate_investment_income(w2 + expenses["L31_NetProfitLoss"], rng)
    set_text("//Return/ReturnData/IRS1040/TaxableInterestAmt", inv["L2b_TaxableInterest"])
    set_text("//Return/ReturnData/IRS1040/OrdinaryDividendsAmt", inv["L3b_OrdinaryDividends"])

    fed_wh = generate_withholding(w2, rng)
    ca_wh  = generate_ca_withholding(w2, rng)
    
    set_text("//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt", fed_wh)
    set_text("//Return/ReturnData/IRSW2/WithholdingAmt", fed_wh)

    root, computed = recompute_derived_fields(root, ca_wh)

    dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    num_kids  = sum(1 for d in dep_nodes if (d.findtext("EligibleForChildTaxCreditInd") or "").strip().upper() in ("X", "TRUE", "1"))
    num_other = max(0, len(dep_nodes) - num_kids)

    actc_vals = compute_actc(
        num_kids=num_kids, w2=w2,
        se_net=expenses["L31_NetProfitLoss"],
        ctc_used=computed["ctc_used"], l18=computed["l18"]
    )

    root = inject_schedule_c_detail(root, gross_rev, expenses)
    root = inject_schedule_se_detail(root, *computed["se_vals"])
    root = inject_form8995_detail(root, *computed["qbi_vals"])
    root = inject_schedule8812_detail(root, num_kids, num_other, *computed["ctc_vals"])
    root = inject_schedule8812_part2(root, actc_vals)
    root = inject_ca540_nodes(root, computed["ca_data"])
    root = inject_voucher_nodes(root, p_first, s_first, p_ssn, s_ssn,
                                computed["owed"], computed["quarterly"],
                                street, f"{city}, {state} {zipcode}")
    root = inject_form4562_detail(root, vehicle, section179=vehicle["dep_allowed"], total_dep=vehicle["dep_allowed"])
    root = inject_preparer_node(root, rng)

    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="wb") as tmp:
        tree = root.getroottree()
        tree.write(tmp, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        tmp_path = tmp.name

    try:
        generate_pdf(tmp_path, source_pdf, output_path)
    finally:
        os.unlink(tmp_path)
"""

code = re.sub(r'def generate_variation.*?(?=\n# ──)', new_generate + "\n\n", code, flags=re.DOTALL)

injection_functions = "\n\n".join([ca540, voucher, schedc, schedse, form8995, sched8812, actc_comp, actc_inj, prep_names, prep_inj, veh_pool, veh_gen, veh_inj])
code = code.replace("def recompute_derived_fields", injection_functions + "\n\ndef recompute_derived_fields")

with open(r"f:\combined\gana_combined\generate_tax_pdf.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Saved generate_tax_pdf.py successfully")
