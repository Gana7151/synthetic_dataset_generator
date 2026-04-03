"""
Statistical Validation Metrics — Guide v2.0 §8

Post-batch aggregate validation for synthetic tax datasets.
These metrics run on collections of generated records (not individual rows).

Implements:
  - KS Complement: 1D marginal fidelity check (§8.1)
  - Mahalanobis Distance: Multivariate hallucination detection (§8.2)
  - Batch summary report
"""

import numpy as np
from scipy import stats


def ks_complement(real_data: np.ndarray, synth_data: np.ndarray) -> float:
    """Kolmogorov-Smirnov Complement for 1D marginal fidelity.

    Guide §8.1: KS Complement = 1 - KS Statistic.
    Higher is better. Target: > 0.90 for income variables.

    Args:
        real_data: 1D array of real values for a single variable.
        synth_data: 1D array of synthetic values for the same variable.

    Returns:
        KS Complement score in [0, 1]. Higher = better fidelity.
    """
    ks_stat, p_value = stats.ks_2samp(real_data, synth_data)
    return round(1.0 - ks_stat, 4)


def detect_synthetic_hallucinations(real_data: np.ndarray,
                                     synth_data: np.ndarray,
                                     feature_cols: list,
                                     p_threshold: float = 0.001) -> dict:
    """Multivariate hallucination detection via Mahalanobis distance.

    Guide §8.2: Records that are individually plausible but jointly
    impossible (e.g., $50K wages + $40K charitable deduction).

    Uses chi-squared distribution to flag outliers in the joint space.
    Maximum 5% hallucination rate for production data.

    Args:
        real_data: (n_real, k) array of real data for k features.
        synth_data: (n_synth, k) array of synthetic data for same features.
        feature_cols: list of column names (for reporting).
        p_threshold: chi-squared p-value threshold for flagging.

    Returns:
        dict with hallucination_rate, flagged_count, total_records, pass status.
    """
    if len(synth_data) == 0:
        return {'hallucination_rate': 0, 'flagged_count': 0,
                'total_records': 0, 'pass': True, 'distances': []}

    # Compute mean and covariance from real data
    mu = np.mean(real_data, axis=0)

    try:
        cov_inv = np.linalg.inv(np.cov(real_data.T))
    except np.linalg.LinAlgError:
        # Singular covariance — use pseudo-inverse (handles collinear vars)
        cov_inv = np.linalg.pinv(np.cov(real_data.T))

    # Squared Mahalanobis distances follow chi-squared(df=k)
    df = real_data.shape[1]
    threshold = stats.chi2.ppf(1 - p_threshold, df=df)

    distances = []
    flags = []
    for row in synth_data:
        diff = row - mu
        d_sq = float(diff @ cov_inv @ diff)
        distances.append(d_sq)
        flags.append(d_sq > threshold)

    hallucination_rate = sum(flags) / len(flags) if len(flags) > 0 else 0

    return {
        'hallucination_rate': round(hallucination_rate, 4),
        'flagged_count': sum(flags),
        'total_records': len(flags),
        'pass': hallucination_rate < 0.05,  # Max 5% hallucination rate
        'distances': distances
    }


def batch_validation_report(records: list, feature_keys: list = None) -> dict:
    """Generate aggregate validation report for a batch of generated records.

    Computes summary statistics across the batch to identify systematic issues.

    Args:
        records: list of dict records (each record is a generated profile's fed results).
        feature_keys: Optional list of keys to analyze. Defaults to common tax fields.

    Returns:
        dict with per-feature statistics and overall quality metrics.
    """
    if not records:
        return {'error': 'No records to validate', 'pass': False}

    if feature_keys is None:
        feature_keys = [
            'wages', 'taxable_interest', 'business_income',
            'agi', 'taxable_income', 'total_tax', 'effective_rate'
        ]

    report = {'features': {}, 'record_count': len(records)}

    for key in feature_keys:
        values = [r.get(key, 0) for r in records if key in r]
        if values:
            arr = np.array(values, dtype=float)
            report['features'][key] = {
                'mean': round(float(np.mean(arr)), 2),
                'median': round(float(np.median(arr)), 2),
                'std': round(float(np.std(arr)), 2),
                'min': round(float(np.min(arr)), 2),
                'max': round(float(np.max(arr)), 2),
                'zero_pct': round(float(np.sum(arr == 0)) / len(arr) * 100, 1),
            }

    # Check for common red flags
    red_flags = []
    if 'agi' in report['features']:
        if report['features']['agi']['min'] < 0:
            red_flags.append('V-01: Negative AGI detected')
    if 'effective_rate' in report['features']:
        if report['features']['effective_rate']['max'] > 50:
            red_flags.append('Effective rate exceeds 50% — possible calculation error')

    report['red_flags'] = red_flags
    report['pass'] = len(red_flags) == 0

    return report
