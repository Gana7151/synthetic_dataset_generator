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
import warnings
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


IRS_NS = ""   # IRS MeF XML has no namespace prefix

def xget(root, xpath, default=""):
    """Return text of first matching element, or default."""
    nodes = root.xpath(xpath)
    if nodes:
        return (nodes[0].text or "").strip()
    return default

def s(root, xpath, val):
    """Set the text of the first matching node, create if absent.

    Negative values are preserved.  Use s_nonneg() for lines that are
    legally required to be >= 0 (tax amounts, credits, payments).
    """
    nodes = root.xpath(xpath)
    if nodes:
        nodes[0].text = str(int(val))
    else:
        parts = xpath.rsplit("/", 1)
        if len(parts) == 2:
            parent_xpath, tag = parts
            parents = root.xpath(parent_xpath)
            if parents:
                from lxml import etree
                new_el = etree.SubElement(parents[0], tag)
                new_el.text = str(int(val))


def s_nonneg(root, xpath, val):
    """Like s(), but clamps to >= 0.

    Use for IRS lines that are defined as non-negative:
    TaxAmt, TotalTaxAmt, TotalCreditsAmt, TotalPaymentsAmt, RefundAmt,
    AmountOwedAmt, ChildTaxCreditAmt, and all payment/withholding lines.
    """
    s(root, xpath, max(0, int(val)))



def fmt_money(val: str) -> str:
    try:
        n = int(val)
        if n == 0:
            return ""          # don't render zero-value fields
        return f"{n:,}"
    except (ValueError, TypeError):
        return val


def fmt_money_required(val: str) -> str:
    """Like fmt_money but always renders, even for zero.
    Use on mandatory total/summary lines (AGI, TaxableIncome, TotalTax, etc.).
    """
    try:
        n = int(val)
        return f"{n:,}" if n != 0 else "0"
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

def top_to_y(top: float, page_h: float, font_size: float = 9) -> float:
    """Convert PDF 'top' coordinate (y from top) to ReportLab y (from bottom).

    Args:
        top:       y-distance from page top in PDF points (from form_structure.json).
        page_h:    Actual page height in points, read from source_page.mediabox.height.
        font_size: Nominal font size in points.

    Returns:
        ReportLab y-coordinate (distance from page bottom).
    """
    CAP_HEIGHT_RATIO = 0.72   # Helvetica cap-height ~72% of the em square
    return page_h - top - (font_size * CAP_HEIGHT_RATIO)


