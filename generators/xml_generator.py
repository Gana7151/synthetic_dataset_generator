"""
Generates IRS MeF-style XML return data for each dataset,
matching the structure of the provided sample (Tax Return Data - Prompt.xml).
"""

import xml.etree.ElementTree as ET
from xml.dom import minidom


def generate_xml(profile, output_path: str):
    """Generate a structured XML file matching IRS e-file format.

    Args:
        profile: A fully computed TaxProfile.
        output_path: Path to write the XML file.
    """
    fed = profile.federal_results

    root = ET.Element("Return", returnVersion=f"{profile.tax_year}v5.0")

    # ------------------------------------------------------------------
    # ReturnHeader
    # ------------------------------------------------------------------
    header = ET.SubElement(root, "ReturnHeader", binaryAttachmentCnt="0")

    ET.SubElement(header, "ReturnTs").text = f"{profile.tax_year + 1}-04-15T00:00:00Z"
    ET.SubElement(header, "TaxYr").text = str(profile.tax_year)
    ET.SubElement(header, "TaxPeriodBeginDt").text = f"{profile.tax_year}-01-01"
    ET.SubElement(header, "TaxPeriodEndDt").text = f"{profile.tax_year}-12-31"

    # Self-select PIN group
    pin_grp = ET.SubElement(header, "SelfSelectPINGrp")
    ET.SubElement(pin_grp, "PrimaryBirthDt").text = profile.primary_dob
    if profile.spouse_dob:
        ET.SubElement(pin_grp, "SpouseBirthDt").text = profile.spouse_dob
    ET.SubElement(pin_grp, "PrimaryPriorYearAGIAmt").text = "0"

    ET.SubElement(header, "PrimaryPINEnteredByCd").text = "Taxpayer"
    ET.SubElement(header, "PrimarySignaturePIN").text = str(
        int(profile.primary_ssn[:5]))
    ET.SubElement(header, "PrimarySignatureDt").text = f"{profile.tax_year + 1}-04-15"

    if profile.filing_status == "mfj":
        ET.SubElement(header, "SpousePINEnteredByCd").text = "Taxpayer"
        ET.SubElement(header, "SpouseSignaturePIN").text = str(
            int(profile.spouse_ssn[:5]))
        ET.SubElement(header, "SpouseSignatureDt").text = f"{profile.tax_year + 1}-04-15"

    ET.SubElement(header, "ReturnTypeCd").text = "1040"

    # Filer
    filer = ET.SubElement(header, "Filer")
    ET.SubElement(filer, "PrimarySSN").text = profile.primary_ssn
    if profile.filing_status == "mfj":
        ET.SubElement(filer, "SpouseSSN").text = profile.spouse_ssn
    ET.SubElement(filer, "NameLine1Txt").text = f"{profile.primary_first} {profile.primary_last}"
    if profile.filing_status == "mfj":
        ET.SubElement(filer, "SpouseNameLine1Txt").text = f"{profile.spouse_first} {profile.spouse_last}"
    ET.SubElement(filer, "PrimaryNameControlTxt").text = profile.primary_first[:4].upper()
    if profile.filing_status == "mfj":
        ET.SubElement(filer, "SpouseNameControlTxt").text = profile.spouse_first[:4].upper()

    addr = ET.SubElement(filer, "USAddress")
    ET.SubElement(addr, "AddressLine1Txt").text = profile.address
    ET.SubElement(addr, "CityNm").text = profile.city
    ET.SubElement(addr, "StateAbbreviationCd").text = profile.state
    ET.SubElement(addr, "ZIPCd").text = profile.zip_code

    # ------------------------------------------------------------------
    # ReturnData
    # ------------------------------------------------------------------
    doc_count = _count_documents(profile)
    return_data = ET.SubElement(root, "ReturnData", documentCnt=str(doc_count))

    # --- IRS1040 ---
    _add_form_1040(return_data, profile)

    # --- Schedule 2 (if SE tax) ---
    if fed.get("se_tax", 0) > 0:
        _add_schedule_2(return_data, profile)

    # --- Schedule B (if interest/dividends) ---
    if fed.get("taxable_interest", 0) > 0 or fed.get("ordinary_dividends", 0) > 0:
        _add_schedule_b(return_data, profile)

    # --- Schedule 1-A (OBBBA, 2025+) ---
    if fed.get("schedule_1a_total", 0) > 0:
        _add_schedule_1a(return_data, profile)

    # --- Schedule C (if business income) ---
    if profile.business_income:
        _add_schedule_c(return_data, profile)

    # --- Schedule SE (if SE tax) ---
    if fed.get("se_tax", 0) > 0:
        _add_schedule_se(return_data, profile)

    # --- Schedule 8812 (if CTC) ---
    if fed.get("child_tax_credit", 0) > 0:
        _add_schedule_8812(return_data, profile)

    # --- Form 8995 (if QBI) ---
    if fed.get("qbi_deduction", 0) > 0:
        _add_form_8995(return_data, profile)

    # --- Form 4562 (if depreciation) ---
    if profile.business_income and profile.business_income.depreciation > 0:
        _add_form_4562(return_data, profile)

    # --- W-2(s) ---
    for i, w2 in enumerate(profile.w2_incomes):
        _add_w2(return_data, w2, i)

    # Write XML
    xml_str = ET.tostring(root, encoding='unicode', xml_declaration=False)
    pretty = minidom.parseString(xml_str).toprettyxml(indent="  ")
    # Remove extra XML declaration from minidom
    lines = pretty.split('\n')
    if lines[0].startswith('<?xml'):
        lines[0] = '<?xml version="1.0" encoding="UTF-8"?>'
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))


