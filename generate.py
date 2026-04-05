#!/usr/bin/env python3
"""
Synthetic Tax Dataset Generator — v5.0 Guide v2.0 Compliant

Generates complete synthetic tax datasets with all required documents:
  1. Client Summary (PDF)
  2. Input Documents (W-2, 1099, bank statements, invoices — PDF + XLSX)
  3. Completed Tax Forms (Form 1040 + schedules — PDF)
  4. Executive Summary (PDF)
  5. XML data file (IRS MeF format)
  6. Validation (22-rule engine, discard + re-seed on failure)

Usage:
    python generate.py --count 20 --output ./output
    python generate.py --count 2000 --output ./output --seed 12345
"""

import argparse
import csv
import json
import os
import sys
import random
import time

from tax_engine.profile_generator import generate_profile, reset_ssn_pool
from tax_engine.federal_calculator import compute_federal_tax
from tax_engine.state_calculator import compute_state_tax
from generators.xml_generator import generate_xml
from generators.client_summary import generate_client_summary
from generators.input_documents import generate_all_input_documents
from generators.tax_forms import generate_tax_forms
from generators.executive_summary import generate_executive_summary
from validation import ValidationEngine
from pathlib import Path

MAX_RETRIES = 3


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate synthetic U.S. individual tax datasets (v4.0 spec)."
    )
    parser.add_argument("--count", type=int, default=20,
                        help="Number of datasets to generate (default: 20)")
    parser.add_argument("--states", type=str, default="CA,TX,NY,IL,FL",
                        help="Comma-separated state codes (default: CA,TX,NY,IL,FL)")
    parser.add_argument("--years", type=str, default="2020,2021,2022,2023,2024,2025",
                        help="Comma-separated tax years (default: 2020-2025)")
    parser.add_argument("--levels", type=str, default="1,2,3",
                        help="Comma-separated complexity levels (default: 1,2,3)")
    parser.add_argument("--output", type=str, default="./output",
                        help="Output directory (default: ./output)")
    parser.add_argument("--seed", type=int, default=None,
                        help="Random seed for reproducible generation")
    parser.add_argument("--validate", action="store_true", default=True,
                        help="Run 15-rule validation on each dataset")
    return parser.parse_args()


def distribute_datasets(count, states, years, levels):
    """Create a list of (state, year, level) assignments, evenly distributed."""
    assignments = []
    total_combos = len(states) * len(years) * len(levels)

    base_per_combo = count // total_combos
    remainder = count % total_combos

    for state in states:
        for year in years:
            for level in levels:
                n = base_per_combo + (1 if remainder > 0 else 0)
                remainder -= 1 if remainder > 0 else 0
                for _ in range(n):
                    assignments.append((state, year, level))

    random.shuffle(assignments)
    return assignments[:count]


def generate_single_dataset(dataset_id, state, year, level, output_dir,
                            validator=None, attempt=1):
    """Generate a complete dataset with all documents.

    Returns (metadata_dict, profile) or (None, None) on failure.
    """
    ds_id = f"DS_{dataset_id:04d}"
    folder_name = f"Dataset_{dataset_id:04d}_{state}_{year}_L{level}"
    dataset_dir = os.path.join(output_dir, folder_name)

    dirs = {
        "summary": os.path.join(dataset_dir, "1. Client Summary"),
        "input":   os.path.join(dataset_dir, "2. Input Documents"),
        "forms":   os.path.join(dataset_dir, "3. Complete Forms"),
        "exec":    os.path.join(dataset_dir, "4. Executive Summary"),
        "prompt":  os.path.join(dataset_dir, "Prompt"),
    }
    for d in dirs.values():
        os.makedirs(d, exist_ok=True)

    # 1. Generate profile
    profile = generate_profile(ds_id, state, year, level)

    # 2. Compute federal tax
    fed = compute_federal_tax(profile)

    # 3. Compute state tax
    st = compute_state_tax(profile)

    # 4. Generate documents
    generate_client_summary(
        profile,
        os.path.join(dirs["summary"], "Client_Summary.pdf"))

    generate_all_input_documents(profile, dirs["input"])

    generate_tax_forms(
        profile,
        os.path.join(dirs["forms"],
                     f"Tax_Return_{year}_{profile.primary_last.upper()}.pdf"))

    generate_executive_summary(
        profile,
        os.path.join(dirs["exec"], "Executive_Summary.pdf"))

    generate_xml(
        profile,
        os.path.join(dirs["prompt"], "Tax_Return_Data.xml"))

    # 4b. Generate 28-page overlay PDF (realistic IRS form layout)
    blank_form_pdf = Path(__file__).parent / "blank_form.pdf"
    if blank_form_pdf.exists():
        from generate_tax_pdf import generate_variation
        overlay_pdf_path = os.path.join(
            dirs["forms"],
            f"Completed_Tax_Return_{year}_{profile.primary_last.upper()}.pdf"
        )
        try:
            generate_variation(
                str(blank_form_pdf), overlay_pdf_path,
                seed=hash(ds_id) & 0xFFFFFFFF
            )
        except Exception as e:
            print(f"    [WARN] Overlay PDF failed: {e}")

    # 5. Validate (if validator provided)
    if validator:
        result = validator.run_all(profile, dataset_dir)
        if not result.passed:
            return None, result.failures

    # Metadata for index
    metadata = {
        "dataset_id": ds_id,
        "folder": folder_name,
        "state": state,
        "tax_year": year,
        "level": level,
        "filing_status": profile.filing_status,
        "primary_name": f"{profile.primary_first} {profile.primary_last}",
        "spouse_name": (f"{profile.spouse_first} {profile.spouse_last}"
                        if profile.spouse_first else "N/A"),
        "dependents": len(profile.dependents),
        "total_income": fed["total_income"],
        "agi": fed["agi"],
        "taxable_income": fed["taxable_income"],
        "total_tax": fed["total_tax"],
        "refund": fed.get("refund", 0),
        "amount_owed": fed.get("amount_owed", 0),
        "state_tax": st.get("total_tax", 0),
        "effective_rate": fed.get("effective_rate", 0),
        "obbba_total": fed.get("schedule_1a_total", 0),
        "medicare_surtax": fed.get("medicare_surtax", 0),
        "is_tipped": profile.is_tipped_worker,
        "has_car_loan": profile.has_car_loan,
        "is_senior": profile.is_senior_65_plus,
    }

    return metadata, None


