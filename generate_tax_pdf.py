"""
generate_tax_pdf.py
====================
Synthetic Tax Return PDF Generator
Reads johnson_2024_tax_return.xml and overlays every field value
onto the original blank-form PDF using exact coordinates extracted
from form_structure.json.

Usage:
    python generate_tax_pdf.py \
        --xml    johnson_2024_tax_return.xml \
        --source 2024_Tax_Return_Documents__JOHNSON_JOHN_and_EMILY_.pdf \
        --out    output_synthetic.pdf

For batch synthetic generation pass --variations N to produce N
randomized variants (names/SSNs/amounts perturbed).

Dependencies:
    pip install pypdf pdfplumber reportlab lxml
"""

import argparse
import copy
import json
import random
import string
import sys
from pathlib import Path
from typing import Any

from lxml import etree
from pypdf import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import io


# ─────────────────────────────────────────────────────────────────────────────
# XML HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def load_xml(path: str) -> etree._Element:
    tree = etree.parse(path)
    return tree.getroot()


def xget(root: etree._Element, xpath: str, default: str = "") -> str:
    """Return text of first matching element, or default."""
    nodes = root.xpath(xpath)
    if nodes:
        return (nodes[0].text or "").strip()
    return default


def fmt_money(val: str) -> str:
    """Format raw integer string as comma-separated dollars, no dollar sign."""
    try:
        return f"{int(val):,}"
    except (ValueError, TypeError):
        return val


def fmt_ssn(val: str) -> str:
    """Ensure SSN is formatted as XXX-XX-XXXX."""
    digits = val.replace("-", "").replace(" ", "")
    if len(digits) == 9:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return val


# ─────────────────────────────────────────────────────────────────────────────
# FIELD MAP: maps (page_number, field_key) → (x, y, font_size)
# Coordinates are PDF points; y=0 is BOTTOM of page (ReportLab convention).
# Page height = 792pt for all pages (US Letter).
# These were extracted by running extract_form_structure.py and cross-
# referencing known values against their bounding boxes.
# ─────────────────────────────────────────────────────────────────────────────

PAGE_H = 792.0  # All pages are US Letter

def top_to_y(top: float, font_size: float = 9) -> float:
    """Convert PDF 'top' coordinate (y from top) to ReportLab y (from bottom)."""
    return PAGE_H - top - font_size