def _count_documents(profile) -> int:
    count = 1  # IRS1040
    fed = profile.federal_results
    if fed.get("schedule_1a_total", 0) > 0:
        count += 1  # Schedule 1-A
    if fed.get("se_tax", 0) > 0:
        count += 2  # Schedule 2 + SE
    if fed.get("taxable_interest", 0) > 0 or fed.get("ordinary_dividends", 0) > 0:
        count += 1  # Schedule B
    if profile.business_income:
        count += 1  # Schedule C
    if fed.get("child_tax_credit", 0) > 0:
        count += 1  # 8812
    if fed.get("qbi_deduction", 0) > 0:
        count += 1  # 8995
    if profile.business_income and profile.business_income.depreciation > 0:
        count += 1  # 4562
    count += len(profile.w2_incomes)  # W-2s
    return count


def _add_form_1040(parent, profile):
    fed = profile.federal_results
    filing_code = {"single": "1", "mfj": "2", "hoh": "4"}.get(
        profile.filing_status, "1")

    elem = ET.SubElement(parent, "IRS1040", documentId="1")
    ET.SubElement(elem, "IndividualReturnFilingStatusCd").text = filing_code

    if profile.filing_status == "mfj":
        ET.SubElement(elem, "SpouseSSN").text = profile.spouse_ssn

    ET.SubElement(elem, "VirtualCurAcquiredDurTYInd").text = "false"

    num_primary_spouse = 2 if profile.filing_status == "mfj" else 1
    ET.SubElement(elem, "TotalExemptPrimaryAndSpouseCnt").text = str(num_primary_spouse)
    ET.SubElement(elem, "TotalExemptionsCnt").text = str(
        num_primary_spouse + len(profile.dependents))

    # Dependents
    for dep in profile.dependents:
        dep_elem = ET.SubElement(elem, "DependentDetail")
        ET.SubElement(dep_elem, "DependentFirstNm").text = dep.first_name
        ET.SubElement(dep_elem, "DependentLastNm").text = dep.last_name
        ET.SubElement(dep_elem, "DependentNameControlTxt").text = dep.first_name[:4].upper()
        ET.SubElement(dep_elem, "DependentSSN").text = dep.ssn
        ET.SubElement(dep_elem, "DependentRelationshipCd").text = dep.relationship
        if dep.age < 17:
            ET.SubElement(dep_elem, "EligibleForChildTaxCreditInd").text = "X"

    # Income lines
    _add_amt(elem, "WagesAmt", fed["wages"], "IRSW2-0")
    _add_amt(elem, "WagesSalariesAndTipsAmt", fed["wages"])
    _add_amt(elem, "TaxExemptInterestAmt", 0, "IRS1040ScheduleB")
    _add_amt(elem, "TaxableInterestAmt", fed["taxable_interest"], "IRS1040ScheduleB")
    _add_amt(elem, "OrdinaryDividendsAmt", fed["ordinary_dividends"], "IRS1040ScheduleB")

    if profile.business_income:
        _add_amt(elem, "BusinessIncomeAmt", fed["business_income"], "IRS1040ScheduleC")

    _add_amt(elem, "TotalIncomeAmt", fed["total_income"])
    _add_amt(elem, "AdjustedGrossIncomeAmt", fed["agi"])
    _add_amt(elem, "TotalItemizedOrStandardDedAmt", fed["deduction_used"])

    if fed.get("qbi_deduction", 0) > 0:
        _add_amt(elem, "QualifiedBusinessIncomeDedAmt", fed["qbi_deduction"], "IRS8995")

    _add_amt(elem, "TotalDeductionsAmt", fed["total_deductions"])
    _add_amt(elem, "TaxableIncomeAmt", fed["taxable_income"])
    _add_amt(elem, "TaxAmt", fed["income_tax"])

    if fed.get("child_tax_credit", 0) > 0:
        _add_amt(elem, "ChildTaxCreditAmt", fed["child_tax_credit"], "IRS1040Schedule8812")

    _add_amt(elem, "TotalCreditsAmt", fed["total_credits"])
    _add_amt(elem, "TotalTaxBeforeCrAndOthTaxesAmt", fed["income_tax"])
    _add_amt(elem, "TaxLessCreditsAmt", fed["tax_after_credits"])

    if fed.get("other_taxes", 0) > 0:
        _add_amt(elem, "OtherTaxesAmt", fed["other_taxes"], "IRS1040Schedule2")
        _add_amt(elem, "TotalOtherTaxesAmt", fed["other_taxes"])

    _add_amt(elem, "TotalTaxAmt", fed["total_tax"])
    _add_amt(elem, "FormW2WithheldTaxAmt", fed["federal_withheld"])
    _add_amt(elem, "WithholdingTaxAmt", fed["federal_withheld"])
    _add_amt(elem, "TotalPaymentsAmt", fed["total_payments"])

    if fed.get("refund", 0) > 0:
        _add_amt(elem, "OverpaidAmt", fed["refund"])
        _add_amt(elem, "RefundAmt", fed["refund"])
    if fed.get("amount_owed", 0) > 0:
        _add_amt(elem, "AmountOwedAmt", fed["amount_owed"])


