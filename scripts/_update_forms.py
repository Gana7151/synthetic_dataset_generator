import re

path = r"f:\\combined\\gana_combined\\generators\\tax_forms.py"
with open(path, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Update imports
imports_old = """from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)"""
imports_new = """from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                 TableStyle, HRFlowable, PageBreak)
from reportlab.pdfgen import canvas"""
content = content.replace(imports_old, imports_new)

# 2. Add Coordinate Tooling (after line 77)
tooling = """
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
"""
content = content.replace("# ===========================================================================\n# Form 1040", tooling + "\n# ===========================================================================\n# Form 1040")

# 3. Add new Scheduled renderers at the end
new_forms = """

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

"""
content += new_forms

# 4. Integrate into main generator function
generate_tax_forms_old = """    # Schedule A (Itemized Deductions)
    fed = profile.federal_results
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

        # Schedule SE
        if fed.get("se_tax", 0) > 0:
            story.append(PageBreak())
            _add_schedule_se_page(story, profile, styles)

    # State form (if applicable)"""

generate_tax_forms_new = """    fed = profile.federal_results
    
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

    # State form (if applicable)"""

content = content.replace(generate_tax_forms_old, generate_tax_forms_new)

with open(path, "w", encoding="utf-8") as f:
    f.write(content)

print("done")