# Each entry: (page, xml_xpath, x, top_coord, font_size, formatter)
# top_coord is in PDF "y from top" units as observed in form_structure.json.
FIELD_DEFINITIONS = [

    # ── PAGE 1 — Form 1040 ──────────────────────────────────────────────────
    (1, "//Return/ReturnHeader/Filer/NameLine1Txt",                          39.1,  93.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/PrimarySSN",                           478.3,  93.5,  9,  fmt_ssn),
    (1, "//Return/ReturnHeader/Filer/SpouseNameLine1Txt",                    39.5, 117.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/SpouseSSN",                            478.3, 117.5,  9,  fmt_ssn),
    (1, "//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt",             39.5, 143.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/USAddress/CityNm",                      39.5, 166.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd",        206.0, 166.5,  9,  None),
    (1, "//Return/ReturnHeader/Filer/USAddress/ZIPCd",                      260.0, 166.5,  9,  None),
    # Dependents
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentFirstNm",   96.7, 381.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentLastNm",   160.0, 381.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentSSN",      290.0, 381.5,  8,  fmt_ssn),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[1]/DependentRelationshipCd", 400.0, 381.5, 8, None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentFirstNm",   96.7, 393.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentLastNm",   160.0, 393.5,  8,  None),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentSSN",      290.0, 393.5,  8,  fmt_ssn),
    (1, "//Return/ReturnData/IRS1040/DependentDetail[2]/DependentRelationshipCd", 400.0, 393.5, 8, None),
    # Income lines
    (1, "//Return/ReturnData/IRS1040/WagesAmt",                            547.1, 429.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt",             547.1, 537.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TaxableInterestAmt",                  547.1, 549.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/OrdinaryDividendsAmt",                547.1, 561.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/BusinessIncomeAmt",                   547.1, 633.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TotalIncomeAmt",                      547.1, 645.5,  9,  fmt_money_required),
    (1, "//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt",              552.7, 657.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/AdjustedGrossIncomeAmt",              547.1, 669.5,  9,  fmt_money_required),
    (1, "//Return/ReturnData/IRS1040/TotalItemizedOrStandardDedAmt",       547.1, 681.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/QualifiedBusinessIncomeDedAmt",       547.1, 693.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TotalDeductionsAmt",                  547.1, 705.5,  9,  fmt_money),
    (1, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                    547.1, 717.5,  9,  fmt_money_required),

    # ── PAGE 2 — Form 1040 (Tax, Credits, Payments) ─────────────────────────
    (2, "//Return/ReturnHeader/Filer/NameLine1Txt",                        118.3,  27.5,  8,  None),
    (2, "//Return/ReturnHeader/Filer/PrimarySSN",                          474.7,  27.5,  8,  fmt_ssn),
    (2, "//Return/ReturnData/IRS1040/TaxAmt",                              552.7,  39.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalTaxBeforeCrAndOthTaxesAmt",      552.7,  63.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",                   552.1,  75.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalCreditsAmt",                     552.1,  99.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TaxLessCreditsAmt",                   552.7, 111.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/OtherTaxesAmt",                       552.7, 123.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalTaxAmt",                         552.7, 135.5,  9,  fmt_money_required),
    (2, "//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt",                455.5, 159.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/WithholdingTaxAmt",                   552.1, 195.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",                    552.1, 291.5,  9,  fmt_money_required),
    (2, "//Return/ReturnData/IRS1040/OverpaidAmt",                         575.1, 303.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/RefundAmt",                           574.5, 315.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRS1040/AmountOwedAmt",                       552.1, 375.5,  9,  fmt_money),
    (2, "//Return/ReturnData/IRSW2/EmployeeOccupation",                    290.0, 555.5,  9,  None),
    (2, "//Return/ReturnData/IRSW2/SpouseOccupation",                      290.0, 569.5,  9,  None),
    (2, "//Return/ReturnHeader/Filer/PhoneNum",                             39.5, 583.5,  9,  None),
    (2, "//Return/ReturnHeader/Filer/EmailAddressTxt",                     200.0, 583.5,  9,  None),

    # ── PAGE 3 — Schedule 1 Part I ──────────────────────────────────────────
    (3, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (3, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",         547.0, 277.5,  9,  fmt_money),
    (3, "//Return/ReturnData/IRS1040/BusinessIncomeAmt",                   547.0, 501.5,  9,  fmt_money),

    # ── PAGE 4 — Schedule 1 Part II ─────────────────────────────────────────
    (4, "//Return/ReturnData/IRS1040ScheduleSE/DeductibleSelfEmploymentTaxAmt", 547.0, 218.5, 9, fmt_money),
    (4, "//Return/ReturnData/IRS1040/AdjustmentsToIncomeAmt",              547.0, 598.5,  9,  fmt_money),

    # ── PAGE 5 — Schedule 2 Part I ──────────────────────────────────────────
    (5, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (5, "//Return/ReturnData/IRS1040Schedule2/AlternativeMinimumTaxAmt",   547.0, 282.5,  9,  fmt_money),
    (5, "//Return/ReturnData/IRS1040Schedule2/TotalAdditionalTaxAmt",      547.0, 296.5,  9,  fmt_money),
    (5, "//Return/ReturnData/IRS1040Schedule2/SelfEmploymentTaxAmt",       547.0, 324.5,  9,  fmt_money),

    # ── PAGE 6 — Schedule 2 Part II ─────────────────────────────────────────
    (6, "//Return/ReturnData/IRS1040Schedule2/TotalOtherTaxesAmt",         547.0, 720.5,  9,  fmt_money),

    # ── PAGE 7 — Schedule B ──────────────────────────────────────────────────
    (7, "//Return/ReturnHeader/Filer/NameLine1Txt", 39.1, 75.5, 9, None),
    (7, "//Return/ReturnHeader/Filer/PrimarySSN", 478.3, 75.5, 9, fmt_ssn),
    (7, "//Return/ReturnData/IRS1040ScheduleB/InterestPayerName",           43.0, 148.5,  9,  None),
    (7, "//Return/ReturnData/IRS1040ScheduleB/InterestAmt",                547.0, 148.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/TotalInterestAmt",           547.0, 220.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/TotalInterestAmt",           547.0, 248.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/DividendPayerName",           43.0, 330.5,  9,  None),
    (7, "//Return/ReturnData/IRS1040ScheduleB/OrdinaryDividendsAmt",       547.0, 330.5,  9,  fmt_money),
    (7, "//Return/ReturnData/IRS1040ScheduleB/TotalOrdinaryDividendsAmt",  547.0, 388.5,  9,  fmt_money),

    # ── PAGE 8 — Schedule C ──────────────────────────────────────────────────
    (8, "//Return/ReturnData/IRS1040ScheduleC/ProprietorNm",                43.0,  99.5,  9,  None),
    (8, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (8, "//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityDesc", 43.0, 118.5, 9, None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityCd", 440.0, 118.5, 9, None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/BusinessName/BusinessNameLine1Txt", 43.0, 130.5, 9, None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/BusinessAddressTxt",          43.0, 142.5,  9,  None),
    (8, "//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt",    547.0, 204.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/TotalGrossReceiptsAmt",      547.0, 256.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/AdvertisingAmt",             267.0, 280.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/DepreciationAmt",            267.0, 340.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/OfficeExpensesAmt",          488.0, 280.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/RentLeaseAmt",               488.0, 304.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/SuppliesAmt",                267.0, 352.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/TaxesAndLicensesAmt",        267.0, 364.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/MealsAmt",                   488.0, 328.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/OtherBusinessExpensesAmt",   267.0, 400.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/TotalExpensesAmt",           547.0, 412.5,  9,  fmt_money),
    (8, "//Return/ReturnData/IRS1040ScheduleC/NetProfitOrLossAmt",         547.0, 448.5,  9,  fmt_money),

    # ── PAGE 9 — Schedule C Part V ───────────────────────────────────────────
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='1']/Description", 43.0, 466.5, 9, None),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='1']/Amount",     488.0, 466.5, 9, fmt_money),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='2']/Description", 43.0, 478.5, 9, None),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='2']/Amount",     488.0, 478.5, 9, fmt_money),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='3']/Description", 43.0, 490.5, 9, None),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/Item[@seq='3']/Amount",     488.0, 490.5, 9, fmt_money),
    (9, "//Return/ReturnData/IRS1040ScheduleC/Part5_OtherExpenses/L48_TotalOtherExpenses",   488.0, 550.5, 9, fmt_money),

    # ── PAGE 10 — Schedule SE ────────────────────────────────────────────────
    (10, "//Return/ReturnHeader/Filer/NameLine1Txt",                         43.0,  99.5,  9,  None),
    (10, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/NetProfitOrLossAmt",        547.0, 196.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/SETotalNetEarningsOrLossAmt", 547.0, 208.5, 9, fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L4a_Multiply_9235",         547.0, 222.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L4c_Combined",              547.0, 238.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L6_AddLines4c5b",           547.0, 280.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L9_Subtract8dFrom7",        547.0, 406.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L10_Multiply_124",          547.0, 418.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/L11_Multiply_029",          547.0, 430.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/SelfEmploymentTaxAmt",      547.0, 444.5,  9,  fmt_money),
    (10, "//Return/ReturnData/IRS1040ScheduleSE/DeductibleSelfEmploymentTaxAmt", 547.0, 460.5, 9, fmt_money),

    # ── PAGE 11 — Schedule 8812 ──────────────────────────────────────────────
    (11, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L1_AGI",                  547.0, 174.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L3_AddLines1_2d",         547.0, 210.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L4_QualifyingChildrenUnder17", 300.0, 228.5, 9, None),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L5_Multiply2000",         547.0, 228.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L6_OtherDependents",      300.0, 248.5,  9,  None),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L7_Multiply500",          547.0, 248.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L8_AddLines5_7",          547.0, 264.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L12_CreditAfterPhaseout", 547.0, 336.5,  9,  fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/L13_CreditLimitWorksheetA", 547.0, 348.5, 9, fmt_money),
    (11, "//Return/ReturnData/IRS1040Schedule8812/ChildTaxCreditAmt",       547.0, 360.5,  9,  fmt_money),

    # ── PAGE 13 — Form 8995 ──────────────────────────────────────────────────
    (13, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (13, "//Return/ReturnData/IRS8995/QBITrades/Trade[@seq='1']/n",          43.0, 145.5,  8,  None),
    (13, "//Return/ReturnData/IRS8995/QBITrades/Trade[@seq='1']/TaxpayerID", 350.0, 145.5, 8,  fmt_ssn),
    (13, "//Return/ReturnData/IRS8995/QBITrades/Trade[@seq='1']/QBIAmount",  488.0, 145.5, 8,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L2_TotalQBI",                         488.0, 187.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L4_TotalQBIAfterCarryforward",        488.0, 211.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L5_QBIComponent_20pct",               488.0, 225.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L10_QBIDeductionBeforeLimit",         488.0, 309.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L11_TaxableIncomeBeforeQBI",          488.0, 321.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L13_L11MinusL12",                     488.0, 345.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L14_IncomeLimitation",                488.0, 357.5,  9,  fmt_money),
    (13, "//Return/ReturnData/IRS8995/L15_QBIDeduction",                    488.0, 371.5,  9,  fmt_money),

    # ── PAGE 16 — Form 4562 ──────────────────────────────────────────────────
    (16, "//Return/ReturnHeader/Filer/PrimarySSN",                          478.3,  99.5,  9,  fmt_ssn),
    (16, "//Return/ReturnData/IRS4562/Section179ExpenseAmt",                488.0, 148.5,  9,  fmt_money),
    (16, "//Return/ReturnData/IRS4562/DepreciationAmt",                     488.0, 160.5,  9,  fmt_money),
    (16, "//Return/ReturnData/IRS4562/TotalDepreciationAmt",                488.0, 612.5,  9,  fmt_money),

    # ── PAGE 18 — Form 1040-V ────────────────────────────────────────────────
    (18, "//Return/ReturnData/Form1040V/PrimarySSN",                         43.0, 280.5, 10,  fmt_ssn),
    (18, "//Return/ReturnData/Form1040V/SpouseSSN",                         200.0, 280.5, 10,  fmt_ssn),
    (18, "//Return/ReturnData/Form1040V/PaymentAmount",                     400.0, 280.5, 10,  fmt_money),
    (18, "//Return/ReturnData/Form1040V/TaxpayerName",                       43.0, 350.5, 10,  None),
    (18, "//Return/ReturnData/Form1040V/Address",                            43.0, 365.5, 10,  None),
    (18, "//Return/ReturnData/Form1040V/City",                               43.0, 380.5, 10,  None),

    # ── PAGES 19–22 — Form 1040-ES Vouchers ─────────────────────────────────
    (19, "//Return/ReturnData/Form1040ES/Voucher[@seq='1']/Amount",         400.0, 280.5, 10,  fmt_money),
    (19, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),
    (20, "//Return/ReturnData/Form1040ES/Voucher[@seq='2']/Amount",         400.0, 280.5, 10,  fmt_money),
    (20, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),
    (21, "//Return/ReturnData/Form1040ES/Voucher[@seq='3']/Amount",         400.0, 280.5, 10,  fmt_money),
    (21, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),
    (22, "//Return/ReturnData/Form1040ES/Voucher[@seq='4']/Amount",         400.0, 280.5, 10,  fmt_money),
    (22, "//Return/ReturnData/Form1040ES/TaxpayerName",                      43.0, 350.5, 10,  None),

    # ── PAGE 23 — CA 540 Page 1 ──────────────────────────────────────────────
    (23, "//Return/ReturnData/CA540/Header/PrimarySSN",                     350.0,  99.5,  9,  fmt_ssn),
    (23, "//Return/ReturnData/CA540/Header/SpouseSSN",                      440.0,  99.5,  9,  fmt_ssn),
    (23, "//Return/ReturnData/CA540/Header/PrimaryFirstName",                43.0, 118.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/PrimaryLastName",                200.0, 118.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/SpouseFirstName",                 43.0, 130.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/SpouseLastName",                 200.0, 130.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/Address",                         43.0, 148.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/City",                            43.0, 162.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/State",                          290.0, 162.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Header/ZIP",                            310.0, 162.5,  9,  None),
    (23, "//Return/ReturnData/CA540/Exemptions/L7_PersonalExemption_Amount", 488.0, 376.5, 9, fmt_money),

    # ── PAGE 24 — CA 540 Page 2 ──────────────────────────────────────────────
    (24, "//Return/ReturnHeader/Filer/NameLine1Txt", 90.0, 49.1, 9, None),
    (24, "//Return/ReturnHeader/Filer/PrimarySSN", 306.0, 49.1, 9, fmt_ssn),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='1']/FirstName", 43.0, 76.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='1']/LastName",  120.0, 76.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='1']/SSN",       220.0, 76.5, 8, fmt_ssn),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='2']/FirstName", 43.0, 89.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='2']/LastName",  120.0, 89.5, 8, None),
    (24, "//Return/ReturnData/CA540/Dependents/Dependent[@seq='2']/SSN",       220.0, 89.5, 8, fmt_ssn),
    (24, "//Return/ReturnData/CA540/L11_TotalExemptionCredits",             488.0, 133.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L12_StateWages",          488.0, 152.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L13_FederalAGI",          488.0, 164.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L15_AfterSubtractions",   488.0, 188.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L16_CAAdditions",         488.0, 200.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L17_CAAdjustedGrossIncome", 488.0, 212.5, 9, fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L18_Deduction",           488.0, 234.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/TaxableIncome/L19_TaxableIncome",       488.0, 248.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L31_TaxFromTable",                  488.0, 312.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L32_ExemptionCredits",              488.0, 324.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L33_TaxAfterExemptionCredits",      488.0, 336.5,  9,  fmt_money),
    (24, "//Return/ReturnData/CA540/Tax/L35_TotalTax",                      488.0, 354.5,  9,  fmt_money),

    # ── PAGE 25 — CA 540 Page 3 ──────────────────────────────────────────────
    (25, "//Return/ReturnHeader/Filer/NameLine1Txt", 90.0, 49.1, 9, None),
    (25, "//Return/ReturnHeader/Filer/PrimarySSN", 306.0, 49.1, 9, fmt_ssn),
    (25, "//Return/ReturnData/CA540/SpecialCredits/L48_TaxAfterCredits",    488.0, 108.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/OtherTaxes/L64_TotalTax",               488.0, 192.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/Payments/L71_CAWithheld",               488.0, 218.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/Payments/L78_TotalPayments",            488.0, 290.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/UseAndPenalty/L93_PaymentsAfterISR",    488.0, 378.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/UseAndPenalty/L95_PaymentsBalance",     488.0, 404.5,  9,  fmt_money),
    (25, "//Return/ReturnData/CA540/RefundOrOwed/L96_OverpaidTax",          488.0, 430.5,  9,  fmt_money),

    # ── PAGE 26 — CA 540 Page 4 ──────────────────────────────────────────────
    (26, "//Return/ReturnHeader/Filer/NameLine1Txt", 90.0, 49.1, 9, None),
    (26, "//Return/ReturnHeader/Filer/PrimarySSN", 306.0, 49.1, 9, fmt_ssn),
    (26, "//Return/ReturnData/CA540/RefundOrOwed/L97_OverpaidTaxAvailable", 488.0,  80.5,  9,  fmt_money),
    (26, "//Return/ReturnData/CA540/RefundOrOwed/L99_RefundAvailable",      488.0, 104.5,  9,  fmt_money),

    # ── PAGE 27 — CA 540 Page 5 ──────────────────────────────────────────────
    (27, "//Return/ReturnHeader/Filer/NameLine1Txt", 90.0, 49.1, 9, None),
    (27, "//Return/ReturnHeader/Filer/PrimarySSN", 306.0, 49.1, 9, fmt_ssn),
    (27, "//Return/ReturnData/CA540/AmountOwedOrRefund/L115_Refund",        488.0, 200.5,  9,  fmt_money),

    # ── PAGE 28 — CA 540 Page 6 ──────────────────────────────────────────────
    (28, "//Return/ReturnHeader/Filer/NameLine1Txt", 93.6, 49.1, 9, None),
    (28, "//Return/ReturnHeader/Filer/PrimarySSN", 306.0, 49.1, 9, fmt_ssn),
    (28, "//Return/ReturnHeader/Filer/EmailAddressTxt",                      43.0, 490.5,  9,  None),
    (28, "//Return/ReturnHeader/Filer/PhoneNum",                            290.0, 490.5,  9,  None),

    # ── PAGE 12 — Schedule 8812 Part II-A (ACTC) ────────────────────────────
    (12, "//Return/ReturnHeader/Filer/NameLine1Txt", 154.3, 39.5,  9,  None),
    (12, "//Return/ReturnHeader/Filer/PrimarySSN", 478.3, 39.5,  9,  fmt_ssn),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L16a_NumKidsX1700",           575.1,  97.7,  9,  fmt_money),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L16b_EarnedIncome",           575.1, 133.7,  9,  fmt_money),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L17_SmallerOf16a16b",         575.1, 157.7,  9,  fmt_money),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L18a_EarnedIncome",           480.0, 169.7,  9,  fmt_money),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L19_Subtract2500",            575.1, 217.7,  9,  fmt_money),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L20_Multiply15pct",           575.1, 229.7,  9,  fmt_money),
    (12, "//Return/ReturnData/IRS1040Schedule8812/L27_AdditionalChildTaxCredit",575.1, 493.7,  9,  fmt_money),

    # ── PAGE 14 — Form 8867 Page 1 (Paid Preparer Due Diligence) ────────────
    (14, "//Return/ReturnHeader/Filer/NameLine1Txt", 46.3, 111.5,  9,  None),
    (14, "//Return/ReturnHeader/Filer/PrimarySSN", 442.3, 111.5,  9,  fmt_ssn),
    (14, "//Return/ReturnData/PreparedBy/PreparerName",                          46.3, 133.7,  9,  None),
    (14, "//Return/ReturnData/PreparedBy/PreparerPTIN",                         442.2, 133.7,  9,  None),
    (14, "//Return/ReturnData/PreparedBy/DocumentsReliedOn",                     67.9, 487.7,  9,  None),

    # ── PAGE 15 — Form 8867 Page 2 ──────────────────────────────────────────
    (15, "//Return/ReturnHeader/Filer/NameLine1Txt", 125.5, 39.5,  9,  None),
    (15, "//Return/ReturnHeader/Filer/PrimarySSN", 442.3, 39.5,  9,  fmt_ssn),

    # ── PAGE 17 — Form 4562 Page 2 (Vehicle Depreciation) ───────────────────
    (17, "//Return/ReturnHeader/Filer/NameLine1Txt", 118.3, 27.5,  9,  None),
    (17, "//Return/ReturnHeader/Filer/PrimarySSN", 435.1, 27.5,  9,  fmt_ssn),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description",            46.3, 181.7,  8,  None),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/BusinessUsePct",        192.7, 181.7,  8,  None),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/DepreciationAllowed",   467.3, 181.7,  8,  fmt_money),
    (17, "//Return/ReturnData/IRS4562/L28_TotalListedPropDep",                  442.1, 264.7,  9,  fmt_money),
    (17, "//Return/ReturnData/IRS4562/Section179ExpenseAmt",                    499.7, 276.7,  9,  fmt_money),
    (17, "//Return/ReturnData/IRS4562/L30_BusinessMiles",                       261.5, 349.7,  9,  None),
    (17, "//Return/ReturnData/IRS4562/L31_CommutingMiles",                      261.5, 361.7,  9,  None),
    (17, "//Return/ReturnData/IRS4562/L32_OtherPersonalMiles",                  261.5, 373.7,  9,  None),
    (17, "//Return/ReturnData/IRS4562/L33_TotalMiles",                          261.5, 409.7,  9,  None),
]


# ─────────────────────────────────────────────────────────────────────────────
# CHECKBOX FIELD MAP
# (page, xpath_returns_true_if_checked, x, top_coord)
# ─────────────────────────────────────────────────────────────────────────────
CHECKBOX_DEFINITIONS = [
    # Form 8867 page 1 — EIC checkbox: only tick if EIC was actually claimed
    (14, "//Return/ReturnData/IRS1040/EarnedIncomeCreditAmt",                377.5, 169.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.5, 193.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.6, 241.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.6, 313.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     532.4, 349.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.4, 463.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.4, 559.7),
    # (14, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     503.4, 571.7),
    # Form 8867 page 1 — Schedule C profit: check only if Schedule C filed
    (14, "//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt",     503.4, 619.7),
    # Form 8867 page 2 — CTC checkbox: only tick if CTC was claimed
    (15, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",                    503.5, 181.7),
    # Form 8867 page 2 — ACTC checkbox: only tick if ACTC was claimed
    (15, "//Return/ReturnData/IRS1040Schedule8812/L27_AdditionalChildTaxCredit", 503.5, 217.7),
    # (15, "//Return/ReturnData/IRS1040/TaxableIncomeAmt",                     532.4, 613.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 312.7,  97.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 521.5,  97.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 262.3, 433.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 233.5, 457.7),
    (17, "//Return/ReturnData/IRS4562/Vehicle[@seq='1']/Description", 233.5, 469.7),
]



# ─────────────────────────────────────────────────────────────────────────────
# OVERLAY ENGINE
# ─────────────────────────────────────────────────────────────────────────────




def generate_blank_form(source_pdf: str, output_path: str):
    """
    Creates blank_form.pdf by permanently redacting all Johnson data
    from the source PDF using PyMuPDF content-stream redaction.
    PyMuPDF's apply_redactions() physically removes text — not just covers it.
    Run once. The output blank_form.pdf should be committed to the repo.
    """
    import fitz  # PyMuPDF

    FULL_CLEAR_ZONES = {
        1: [
            (35,  85, 475, 105),   # primary name
            (465, 85, 612, 105),   # primary SSN
            (35, 109, 475, 128),   # spouse name
            (465,109, 612, 128),   # spouse SSN
            (35, 133, 612, 153),   # address
            (35, 157, 612, 177),   # city/state/zip
            (85, 373, 520, 410),   # dependents rows
            (530,296, 580, 313),   # digital assets checkbox
            (455,373, 480, 410),   # dependent CTC checkboxes
            (530,373, 580, 410),   # dependent credit X
            (535,420, 612, 730),   # all right-column income amounts
        ],
        2: [
            (110, 20, 475,  40),   # name header
            (465, 20, 612,  40),   # SSN header
            (450,154, 490, 174),   # withholding amount (line 25a)
            (535, 30, 612, 400),   # all tax/payment amounts
            (130,520, 445, 540),   # phone + email
            (285,547, 580, 592),   # occupation fields
            (35, 592, 612, 792),   # preparer block + signature
        ],
        3: [
            (35,  90, 612, 112),   # name header
            (535, 210, 612, 235),  # business income line
            (535, 655, 612, 680),  # total additional income
        ],
        4:  [(535, 205, 612, 615)],
        5:  [
            (35,  82, 612, 102),   # name header
            (540, 270, 612, 345),  # SE tax amounts
            (540, 442, 590, 462),  # 6,034 line
        ],
        6:  [
            (540, 568, 590, 588),  # 6,034
            (535, 710, 612, 732),  # total other taxes
        ],
        7:  [
            (35,  67, 612,  88),   # name/SSN header
            (35, 138, 612, 162),   # interest payer name
            (35, 320, 612, 344),   # dividend payer name
            (535,138, 612, 410),   # amounts
        ],
        8:  [
            (35,  90, 612, 108),   # proprietor name + SSN
            (35, 108, 612, 125),   # business description
            (35, 123, 612, 138),   # business name
            (35, 137, 612, 152),   # address
            (255,192, 612, 460),   # all income/expense amounts
            (535,550, 590, 570),   # net profit line
            (535,646, 590, 666),   # another amount line
        ],
        9:  [
            (35,  46, 612,  66),   # name/SSN header (Schedule C p2)
            (35, 456, 612, 560),   # Part V other expenses
        ],
        10: [
            (35,  90, 612, 112),   # name header
            (535, 183, 612, 475),  # SE calculation amounts
            (540, 526, 590, 546),  # deductible SE tax
        ],
        11: [
            (35, 100, 612, 125),   # name header + L1_AGI
            (535, 130, 590, 150),  # 94,803
            (535, 160, 612, 375),  # CTC calculation amounts
            (540, 394, 590, 414),  # 2,500
            (540, 442, 590, 475),  # 6,313 + 2,500
        ],
        12: [
            (145, 28, 612, 55),    # header
            (565, 85, 612, 510),   # ACTC amounts
        ],
        13: [
            (35,  90, 612, 112),   # name header
            (68, 106, 560, 126),   # EMILY JOHNSON + SSN
            (405,226, 485, 246),   # SSN in formula area
            (35, 135, 612, 160),   # business name row
            (475,135, 612, 380),   # QBI amounts
            (530,382, 585, 397),
            (530,478, 585, 498),
            (530,562, 585, 582),
            (418,658, 475, 678),
        ],
        14: [
            (35, 100, 612, 120),   # taxpayer name
            (35, 120, 612, 145),   # preparer name/PTIN
            (55, 475, 612, 500),   # documents relied on
        ],
        15: [(115, 30, 612, 55)],
        16: [
            (35,  85, 612, 120),   # name/SSN header + business name
            (475,135, 612, 175),   # depreciation amounts
        ],
        17: [
            (110, 20, 612,  42),   # name/SSN header
            (35, 170, 612, 200),   # vehicle info row
            (255,335, 612, 430),   # mileage section
        ],
        18: [(35, 50, 612, 792)],
        19: [(35, 50, 612, 792)],
        20: [(35, 50, 612, 792)],
        21: [(35, 50, 612, 792)],
        22: [(35, 50, 612, 792)],
        23: [
            (35,  85, 330, 108),   # primary name
            (330, 85, 612, 108),   # SSNs
            (35, 108, 612, 182),   # address block
        ],
        24: [
            (35,  40, 612, 135),   # header + dependent rows
            (475,145, 612, 365),   # CA income/tax amounts
        ],
        25: [
            (35,  40, 612,  72),   # header
            (475, 95, 612, 445),   # CA tax/payment amounts
        ],
        26: [
            (35,  40, 612,  72),   # header
            (475, 70, 612, 115),   # refund amounts
        ],
        27: [
            (35,  40, 612,  72),   # header
            (475,185, 612, 215),   # refund line
        ],
        28: [
            (35,  40, 612, 215),   # header + signature block
            (35, 480, 612, 510),   # phone/email
        ],
    }

    doc = fitz.open(source_pdf)
    for i in range(len(doc)):
        page_num = i + 1
        page = doc[i]
        zones = FULL_CLEAR_ZONES.get(page_num, [])
        for (x0, top, x1, bot) in zones:
            page.add_redact_annot(fitz.Rect(x0, top, x1, bot), fill=(1, 1, 1))
        if zones:
            page.apply_redactions()

    doc.save(output_path)
    print(f"Blank form written: {output_path}  ({len(doc)} pages)")





def build_overlay_page(fields_for_page: list, page_width: float, page_height: float) -> bytes:
    """
    Build a transparent PDF overlay for one page using ReportLab.
    Returns raw PDF bytes.
    """
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(page_width, page_height))
    c.setFont("Helvetica", 9)
    c.setFillColorRGB(0, 0, 0)

    for (x, top, font_size, text, is_checkbox) in fields_for_page:
        y = top_to_y(top, page_height, font_size)
        if is_checkbox:
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

    # Warn early if FIELD_DEFINITIONS references pages the source PDF doesn't have
    defined_pages = {p for p, *_ in FIELD_DEFINITIONS}
    source_page_count = len(reader.pages)
    extra_pages = {p for p in defined_pages if p > source_page_count}
    if extra_pages:
        warnings.warn(
            f"FIELD_DEFINITIONS references pages {sorted(extra_pages)} but "
            f"source PDF only has {source_page_count} pages. "
            "Those fields will be silently skipped.",
            stacklevel=2,
        )

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

        # Skip overlay for pages beyond the source PDF (already warned above)
        if page_num > source_page_count:
            writer.add_page(source_page)
            continue

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

def inject_ca540_nodes(root, ca_data: dict):
    """
    Create <CA540> element under <ReturnData> with all fields
    needed for pages 23-28 of the PDF overlay.
    ca_data keys match the XPaths used in FIELD_DEFINITIONS.
    """
    from lxml import etree

    rd = root.xpath("//Return/ReturnData")
    if not rd:
        return root
    rd = rd[0]

    # Remove existing CA540 if present (idempotent)
    for old in rd.xpath("CA540"):
        rd.remove(old)

    ca = etree.SubElement(rd, "CA540")

    def add(parent_el, tag, value):
        el = etree.SubElement(parent_el, tag)
        el.text = str(value)
        return el

    # Header — pulled from federal filer info
    hdr = etree.SubElement(ca, "Header")
    primary_ssn  = xget(root, "//Return/ReturnHeader/Filer/PrimarySSN")
    spouse_ssn   = xget(root, "//Return/ReturnHeader/Filer/SpouseSSN")
    name_line    = xget(root, "//Return/ReturnHeader/Filer/NameLine1Txt")
    spouse_name  = xget(root, "//Return/ReturnHeader/Filer/SpouseNameLine1Txt")
    # Split "First Last" into parts (best-effort)
    p_parts = name_line.split(" ", 1)
    s_parts = spouse_name.split(" ", 1)
    add(hdr, "PrimarySSN",    primary_ssn)
    add(hdr, "SpouseSSN",     spouse_ssn)
    add(hdr, "PrimaryFirstName",  p_parts[0] if p_parts else "")
    add(hdr, "PrimaryLastName",   p_parts[1] if len(p_parts) > 1 else "")
    add(hdr, "SpouseFirstName",   s_parts[0] if s_parts else "")
    add(hdr, "SpouseLastName",    s_parts[1] if len(s_parts) > 1 else "")
    add(hdr, "Address",   xget(root, "//Return/ReturnHeader/Filer/USAddress/AddressLine1Txt"))
    add(hdr, "City",      xget(root, "//Return/ReturnHeader/Filer/USAddress/CityNm"))
    add(hdr, "State",     xget(root, "//Return/ReturnHeader/Filer/USAddress/StateAbbreviationCd"))
    add(hdr, "ZIP",       xget(root, "//Return/ReturnHeader/Filer/USAddress/ZIPCd"))

    # Exemption credits (2024 FTB: $144 per person/spouse + $433 per dependent)
    dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    num_deps   = len(dep_nodes)
    personal_exempt  = 144 * 2        # MFJ: taxpayer + spouse
    dependent_exempt = 433 * num_deps
    total_exempt     = personal_exempt + dependent_exempt

    exm = etree.SubElement(ca, "Exemptions")
    add(exm, "L7_PersonalExemption_Amount", personal_exempt)

    deps_el = etree.SubElement(ca, "Dependents")
    for i, dep in enumerate(dep_nodes[:2], start=1):
        # Bug 4 fix: skip unpopulated template slots (both names empty)
        first = dep.findtext("DependentFirstNm") or ""
        last  = dep.findtext("DependentLastNm")  or ""
        ssn   = dep.findtext("DependentSSN")     or ""
        if not first and not last:
            continue    # blank template stub — not a real dependent
        d = etree.SubElement(deps_el, "Dependent")
        d.set("seq", str(i))
        add(d, "FirstName", first)
        add(d, "LastName",  last)
        add(d, "SSN",       ssn)

    add(ca, "L11_TotalExemptionCredits", total_exempt)

    # Populate computed values from ca_data dict
    ti_el  = etree.SubElement(ca, "TaxableIncome")
    tax_el = etree.SubElement(ca, "Tax")
    sc_el  = etree.SubElement(ca, "SpecialCredits")
    ot_el  = etree.SubElement(ca, "OtherTaxes")
    pay_el = etree.SubElement(ca, "Payments")
    up_el  = etree.SubElement(ca, "UseAndPenalty")
    ro_el  = etree.SubElement(ca, "RefundOrOwed")
    ao_el  = etree.SubElement(ca, "AmountOwedOrRefund")

    add(ti_el,  "L12_StateWages",            ca_data.get("state_wages", 0))
    add(ti_el,  "L13_FederalAGI",            ca_data.get("ca_agi", 0))
    add(ti_el,  "L15_AfterSubtractions",     ca_data.get("ca_agi", 0))
    add(ti_el,  "L16_CAAdditions",           0)
    add(ti_el,  "L17_CAAdjustedGrossIncome", ca_data.get("ca_agi", 0))
    add(ti_el,  "L18_Deduction",             ca_data.get("ca_std", 11080))
    add(ti_el,  "L19_TaxableIncome",         ca_data.get("ca_ti", 0))
    add(tax_el, "L31_TaxFromTable",          ca_data.get("ca_tax", 0))
    add(tax_el, "L32_ExemptionCredits",      total_exempt)
    add(tax_el, "L33_TaxAfterExemptionCredits", ca_data.get("ca_tax_after", 0))
    add(tax_el, "L35_TotalTax",              ca_data.get("ca_tax_after", 0))
    add(sc_el,  "L48_TaxAfterCredits",       ca_data.get("ca_tax_after", 0))
    add(ot_el,  "L64_TotalTax",              ca_data.get("ca_tax_after", 0))
    add(pay_el, "L71_CAWithheld",            ca_data.get("ca_withheld", 0))
    add(pay_el, "L78_TotalPayments",         ca_data.get("ca_withheld", 0))
    add(up_el,  "L93_PaymentsAfterISR",      ca_data.get("ca_withheld", 0))
    add(up_el,  "L95_PaymentsBalance",       ca_data.get("ca_withheld", 0))
    add(ro_el,  "L96_OverpaidTax",           ca_data.get("ca_refund", 0))
    add(ro_el,  "L97_OverpaidTaxAvailable",  ca_data.get("ca_refund", 0))
    add(ro_el,  "L99_RefundAvailable",       ca_data.get("ca_refund", 0))
    add(ro_el,  "L100_TaxDue",              ca_data.get("ca_owed", 0))
    add(ao_el,  "L115_Refund",              ca_data.get("ca_refund", 0))

    return root

def inject_voucher_nodes(root, p_name: str, s_name: str,
                          p_ssn: str, s_ssn: str,
                          owed: int, quarterly_payment: int,
                          address: str, city: str):
    """Inject Form1040V and Form1040ES nodes into XML."""
    from lxml import etree
    rd = root.xpath("//Return/ReturnData")[0]

    # --- 1040-V ---
    for old in rd.xpath("Form1040V"):
        rd.remove(old)
    v = etree.SubElement(rd, "Form1040V")
    def add(p, t, v_): el = etree.SubElement(p, t); el.text = str(v_); return el
    add(v, "PrimarySSN",    p_ssn)
    add(v, "SpouseSSN",     s_ssn)
    add(v, "PaymentAmount", owed)
    add(v, "TaxpayerName",  f"{p_name} & {s_name}")
    add(v, "Address",       address)
    add(v, "City",          city)

    # --- 1040-ES (4 quarterly vouchers) ---
    for old in rd.xpath("Form1040ES"):
        rd.remove(old)
    es = etree.SubElement(rd, "Form1040ES")
    add(es, "TaxpayerName", f"{p_name} & {s_name}")
    for i in range(1, 5):
        vch = etree.SubElement(es, "Voucher")
        vch.set("seq", str(i))
        amt = etree.SubElement(vch, "Amount")
        amt.text = str(quarterly_payment)

    return root

def inject_schedule_c_detail(root, gross_rev: int, expenses: dict):
    """
    Adds missing detail lines to IRS1040ScheduleC.
    expenses = output of generate_schedule_c_expenses()
    """
    from lxml import etree
    sc = root.xpath("//Return/ReturnData/IRS1040ScheduleC")
    if not sc:
        return root
    sc = sc[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(value))
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(value))

    set_or_add(sc, "GrossReceiptsOrSalesAmt",    gross_rev)
    set_or_add(sc, "TotalGrossReceiptsAmt",       gross_rev)
    set_or_add(sc, "AdvertisingAmt",              expenses.get("L8_Advertising", 0))
    set_or_add(sc, "DepreciationAmt",             expenses.get("L13_DepreciationSection179", 0))
    set_or_add(sc, "OfficeExpensesAmt",           expenses.get("L18_OfficeExpense", 0))
    set_or_add(sc, "RentLeaseAmt",                expenses.get("L20b_RentLeaseOtherProperty", 0))
    set_or_add(sc, "SuppliesAmt",                 expenses.get("L22_Supplies", 0))
    set_or_add(sc, "TaxesAndLicensesAmt",         expenses.get("L23_TaxesLicenses", 0))
    set_or_add(sc, "MealsAmt",                    expenses.get("L24b_DeductibleMeals", 0))
    set_or_add(sc, "OtherBusinessExpensesAmt",    expenses.get("L27a_OtherExpenses_Total", 0))
    set_or_add(sc, "TotalExpensesAmt",            expenses.get("L28_TotalExpensesBeforeHome", 0))
    set_or_add(sc, "NetProfitOrLossAmt",          expenses.get("L31_NetProfitLoss", 0))

    # Part V — Other Expenses detail (page 9)
    other_items = [
        ("Software Subscriptions", int(expenses.get("L27a_OtherExpenses_Total", 0) * 0.40)),
        ("Professional Development", int(expenses.get("L27a_OtherExpenses_Total", 0) * 0.35)),
        ("Bank Charges",            int(expenses.get("L27a_OtherExpenses_Total", 0) * 0.25)),
    ]
    for old in sc.xpath("Part5_OtherExpenses"):
        sc.remove(old)
    p5 = etree.SubElement(sc, "Part5_OtherExpenses")
    for i, (desc, amt) in enumerate(other_items, start=1):
        item = etree.SubElement(p5, "Item")
        item.set("seq", str(i))
        d = etree.SubElement(item, "Description"); d.text = desc
        a = etree.SubElement(item, "Amount");      a.text = str(amt)
    total_other = etree.SubElement(p5, "L48_TotalOtherExpenses")
    total_other.text = str(expenses.get("L27a_OtherExpenses_Total", 0))

    return root

def inject_schedule_se_detail(root, se_net, se_taxable, se_ss_tax, se_med_tax, se_total, se_deduction):
    from lxml import etree
    se = root.xpath("//Return/ReturnData/IRS1040ScheduleSE")
    if not se:
        return root
    se = se[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(value))   # callers clamp where needed
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(value))

    set_or_add(se, "NetProfitOrLossAmt",             se_net)
    set_or_add(se, "SETotalNetEarningsOrLossAmt",     se_net)
    set_or_add(se, "SEBaseAmt",                       se_taxable)
    set_or_add(se, "MinimumProfitForSETaxAmt",        se_taxable)
    set_or_add(se, "L4a_Multiply_9235",               se_taxable)
    set_or_add(se, "L4c_Combined",                    se_taxable)
    set_or_add(se, "L6_AddLines4c5b",                 se_taxable)
    set_or_add(se, "L9_Subtract8dFrom7",              se_taxable)
    set_or_add(se, "L10_Multiply_124",                se_ss_tax)
    set_or_add(se, "L11_Multiply_029",                se_med_tax)
    set_or_add(se, "SelfEmploymentTaxAmt",            se_total)
    set_or_add(se, "DeductibleSelfEmploymentTaxAmt",  se_deduction)

    return root