def _add_schedule_2(parent, profile):
    fed = profile.federal_results
    elem = ET.SubElement(parent, "IRS1040Schedule2", documentId="IRS1040Schedule2")
    _add_amt(elem, "SelfEmploymentTaxAmt", fed["se_tax"], "IRS1040ScheduleSE")
    _add_amt(elem, "TotalOtherTaxesAmt", fed["other_taxes"])


def _add_schedule_b(parent, profile):
    fed = profile.federal_results
    elem = ET.SubElement(parent, "IRS1040ScheduleB", documentId="IRS1040ScheduleB")
    _add_amt(elem, "InterestAmt", fed["taxable_interest"])
    _add_amt(elem, "TotalInterestAmt", fed["taxable_interest"])
    _add_amt(elem, "OrdinaryDividendsAmt", fed["ordinary_dividends"])
    _add_amt(elem, "TotalOrdinaryDividendsAmt", fed["ordinary_dividends"])


def _add_schedule_c(parent, profile):
    biz = profile.business_income
    elem = ET.SubElement(parent, "IRS1040ScheduleC", documentId="IRS1040ScheduleC")

    biz_name_elem = ET.SubElement(elem, "BusinessName")
    ET.SubElement(biz_name_elem, "BusinessNameLine1Txt").text = biz.business_name

    ET.SubElement(elem, "PrincipalBusinessActivityCd").text = biz.activity_code
    ET.SubElement(elem, "BusinessNameControlTxt").text = biz.business_name[:4].upper()
    ET.SubElement(elem, "PrincipalBusinessActivityDesc").text = biz.activity_desc
    ET.SubElement(elem, "MethodOfAccountingCashInd").text = "X"

    _add_amt(elem, "TotalGrossReceiptsAmt", biz.gross_receipts)
    _add_amt(elem, "GrossReceiptsOrSalesAmt", biz.gross_receipts)

    exp = biz.expenses
    if exp.advertising > 0:
        _add_amt(elem, "AdvertisingAmt", exp.advertising)
    if exp.car_and_truck > 0:
        _add_amt(elem, "CarAndTruckExpensesAmt", exp.car_and_truck)
    if exp.insurance > 0:
        _add_amt(elem, "InsuranceAmt", exp.insurance)
    if exp.office_expense > 0:
        _add_amt(elem, "OfficeExpensesAmt", exp.office_expense)
    if exp.supplies > 0:
        _add_amt(elem, "SuppliesAmt", exp.supplies)
    if exp.utilities > 0:
        _add_amt(elem, "UtilitiesAmt", exp.utilities)
    if exp.other > 0:
        _add_amt(elem, "OtherBusinessExpensesAmt", exp.other)

    _add_amt(elem, "TotalExpensesAmt", exp.total)
    _add_amt(elem, "NetProfitOrLossAmt", biz.net_profit)