# Each entry: (page, xml_xpath, x, top_coord, font_size, formatter)
# top_coord is in PDF "y from top" units as observed in form_structure.json.
FIELD_DEFINITIONS = [

    # ── PAGE 1 — Form 1040 ──────────────────────────────────────────────────
    # Header / Filer info
    (1, "//Taxpayer/Primary/FirstName",          39.1,  93.5,  9,  None),
    (1, "//Taxpayer/Primary/LastName",           247.9, 93.5,  9,  None),
    (1, "//Taxpayer/Primary/SSN",                478.3, 93.5,  9,  fmt_ssn),
    (1, "//Taxpayer/Spouse/FirstName",           39.5,  117.5, 9,  None),
    (1, "//Taxpayer/Spouse/LastName",            247.9, 117.5, 9,  None),
    (1, "//Taxpayer/Spouse/SSN",                 478.3, 117.5, 9,  fmt_ssn),
    (1, "//Taxpayer/Address/Street",             39.5,  143.5, 9,  None),
    (1, "//Taxpayer/Address/City",               39.5,  166.5, 9,  None),
    (1, "//Taxpayer/Address/State",              206.0, 166.5, 9,  None),
    (1, "//Taxpayer/Address/ZIP",                260.0, 166.5, 9,  None),

    # Dependents
    (1, "//Taxpayer/Dependents/Dependent[@seq='1']/FirstName",  96.7,  381.5, 8, None),
    (1, "//Taxpayer/Dependents/Dependent[@seq='1']/LastName",   160.0, 381.5, 8, None),
    (1, "//Taxpayer/Dependents/Dependent[@seq='1']/SSN",        290.0, 381.5, 8, fmt_ssn),
    (1, "//Taxpayer/Dependents/Dependent[@seq='1']/Relationship", 400.0, 381.5, 8, None),
    (1, "//Taxpayer/Dependents/Dependent[@seq='2']/FirstName",  96.7,  393.5, 8, None),
    (1, "//Taxpayer/Dependents/Dependent[@seq='2']/LastName",   160.0, 393.5, 8, None),
    (1, "//Taxpayer/Dependents/Dependent[@seq='2']/SSN",        290.0, 393.5, 8, fmt_ssn),
    (1, "//Taxpayer/Dependents/Dependent[@seq='2']/Relationship", 400.0, 393.5, 8, None),

    # Income lines
    (1, "//Form1040/Income/L1a_WagesW2",              547.1, 429.5, 9, fmt_money),
    (1, "//Form1040/Income/L1z_TotalWages",           547.1, 537.5, 9, fmt_money),
    (1, "//Form1040/Income/L2b_TaxableInterest",      547.1, 549.5, 9, fmt_money),
    (1, "//Form1040/Income/L3b_OrdinaryDividends",    547.1, 561.5, 9, fmt_money),
    (1, "//Form1040/Income/L8_AdditionalIncomeSchedule1", 547.1, 633.5, 9, fmt_money),
    (1, "//Form1040/Income/L9_TotalIncome",           547.1, 645.5, 9, fmt_money),
    (1, "//Form1040/AGI/L10_AdjustmentsSchedule1",    552.7, 657.5, 9, fmt_money),
    (1, "//Form1040/AGI/L11_AdjustedGrossIncome",     547.1, 669.5, 9, fmt_money),
    (1, "//Form1040/TaxableIncome/L12_StandardOrItemizedDeduction", 547.1, 681.5, 9, fmt_money),
    (1, "//Form1040/TaxableIncome/L13_QBIDeductionForm8995",  547.1, 693.5, 9, fmt_money),
    (1, "//Form1040/TaxableIncome/L15_TaxableIncome",         547.1, 717.5, 9, fmt_money),

    # ── PAGE 2 — Form 1040 (Tax, Credits, Payments) ─────────────────────────
    (2, "//Taxpayer/Primary/FirstName",           39.5,  27.5,  8, None),   # header name repeat
    (2, "//Taxpayer/Primary/SSN",                474.7,  27.5,  8, fmt_ssn),
    (2, "//Form1040/TaxAndCredits/L16_Tax",              552.7, 39.5,  9, fmt_money),
    (2, "//Form1040/TaxAndCredits/L18_TotalTax",         552.7, 63.5,  9, fmt_money),
    (2, "//Form1040/TaxAndCredits/L19_ChildTaxCreditSchedule8812", 552.1, 75.5, 9, fmt_money),
    (2, "//Form1040/TaxAndCredits/L21_TotalCredits",     552.1, 99.5,  9, fmt_money),
    (2, "//Form1040/TaxAndCredits/L22_TaxAfterCredits",  552.7, 111.5, 9, fmt_money),
    (2, "//Form1040/TaxAndCredits/L23_OtherTaxesSchedule2", 552.7, 123.5, 9, fmt_money),
    (2, "//Form1040/TaxAndCredits/L24_TotalTax",         552.7, 135.5, 9, fmt_money),
    (2, "//Form1040/Payments/L25a_FederalWithheldW2",    455.5, 159.5, 9, fmt_money),
    (2, "//Form1040/Payments/L25d_TotalFederalWithheld", 552.1, 195.5, 9, fmt_money),
    (2, "//Form1040/Payments/L33_TotalPayments",         552.1, 291.5, 9, fmt_money),
    (2, "//Form1040/RefundOrOwed/L34_Overpaid",          575.1, 303.5, 9, fmt_money),
    (2, "//Form1040/RefundOrOwed/L35a_RefundAmount",     574.5, 315.5, 9, fmt_money),
    (2, "//Form1040/RefundOrOwed/L37_AmountOwed",        552.1, 375.5, 9, fmt_money),
    (2, "//Taxpayer/Primary/Occupation",                 290.0, 555.5, 9, None),
    (2, "//Taxpayer/Spouse/Occupation",                  290.0, 569.5, 9, None),
    (2, "//Taxpayer/Primary/Phone",                      39.5,  583.5, 9, None),
    (2, "//Taxpayer/Primary/Email",                      200.0, 583.5, 9, None),

    # ── PAGE 3 — Schedule 1 Part I ──────────────────────────────────────────
    (3, "//Taxpayer/Primary/SSN",                       478.3, 99.5,  9, fmt_ssn),
    (3, "//Schedule1/Part1_AdditionalIncome/L3_BusinessIncomeScheduleC", 547.0, 277.5, 9, fmt_money),
    (3, "//Schedule1/Part1_AdditionalIncome/L10_TotalAdditionalIncome",  547.0, 501.5, 9, fmt_money),

    # ── PAGE 4 — Schedule 1 Part II ─────────────────────────────────────────
    (4, "//Schedule1/Part2_AdjustmentsToIncome/L15_SelfEmploymentTaxDeduction", 547.0, 218.5, 9, fmt_money),
    (4, "//Schedule1/Part2_AdjustmentsToIncome/L26_TotalAdjustments",           547.0, 598.5, 9, fmt_money),

    # ── PAGE 5 — Schedule 2 Part I ──────────────────────────────────────────
    (5, "//Taxpayer/Primary/SSN",                478.3, 99.5,  9, fmt_ssn),
    (5, "//Schedule2/Part1_Tax/L1z_TotalAdditions",     547.0, 268.5, 9, fmt_money),
    (5, "//Schedule2/Part1_Tax/L2_AlternativeMinimumTax", 547.0, 282.5, 9, fmt_money),
    (5, "//Schedule2/Part1_Tax/L3_TotalTaxPart1",        547.0, 296.5, 9, fmt_money),
    (5, "//Schedule2/Part2_OtherTaxes/L4_SelfEmploymentTax", 547.0, 324.5, 9, fmt_money),

    # ── PAGE 6 — Schedule 2 Part II (continued) ─────────────────────────────
    (6, "//Schedule2/Part2_OtherTaxes/L21_TotalOtherTaxes", 547.0, 720.5, 9, fmt_money),

    # ── PAGE 7 — Schedule B ─────────────────────────────────────────────────
    (7, "//Taxpayer/Primary/SSN",                 478.3, 99.5, 9, fmt_ssn),
    (7, "//ScheduleB/Part1_Interest/InterestItems/Item[@seq='1']/Payer",   43.0, 148.5, 9, None),
    (7, "//ScheduleB/Part1_Interest/InterestItems/Item[@seq='1']/Amount",  547.0, 148.5, 9, fmt_money),
    (7, "//ScheduleB/Part1_Interest/L2_TotalInterest",                     547.0, 220.5, 9, fmt_money),
    (7, "//ScheduleB/Part1_Interest/L4_TaxableInterest",                   547.0, 248.5, 9, fmt_money),
    (7, "//ScheduleB/Part2_OrdinaryDividends/DividendItems/Item[@seq='1']/Payer",  43.0, 330.5, 9, None),
    (7, "//ScheduleB/Part2_OrdinaryDividends/DividendItems/Item[@seq='1']/Amount", 547.0, 330.5, 9, fmt_money),
    (7, "//ScheduleB/Part2_OrdinaryDividends/L6_TotalOrdinaryDividends",           547.0, 388.5, 9, fmt_money),

    # ── PAGE 8 — Schedule C Part I & II ─────────────────────────────────────
    (8, "//ScheduleC/Header/ProprietorName",         43.0,  99.5, 9, None),
    (8, "//ScheduleC/Header/ProprietorSSN",         478.3,  99.5, 9, fmt_ssn),
    (8, "//ScheduleC/Header/BusinessDescription",    43.0, 118.5, 9, None),
    (8, "//ScheduleC/Header/PrincipalBusinessCode", 440.0, 118.5, 9, None),
    (8, "//ScheduleC/Header/BusinessName",           43.0, 130.5, 9, None),
    (8, "//ScheduleC/Header/BusinessAddress",        43.0, 142.5, 9, None),
    (8, "//ScheduleC/Part1_Income/L1_GrossReceipts", 547.0, 204.5, 9, fmt_money),
    (8, "//ScheduleC/Part1_Income/L7_GrossIncome",   547.0, 256.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L8_Advertising",      267.0, 280.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L13_DepreciationSection179",  267.0, 340.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L18_OfficeExpense",           488.0, 280.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L20b_RentLeaseOtherProperty", 488.0, 304.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L22_Supplies",                267.0, 352.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L23_TaxesLicenses",           267.0, 364.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L24b_DeductibleMeals",        488.0, 328.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L27a_OtherExpenses_Total",    267.0, 400.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L28_TotalExpensesBeforeHome", 547.0, 412.5, 9, fmt_money),
    (8, "//ScheduleC/Part2_Expenses/L31_NetProfitLoss",           547.0, 448.5, 9, fmt_money),

    # ── PAGE 9 — Schedule C Part V (Other Expenses) ──────────────────────────
    (9, "//ScheduleC/Part5_OtherExpenses/Item[@seq='1']/Description",  43.0, 466.5, 9, None),
    (9, "//ScheduleC/Part5_OtherExpenses/Item[@seq='1']/Amount",      488.0, 466.5, 9, fmt_money),
    (9, "//ScheduleC/Part5_OtherExpenses/Item[@seq='2']/Description",  43.0, 478.5, 9, None),
    (9, "//ScheduleC/Part5_OtherExpenses/Item[@seq='2']/Amount",      488.0, 478.5, 9, fmt_money),
    (9, "//ScheduleC/Part5_OtherExpenses/Item[@seq='3']/Description",  43.0, 490.5, 9, None),
    (9, "//ScheduleC/Part5_OtherExpenses/Item[@seq='3']/Amount",      488.0, 490.5, 9, fmt_money),
    (9, "//ScheduleC/Part5_OtherExpenses/L48_TotalOtherExpenses",     488.0, 550.5, 9, fmt_money),

    # ── PAGE 10 — Schedule SE ────────────────────────────────────────────────
    (10, "//ScheduleSE/PersonName",                     43.0,  99.5, 9, None),
    (10, "//ScheduleSE/PersonSSN",                     478.3,  99.5, 9, fmt_ssn),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L2_NetProfitScheduleC", 547.0, 196.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L3_CombinedLines",      547.0, 208.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L4a_Multiply_9235",     547.0, 222.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L4c_Combined",          547.0, 238.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L6_AddLines4c5b",       547.0, 280.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L9_Subtract8dFrom7",    547.0, 406.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L10_Multiply_124",      547.0, 418.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L11_Multiply_029",      547.0, 430.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L12_SelfEmploymentTax", 547.0, 444.5, 9, fmt_money),
    (10, "//ScheduleSE/Part1_SelfEmploymentTax/L13_DeductionHalfSETax",547.0, 460.5, 9, fmt_money),

    # ── PAGE 11 — Schedule 8812 ──────────────────────────────────────────────
    (11, "//Taxpayer/Primary/SSN",                 478.3,  99.5, 9, fmt_ssn),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L1_AGI",                 547.0, 174.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L3_AddLines1_2d",        547.0, 210.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L4_QualifyingChildrenUnder17", 300.0, 228.5, 9, None),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L5_Multiply2000",        547.0, 228.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L6_OtherDependents",     300.0, 248.5, 9, None),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L7_Multiply500",         547.0, 248.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L8_AddLines5_7",         547.0, 264.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L12_CreditAfterPhaseout",547.0, 336.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L13_CreditLimitWorksheetA",547.0, 348.5, 9, fmt_money),
    (11, "//Schedule8812/Part1_ChildTaxCredit/L14_ChildTaxCredit",     547.0, 360.5, 9, fmt_money),

    # ── PAGE 13 — Form 8995 ──────────────────────────────────────────────────
    (13, "//Taxpayer/Primary/SSN",                  478.3,  99.5, 9, fmt_ssn),
    (13, "//Form8995/QBITrades/Trade[@seq='1']/n",     43.0, 145.5, 8, None),
    (13, "//Form8995/QBITrades/Trade[@seq='1']/TaxpayerID", 350.0, 145.5, 8, fmt_ssn),
    (13, "//Form8995/QBITrades/Trade[@seq='1']/QBIAmount",  488.0, 145.5, 8, fmt_money),
    (13, "//Form8995/L2_TotalQBI",           488.0, 187.5, 9, fmt_money),
    (13, "//Form8995/L4_TotalQBIAfterCarryforward", 488.0, 211.5, 9, fmt_money),
    (13, "//Form8995/L5_QBIComponent_20pct", 488.0, 225.5, 9, fmt_money),
    (13, "//Form8995/L10_QBIDeductionBeforeLimit",  488.0, 309.5, 9, fmt_money),
    (13, "//Form8995/L11_TaxableIncomeBeforeQBI",   488.0, 321.5, 9, fmt_money),
    (13, "//Form8995/L13_L11MinusL12",       488.0, 345.5, 9, fmt_money),
    (13, "//Form8995/L14_IncomeLimitation",  488.0, 357.5, 9, fmt_money),
    (13, "//Form8995/L15_QBIDeduction",      488.0, 371.5, 9, fmt_money),

    # ── PAGE 16 — Form 4562 ──────────────────────────────────────────────────
    (16, "//Taxpayer/Primary/SSN",               478.3,  99.5, 9, fmt_ssn),
    (16, "//Form4562/Part1_Section179/L1_MaxAmount",         488.0, 148.5, 9, fmt_money),
    (16, "//Form4562/Part1_Section179/L2_TotalCostSection179", 488.0, 160.5, 9, fmt_money),
    (16, "//Form4562/Part4_Summary/L22_TotalDepreciation",   488.0, 612.5, 9, fmt_money),

    # ── PAGE 18 — Form 1040-V ────────────────────────────────────────────────
    (18, "//Form1040V/PrimarySSN",           43.0,  280.5, 10, fmt_ssn),
    (18, "//Form1040V/SpouseSSN",           200.0,  280.5, 10, fmt_ssn),
    (18, "//Form1040V/PaymentAmount",       400.0,  280.5, 10, fmt_money),
    (18, "//Form1040V/TaxpayerName",         43.0,  350.5, 10, None),
    (18, "//Taxpayer/Address/Street",        43.0,  365.5, 10, None),
    (18, "//Taxpayer/Address/City",          43.0,  380.5, 10, None),

    # ── PAGES 19-22 — Form 1040-ES Vouchers ─────────────────────────────────
    (19, "//Form1040ES/Voucher[@seq='1']/Amount",   400.0, 280.5, 10, fmt_money),
    (19, "//Form1040ES/TaxpayerName",                43.0, 350.5, 10, None),
    (20, "//Form1040ES/Voucher[@seq='2']/Amount",   400.0, 280.5, 10, fmt_money),
    (20, "//Form1040ES/TaxpayerName",                43.0, 350.5, 10, None),
    (21, "//Form1040ES/Voucher[@seq='3']/Amount",   400.0, 280.5, 10, fmt_money),
    (21, "//Form1040ES/TaxpayerName",                43.0, 350.5, 10, None),
    (22, "//Form1040ES/Voucher[@seq='4']/Amount",   400.0, 280.5, 10, fmt_money),
    (22, "//Form1040ES/TaxpayerName",                43.0, 350.5, 10, None),

    # ── PAGE 23 — CA 540 Page 1 ──────────────────────────────────────────────
    (23, "//CA540/Header/PrimarySSN",          350.0, 99.5,  9, fmt_ssn),
    (23, "//CA540/Header/SpouseSSN",           440.0, 99.5,  9, fmt_ssn),
    (23, "//CA540/Header/PrimaryFirstName",     43.0, 118.5, 9, None),
    (23, "//CA540/Header/PrimaryLastName",     200.0, 118.5, 9, None),
    (23, "//CA540/Header/SpouseFirstName",      43.0, 130.5, 9, None),
    (23, "//CA540/Header/SpouseLastName",      200.0, 130.5, 9, None),
    (23, "//CA540/Header/Address",              43.0, 148.5, 9, None),
    (23, "//CA540/Header/City",                 43.0, 162.5, 9, None),
    (23, "//CA540/Header/State",               290.0, 162.5, 9, None),
    (23, "//CA540/Header/ZIP",                 310.0, 162.5, 9, None),
    (23, "//CA540/Exemptions/L7_PersonalExemption_Amount", 488.0, 376.5, 9, fmt_money),

    # ── PAGE 24 — CA 540 Page 2 ──────────────────────────────────────────────
    (24, "//Taxpayer/Primary/SSN",              478.3,  27.5, 9, fmt_ssn),
    (24, "//CA540/Dependents/Dependent[@seq='1']/FirstName",  43.0, 76.5, 8, None),
    (24, "//CA540/Dependents/Dependent[@seq='1']/LastName",  120.0, 76.5, 8, None),
    (24, "//CA540/Dependents/Dependent[@seq='1']/SSN",       220.0, 76.5, 8, fmt_ssn),
    (24, "//CA540/Dependents/Dependent[@seq='2']/FirstName",  43.0, 89.5, 8, None),
    (24, "//CA540/Dependents/Dependent[@seq='2']/LastName",  120.0, 89.5, 8, None),
    (24, "//CA540/Dependents/Dependent[@seq='2']/SSN",       220.0, 89.5, 8, fmt_ssn),
    (24, "//CA540/Dependents/L10_DependentExemption_Amount", 488.0, 115.5, 9, fmt_money),
    (24, "//CA540/L11_TotalExemptionCredits",                488.0, 133.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L12_StateWages",             488.0, 152.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L13_FederalAGI",             488.0, 164.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L15_AfterSubtractions",      488.0, 188.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L16_CAAdditions",            488.0, 200.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L17_CAAdjustedGrossIncome",  488.0, 212.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L18_Deduction",              488.0, 234.5, 9, fmt_money),
    (24, "//CA540/TaxableIncome/L19_TaxableIncome",          488.0, 248.5, 9, fmt_money),
    (24, "//CA540/Tax/L31_TaxFromTable",                     488.0, 312.5, 9, fmt_money),
    (24, "//CA540/Tax/L32_ExemptionCredits",                 488.0, 324.5, 9, fmt_money),
    (24, "//CA540/Tax/L33_TaxAfterExemptionCredits",         488.0, 336.5, 9, fmt_money),
    (24, "//CA540/Tax/L35_TotalTax",                         488.0, 354.5, 9, fmt_money),

    # ── PAGE 25 — CA 540 Page 3 ──────────────────────────────────────────────
    (25, "//Taxpayer/Primary/SSN",              478.3,  27.5, 9, fmt_ssn),
    (25, "//CA540/SpecialCredits/L48_TaxAfterCredits",    488.0, 108.5, 9, fmt_money),
    (25, "//CA540/OtherTaxes/L64_TotalTax",               488.0, 192.5, 9, fmt_money),
    (25, "//CA540/Payments/L71_CAWithheld",               488.0, 218.5, 9, fmt_money),
    (25, "//CA540/Payments/L78_TotalPayments",            488.0, 290.5, 9, fmt_money),
    (25, "//CA540/UseAndPenalty/L93_PaymentsAfterISR",    488.0, 378.5, 9, fmt_money),
    (25, "//CA540/UseAndPenalty/L95_PaymentsBalance",     488.0, 404.5, 9, fmt_money),
    (25, "//CA540/RefundOrOwed/L96_OverpaidTax",          488.0, 430.5, 9, fmt_money),

    # ── PAGE 26 — CA 540 Page 4 ──────────────────────────────────────────────
    (26, "//Taxpayer/Primary/SSN",              478.3,  27.5, 9, fmt_ssn),
    (26, "//CA540/RefundOrOwed/L97_OverpaidTaxAvailable", 488.0,  80.5, 9, fmt_money),
    (26, "//CA540/RefundOrOwed/L99_RefundAvailable",      488.0, 104.5, 9, fmt_money),

    # ── PAGE 27 — CA 540 Page 5 ──────────────────────────────────────────────
    (27, "//Taxpayer/Primary/SSN",              478.3,  27.5, 9, fmt_ssn),
    (27, "//CA540/AmountOwedOrRefund/L115_Refund",        488.0, 200.5, 9, fmt_money),

    # ── PAGE 28 — CA 540 Page 6 ──────────────────────────────────────────────
    (28, "//Taxpayer/Primary/SSN",              478.3,  27.5, 9, fmt_ssn),
    (28, "//Taxpayer/Primary/Email",             43.0, 490.5, 9, None),
    (28, "//Taxpayer/Primary/Phone",            290.0, 490.5, 9, None),
]


# ─────────────────────────────────────────────────────────────────────────────
# CHECKBOX FIELD MAP
# (page, xpath_returns_true_if_checked, x, top_coord)
# ─────────────────────────────────────────────────────────────────────────────
CHECKBOX_DEFINITIONS = [
    # Form 1040 page 1 - Filing status MFJ box
    (1, "//Form1040/FilingStatus/Status[text()='MFJ']", 43.0, 248.5),
    # Digital assets = No
    (1, "//Form1040/DigitalAssets[text()='false']",     300.0, 204.5),
]


# ─────────────────────────────────────────────────────────────────────────────
# OVERLAY ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def build_overlay_page(fields_for_page: list, page_width: float, page_height: float) -> bytes:
    """
    Build a transparent PDF overlay for one page using ReportLab.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))

    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0, 0, 0)  # black ink

    for (x, top, font_size, text, is_checkbox) in fields_for_page:
        # Convert top (y from top) → ReportLab y (y from bottom)
        y = page_height - top - font_size

        if is_checkbox:
            # Draw X for checked checkboxes
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x, y, "X")
            c.setFont("Helvetica", 9)
        else:
            c.setFont("Helvetica", font_size)
            c.drawString(x, y, text)

    c.save()
    buf.seek(0)
    return buf.read()


def overlay_on_page(source_page, overlay_bytes):
    """Merge overlay PDF onto source page using pypdf."""
    from pypdf import PdfReader as _R
    overlay_reader = _R(io.BytesIO(overlay_bytes))
    overlay_page = overlay_reader.pages[0]
    source_page.merge_page(overlay_page)
    return source_page


def generate_pdf(xml_path: str, source_pdf: str, output_path: str):
    """Main generation function. Reads XML, overlays fields onto source PDF."""
    print(f"[1/4] Loading XML: {xml_path}")
    root = load_xml(xml_path)

    print(f"[2/4] Loading source PDF: {source_pdf}")
    reader = PdfReader(source_pdf)
    writer = PdfWriter()

    # Build a lookup: page_number → list of (x, top, font_size, text, is_checkbox)
    page_fields: dict[int, list] = {}

    # Text fields
    for (page, xpath, x, top, font_size, formatter) in FIELD_DEFINITIONS:
        value = xget(root, xpath)
        if not value:
            continue
        if formatter:
            value = formatter(value)
        page_fields.setdefault(page, []).append((x, top, font_size, value, False))

    # Checkbox fields
    for (page, xpath, x, top) in CHECKBOX_DEFINITIONS:
        nodes = root.xpath(xpath)
        if nodes:
            page_fields.setdefault(page, []).append((x, top, 10, "X", True))

    print(f"[3/4] Overlaying {sum(len(v) for v in page_fields.values())} fields across {len(page_fields)} pages...")

    for i, source_page in enumerate(reader.pages):
        page_num = i + 1
        pw = float(source_page.mediabox.width)
        ph = float(source_page.mediabox.height)

        if page_num in page_fields:
            overlay_bytes = build_overlay_page(page_fields[page_num], pw, ph)
            source_page = overlay_on_page(source_page, overlay_bytes)

        writer.add_page(source_page)

    print(f"[4/4] Writing output: {output_path}")
    with open(output_path, "wb") as f:
        writer.write(f)
    print(f"Done. {len(reader.pages)} pages written.")


# ─────────────────────────────────────────────────────────────────────────────
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
    """Generate realistic correlated expense lines from gross revenue."""
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
    """
    Enforce IRS arithmetic identities across the XML tree.
    Call this after perturbing any leaf values.
    """
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
    """Generate a randomised synthetic variant from the base XML using the Quant Model."""
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
            print(f"\n═══ Variant {i+1}/{args.variations} → {variant_path} ═══")
            generate_variation(args.xml, args.source, variant_path, seed=args.seed + i)
    else:
        generate_pdf(args.xml, args.source, args.out)


if __name__ == "__main__":
    main()