def inject_form8995_detail(root, qbi_income, qbi_component, l11, taxable_b4_qbi, income_limit, qbi_deduction):
    from lxml import etree
    f8995 = root.xpath("//Return/ReturnData/IRS8995")
    if not f8995:
        rd = root.xpath("//Return/ReturnData")[0]
        f8995_el = etree.SubElement(rd, "IRS8995")
    else:
        f8995_el = f8995[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(max(0, value)))
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(max(0, value)))

    # Business name for Trade entry (page 13 header row)
    biz_name = xget(root, "//Return/ReturnData/IRS1040ScheduleC/BusinessName/BusinessNameLine1Txt")
    biz_ein  = xget(root, "//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityCd")

    # Trade entry (seq=1)
    for old in f8995_el.xpath("QBITrades"):
        f8995_el.remove(old)
    trades = etree.SubElement(f8995_el, "QBITrades")
    trade  = etree.SubElement(trades, "Trade")
    trade.set("seq", "1")
    n  = etree.SubElement(trade, "n");            n.text  = biz_name
    tid= etree.SubElement(trade, "TaxpayerID");   tid.text= biz_ein
    qa = etree.SubElement(trade, "QBIAmount");    qa.text = str(qbi_income)

    set_or_add(f8995_el, "QualifiedBusinessIncomeAmt",    qbi_income)
    set_or_add(f8995_el, "L2_TotalQBI",                   qbi_income)
    set_or_add(f8995_el, "L4_TotalQBIAfterCarryforward",  qbi_income)
    set_or_add(f8995_el, "L5_QBIComponent_20pct",         qbi_component)
    set_or_add(f8995_el, "TotalQualifiedBusinessIncomeAmt", qbi_income)
    set_or_add(f8995_el, "L10_QBIDeductionBeforeLimit",   qbi_component)
    set_or_add(f8995_el, "L11_TaxableIncomeBeforeQBI",    l11)
    set_or_add(f8995_el, "L13_L11MinusL12",               taxable_b4_qbi)
    set_or_add(f8995_el, "L14_IncomeLimitation",          income_limit)
    set_or_add(f8995_el, "L15_QBIDeduction",              qbi_deduction)
    set_or_add(f8995_el, "QualifiedBusinessIncomeDedAmt", qbi_deduction)

    return root