def _add_schedule_se(parent, profile):
    fed = profile.federal_results
    biz = profile.business_income
    elem = ET.SubElement(parent, "IRS1040ScheduleSE", documentId="IRS1040ScheduleSE")
    _add_amt(elem, "NetProfitOrLossAmt", biz.net_profit)
    _add_amt(elem, "SETotalNetEarningsOrLossAmt", biz.net_profit)
    ET.SubElement(elem, "MinimumProfitForSETaxAmt").text = "400"

    se_base = round(biz.net_profit * 0.9235, 2)
    _add_amt(elem, "SEBaseAmt", se_base)
    _add_amt(elem, "SelfEmploymentTaxAmt", fed["se_tax"])
    _add_amt(elem, "DeductibleSelfEmploymentTaxAmt", fed["se_tax_deduction"])


def _add_schedule_8812(parent, profile):
    fed = profile.federal_results
    elem = ET.SubElement(parent, "IRS1040Schedule8812", documentId="IRS1040Schedule8812")
    for dep in profile.dependents:
        if dep.age < 17:
            child = ET.SubElement(elem, "QualifyingChildInformation")
            ET.SubElement(child, "ChildFirstAndLastName").text = f"{dep.first_name} {dep.last_name}"
            ET.SubElement(child, "ChildSSN").text = dep.ssn
    _add_amt(elem, "ChildTaxCreditAmt", fed["child_tax_credit"])
    _add_amt(elem, "TotalChildTaxCreditAmt", fed["child_tax_credit"])


def _add_form_8995(parent, profile):
    fed = profile.federal_results
    biz = profile.business_income
    elem = ET.SubElement(parent, "IRS8995", documentId="IRS8995")
    _add_amt(elem, "QualifiedBusinessIncomeAmt", biz.net_profit)
    _add_amt(elem, "TotalQualifiedBusinessIncomeAmt", biz.net_profit)
    _add_amt(elem, "QualifiedBusinessIncomeDedAmt", fed["qbi_deduction"])


def _add_form_4562(parent, profile):
    biz = profile.business_income
    elem = ET.SubElement(parent, "IRS4562", documentId="IRS4562")
    biz_name_elem = ET.SubElement(elem, "BusinessName")
    ET.SubElement(biz_name_elem, "BusinessNameLine1Txt").text = biz.business_name
    _add_amt(elem, "Section179ExpenseAmt", 0)
    _add_amt(elem, "DepreciationAmt", biz.depreciation)
    _add_amt(elem, "TotalDepreciationAmt", biz.depreciation)


