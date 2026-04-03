"""
Versioned Tax Parameter Store — Guide v2.0 §11.3

Central repository for ALL year-dependent tax parameters.
Every calculator MUST use get_tax_parameters(year) to retrieve constants.
Never hardcode a tax parameter in any calculator module.

Sources:
  - IRS Rev. Proc. (inflation adjustments per year)
  - OBBBA statutory text (2025+ provisions)
  - Bradford Tax Institute (AMT analysis)
  - CBO Budget and Economic Outlook (forward projections)
"""

TAX_PARAMETERS = {
    2020: {
        'standard_deduction': {'single': 12400, 'mfj': 24800, 'hoh': 18650, 'mfs': 12400},
        'salt_cap': 10000,
        'ss_wage_base': 137700,
        'amt_exemption': {'single': 72900, 'mfj': 113400},
        'amt_phase_start': {'single': 518400, 'mfj': 1036800},
        'amt_phase_rate': 0.25,
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 518400, 'mfj': 622050},
        'il_eitc_rate': 0.18,
        'ctc_per_child': 2000,
        'ctc_refundable_max': 1400,
        'ctc_phaseout': {'single': 200000, 'mfj': 400000, 'hoh': 200000},
        'qbi_threshold': {'single': 163300, 'mfj': 326600},
        'qbi_phaseout_width': {'single': 50000, 'mfj': 100000},
        'additional_std_deduction': {'single_or_mfs': 1650, 'mfj_per_person': 1300},
        'obbba_active': False,
    },
    2021: {
        'standard_deduction': {'single': 12550, 'mfj': 25100, 'hoh': 18800, 'mfs': 12550},
        'salt_cap': 10000,
        'ss_wage_base': 142800,
        'amt_exemption': {'single': 73600, 'mfj': 114600},
        'amt_phase_start': {'single': 523600, 'mfj': 1047200},
        'amt_phase_rate': 0.25,
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 523600, 'mfj': 628300},
        'il_eitc_rate': 0.20,
        'ctc_per_child': {'under_6': 3600, 'age_6_to_17': 3000},  # ARPA expansion
        'ctc_refundable_max': 1400,
        'ctc_phaseout': {'single': 75000, 'mfj': 150000, 'hoh': 112500},
        'qbi_threshold': {'single': 164900, 'mfj': 329800},
        'qbi_phaseout_width': {'single': 50000, 'mfj': 100000},
        'additional_std_deduction': {'single_or_mfs': 1700, 'mfj_per_person': 1350},
        'obbba_active': False,
    },
    2022: {
        'standard_deduction': {'single': 12950, 'mfj': 25900, 'hoh': 19400, 'mfs': 12950},
        'salt_cap': 10000,
        'ss_wage_base': 147000,
        'amt_exemption': {'single': 75900, 'mfj': 118100},
        'amt_phase_start': {'single': 539900, 'mfj': 1079800},
        'amt_phase_rate': 0.25,
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 539900, 'mfj': 647850},
        'il_eitc_rate': 0.20,
        'ctc_per_child': 2000,
        'ctc_refundable_max': 1500,
        'ctc_phaseout': {'single': 200000, 'mfj': 400000, 'hoh': 200000},
        'qbi_threshold': {'single': 170050, 'mfj': 340100},
        'qbi_phaseout_width': {'single': 50000, 'mfj': 100000},
        'additional_std_deduction': {'single_or_mfs': 1750, 'mfj_per_person': 1400},
        'obbba_active': False,
    },
    2023: {
        'standard_deduction': {'single': 13850, 'mfj': 27700, 'hoh': 20800, 'mfs': 13850},
        'salt_cap': 10000,
        'ss_wage_base': 160200,
        'amt_exemption': {'single': 81300, 'mfj': 126500},
        'amt_phase_start': {'single': 578150, 'mfj': 1156300},
        'amt_phase_rate': 0.25,
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 578125, 'mfj': 693750},
        'il_eitc_rate': 0.20,
        'ctc_per_child': 2000,
        'ctc_refundable_max': 1600,
        'ctc_phaseout': {'single': 200000, 'mfj': 400000, 'hoh': 200000},
        'qbi_threshold': {'single': 182100, 'mfj': 364200},
        'qbi_phaseout_width': {'single': 50000, 'mfj': 100000},
        'additional_std_deduction': {'single_or_mfs': 1850, 'mfj_per_person': 1500},
        'obbba_active': False,
    },
    2024: {
        'standard_deduction': {'single': 14600, 'mfj': 29200, 'hoh': 21900, 'mfs': 14600},
        'salt_cap': 10000,
        'ss_wage_base': 168600,
        'amt_exemption': {'single': 85700, 'mfj': 133300},
        'amt_phase_start': {'single': 609350, 'mfj': 1218700},
        'amt_phase_rate': 0.25,
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 609350, 'mfj': 731200},
        'il_eitc_rate': 0.30,
        'ctc_per_child': 2000,
        'ctc_refundable_max': 1700,
        'ctc_phaseout': {'single': 200000, 'mfj': 400000, 'hoh': 200000},
        'qbi_threshold': {'single': 191950, 'mfj': 383900},
        'qbi_phaseout_width': {'single': 50000, 'mfj': 100000},
        'additional_std_deduction': {'single_or_mfs': 1950, 'mfj_per_person': 1550},
        'obbba_active': False,
    },
    2025: {
        'standard_deduction': {'single': 15750, 'mfj': 31500, 'hoh': 23625, 'mfs': 15750},
        'salt_cap': 40000,           # OBBBA transition year
        'ss_wage_base': 176100,
        'amt_exemption': {'single': 88100, 'mfj': 137000},
        'amt_phase_start': {'single': 626350, 'mfj': 1252700},
        'amt_phase_rate': 0.25,      # Still TCJA rate in 2025
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 626350, 'mfj': 751600},
        'il_eitc_rate': 0.40,
        'ctc_per_child': 2200,       # OBBBA increase
        'ctc_refundable_max': 1700,
        'ctc_phaseout': {'single': 200000, 'mfj': 400000, 'hoh': 200000},
        'qbi_threshold': {'single': 197300, 'mfj': 394600},
        'qbi_phaseout_width': {'single': 75000, 'mfj': 150000},  # OBBBA expansion
        'additional_std_deduction': {'single_or_mfs': 2000, 'mfj_per_person': 1600},
        'obbba_active': True,
    },
    2026: {
        'standard_deduction': {'single': 16100, 'mfj': 32200, 'hoh': 24150, 'mfs': 16100},
        'salt_cap': 40400,           # Indexed
        'ss_wage_base': 183000,      # Estimated (CPI-W)
        'amt_exemption': {'single': 90100, 'mfj': 140300},     # Est.
        'amt_phase_start': {'single': 500000, 'mfj': 1000000}, # OBBBA REVERTED
        'amt_phase_rate': 0.50,      # OBBBA DOUBLED
        'top_bracket_rate': 0.37,
        'top_bracket_start': {'single': 650000, 'mfj': 780000},  # Est. indexed
        'il_eitc_rate': 0.40,        # Assumed maintained
        'ctc_per_child': 2200,
        'ctc_refundable_max': 1700,
        'ctc_phaseout': {'single': 200000, 'mfj': 400000, 'hoh': 200000},
        'qbi_threshold': {'single': 201775, 'mfj': 403500},
        'qbi_phaseout_width': {'single': 75000, 'mfj': 150000},
        'additional_std_deduction': {'single_or_mfs': 2050, 'mfj_per_person': 1650},
        'obbba_active': True,
        # 2026-specific: AMT has different mechanics
        'amt_26_bracket_ceiling': 220700,
        'benefit_cap_237': True,     # 2/37 rule applies
    },
}


def get_tax_parameters(tax_year: int) -> dict:
    """Retrieve verified tax parameters for a given year.

    Raises ValueError if the year is not in the parameter store.
    This prevents silent use of wrong-year parameters.
    """
    if tax_year not in TAX_PARAMETERS:
        raise ValueError(
            f"Tax year {tax_year} not in parameter store. "
            f"Available years: {sorted(TAX_PARAMETERS.keys())}. "
            f"Add parameters before generating data for this year."
        )
    return TAX_PARAMETERS[tax_year]


def is_obbba_year(tax_year: int) -> bool:
    """Check if OBBBA provisions are active for a tax year."""
    params = get_tax_parameters(tax_year)
    return params.get('obbba_active', False)
