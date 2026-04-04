"""
Generates completed federal and state tax return forms as PDF.

Uses ReportLab to create professional-looking forms with correct data.
Form 1040, Schedules 1-3, B, C, SE, and state forms are combined
into a single multi-page PDF per dataset.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)
from reportlab.pdfgen import canvas
from reportlab.lib.enums import TA_RIGHT

from generators.pdf_styles import (
    get_styles, format_ssn, format_ein, format_currency_int,
    DARK_BLUE, MEDIUM_BLUE, LIGHT_BLUE, HEADER_BG,
    BORDER_COLOR, WHITE, LIGHT_GRAY, BLACK, DARK_GRAY,
    GREEN, RED, MARGIN
)
from tax_engine.tax_tables import NO_INCOME_TAX_STATES


def generate_tax_forms(profile, output_path: str):
    """Generate a multi-page PDF of all completed tax forms."""
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = get_styles()
    story = []

    # Form 1040
    _add_form_1040_page(story, profile, styles)

    fed = profile.federal_results
    
    if "schedule_1" in fed:
        story.append(PageBreak())
        _add_schedule_1_page(story, profile, styles)
        
    if "schedule_2" in fed:
        story.append(PageBreak())
        _add_schedule_2_page(story, profile, styles)
        
    if "schedule_8812" in fed:
        story.append(PageBreak())
        _add_schedule_8812_page(story, profile, styles)

    # Schedule A (Itemized Deductions)
    if fed.get("deduction_type") == "itemized":
        story.append(PageBreak())
        _add_schedule_a_page(story, profile, styles)

    # Schedule B (if interest/dividends)
    if fed.get("taxable_interest", 0) > 0 or fed.get("ordinary_dividends", 0) > 0:
        story.append(PageBreak())
        _add_schedule_b_page(story, profile, styles)

    # Schedule C (if business income)
    if profile.business_income:
        story.append(PageBreak())
        _add_schedule_c_page(story, profile, styles)
        
        story.append(PageBreak())
        _add_form_4562_page(story, profile, styles)

        # Schedule SE
        if fed.get("se_tax", 0) > 0:
            story.append(PageBreak())
            _add_schedule_se_page(story, profile, styles)
            
    if "schedule_8995" in fed:
        story.append(PageBreak())
        _add_form_8995_page(story, profile, styles)
        
    if fed.get("estimated_tax_data", {}).get("required"):
        story.append(PageBreak())
        _add_estimated_tax_page(story, profile, styles)

    # State form (if applicable)
    if profile.state not in NO_INCOME_TAX_STATES:
        story.append(PageBreak())
        _add_state_form_page(story, profile, styles)

    doc.build(story)


# ===========================================================================
# Helper: Form line item row
# ===========================================================================

def _line_row(line_num, description, value, bold=False):
    """Create a table row for a form line item."""
    val_str = format_currency_int(value) if isinstance(value, (int, float)) else str(value)
    return [str(line_num), description, val_str]


def _form_header(story, styles, form_name, subtitle, tax_year, profile):
    """Add a standardized form header."""
    story.append(Paragraph(
        f"<b>{form_name}</b>", styles['DocTitle']))
    story.append(Paragraph(subtitle, styles['SmallText']))
    story.append(Spacer(1, 4))

    # Taxpayer info bar
    info_text = (f"<b>{profile.primary_first} {profile.primary_last}</b>"
                 f"  |  SSN: {format_ssn(profile.primary_ssn)}"
                 f"  |  Tax Year: {tax_year}")
    if profile.filing_status == "mfj":
        info_text += f"  |  Spouse: {profile.spouse_first} {profile.spouse_last}"

    story.append(Paragraph(info_text, styles['FieldValue']))
    story.append(HRFlowable(width="100%", thickness=2, color=MEDIUM_BLUE))
    story.append(Spacer(1, 8))


def _build_line_table(rows, styles):
    """Build a styled table from line item rows."""
    t = Table(rows, colWidths=[0.5*inch, 4.8*inch, 1.8*inch])
    style_list = [
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ALIGN', (0, 0), (0, -1), 'CENTER'),
        ('ALIGN', (2, 0), (2, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]
    # Header row
    if rows:
        style_list.extend([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ])

    t.setStyle(TableStyle(style_list))
    return t



# ===========================================================================
# Absolute Coordinate Tooling (Phase 4 Foundation)
# ===========================================================================
def _draw_text(c, x, y, text, font="Helvetica", size=10):
    c.setFont(font, size)
    c.drawString(x, y, str(text))

def _draw_currency(c, x, y, amount, font="Helvetica", size=10):
    text = format_currency_int(amount) if isinstance(amount, (int, float)) else str(amount)
    c.setFont(font, size)
    c.drawRightString(x, y, text)

def _draw_checkbox(c, x, y, checked=False, size=10):
    c.rect(x, y, size, size, stroke=1, fill=0)
    if checked:
        c.line(x, y, x + size, y + size)
        c.line(x, y + size, x + size, y)

# ===========================================================================
# Form 1040
# ===========================================================================

def _add_form_1040_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Form 1040",
                 "U.S. Individual Income Tax Return  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)

    filing_display = {"single": "Single", "mfj": "Married Filing Jointly",
                      "hoh": "Head of Household"}

    # Filing status
    story.append(Paragraph(
        f"Filing Status: <b>{filing_display.get(profile.filing_status)}</b>",
        styles['FieldValue']))
    story.append(Spacer(1, 6))

    # Address
    story.append(Paragraph(
        f"Address: {profile.address}, {profile.city}, {profile.state} {profile.zip_code}",
        styles['FieldValue']))
    story.append(Spacer(1, 6))

    # Dependents
    if profile.dependents:
        story.append(Paragraph("<b>Dependents:</b>", styles['FieldValue']))
        for dep in profile.dependents:
            story.append(Paragraph(
                f"&nbsp;&nbsp;&nbsp;&nbsp;{dep.first_name} {dep.last_name} "
                f"(SSN: {format_ssn(dep.ssn)}) — {dep.relationship}",
                styles['FieldValue']))
        story.append(Spacer(1, 6))

    # Income section
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("1", "Wages, salaries, tips (W-2)", fed["wages"]))
    rows.append(_line_row("2b", "Taxable interest", fed["taxable_interest"]))
    rows.append(_line_row("3b", "Ordinary dividends", fed["ordinary_dividends"]))

    if fed.get("business_income", 0) != 0:
        rows.append(_line_row("8", "Business income (Schedule C)", fed["business_income"]))

    rows.append(_line_row("9", "Total income", fed["total_income"]))

    if fed.get("se_tax_deduction", 0) > 0:
        rows.append(_line_row("10", "Adjustments (½ SE tax deduction)",
                              fed["se_tax_deduction"]))

    rows.append(_line_row("11", "Adjusted Gross Income (AGI)", fed["agi"]))
    
    deduction_label = "Itemized deductions (from Schedule A)" if fed.get("deduction_type") == "itemized" else "Standard deduction"
    rows.append(_line_row("12", deduction_label, fed["deduction_used"]))

    if fed.get("qbi_deduction", 0) > 0:
        rows.append(_line_row("13", "Qualified business income deduction",
                              fed["qbi_deduction"]))

    rows.append(_line_row("14", "Total deductions", fed["total_deductions"]))
    rows.append(_line_row("15", "Taxable income", fed["taxable_income"]))

    story.append(_build_line_table(rows, styles))
    story.append(Spacer(1, 10))

    # Tax computation section
    rows2 = [["Line", "Description", "Amount"]]
    rows2.append(_line_row("16", "Tax (from tax table / brackets)", fed["income_tax"]))

    if fed.get("child_tax_credit", 0) > 0:
        rows2.append(_line_row("19", "Child tax credit", fed["child_tax_credit"]))

    rows2.append(_line_row("21", "Total credits", fed["total_credits"]))
    rows2.append(_line_row("22", "Tax after credits", fed["tax_after_credits"]))

    if fed.get("other_taxes", 0) > 0:
        rows2.append(_line_row("23", "Self-employment tax (Schedule SE)",
                               fed["other_taxes"]))

    rows2.append(_line_row("24", "Total tax", fed["total_tax"]))
    rows2.append(_line_row("25", "Federal income tax withheld (W-2)",
                           fed["federal_withheld"]))
    rows2.append(_line_row("33", "Total payments", fed["total_payments"]))

    if fed.get("refund", 0) > 0:
        rows2.append(_line_row("34", "Overpaid (Refund)", fed["refund"]))
    if fed.get("amount_owed", 0) > 0:
        rows2.append(_line_row("37", "Amount you owe", fed["amount_owed"]))

    story.append(_build_line_table(rows2, styles))


# ===========================================================================
# Schedule A
# ===========================================================================

def _add_schedule_a_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Schedule A — Itemized Deductions",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)

    rows = [["Line", "Description", "Amount"]]
    
    rows.append(_line_row("5", "State and local taxes (subject to cap limit)", fed.get("salt_deduction", 0)))
    rows.append(_line_row("8", "Home mortgage interest and points", fed.get("mortgage_interest_deduction", 0)))
    
    rows.append(_line_row("17", "Total itemized deductions", fed.get("itemized_deductions", 0)))

    story.append(_build_line_table(rows, styles))
    story.append(Spacer(1, 12))


# ===========================================================================
# Schedule B
# ===========================================================================

def _add_schedule_b_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Schedule B — Interest and Ordinary Dividends",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)

    # Part I — Interest
    story.append(Paragraph("<b>Part I — Interest</b>", styles['SectionHeader']))
    int_rows = [["#", "Payer Name", "Amount"]]
    for i, ii in enumerate(profile.interest_incomes, 1):
        int_rows.append([str(i), ii.payer_name, format_currency_int(ii.amount)])
    int_rows.append(["", "Total Interest", format_currency_int(fed["taxable_interest"])])
    story.append(_build_line_table(int_rows, styles))
    story.append(Spacer(1, 12))

    # Part II — Dividends
    story.append(Paragraph("<b>Part II — Ordinary Dividends</b>", styles['SectionHeader']))
    div_rows = [["#", "Payer Name", "Amount"]]
    for i, di in enumerate(profile.dividend_incomes, 1):
        div_rows.append([str(i), di.payer_name,
                         format_currency_int(di.ordinary_dividends)])
    div_rows.append(["", "Total Dividends",
                     format_currency_int(fed["ordinary_dividends"])])
    story.append(_build_line_table(div_rows, styles))


# ===========================================================================
# Schedule C
# ===========================================================================

def _add_schedule_c_page(story, profile, styles):
    biz = profile.business_income
    _form_header(story, styles, "Schedule C — Profit or Loss from Business",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)

    # Business info
    info_rows = [
        ["Business Name", biz.business_name],
        ["Principal Business", f"{biz.activity_desc} (Code: {biz.activity_code})"],
        ["Accounting Method", "Cash"],
    ]
    t = Table(info_rows, colWidths=[2*inch, 5.2*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT_BLUE),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Income and Expenses
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("1", "Gross receipts", biz.gross_receipts))
    rows.append(_line_row("7", "Gross income", biz.gross_receipts))

    exp = biz.expenses
    if exp.advertising > 0:
        rows.append(_line_row("8", "Advertising", exp.advertising))
    if exp.car_and_truck > 0:
        rows.append(_line_row("9", "Car and truck expenses", exp.car_and_truck))
    if exp.insurance > 0:
        rows.append(_line_row("15", "Insurance", exp.insurance))
    if exp.office_expense > 0:
        rows.append(_line_row("18", "Office expense", exp.office_expense))
    if exp.supplies > 0:
        rows.append(_line_row("22", "Supplies", exp.supplies))
    if exp.utilities > 0:
        rows.append(_line_row("25", "Utilities", exp.utilities))
    if exp.other > 0:
        rows.append(_line_row("27a", "Other expenses", exp.other))
    if biz.depreciation > 0:
        rows.append(_line_row("13", "Depreciation (Form 4562)", biz.depreciation))

    rows.append(_line_row("28", "Total expenses", exp.total + biz.depreciation))
    rows.append(_line_row("31", "Net profit (or loss)", biz.net_profit))

    story.append(_build_line_table(rows, styles))


# ===========================================================================
# Schedule SE
# ===========================================================================

def _add_schedule_se_page(story, profile, styles):
    fed = profile.federal_results
    biz = profile.business_income
    _form_header(story, styles, "Schedule SE — Self-Employment Tax",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)

    se_base = round(biz.net_profit * 0.9235, 2)
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("2", "Net profit from Schedule C", biz.net_profit))
    rows.append(_line_row("3", "Combined SE income", biz.net_profit))
    rows.append(_line_row("4a", "92.35% of line 3 (SE tax base)", se_base))
    rows.append(_line_row("12", "Self-employment tax", fed["se_tax"]))
    rows.append(_line_row("13", "Deductible part of SE tax (50%)",
                          fed["se_tax_deduction"]))

    story.append(_build_line_table(rows, styles))


# ===========================================================================
# State Form
# ===========================================================================

def _add_state_form_page(story, profile, styles):
    sr = profile.state_results

    state_form_names = {
        "CA": "Form 540 — California Resident Income Tax Return",
        "NY": "Form IT-201 — New York State Resident Income Tax Return",
        "IL": "Form IL-1040 — Illinois Individual Income Tax Return",
    }

    form_name = state_form_names.get(profile.state, f"{profile.state} State Tax Return")

    _form_header(story, styles, form_name,
                 f"{profile.state} Department of Revenue",
                 profile.tax_year, profile)

    rows = [["Line", "Description", "Amount"]]

    agi_key = f"{profile.state.lower()}_agi"
    if agi_key in sr:
        rows.append(_line_row("1", f"{profile.state} Adjusted Gross Income", sr[agi_key]))

    if "standard_deduction" in sr:
        rows.append(_line_row("", "Standard deduction", sr["standard_deduction"]))

    if "exemptions" in sr:
        rows.append(_line_row("", "Exemptions", sr["exemptions"]))

    rows.append(_line_row("", "Taxable income", sr["taxable_income"]))
    rows.append(_line_row("", f"{profile.state} income tax", sr["state_tax"]))

    if sr.get("sdi", 0) > 0:
        rows.append(_line_row("", "SDI (State Disability Insurance)", sr["sdi"]))

    if sr.get("credits", 0) > 0:
        rows.append(_line_row("", "Credits", sr["credits"]))

    rows.append(_line_row("", "Total state tax", sr["total_tax"]))
    rows.append(_line_row("", "State tax withheld (payments)", sr["payments"]))

    if sr.get("refund", 0) > 0:
        rows.append(_line_row("", "Refund", sr["refund"]))
    if sr.get("amount_owed", 0) > 0:
        rows.append(_line_row("", "Amount owed", sr["amount_owed"]))

    story.append(_build_line_table(rows, styles))


# ===========================================================================
# Schedule 1 (OBBBA adjustments)
# ===========================================================================

def _add_schedule_1_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Schedule 1 — Additional Income and Adjustments to Income",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)
                 
    sch1 = fed.get("schedule_1", {})
    if not sch1: return

    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("3", "Business income or (loss)", sch1.get("line_3", 0)))
    rows.append(_line_row("10", "Additional Income", sch1.get("line_10", 0)))
    
    rows.append(_line_row("15", "Deductible part of self-employment tax", sch1.get("line_15", 0)))
    if sch1.get("line_26_obbba", 0) > 0:
        rows.append(_line_row("26", "OBBBA Adjustments (Tips, Overtime, etc.)", sch1.get("line_26_obbba", 0)))
    
    rows.append(_line_row("26z", "Total Adjustments to Income", sch1.get("line_26", 0)))
    story.append(_build_line_table(rows, styles))
    story.append(Spacer(1, 12))

# ===========================================================================
# Schedule 2, Schedule 8812, Form 8995, Form 4562, Estimated Tax
# ===========================================================================

def _add_schedule_2_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Schedule 2 — Additional Taxes",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)
    sch2 = fed.get("schedule_2", {})
    if not sch2: return
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("2", "Alternative minimum tax", sch2.get("line_3", 0)))    
    rows.append(_line_row("4", "Self-employment tax", sch2.get("line_4", 0)))
    rows.append(_line_row("11", "Additional Medicare Tax", sch2.get("line_11", 0)))
    rows.append(_line_row("12", "Net Investment Income Tax", sch2.get("line_12", 0)))
    rows.append(_line_row("21", "Total additional taxes", sch2.get("line_21", 0)))
    story.append(_build_line_table(rows, styles))

def _add_schedule_8812_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Schedule 8812 — Credits for Qualifying Children",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)
    sch = fed.get("schedule_8812", {})
    if not sch: return
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("4", "Number of qualifying children under 17", sch.get("line_4", 0)))
    rows.append(_line_row("14", "Child Tax Credit", sch.get("line_14", 0)))
    rows.append(_line_row("27", "Additional Child Tax Credit", sch.get("line_27", 0)))
    story.append(_build_line_table(rows, styles))

def _add_form_8995_page(story, profile, styles):
    fed = profile.federal_results
    _form_header(story, styles, "Form 8995 — Qualified Business Income Deduction",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)
    sch = fed.get("schedule_8995", {})
    if not sch: return
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("2", "Total qualified business income", sch.get("line_2", 0)))
    rows.append(_line_row("15", "QBI Deduction", sch.get("line_15", 0)))
    story.append(_build_line_table(rows, styles))

def _add_form_4562_page(story, profile, styles):
    if not profile.business_income or not profile.business_income.depreciable_assets: return
    _form_header(story, styles, "Form 4562 — Depreciation and Amortization",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("22", "Total depreciation", profile.business_income.depreciation))
    story.append(_build_line_table(rows, styles))

def _add_estimated_tax_page(story, profile, styles):
    fed = profile.federal_results
    est = fed.get("estimated_tax_data", {})
    if not est or not est.get("required"): return
    _form_header(story, styles, "Form 1040-ES — Estimated Tax Values",
                 "Form 1040  |  Department of the Treasury — IRS",
                 profile.tax_year, profile)
    rows = [["Line", "Description", "Amount"]]
    rows.append(_line_row("1", "Estimated Tax Required", "YES"))
    rows.append(_line_row("2", "Total Annual Required", est.get("annual_amount", 0)))
    rows.append(_line_row("3", "Per Quarter", est.get("per_quarter", 0)))
    story.append(_build_line_table(rows, styles))

