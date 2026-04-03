"""
Longitudinal Data Synthesis — Guide v2.0 §11

Generates multi-year income panels for single synthetic taxpayers using
an AR(1) process on log income. Ensures year-over-year income is correlated
(not independent) and applies year-specific tax parameters.

Key insight from the guide: "A real taxpayer's 2021 wages correlate with
their 2022 wages more than their wages correlate with a randomly selected
other taxpayer. Ignoring this produces synthetic panel datasets where
year-over-year income volatility is dramatically overstated."

Empirical basis: IRS SOI panel data shows AR(1) coefficient of ~0.85
for wage earners and ~0.70 for self-employed individuals.
"""

import numpy as np
from tax_engine.tax_parameters_store import get_tax_parameters


def generate_longitudinal_income(
    initial_income: float,
    tax_years: list,
    ar_coefficient: float = 0.85,      # Income persistence (~0.80-0.90)
    income_growth_rate: float = 0.03,   # Real income growth ~3% annually
    income_volatility: float = 0.12,    # Year-over-year log income volatility
    seed: int = None
) -> dict:
    """Generate a panel of income observations for a single synthetic taxpayer.

    Uses an AR(1) process on log income to ensure:
    1. Year-over-year income is correlated (not independent)
    2. Long-run income trends upward with the economy
    3. Short-run volatility matches empirical panel data

    Args:
        initial_income: Starting income for the first year.
        tax_years: List of tax years to generate for.
        ar_coefficient: AR(1) persistence parameter.
        income_growth_rate: Expected annual real income growth.
        income_volatility: Standard deviation of year-over-year log income changes.
        seed: Optional random seed for reproducibility.

    Returns:
        dict mapping tax_year -> income value.
    """
    if seed is not None:
        np.random.seed(seed)

    log_income = np.log(max(initial_income, 1.0))
    panel = {}

    for i, year in enumerate(sorted(tax_years)):
        if i == 0:
            panel[year] = initial_income
        else:
            # AR(1): log_income(t) = μ + ρ·log_income(t-1) + ε
            mu = np.log(initial_income) + income_growth_rate * i
            innovation = np.random.normal(0, income_volatility)
            log_income = mu + ar_coefficient * (log_income - mu) + innovation
            panel[year] = max(0.0, round(np.exp(log_income), 2))

    return panel


def apply_year_specific_tax_params(persona: dict, tax_year: int) -> dict:
    """Apply year-specific tax parameters to a longitudinal persona.

    Guide §11.2: This is where IL EITC rates, SALT caps, and bracket
    adjustments are correctly applied per year rather than using the
    most recent year's values.

    CRITICAL: Do NOT apply a flat rate across years in longitudinal datasets.
    Using 2025's 40% IL EITC rate for a 2021 return overstates IL EITC by 100%.

    Args:
        persona: dict with taxpayer attributes (filing_status, state, etc.)
        tax_year: The specific tax year to apply parameters for.

    Returns:
        Copy of persona with year-specific parameters applied.
    """
    year_params = get_tax_parameters(tax_year)

    persona_year = persona.copy()
    persona_year['tax_year'] = tax_year

    # Standard deduction: year-specific
    filing_status = persona.get('filing_status', 'single')
    std_ded = year_params['standard_deduction']
    persona_year['standard_deduction'] = std_ded.get(filing_status, std_ded['single'])

    # SALT cap: year-specific
    persona_year['salt_cap'] = year_params['salt_cap']

    # SS wage base: year-specific
    persona_year['ss_wage_base'] = year_params['ss_wage_base']

    # IL EITC: MUST use year-specific rate
    if persona.get('state') == 'IL':
        persona_year['il_eitc_rate'] = year_params.get('il_eitc_rate', 0.20)

    # OBBBA active flag
    persona_year['obbba_active'] = year_params.get('obbba_active', False)

    return persona_year


def generate_longitudinal_panel(
    base_persona: dict,
    tax_years: list,
    income_key: str = 'wages',
    seed: int = None
) -> list:
    """Generate a complete longitudinal panel for one taxpayer.

    This is the high-level entry point that combines income generation
    with year-specific parameter application.

    Args:
        base_persona: dict with base taxpayer attributes.
        tax_years: List of years to generate.
        income_key: Which income field to use as the AR(1) base.
        seed: Optional random seed.

    Returns:
        List of dicts, one per year, with correlated income and
        year-specific tax parameters.
    """
    initial_income = base_persona.get(income_key, 50000)

    # Use different AR coefficients for different income types
    ar_coeff = 0.85 if income_key == 'wages' else 0.70

    income_panel = generate_longitudinal_income(
        initial_income=initial_income,
        tax_years=tax_years,
        ar_coefficient=ar_coeff,
        seed=seed,
    )

    panel_records = []
    for year in sorted(tax_years):
        record = apply_year_specific_tax_params(base_persona, year)
        record[income_key] = income_panel[year]
        panel_records.append(record)

    return panel_records
