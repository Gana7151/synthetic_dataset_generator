"""
Generates the Executive Summary PDF for each dataset.

Shows a professional breakdown of federal and state tax results
including AGI, taxable income, total tax, payments, and refund/balance due.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.colors import HexColor
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_RIGHT, TA_CENTER

from generators.pdf_styles import (
    get_styles, format_ssn, format_currency_int,
    DARK_BLUE, MEDIUM_BLUE, LIGHT_BLUE, HEADER_BG,
    BORDER_COLOR, WHITE, LIGHT_GRAY, BLACK, GREEN, RED, MARGIN
)
from tax_engine.tax_tables import NO_INCOME_TAX_STATES


def generate_executive_summary(profile, output_path: str):
    """Generate an Executive Summary PDF."""
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = get_styles()
    story = []
    fed = profile.federal_results
    sr = profile.state_results

    # Title
    story.append(Paragraph("Executive Summary", styles['DocTitle']))
    story.append(Paragraph(
        f"Tax Year {profile.tax_year} — Individual Income Tax Return",
        styles['SmallText']))
    story.append(Spacer(1, 4))
    story.append(HRFlowable(width="100%", thickness=2, color=MEDIUM_BLUE))
    story.append(Spacer(1, 16))

    # Taxpayer info
    name = f"{profile.primary_first} {profile.primary_last}"
    if profile.filing_status == "mfj":
        name += f" & {profile.spouse_first} {profile.spouse_last}"

    filing_display = {"single": "Single", "mfj": "Married Filing Jointly",
                      "hoh": "Head of Household"}

    info_data = [
        ["Taxpayer Name", name],
        ["Filing Status", filing_display.get(profile.filing_status)],
        ["Address", f"{profile.address}, {profile.city}, {profile.state} {profile.zip_code}"],
        ["Tax Year", str(profile.tax_year)],
        ["Dependents", str(len(profile.dependents)) if profile.dependents else "None"],
    ]
    t_info = Table(info_data, colWidths=[2*inch, 5.2*inch])
    t_info.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), LIGHT_BLUE),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t_info)
    story.append(Spacer(1, 20))

    # ================================================================
    # Federal Summary
    # ================================================================
    story.append(Paragraph("Federal Tax Summary", styles['SectionHeader']))
    story.append(Spacer(1, 4))

    fed_data = [
        ["Item", "Amount"],
        ["Total Income", format_currency_int(fed["total_income"])],
        ["Adjustments", format_currency_int(fed.get("total_adjustments", 0))],
        ["Adjusted Gross Income (AGI)", format_currency_int(fed["agi"])],
        ["Deductions (Standard)", format_currency_int(fed["deduction_used"])],
    ]

    if fed.get("qbi_deduction", 0) > 0:
        fed_data.append(["QBI Deduction (Sec. 199A)",
                         format_currency_int(fed["qbi_deduction"])])

    # OBBBA Schedule 1-A deductions (2025+)
    s1a = fed.get("schedule_1a", {})
    if s1a.get("total", 0) > 0:
        fed_data.append(["── OBBBA Schedule 1-A Deductions ──", ""])
        if s1a.get("tips", 0) > 0:
            fed_data.append(["    Tips Deduction (Part II)",
                             format_currency_int(s1a["tips"])])
        if s1a.get("overtime", 0) > 0:
            fed_data.append(["    Overtime Deduction (Part III)",
                             format_currency_int(s1a["overtime"])])
        if s1a.get("car_loan", 0) > 0:
            fed_data.append(["    Car Loan Interest (Part IV)",
                             format_currency_int(s1a["car_loan"])])
        if s1a.get("senior", 0) > 0:
            fed_data.append(["    Senior Deduction (Part V)",
                             format_currency_int(s1a["senior"])])
        fed_data.append(["    Schedule 1-A Total",
                         format_currency_int(s1a["total"])])

    fed_data.extend([
        ["Taxable Income", format_currency_int(fed["taxable_income"])],
        ["Income Tax", format_currency_int(fed["income_tax"])],
    ])

    if fed.get("child_tax_credit", 0) > 0:
        fed_data.append(["Child Tax Credit",
                         f"({format_currency_int(fed['child_tax_credit'])})"])

    if fed.get("se_tax", 0) > 0:
        fed_data.append(["Self-Employment Tax",
                         format_currency_int(fed["se_tax"])])

    if fed.get("medicare_surtax", 0) > 0:
        fed_data.append(["Medicare Surtax (0.9%)",
                         format_currency_int(fed["medicare_surtax"])])

    # AMT (Guide §6 — un-gated for 2024+)
    if fed.get("amt_excess", 0) > 0:
        fed_data.append(["Alternative Minimum Tax (AMT Excess)",
                         format_currency_int(fed["amt_excess"])])

    fed_data.extend([
        ["Total Tax", format_currency_int(fed["total_tax"])],
        ["Total Payments (Withheld)", format_currency_int(fed["total_payments"])],
    ])

    if fed.get("refund", 0) > 0:
        fed_data.append(["REFUND DUE", format_currency_int(fed["refund"])])
    elif fed.get("amount_owed", 0) > 0:
        fed_data.append(["BALANCE DUE", format_currency_int(fed["amount_owed"])])

    fed_data.append(["Effective Tax Rate", f"{fed.get('effective_rate', 0):.1f}%"])

    t_fed = Table(fed_data, colWidths=[4.5*inch, 2.7*inch])
    fed_styles = [
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]

    # Highlight refund/balance due row
    last_row = len(fed_data) - 2  # second to last row (before effective rate)
    if fed.get("refund", 0) > 0:
        fed_styles.append(('BACKGROUND', (0, last_row), (-1, last_row),
                          HexColor("#c6f6d5")))
        fed_styles.append(('FONTNAME', (0, last_row), (-1, last_row),
                          'Helvetica-Bold'))
        fed_styles.append(('TEXTCOLOR', (0, last_row), (-1, last_row), GREEN))
    elif fed.get("amount_owed", 0) > 0:
        fed_styles.append(('BACKGROUND', (0, last_row), (-1, last_row),
                          HexColor("#fed7d7")))
        fed_styles.append(('FONTNAME', (0, last_row), (-1, last_row),
                          'Helvetica-Bold'))
        fed_styles.append(('TEXTCOLOR', (0, last_row), (-1, last_row), RED))

    t_fed.setStyle(TableStyle(fed_styles))
    story.append(t_fed)
    story.append(Spacer(1, 20))

    # ================================================================
    # State Summary
    # ================================================================
    story.append(Paragraph(f"State Tax Summary — {profile.state}",
                           styles['SectionHeader']))
    story.append(Spacer(1, 4))

    if profile.state in NO_INCOME_TAX_STATES:
        story.append(Paragraph(
            f"<b>{profile.state}</b> does not impose a state income tax. "
            "No state return is required.",
            styles['FieldValue']))
    else:
        state_data = [
            ["Item", "Amount"],
            [f"{profile.state} Adjusted Gross Income",
             format_currency_int(sr.get("taxable_income", 0) +
                                 sr.get("standard_deduction", 0) +
                                 sr.get("exemptions", 0))],
        ]

        # OBBBA add-back (Guide §10 — non-conforming states)
        if sr.get("obbba_addback", 0) > 0:
            state_data.append(["OBBBA Schedule 1-A Add-back",
                               format_currency_int(sr["obbba_addback"])])

        if "standard_deduction" in sr:
            state_data.append(["Standard Deduction",
                               format_currency_int(sr["standard_deduction"])])
        if sr.get("exemptions", 0) > 0:
            state_data.append(["Exemptions",
                               format_currency_int(sr["exemptions"])])

        state_data.extend([
            ["Taxable Income", format_currency_int(sr["taxable_income"])],
            [f"{profile.state} Income Tax", format_currency_int(sr["state_tax"])],
        ])

        if sr.get("sdi", 0) > 0:
            state_data.append(["SDI Withheld", format_currency_int(sr["sdi"])])

        # State-specific credits
        if sr.get("caleitc", 0) > 0:
            state_data.append(["CalEITC", format_currency_int(sr["caleitc"])])
        if sr.get("yctc", 0) > 0:
            state_data.append(["Young Child Tax Credit", format_currency_int(sr["yctc"])])
        if sr.get("il_eitc", 0) > 0:
            state_data.append([f"IL EITC ({sr.get('il_eitc_rate', 0)*100:.0f}% of Federal)",
                               format_currency_int(sr["il_eitc"])])
        if sr.get("credits", 0) > 0 and not sr.get("caleitc", 0) and not sr.get("il_eitc", 0):
            state_data.append(["Credits", format_currency_int(sr["credits"])])

        state_data.extend([
            ["Total State Tax", format_currency_int(sr["total_tax"])],
            ["State Tax Withheld", format_currency_int(sr["payments"])],
        ])

        # NY IT-2105 voucher flag
        if sr.get("requires_it2105", False):
            state_data.append(["IT-2105 Est. Tax Vouchers", "REQUIRED"])

        if sr.get("refund", 0) > 0:
            state_data.append(["STATE REFUND DUE",
                               format_currency_int(sr["refund"])])
        elif sr.get("amount_owed", 0) > 0:
            state_data.append(["STATE BALANCE DUE",
                               format_currency_int(sr["amount_owed"])])

        t_state = Table(state_data, colWidths=[4.5*inch, 2.7*inch])
        state_styles = [
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]
        t_state.setStyle(TableStyle(state_styles))
        story.append(t_state)

    # Footer
    story.append(Spacer(1, 30))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<i>Generated for Dataset {profile.dataset_id} | "
        f"Complexity Level {profile.level} | "
        f"{profile.state} — Tax Year {profile.tax_year}</i>",
        styles['SmallText']))
    story.append(Paragraph(
        "<i>All data is synthetic. Not for official filing.</i>",
        styles['SmallText']))

    doc.build(story)
