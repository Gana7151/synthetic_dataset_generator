"""
Generates the Client Summary / Intake Questionnaire PDF.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable)
from reportlab.lib.enums import TA_LEFT, TA_CENTER
from generators.pdf_styles import (
    get_styles, format_ssn, format_currency_int,
    DARK_BLUE, MEDIUM_BLUE, LIGHT_BLUE, HEADER_BG,
    BORDER_COLOR, WHITE, LIGHT_GRAY, MARGIN
)


def generate_client_summary(profile, output_path: str):
    """Generate a Client Summary / Intake Questionnaire PDF."""
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
    )
    styles = get_styles()
    story = []

    # Title
    story.append(Paragraph(
        f"Client Intake Questionnaire — Tax Year {profile.tax_year}",
        styles['DocTitle']))
    story.append(Spacer(1, 6))
    story.append(HRFlowable(width="100%", thickness=2, color=MEDIUM_BLUE))
    story.append(Spacer(1, 12))

    # ----- Section 1: Personal Information -----
    story.append(Paragraph("1. Personal Information", styles['SectionHeader']))

    filing_status_display = {
        "single": "Single", "mfj": "Married Filing Jointly",
        "hoh": "Head of Household"
    }

    data = [
        ["Field", "Primary Taxpayer", "Spouse" if profile.filing_status == "mfj" else ""],
        ["Full Name",
         f"{profile.primary_first} {profile.primary_last}",
         f"{profile.spouse_first} {profile.spouse_last}" if profile.spouse_first else "N/A"],
        ["SSN",
         format_ssn(profile.primary_ssn),
         format_ssn(profile.spouse_ssn) if profile.spouse_ssn else "N/A"],
        ["Date of Birth",
         profile.primary_dob,
         profile.spouse_dob if profile.spouse_dob else "N/A"],
        ["Occupation",
         profile.primary_occupation,
         profile.spouse_occupation if profile.spouse_occupation else "N/A"],
        ["Filing Status", filing_status_display.get(profile.filing_status, profile.filing_status), ""],
    ]

    t = Table(data, colWidths=[1.8*inch, 2.7*inch, 2.7*inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
        ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BACKGROUND', (0, 1), (0, -1), LIGHT_BLUE),
        ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)

    # Address
    story.append(Spacer(1, 8))
    addr_data = [
        ["Address", f"{profile.address}, {profile.city}, {profile.state} {profile.zip_code}"],
    ]
    t2 = Table(addr_data, colWidths=[1.8*inch, 5.4*inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), LIGHT_BLUE),
        ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t2)
    story.append(Spacer(1, 12))

    # ----- Section 2: Dependents -----
    story.append(Paragraph("2. Dependents", styles['SectionHeader']))

    if profile.dependents:
        dep_data = [["Name", "SSN", "Date of Birth", "Relationship", "Age"]]
        for dep in profile.dependents:
            dep_data.append([
                f"{dep.first_name} {dep.last_name}",
                format_ssn(dep.ssn),
                dep.dob,
                dep.relationship.title(),
                str(dep.age),
            ])
        t3 = Table(dep_data, colWidths=[2*inch, 1.4*inch, 1.3*inch, 1.3*inch, 0.8*inch])
        t3.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t3)
    else:
        story.append(Paragraph("No dependents claimed.", styles['FieldValue']))

    story.append(Spacer(1, 12))

    # ----- Section 3: Income Information -----
    story.append(Paragraph("3. Income Information", styles['SectionHeader']))

    # W-2 Income
    story.append(Paragraph("<b>Employment Income (W-2)</b>", styles['FieldValue']))
    if profile.w2_incomes:
        w2_data = [["Employer", "Employee", "Wages", "Fed. Withheld"]]
        for w2 in profile.w2_incomes:
            w2_data.append([
                w2.employer_name,
                w2.employee_name,
                format_currency_int(w2.wages),
                format_currency_int(w2.federal_withheld),
            ])
        tw = Table(w2_data, colWidths=[2.5*inch, 2*inch, 1.3*inch, 1.3*inch])
        tw.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tw)
    story.append(Spacer(1, 6))

    # Interest Income
    if profile.interest_incomes:
        story.append(Paragraph("<b>Interest Income (1099-INT)</b>", styles['FieldValue']))
        int_data = [["Payer", "Amount"]]
        for ii in profile.interest_incomes:
            int_data.append([ii.payer_name, format_currency_int(ii.amount)])
        ti = Table(int_data, colWidths=[5*inch, 2.2*inch])
        ti.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(ti)
        story.append(Spacer(1, 6))

    # Dividend Income
    if profile.dividend_incomes:
        story.append(Paragraph("<b>Dividend Income (1099-DIV)</b>", styles['FieldValue']))
        div_data = [["Payer", "Ordinary Dividends", "Qualified Dividends"]]
        for di in profile.dividend_incomes:
            div_data.append([
                di.payer_name,
                format_currency_int(di.ordinary_dividends),
                format_currency_int(di.qualified_dividends),
            ])
        td = Table(div_data, colWidths=[3.5*inch, 1.8*inch, 1.8*inch])
        td.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(td)
        story.append(Spacer(1, 6))

    # Self-Employment Income
    if profile.business_income:
        biz = profile.business_income
        story.append(Paragraph("<b>Self-Employment Income (Schedule C)</b>", styles['FieldValue']))
        biz_data = [
            ["Business Name", biz.business_name],
            ["Business Type", f"{biz.activity_desc} ({biz.activity_code})"],
            ["Gross Receipts", format_currency_int(biz.gross_receipts)],
            ["Total Expenses", format_currency_int(biz.expenses.total)],
            ["Net Profit", format_currency_int(biz.net_profit)],
        ]
        tb = Table(biz_data, colWidths=[2.5*inch, 4.7*inch])
        tb.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), LIGHT_BLUE),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(tb)
        story.append(Spacer(1, 6))

    story.append(Spacer(1, 12))

    # ----- Section 4: Deductions -----
    story.append(Paragraph("4. Deductions & Credits", styles['SectionHeader']))
    story.append(Paragraph(
        f"Standard deduction will be applied: <b>{format_currency_int(profile.federal_results.get('standard_deduction', 0))}</b>",
        styles['FieldValue']))

    if profile.federal_results.get('qbi_deduction', 0) > 0:
        story.append(Paragraph(
            f"Qualified Business Income Deduction (Section 199A): <b>"
            f"{format_currency_int(profile.federal_results['qbi_deduction'])}</b>",
            styles['FieldValue']))

    if profile.federal_results.get('child_tax_credit', 0) > 0:
        story.append(Paragraph(
            f"Child Tax Credit: <b>"
            f"{format_currency_int(profile.federal_results['child_tax_credit'])}</b>",
            styles['FieldValue']))

    story.append(Spacer(1, 12))

    # ----- Section 5: State-Specific -----
    story.append(Paragraph(f"5. State-Specific Information ({profile.state})",
                           styles['SectionHeader']))

    state_notes = {
        "CA": "California: Subject to CA state income tax (Form 540). "
              "SDI withholding applies. Eligible for CalEITC/YCTC if applicable. "
              "Renter's credit may apply if AGI is below threshold.",
        "TX": "Texas: No state income tax. No state return required.",
        "NY": "New York: Subject to NY state income tax (IT-201). "
              "NYC additional tax may apply for New York City residents.",
        "IL": "Illinois: Subject to IL flat rate income tax (4.95%). "
              "Personal exemptions of $2,625 per person.",
        "FL": "Florida: No state income tax. No state return required.",
    }
    story.append(Paragraph(state_notes.get(profile.state, ""), styles['FieldValue']))

    story.append(Spacer(1, 12))

    # ----- Section 6: OBBBA Eligibility (2025+) -----
    if profile.tax_year >= 2025:
        story.append(Paragraph("6. OBBBA Deduction Eligibility", styles['SectionHeader']))

        obbba_data = [
            ["Provision", "Eligible", "Details"],
            ["Tipped Worker (Part II)",
             "Yes" if profile.is_tipped_worker else "No",
             profile.primary_occupation if profile.is_tipped_worker else "N/A"],
            ["Overtime (Part III)",
             "Yes" if profile.overtime_eligible else "No",
             "FLSA overtime-eligible position" if profile.overtime_eligible else "N/A"],
            ["Car Loan Interest (Part IV)",
             "Yes" if profile.has_car_loan else "No",
             ""],
            ["Senior Deduction (Part V)",
             "Yes" if profile.is_senior_65_plus else "No",
             "Age 65+ as of Dec 31" if profile.is_senior_65_plus else "N/A"],
        ]

        # Add car loan details
        if profile.has_car_loan and profile.car_loan:
            obbba_data[3][2] = (
                f"VIN: {profile.car_loan.vin} | "
                f"Annual Interest: {format_currency_int(profile.car_loan.annual_interest)}"
            )

        t_obbba = Table(obbba_data, colWidths=[2.2*inch, 1*inch, 4*inch])
        t_obbba.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
            ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('BACKGROUND', (0, 1), (0, -1), LIGHT_BLUE),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ]))
        story.append(t_obbba)

        # Show Schedule 1-A computation results if available
        s1a = profile.federal_results.get('schedule_1a', {})
        if s1a.get('total', 0) > 0:
            story.append(Spacer(1, 6))
            s1a_data = [["Schedule 1-A Deduction", "Amount"]]
            if s1a.get("tips", 0) > 0:
                s1a_data.append(["Tip Income (Part II)", format_currency_int(s1a["tips"])])
            if s1a.get("overtime", 0) > 0:
                s1a_data.append(["Overtime (Part III)", format_currency_int(s1a["overtime"])])
            if s1a.get("car_loan", 0) > 0:
                s1a_data.append(["Car Loan Interest (Part IV)", format_currency_int(s1a["car_loan"])])
            if s1a.get("senior", 0) > 0:
                s1a_data.append(["Senior Deduction (Part V)", format_currency_int(s1a["senior"])])
            s1a_data.append(["Total Schedule 1-A", format_currency_int(s1a["total"])])

            t_s1a = Table(s1a_data, colWidths=[5*inch, 2.2*inch])
            t_s1a.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), HEADER_BG),
                ('TEXTCOLOR', (0, 0), (-1, 0), WHITE),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
                ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
                ('TOPPADDING', (0, 0), (-1, -1), 4),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ]))
            story.append(t_s1a)

        story.append(Spacer(1, 12))
        section_num = 7
    else:
        section_num = 6

    # ----- Section N: Compliance -----
    story.append(Paragraph(f"{section_num}. Prior-Year Compliance", styles['SectionHeader']))
    story.append(Paragraph(
        "Prior year returns filed: <b>Yes</b><br/>"
        "Estimated tax payments made: <b>No</b><br/>"
        "Any outstanding tax liabilities: <b>No</b>",
        styles['FieldValue']))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", thickness=1, color=LIGHT_GRAY))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        f"<i>Document generated for Dataset {profile.dataset_id} | "
        f"Tax Year {profile.tax_year} | {profile.state}</i>",
        styles['SmallText']))

    doc.build(story)