def _add_w2(parent, w2, index):
    elem = ET.SubElement(parent, "IRSW2", documentId=f"IRSW2-{index}")
    ET.SubElement(elem, "EmployeeSSN").text = w2.employee_ssn
    ET.SubElement(elem, "EmployerEIN").text = w2.employer_ein
    ET.SubElement(elem, "EmployerNameControlTxt").text = w2.employer_name[:4].upper()

    emp_name = ET.SubElement(elem, "EmployerName")
    ET.SubElement(emp_name, "BusinessNameLine1Txt").text = w2.employer_name

    emp_addr = ET.SubElement(elem, "EmployerUSAddress")
    ET.SubElement(emp_addr, "AddressLine1Txt").text = w2.employer_address
    ET.SubElement(emp_addr, "CityNm").text = w2.employer_city
    ET.SubElement(emp_addr, "StateAbbreviationCd").text = w2.employer_state
    ET.SubElement(emp_addr, "ZIPCd").text = w2.employer_zip

    ET.SubElement(elem, "EmployeeNm").text = w2.employee_name

    ee_addr = ET.SubElement(elem, "EmployeeUSAddress")
    # Uses same address from profile (simplified)
    ET.SubElement(ee_addr, "AddressLine1Txt").text = w2.employer_address  # placeholder
    ET.SubElement(ee_addr, "CityNm").text = w2.employer_city
    ET.SubElement(ee_addr, "StateAbbreviationCd").text = w2.employer_state
    ET.SubElement(ee_addr, "ZIPCd").text = w2.employer_zip

    _add_amt(elem, "WagesAmt", w2.wages)
    _add_amt(elem, "WithholdingAmt", w2.federal_withheld)
    _add_amt(elem, "SocialSecurityWagesAmt", w2.ss_wages)
    _add_amt(elem, "SocialSecurityTaxAmt", w2.ss_tax)
    _add_amt(elem, "MedicareWagesAndTipsAmt", w2.medicare_wages)
    _add_amt(elem, "MedicareTaxWithheldAmt", w2.medicare_tax)
    if w2.box_7_tips > 0:
        _add_amt(elem, "SocialSecurityTipsAmt", w2.box_7_tips)
    if w2.overtime_pay > 0:
        _add_amt(elem, "OvertimePayAmt", w2.overtime_pay)
    if w2.box_14_sdi > 0:
        _add_amt(elem, "StateDisabilityInsuranceAmt", w2.box_14_sdi)
    ET.SubElement(elem, "StandardOrNonStandardCd").text = "S"


def _add_schedule_1a(parent, profile):
    """Schedule 1-A — OBBBA Deductions (2025+)."""
    fed = profile.federal_results
    s1a = fed.get("schedule_1a", {})
    elem = ET.SubElement(parent, "Schedule1A", documentId="Schedule1A")

    if s1a.get("tips", 0) > 0:
        tips_elem = ET.SubElement(elem, "TipsDeduction")
        _add_amt(tips_elem, "DeductionAmt", s1a["tips"])
    if s1a.get("overtime", 0) > 0:
        ot_elem = ET.SubElement(elem, "OvertimeDeduction")
        _add_amt(ot_elem, "DeductionAmt", s1a["overtime"])
    if s1a.get("car_loan", 0) > 0:
        cl_elem = ET.SubElement(elem, "CarLoanInterestDeduction")
        _add_amt(cl_elem, "DeductionAmt", s1a["car_loan"])
        if profile.car_loan:
            ET.SubElement(cl_elem, "VIN").text = profile.car_loan.vin
    if s1a.get("senior", 0) > 0:
        sr_elem = ET.SubElement(elem, "SeniorDeduction")
        _add_amt(sr_elem, "DeductionAmt", s1a["senior"])

    _add_amt(elem, "TotalSchedule1AAmt", s1a.get("total", 0))


def _add_amt(parent, tag, value, ref_doc_id=None):
    """Helper to add an amount element, optionally with a referenceDocumentId."""
    attribs = {}
    if ref_doc_id:
        attribs["referenceDocumentId"] = ref_doc_id
    elem = ET.SubElement(parent, tag, **attribs)
    elem.text = str(int(round(value)))