def main():
    args = parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    reset_ssn_pool()

    states = [s.strip().upper() for s in args.states.split(",")]
    years = [int(y.strip()) for y in args.years.split(",")]
    levels = [int(l.strip()) for l in args.levels.split(",")]

    print(f"\n{'='*60}")
    print(f"  Synthetic Tax Dataset Generator v5.0")
    print(f"{'='*60}")
    print(f"  Datasets to generate : {args.count}")
    print(f"  States               : {', '.join(states)}")
    print(f"  Tax Years            : {', '.join(map(str, years))}")
    print(f"  Complexity Levels    : {', '.join(map(str, levels))}")
    print(f"  Output Directory     : {args.output}")
    print(f"  Validation           : {'Enabled (22 rules)' if args.validate else 'Disabled'}")
    print(f"{'='*60}\n")

    assignments = distribute_datasets(args.count, states, years, levels)
    os.makedirs(args.output, exist_ok=True)

    validator = ValidationEngine() if args.validate else None

    index_rows = []
    start_time = time.time()
    total_discarded = 0
    total_retries = 0

    for i, (state, year, level) in enumerate(assignments, 1):
        success = False
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                metadata, failures = generate_single_dataset(
                    i, state, year, level, args.output, validator, attempt)

                if metadata is not None:
                    index_rows.append(metadata)
                    success = True

                    elapsed = time.time() - start_time
                    rate = i / elapsed if elapsed > 0 else 0
                    eta = (args.count - i) / rate if rate > 0 else 0

                    obbba_flag = ""
                    if metadata.get("obbba_total", 0) > 0:
                        obbba_flag = " [OBBBA]"
                    if metadata.get("is_senior"):
                        obbba_flag += " [65+]"

                    print(f"  [{i:4d}/{args.count}]  {metadata['folder']}"
                          f"  |  {metadata['primary_name']:<25s}"
                          f"  |  AGI: ${metadata['agi']:>10,.0f}"
                          f"  |  ETA: {eta:.0f}s{obbba_flag}")
                    break
                else:
                    total_retries += 1
                    if attempt < MAX_RETRIES:
                        pass  # retry silently
                    else:
                        total_discarded += 1
                        print(f"  [{i:4d}/{args.count}]  DISCARDED after {MAX_RETRIES} retries"
                              f"  |  Failures: {failures[:2]}")

            except Exception as e:
                if attempt == MAX_RETRIES:
                    total_discarded += 1
                    print(f"  [ERROR] Dataset {i}, attempt {attempt}: {e}")
                    import traceback
                    traceback.print_exc()

    # Write master index
    index_path = os.path.join(args.output, "master_index.csv")
    if index_rows:
        fieldnames = index_rows[0].keys()
        with open(index_path, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(index_rows)

    # Write validation summary
    if validator and args.validate:
        summary = {
            "total_generated": len(index_rows),
            "total_discarded": total_discarded,
            "total_retries": total_retries,
            "discard_rate": f"{total_discarded / args.count * 100:.2f}%",
            "rule_failure_breakdown": validator.rule_failure_counts,
            "ssn_pool_size": len(validator._used_ssns),
        }
        summary_path = os.path.join(args.output, "validation_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2)
        print(f"\n  Validation Summary: {summary_path}")

    elapsed = time.time() - start_time
    print(f"\n{'='*60}")
    print(f"  [OK] COMPLETE (v5.0 Spec)")
    print(f"  Generated: {len(index_rows)}/{args.count} datasets")
    if total_discarded > 0:
        print(f"  Discarded: {total_discarded} (after {MAX_RETRIES} retries each)")
    print(f"  Time: {elapsed:.1f}s ({len(index_rows)/elapsed:.1f} datasets/sec)")
    print(f"  Output: {os.path.abspath(args.output)}")
    print(f"  Index: {os.path.abspath(index_path)}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
