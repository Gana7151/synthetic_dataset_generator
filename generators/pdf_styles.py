"""
Shared PDF utility functions for consistent styling across all generated documents.
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT


# Color palette
DARK_BLUE = HexColor("#1a365d")
MEDIUM_BLUE = HexColor("#2b6cb0")
LIGHT_BLUE = HexColor("#bee3f8")
HEADER_BG = HexColor("#2d3748")
ROW_ALT = HexColor("#f7fafc")
BORDER_COLOR = HexColor("#cbd5e0")
BLACK = HexColor("#000000")
DARK_GRAY = HexColor("#2d3748")
MEDIUM_GRAY = HexColor("#718096")
LIGHT_GRAY = HexColor("#e2e8f0")
WHITE = HexColor("#ffffff")
GREEN = HexColor("#276749")
RED = HexColor("#c53030")

PAGE_WIDTH, PAGE_HEIGHT = letter
MARGIN = 0.6 * inch


def get_styles():
    """Return a set of paragraph styles for documents."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'DocTitle', parent=styles['Title'],
        fontSize=18, textColor=DARK_BLUE, spaceAfter=12,
        alignment=TA_CENTER,
    ))
    styles.add(ParagraphStyle(
        'SectionHeader', parent=styles['Heading2'],
        fontSize=12, textColor=DARK_BLUE, spaceBefore=16, spaceAfter=6,
        borderWidth=0, borderColor=MEDIUM_BLUE, borderPadding=4,
    ))
    styles.add(ParagraphStyle(
        'FieldLabel', parent=styles['Normal'],
        fontSize=8, textColor=MEDIUM_GRAY,
    ))
    styles.add(ParagraphStyle(
        'FieldValue', parent=styles['Normal'],
        fontSize=10, textColor=BLACK, spaceBefore=2, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        'SmallText', parent=styles['Normal'],
        fontSize=7, textColor=MEDIUM_GRAY,
    ))
    styles.add(ParagraphStyle(
        'TableHeader', parent=styles['Normal'],
        fontSize=9, textColor=WHITE, alignment=TA_CENTER,
    ))

    return styles


def format_ssn(ssn: str) -> str:
    """Format SSN as XXX-XX-XXXX."""
    if len(ssn) == 9:
        return f"{ssn[:3]}-{ssn[3:5]}-{ssn[5:]}"
    return ssn


def format_ein(ein: str) -> str:
    """Format EIN as XX-XXXXXXX."""
    if len(ein) == 9:
        return f"{ein[:2]}-{ein[2:]}"
    return ein


def format_currency(amount) -> str:
    """Format number as currency string."""
    if amount < 0:
        return f"(${abs(amount):,.2f})"
    return f"${amount:,.2f}"


def format_currency_int(amount) -> str:
    """Format number as currency string with no decimals."""
    if amount < 0:
        return f"(${abs(int(amount)):,})"
    return f"${int(amount):,}"