def inject_schedule8812_detail(root, num_kids, num_other, l11, ctc_raw, ctc, ctc_used, l18):
    from lxml import etree
    rd  = root.xpath("//Return/ReturnData")[0]
    s8812 = root.xpath("//Return/ReturnData/IRS1040Schedule8812")
    if not s8812:
        s8812 = etree.SubElement(rd, "IRS1040Schedule8812")
    else:
        s8812 = s8812[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(value)
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(value)

    # Part I detail (page 11)
    set_or_add(s8812, "L1_AGI",                       l11)
    set_or_add(s8812, "L3_AddLines1_2d",               l11)
    set_or_add(s8812, "L4_QualifyingChildrenUnder17",  num_kids)
    set_or_add(s8812, "L5_Multiply2000",               num_kids * 2000)
    set_or_add(s8812, "L6_OtherDependents",            num_other)
    set_or_add(s8812, "L7_Multiply500",                num_other * 500)
    set_or_add(s8812, "L8_AddLines5_7",                ctc_raw)
    set_or_add(s8812, "L12_CreditAfterPhaseout",       ctc)
    set_or_add(s8812, "L13_CreditLimitWorksheetA",     l18)
    set_or_add(s8812, "L14_ChildTaxCredit",            ctc_used)
    set_or_add(s8812, "ChildTaxCreditAmt",             ctc_used)
    set_or_add(s8812, "TotalChildTaxCreditAmt",        ctc_used)
    return root

def compute_actc(num_kids: int, w2: int, se_net: int,
                 ctc_used: int, l18: int) -> dict:
    """
    Compute Additional Child Tax Credit (Schedule 8812 Part II-A).
    Only applicable when CTC is not fully absorbed by tax liability.
    
    num_kids    — qualifying children under 17
    w2          — W-2 wages
    se_net      — net self-employment profit
    ctc_used    — non-refundable CTC used (from page 11 calculation)
    l18         — total tax before credits (Form 1040 line 18)
    
    Returns dict of all Part II line values.
    """
    # Non-refundable CTC already absorbed. ACTC is the leftover.
    ctc_raw      = num_kids * 2000   # base credit before phaseout
    # Remaining credit after non-refundable absorption
    ctc_remaining = max(0, ctc_raw - ctc_used)

    # Part II-A: Earned income method (for most filers)
    earned_income = w2 + max(0, se_net)   # W-2 + SE profit (not investment)

    # L16a: num_kids × $1,700 (2024 ACTC cap per child)
    l16a = num_kids * 1700

    # L16b: earned income (used to compare against l16a cap)
    l16b = earned_income

    # L17: smaller of l16a and l16b — max potential ACTC
    l17 = min(l16a, l16b)

    if l17 == 0 or ctc_remaining == 0:
        # No ACTC possible — all lines zero
        return {k: 0 for k in [
            "l16a","l16b","l17","l18a","l18b","l19","l20","l27"]}

    # L18a: earned income (same as l16b for wage+SE earners)
    l18a = earned_income
    l18b = 0   # nontaxable combat pay — $0 for civilians

    # L19: subtract $2,500 threshold from earned income
    l19 = max(0, l18a - 2500)

    # L20: 15% of l19
    l20 = int(l19 * 0.15)

    # Part II-B (3+ children) is more complex — skip for ≤2 children
    # For ≤2 children: ACTC = min(l17, l20)
    if num_kids <= 2:
        actc = min(l17, l20)
    else:
        # Part II-B: also consider SS/Medicare taxes paid on SE income
        # (simplified — only use earned income method result)
        actc = min(l17, l20)

    # Cap ACTC at the remaining credit
    actc = min(actc, ctc_remaining)

    return {
        "l16a": l16a,
        "l16b": l16b,
        "l17":  l17,
        "l18a": l18a,
        "l18b": l18b,
        "l19":  l19,
        "l20":  l20,
        "l27":  actc,
    }

def inject_schedule8812_part2(root, actc_vals: dict):
    """
    Inject Schedule 8812 Part II (ACTC) values.
    actc_vals = output of compute_actc()
    Also updates Form 1040 line 28 and recalculates refund/owed.
    """
    from lxml import etree
    rd = root.xpath("//Return/ReturnData")[0]
    s8812 = root.xpath("//Return/ReturnData/IRS1040Schedule8812")
    if not s8812:
        s8812 = etree.SubElement(rd, "IRS1040Schedule8812")
    else:
        s8812 = s8812[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(int(value))   # callers clamp where needed
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(int(value))

    set_or_add(s8812, "L16a_NumKidsX1700",         actc_vals["l16a"])
    set_or_add(s8812, "L16b_EarnedIncome",          actc_vals["l16b"])
    set_or_add(s8812, "L17_SmallerOf16a16b",        actc_vals["l17"])
    set_or_add(s8812, "L18a_EarnedIncome",          actc_vals["l18a"])
    set_or_add(s8812, "L19_Subtract2500",           actc_vals["l19"])
    set_or_add(s8812, "L20_Multiply15pct",          actc_vals["l20"])
    set_or_add(s8812, "L27_AdditionalChildTaxCredit", actc_vals["l27"])

    # Update Form 1040 line 28 (ACTC) and recalculate payments/refund
    actc = actc_vals["l27"]
    if actc > 0:
        def g(xpath):
            nodes = root.xpath(xpath)
            return int((nodes[0].text or "0").replace(",","")) if nodes and nodes[0].text else 0

        withheld = g("//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt")
        l24      = g("//Return/ReturnData/IRS1040/TotalTaxAmt")

        # ACTC is a refundable credit — adds to payments
        set_or_add(root.xpath("//Return/ReturnData/IRS1040")[0],
                   "AdditionalChildTaxCreditAmt", actc)
        total_payments = withheld + actc
        set_or_add(root.xpath("//Return/ReturnData/IRS1040")[0],
                   "TotalPaymentsAmt", total_payments)

        refund = max(0, total_payments - l24)
        owed   = max(0, l24 - total_payments)
        set_or_add(root.xpath("//Return/ReturnData/IRS1040")[0], "OverpaidAmt", refund)
        set_or_add(root.xpath("//Return/ReturnData/IRS1040")[0], "RefundAmt", refund)
        set_or_add(root.xpath("//Return/ReturnData/IRS1040")[0], "AmountOwedAmt", owed)

    return root

PREPARER_NAMES = [
    ("Sarah Mitchell", "P87654321"), ("David Chen", "P23456789"),
    ("Rachel Torres", "P34567890"), ("Kevin O'Brien", "P45678901"),
    ("Lisa Patel",    "P56789012"), ("Mark Johnson",  "P67890123"),
    ("Anne Williams", "P78901234"), ("James Rodriguez","P89012345"),
    ("Karen Thompson","P90123456"), ("Robert Kim",    "P01234567"),
]

def inject_preparer_node(root, rng):
    """Inject synthetic preparer identity into XML."""
    from lxml import etree
    rd = root.xpath("//Return/ReturnData")[0]
    for old in rd.xpath("PreparedBy"):
        rd.remove(old)
    prep = etree.SubElement(rd, "PreparedBy")
    name, ptin = rng.choice(PREPARER_NAMES)
    def add(p, t, v): el = etree.SubElement(p, t); el.text = v; return el
    add(prep, "PreparerName", name)
    add(prep, "PreparerPTIN", ptin)
    # Documents the preparer says they relied on (for line 5 document list)
    docs = rng.choice([
        "W-2, Social Security records",
        "Birth certificates, school records",
        "Childcare records, receipts",
        "Custody agreement, birth records",
    ])
    add(prep, "DocumentsReliedOn", docs)
    return root

VEHICLE_POOL = [
    ("2021 Toyota Camry",  "01-15-2021", 28000, 4),
    ("2022 Honda Accord",  "03-01-2022", 32000, 3),
    ("2023 Ford F-150",    "06-01-2023", 45000, 2),
    ("2022 Chevrolet Equi","01-01-2022", 35000, 3),
    ("2021 Nissan Sentra", "07-01-2021", 22000, 4),
    ("2023 Tesla Model 3", "02-15-2023", 40000, 2),
    ("2022 Hyundai Elantra","05-01-2022", 24000, 3),
    ("2021 Kia Sorento",   "04-01-2021", 29000, 4),
]

LUXURY_AUTO_CAPS = {1: 12400, 2: 19800, 3: 11900, 4: 7160}  # 2024 caps

def generate_vehicle_depreciation(rng) -> dict:
    """Generate realistic business vehicle depreciation for Schedule C filer."""
    desc, placed_in_service, cost, year_num = rng.choice(VEHICLE_POOL)
    business_pct = rng.choice([100, 95, 90, 85, 80])  # % business use

    # 5-year MACRS 200DB rate for year_num
    macrs_rates  = {1: 0.20, 2: 0.32, 3: 0.192, 4: 0.1152, 5: 0.1152}
    macrs_rate   = macrs_rates.get(year_num, 0.0576)

    # Business cost basis
    business_basis = int(cost * business_pct / 100)

    # Depreciation before luxury limit
    dep_before_limit = int(business_basis * macrs_rate)

    # Apply luxury auto cap
    luxury_cap = LUXURY_AUTO_CAPS.get(year_num, 7160)
    dep_allowed = min(dep_before_limit, luxury_cap)

    # Business miles (realistic for full-time business use)
    business_miles   = rng.randint(8000, 22000)
    commute_miles    = 0     # self-employed: no commuting miles
    personal_miles   = int(business_miles * (100 - business_pct) / business_pct) if business_pct < 100 else 0
    total_miles      = business_miles + commute_miles + personal_miles

    return {
        "description":       f"{desc}  {placed_in_service}",
        "business_pct":      str(float(business_pct)),
        "dep_allowed":       dep_allowed,
        "business_miles":    business_miles,
        "commute_miles":     commute_miles,
        "personal_miles":    personal_miles,
        "total_miles":       total_miles,
        "cost":              cost,
        "business_basis":    business_basis,
    }

def inject_form4562_detail(root, vehicle: dict, section179: int, total_dep: int):
    """
    Inject Form 4562 page 2 vehicle and depreciation detail into XML.
    Bug 2 fix: find-or-create Vehicle[@seq='1'] — never duplicate.
    """
    from lxml import etree
    f4562 = root.xpath("//Return/ReturnData/IRS4562")
    if not f4562:
        rd = root.xpath("//Return/ReturnData")[0]
        f4562 = etree.SubElement(rd, "IRS4562")
    else:
        f4562 = f4562[0]

    def set_or_add(parent, tag, value):
        existing = parent.xpath(tag)
        if existing:
            existing[0].text = str(value)
        else:
            el = etree.SubElement(parent, tag)
            el.text = str(value)

    # Bug 2 fix: find existing Vehicle[@seq='1'] or create it — never duplicate
    existing_veh = f4562.xpath("Vehicle[@seq='1']")
    if existing_veh:
        veh = existing_veh[0]
    else:
        veh = etree.SubElement(f4562, "Vehicle")
        veh.set("seq", "1")

    def _veh_set(tag, val):
        el = veh.find(tag)
        if el is None:
            el = etree.SubElement(veh, tag)
        el.text = str(val)

    _veh_set("Description",        vehicle["description"])
    _veh_set("BusinessUsePct",     vehicle["business_pct"])
    _veh_set("DepreciationAllowed", vehicle["dep_allowed"])

    # Section B — vehicle usage statistics
    set_or_add(f4562, "L30_BusinessMiles",      vehicle["business_miles"])
    set_or_add(f4562, "L31_CommutingMiles",     vehicle["commute_miles"])
    set_or_add(f4562, "L32_OtherPersonalMiles", vehicle["personal_miles"])
    set_or_add(f4562, "L33_TotalMiles",         vehicle["total_miles"])
    set_or_add(f4562, "L28_TotalListedPropDep", vehicle["dep_allowed"])
    set_or_add(f4562, "DepreciationAmt",         vehicle["dep_allowed"])
    set_or_add(f4562, "TotalDepreciationAmt",    vehicle["dep_allowed"])

    return root

def recompute_derived_fields(root, ca_withheld=0):
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
    # Bug 6 fix: parameterise by filing status and tax year
    year       = int(xget(root, "//Return/ReturnHeader/TaxYr") or "2024")
    filing_cd  = xget(root, "//Return/ReturnData/IRS1040/IndividualReturnFilingStatusCd") or "2"
    filing_key = {"1": "single", "2": "mfj", "4": "hoh"}.get(str(filing_cd), "mfj")
    _TAX_PARAMS = {
        2024: {
            "mfj":    {"std_ded": 29200, "brackets": [(23200,0.10),(94300,0.12),(201050,0.22),(383900,0.24),(487450,0.32),(731200,0.35),(float("inf"),0.37)]},
            "single": {"std_ded": 14600, "brackets": [(11600,0.10),(47150,0.12),(100525,0.22),(191950,0.24),(243725,0.32),(609350,0.35),(float("inf"),0.37)]},
            "hoh":    {"std_ded": 21900, "brackets": [(16550,0.10),(63100,0.12),(100500,0.22),(191950,0.24),(243700,0.32),(609350,0.35),(float("inf"),0.37)]},
        },
        2023: {
            "mfj":    {"std_ded": 27700, "brackets": [(22000,0.10),(89075,0.12),(190750,0.22),(364200,0.24),(462500,0.32),(693750,0.35),(float("inf"),0.37)]},
            "single": {"std_ded": 13850, "brackets": [(11000,0.10),(44725,0.12),(95375,0.22),(182050,0.24),(231250,0.32),(578125,0.35),(float("inf"),0.37)]},
            "hoh":    {"std_ded": 20800, "brackets": [(15700,0.10),(59850,0.12),(95350,0.22),(182050,0.24),(231250,0.32),(578100,0.35),(float("inf"),0.37)]},
        },
    }
    params       = _TAX_PARAMS.get(year, _TAX_PARAMS[2024]).get(filing_key, _TAX_PARAMS[2024]["mfj"])
    standard_ded = params["std_ded"]
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

    def _apply_brackets(income, brackets):
        tax, prev = 0, 0
        for limit, rate in brackets:
            seg = min(income, limit) - prev
            if seg <= 0: break
            tax += int(seg * rate)
            prev = limit
        return tax

    l16  = _apply_brackets(l15, params["brackets"])
    l17  = 0
    l18  = l16 + l17


    dep_nodes = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    num_kids  = sum(1 for d in dep_nodes
                    if (d.findtext("EligibleForChildTaxCreditInd") or "").strip().upper() in ("X", "TRUE", "1"))
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

    s_nonneg(root, "//Return/ReturnData/IRS1040/TaxAmt",                     l16)
    s_nonneg(root, "//Return/ReturnData/IRS1040/TotalTaxBeforeCrAndOthTaxesAmt", l18)
    s_nonneg(root, "//Return/ReturnData/IRS1040/ChildTaxCreditAmt",           ctc_used)
    s_nonneg(root, "//Return/ReturnData/IRS1040/TotalCreditsAmt",             ctc_used)
    s_nonneg(root, "//Return/ReturnData/IRS1040/TaxLessCreditsAmt",           max(0, l18 - ctc_used))
    s_nonneg(root, "//Return/ReturnData/IRS1040/OtherTaxesAmt",               se_total)
    s_nonneg(root, "//Return/ReturnData/IRS1040/TotalTaxAmt",                 l24)
    s_nonneg(root, "//Return/ReturnData/IRS1040/TotalPaymentsAmt",            withheld)
    s_nonneg(root, "//Return/ReturnData/IRS1040/OverpaidAmt",                 refund)
    s_nonneg(root, "//Return/ReturnData/IRS1040/RefundAmt",                   refund)
    s_nonneg(root, "//Return/ReturnData/IRS1040/AmountOwedAmt",               owed)

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


BLANK_TEMPLATE_PATH = Path(__file__).parent / "blank_template.xml"

def generate_variation(source_pdf: str, output_path: str, seed: int):
    root = load_xml(str(BLANK_TEMPLATE_PATH))
    import random
    rng = random.Random(seed)

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
    # Bug 3 fix: add missing PhoneNum
    phone = f"({rng.randint(200,999)}){rng.randint(200,999)}-{rng.randint(1000,9999)}"
    set_text("//Return/ReturnHeader/Filer/PhoneNum", phone)
    set_text("//Return/ReturnData/IRSW2/EmployeeOccupation", rng.choice(OCCUPATIONS_P))
    set_text("//Return/ReturnData/IRSW2/SpouseOccupation", rng.choice(OCCUPATIONS_S))

    # W-2 identity
    set_text("//Return/ReturnData/IRSW2/EmployeeNm", f"{p_first} {p_last}")
    set_text("//Return/ReturnData/IRSW2/EmployeeSSN", p_ssn)
    set_text("//Return/ReturnData/IRSW2/EmployerEIN", f"{rng.randint(10,99)}-{rng.randint(1000000,9999999)}")
    set_text("//Return/ReturnData/IRSW2/EmployerName/BusinessNameLine1Txt", f"{p_last} {rng.choice(['Enterprises', 'Corp', 'Solutions', 'LLC'])}")

    # Schedule B payer names (Bug 3: must run before inject)
    set_text("//Return/ReturnData/IRS1040ScheduleB/InterestPayerName", rng.choice(["Wells Fargo", "Bank of America", "Chase Bank", "Ally Bank"]))
    set_text("//Return/ReturnData/IRS1040ScheduleB/DividendPayerName", rng.choice(["Charles Schwab", "Fidelity", "Vanguard", "E-Trade"]))

    # Schedule C identity fields (Bug 3: must run before inject_schedule_c_detail)
    biz_types = ["Professional Services", "Consulting", "Retail", "Management", "Freelance Design", "IT Support"]
    biz_name_suffix = rng.choice(["Consulting Services", "Solutions", "Group", "Associates", "Enterprises"])
    set_text("//Return/ReturnData/IRS1040ScheduleC/ProprietorNm", f"{p_first} {p_last}")
    set_text("//Return/ReturnData/IRS1040ScheduleC/BusinessName/BusinessNameLine1Txt", f"{p_last} {biz_name_suffix}")
    set_text("//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityDesc", rng.choice(biz_types))
    set_text("//Return/ReturnData/IRS1040ScheduleC/PrincipalBusinessActivityCd", rng.choice(["541990", "541510", "722511", "811192"]))
    set_text("//Return/ReturnData/IRS1040ScheduleC/BusinessAddressTxt", street)

    # CA-540 Headers
    set_text("//Return/ReturnData/CA540/Header/PrimaryFirstName", p_first)
    set_text("//Return/ReturnData/CA540/Header/PrimaryLastName", p_last)
    set_text("//Return/ReturnData/CA540/Header/SpouseFirstName", s_first)
    set_text("//Return/ReturnData/CA540/Header/SpouseLastName", s_last)
    set_text("//Return/ReturnData/CA540/Header/Address", street)
    set_text("//Return/ReturnData/CA540/Header/City", city)
    set_text("//Return/ReturnData/CA540/Header/State", state)
    set_text("//Return/ReturnData/CA540/Header/ZIP", zipcode)

    # Preparer block set_text (overridden later by inject_preparer_node)
    set_text("//Return/ReturnData/PreparedBy/PreparerName", f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}")
    set_text("//Return/ReturnData/PreparedBy/PreparerPTIN", f"P{rng.randint(10000000,99999999)}")

    w2        = rng.randint(30000, 150000)
    gross_rev = rng.randint(30000, 200000)

    set_text("//Return/ReturnData/IRS1040/WagesAmt", w2)
    set_text("//Return/ReturnData/IRS1040/WagesSalariesAndTipsAmt", w2)
    set_text("//Return/ReturnData/IRSW2/WagesAmt", w2)
    set_text("//Return/ReturnData/IRS1040ScheduleC/GrossReceiptsOrSalesAmt", gross_rev)
    set_text("//Return/ReturnData/IRS1040ScheduleC/TotalGrossReceiptsAmt", gross_rev)

    expenses = generate_schedule_c_expenses(gross_rev, rng)
    vehicle  = generate_vehicle_depreciation(rng)
    if "description" not in vehicle:
        vehicle["description"] = f"20{rng.randint(18,24)} {rng.choice(['Honda', 'Toyota', 'Ford'])}"
    expenses["L13_DepreciationSection179"] = vehicle["dep_allowed"]

    inv = generate_investment_income(w2 + expenses["L31_NetProfitLoss"], rng)
    set_text("//Return/ReturnData/IRS1040/TaxableInterestAmt", inv["L2b_TaxableInterest"])
    set_text("//Return/ReturnData/IRS1040/OrdinaryDividendsAmt", inv["L3b_OrdinaryDividends"])

    fed_wh = generate_withholding(w2, rng)
    ca_wh  = generate_ca_withholding(w2, rng)
    set_text("//Return/ReturnData/IRS1040/FormW2WithheldTaxAmt", fed_wh)
    set_text("//Return/ReturnData/IRSW2/WithholdingAmt", fed_wh)

    # Bug 1 fix: populate dependents BEFORE recompute so CTC is computed correctly
    target_kids = rng.choice([0, 1, 2])
    dep_nodes   = root.xpath("//Return/ReturnData/IRS1040/DependentDetail")
    for i in range(min(target_kids, len(dep_nodes))):
        c_first = rng.choice(FIRST_NAMES)
        c_ssn   = random_ssn(rng).replace("-", "")
        dep_el  = dep_nodes[i]
        def _set_sub(tag, val, _el=dep_el):
            el = _el.find(tag)
            if el is None:
                from lxml import etree
                el = etree.SubElement(_el, tag)
            el.text = str(val)
        _set_sub("DependentFirstNm",             c_first)
        _set_sub("DependentLastNm",              p_last)
        _set_sub("DependentSSN",                 c_ssn)
        _set_sub("DependentRelationshipCd",      rng.choice(["DAUGHTER", "SON"]))
        _set_sub("EligibleForChildTaxCreditInd", "X")
    num_kids  = target_kids
    num_other = max(0, len(dep_nodes) - num_kids)

    # Now recompute — will see correct dependent data (Bug 1 resolved)
    root, computed = recompute_derived_fields(root, ca_wh)


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

    import tempfile, os, shutil
    from pathlib import Path as _Path
    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False, mode="wb") as tmp:
        tree = root.getroottree()
        tree.write(tmp, xml_declaration=True, encoding="UTF-8", pretty_print=True)
        tmp_path = tmp.name

    try:
        generate_pdf(tmp_path, source_pdf, output_path)
    finally:
        os.unlink(tmp_path)

    # Bug 5 fix: save copies to pdfs_only/ and completed_form/
    filename = _Path(output_path).name
    for dest_dir in ["pdfs_only", "completed_form"]:
        os.makedirs(dest_dir, exist_ok=True)
        dest = os.path.join(dest_dir, filename)
        shutil.copy2(output_path, dest)
    print(f"  → pdfs_only/{filename}")
    print(f"  → completed_form/{filename}")



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
    parser.add_argument("--make-blank", action="store_true",
                        help="Generate blank_form.pdf from source PDF and exit")
    parser.add_argument("--variations", type=int, default=0,
                        help="If > 0, generate N synthetic variants instead of exact reproduction")
    parser.add_argument("--seed",   type=int, default=42,
                        help="Base random seed for synthetic variants")
    args = parser.parse_args()

    if args.make_blank:
        generate_blank_form(args.source, "blank_form.pdf")
        import sys
        sys.exit(0)

    if args.variations > 0:
        out_path = Path(args.out)
        out_path.mkdir(parents=True, exist_ok=True)
        for i in range(args.variations):
            variant_path = out_path / f"test_output_variant_{i+1:03d}.pdf"
            print(f"\n═══ Variant {i+1}/{args.variations} → {variant_path.name} ═══")
            generate_variation(args.source, str(variant_path), seed=args.seed + i)
    else:
        generate_pdf(str(BLANK_TEMPLATE_PATH), args.source, args.out)

if __name__ == "__main__":
    main()
