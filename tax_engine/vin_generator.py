"""
ISO 3779-compliant VIN generator for OBBBA Schedule 1-A Part IV
(Car Loan Interest Deduction eligibility).

Constraints:
  - 17 characters total
  - Position 1 (WMI[0]) ∈ ['1', '4', '5']  →  US-assembled vehicles
  - Position 9 = mod-11 check digit
  - Characters I, O, Q are excluded from VINs
"""

import random
import string
from datetime import date


# ---------------------------------------------------------------------------
# VIN character set (ISO 3779 — excludes I, O, Q)
# ---------------------------------------------------------------------------

VIN_CHARS = string.digits + "ABCDEFGHJKLMNPRSTUVWXYZ"  # no I, O, Q

# Transliteration table for mod-11 check digit
TRANSLITERATION = {
    'A': 1, 'B': 2, 'C': 3, 'D': 4, 'E': 5, 'F': 6, 'G': 7, 'H': 8,
    'J': 1, 'K': 2, 'L': 3, 'M': 4, 'N': 5, 'P': 7, 'R': 9,
    'S': 2, 'T': 3, 'U': 4, 'V': 5, 'W': 6, 'X': 7, 'Y': 8, 'Z': 9,
    **{str(d): d for d in range(10)}
}

# Position weights (1-indexed positions but stored 0-indexed)
POSITION_WEIGHTS = [8, 7, 6, 5, 4, 3, 2, 10, 0, 9, 8, 7, 6, 5, 4, 3, 2]

# US assembly plant indicators (position 1)
US_ASSEMBLY_CODES = ['1', '4', '5']

# Model year codes (position 10)
MODEL_YEAR_CODES = {
    2020: 'L', 2021: 'M', 2022: 'N', 2023: 'P', 2024: 'R',
    2025: 'S', 2026: 'T', 2027: 'V', 2028: 'W',
}


def compute_check_digit(vin: str) -> str:
    """Compute ISO 3779 mod-11 check digit for a VIN.

    Args:
        vin: 17-character VIN (position 9 is ignored in calculation).

    Returns:
        Check digit character: '0'-'9' or 'X' (for remainder 10).
    """
    total = sum(
        TRANSLITERATION[c] * POSITION_WEIGHTS[i]
        for i, c in enumerate(vin)
        if i != 8  # skip position 9 (the check digit position)
    )
    remainder = total % 11
    return 'X' if remainder == 10 else str(remainder)


def generate_vin(model_year: int = 2025) -> str:
    """Generate a valid ISO 3779-compliant VIN for a US-assembled vehicle.

    Args:
        model_year: Vehicle model year (default: 2025).

    Returns:
        A 17-character VIN string with valid mod-11 check digit.
    """
    # Position 1: US assembly indicator
    pos1 = random.choice(US_ASSEMBLY_CODES)

    # Positions 2-3: Manufacturer code (random valid chars)
    pos2 = random.choice(VIN_CHARS)
    pos3 = random.choice(VIN_CHARS)

    # Positions 4-8: Vehicle attributes
    pos4_8 = ''.join(random.choice(VIN_CHARS) for _ in range(5))

    # Position 9: placeholder (will be replaced by check digit)
    pos9 = '0'

    # Position 10: Model year code
    pos10 = MODEL_YEAR_CODES.get(model_year, 'S')

    # Position 11: Assembly plant
    pos11 = random.choice(VIN_CHARS)

    # Positions 12-17: Sequential number
    pos12_17 = ''.join(random.choice(string.digits) for _ in range(6))

    # Build VIN with placeholder check digit
    vin = pos1 + pos2 + pos3 + pos4_8 + pos9 + pos10 + pos11 + pos12_17

    # Compute and insert correct check digit
    check = compute_check_digit(vin)
    vin = vin[:8] + check + vin[9:]

    return vin


def validate_vin(vin: str) -> tuple:
    """Validate a VIN for Schedule 1-A Part IV eligibility.

    Returns:
        (is_valid: bool, errors: list of str)
    """
    errors = []

    if len(vin) != 17:
        errors.append(f"Length {len(vin)} ≠ 17")

    if vin[0] not in US_ASSEMBLY_CODES:
        errors.append(f"Position 1 '{vin[0]}' not US-assembled (must be 1, 4, or 5)")

    expected_check = compute_check_digit(vin)
    if vin[8] != expected_check:
        errors.append(f"Check digit '{vin[8]}' ≠ expected '{expected_check}'")

    # Check for invalid characters (I, O, Q)
    for i, c in enumerate(vin):
        if c in ('I', 'O', 'Q'):
            errors.append(f"Position {i+1} contains invalid character '{c}'")

    return (len(errors) == 0, errors)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("VIN Generator — Self Test")
    print("=" * 50)

    # Generate and validate 100 VINs
    pass_count = 0
    for i in range(100):
        vin = generate_vin(random.choice([2024, 2025]))
        valid, errors = validate_vin(vin)
        if valid:
            pass_count += 1
        else:
            print(f"  FAIL: {vin} — {errors}")

    print(f"\n  Passed: {pass_count}/100")
    assert pass_count == 100, "VIN generator failed self-test!"
    print("  ✅ All VINs valid")

    # Show sample VINs
    print("\n  Sample VINs:")
    for _ in range(5):
        v = generate_vin(2025)
        print(f"    {v}  (check digit: {v[8]})")
