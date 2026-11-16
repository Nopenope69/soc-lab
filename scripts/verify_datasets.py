#!/usr/bin/env python3
"""Dataset Manifest Verification Script for soc-lab.

Checks manifests in data/manifests/<dataset>.sha256 against actual files on disk.
Prints present vs missing files and verification status per dataset.

Statuses:
- INTEGRITY_OK: All expected files present on disk, hashes match.
- MISSING: Raw data folder or expected files not found on disk.
- CORRUPT: Files exist on disk but SHA-256 hash fails against manifest (violates Rule R2).
- NOT_DOWNLOADED: Intentionally not acquired (stub manifest; not an error).
- FABRICATED: Manifest contains placeholder, synthetic, or invented hashes/files.

Rules Enforced:
R1. Raw data lives OUTSIDE repo at $SOC_DATA_DIR (default ~/soc_data), except calce_a123 in repo.
R2. Loaders and verifiers must read real files. No simulation or defaulted values.
"""

import argparse
import hashlib
import os
from pathlib import Path
import re
import sys
from typing import Dict, List, Optional, Tuple

# Ensure repository root and src are in python path
REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from soc.data.registry import (
    DATASET_METADATA,
    DatasetManifest,
    get_manifest_path,
    get_soc_data_dir,
    resolve_dataset_dir,
)


def is_fabricated_hash(h: str) -> bool:
    """Detect whether a SHA-256 hash is a known placeholder, pattern, or synthetic token."""
    h = h.strip().lower()
    if len(h) != 64:
        return True
    # 1. All zeros
    if h == "0" * 64:
        return True
    # 2. Empty-input SHA-256
    if h == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855":
        return True
    # 3. Empty-input MD5 (32 hex characters zero-padded)
    if h.startswith("d41d8cd98f00b204e9800998ecf8427e"):
        return True
    # 4. Repeated short pattern (k = 1, 2, 4, 8, 16, 32)
    for k in (1, 2, 4, 8, 16, 32):
        if (h[:k] * (64 // k + 1))[:64] == h:
            return True
    # 5. Runs or rotations of sequential hex characters
    seq_patterns = (
        "0123456789abcdef" * 5,
        "1234567890abcdef" * 5,
        "fedcba9876543210" * 5,
        "fedcba0987654321" * 5,
    )
    for pat in ("1234567890abcdef", "0123456789abcdef", "fedcba9876543210", "fedcba0987654321"):
        if pat in h:
            return True
    if any(any(h[i:i+16] in s for s in seq_patterns) for i in range(0, 48, 16)):
        return True
    # 6. Doubled hex digits (e.g. aa11bb22cc33...)
    if all(h[i] == h[i+1] for i in range(0, 64, 2)):
        return True
    # 7. Interleaved sequential letters and digits (e.g. a0b1c2d3...)
    letters_cycle = "abcdef" * 15
    digits_cycle = "0123456789" * 15
    if (h[0::2] in letters_cycle and h[1::2] in digits_cycle) or (h[0::2] in digits_cycle and h[1::2] in letters_cycle):
        return True

    return False


def verify_datasets(
    data_dir: Path,
    target_dataset: Optional[str] = None,
    verbose: bool = False,
) -> int:
    """Audit datasets against their manifests and print verification report."""
    print("=" * 100)
    print("SOC-LAB DATASET INTEGRITY & MANIFEST AUDIT")
    print(f"Data Root Directory: {data_dir} (via $SOC_DATA_DIR or default)")
    print("=" * 100)

    datasets_to_check = (
        [target_dataset] if target_dataset else list(DATASET_METADATA.keys())
    )

    results = []
    any_corrupt = False
    any_fabricated = False
    any_missing = False

    for ds_id in datasets_to_check:
        if ds_id not in DATASET_METADATA:
            print(f"ERROR: Unknown dataset '{ds_id}'")
            return 1

        meta = DATASET_METADATA[ds_id]
        manifest_path = get_manifest_path(ds_id)

        if not manifest_path.exists():
            print(f"[{ds_id}] Manifest missing: {manifest_path}")
            any_missing = True
            results.append({
                "id": ds_id,
                "licence": meta.licence,
                "total": 0,
                "valid": 0,
                "missing": 0,
                "corrupt": 0,
                "status": "MISSING",
                "path": "N/A",
            })
            continue

        manifest = DatasetManifest.load(manifest_path)
        dataset_path = resolve_dataset_dir(ds_id, custom_data_dir=data_dir)

        # Check for stub / NOT_DOWNLOADED manifest
        if manifest.status == "NOT_DOWNLOADED" or meta.download_date == "NOT_DOWNLOADED":
            status = "NOT_DOWNLOADED"
            results.append({
                "id": ds_id,
                "licence": meta.licence,
                "total": len(manifest.expected_hashes),
                "valid": 0,
                "missing": 0,
                "corrupt": 0,
                "status": status,
                "path": str(dataset_path),
            })
            continue

        # Check for fabricated hashes in manifest
        fabricated_hashes = [
            (rel, h) for rel, h in manifest.expected_hashes.items()
            if is_fabricated_hash(h)
        ]
        if fabricated_hashes:
            status = "FABRICATED"
            any_fabricated = True
            results.append({
                "id": ds_id,
                "licence": meta.licence,
                "total": len(manifest.expected_hashes),
                "valid": 0,
                "missing": len(manifest.expected_hashes),
                "corrupt": 0,
                "status": status,
                "path": str(dataset_path),
            })
            if verbose:
                print(f"\n[FABRICATED] {ds_id} contains placeholder/synthetic hashes:")
                for rel, h in fabricated_hashes:
                    print(f"  {h}  {rel}")
            continue

        total_files = len(manifest.expected_hashes)
        if not dataset_path.exists() or not dataset_path.is_dir():
            status = "MISSING"
            any_missing = True
            valid_count = 0
            missing_count = total_files
            corrupt_count = 0
        else:
            valid_files, missing_files, corrupt_files = manifest.audit_dataset_directory(dataset_path)
            valid_count = len(valid_files)
            missing_count = len(missing_files)
            corrupt_count = len(corrupt_files)

            if corrupt_count > 0:
                status = "CORRUPT"
                any_corrupt = True
            elif missing_count == 0 and valid_count > 0:
                status = "INTEGRITY_OK"
            elif valid_count > 0 and missing_count > 0:
                status = "MISSING"
                any_missing = True
            else:
                status = "MISSING"
                any_missing = True

            if verbose:
                print(f"\n--- Detailed File Report for {ds_id} ({dataset_path}) ---")
                for f_path in valid_files:
                    print(f"  [VALID]   {f_path}")
                for f_path in missing_files:
                    print(f"  [MISSING] {f_path}")
                for f_path in corrupt_files:
                    print(f"  [CORRUPT] {f_path}")

        results.append({
            "id": ds_id,
            "licence": meta.licence,
            "total": total_files,
            "valid": valid_count,
            "missing": missing_count,
            "corrupt": corrupt_count,
            "status": status,
            "path": str(dataset_path),
        })

    # Print summary table
    print(f"\n{'Dataset ID':<24} | {'Licence':<18} | {'Total':<5} | {'Valid':<5} | {'Miss':<5} | {'Corr':<5} | {'Status':<18}")
    print("-" * 96)
    for r in results:
        print(
            f"{r['id']:<24} | "
            f"{r['licence'][:18]:<18} | "
            f"{r['total']:<5} | "
            f"{r['valid']:<5} | "
            f"{r['missing']:<5} | "
            f"{r['corrupt']:<5} | "
            f"{r['status']:<18}"
        )

    print("-" * 96)
    print("\nOperational Status Summary:")
    print("  - INTEGRITY_OK: Real files present on disk with 100% SHA-256 manifest integrity.")
    print("  - NOT_DOWNLOADED: Dataset intentionally not acquired (stub manifest; not an error).")
    print("  - MISSING: Raw data not located at $SOC_DATA_DIR. Files must be acquired externally.")
    print("  - CORRUPT: Files exist on disk but SHA-256 hash fails against manifest (violates Rule R2).")
    print("  - FABRICATED: Manifest contains placeholder, synthetic, or invented hashes/files.")

    if any_fabricated:
        return 3
    if any_corrupt:
        return 2
    if any_missing:
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(description="Verify battery datasets against manifest checksums.")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Path to external raw data directory (defaults to $SOC_DATA_DIR or ~/soc_data).",
    )
    parser.add_argument(
        "--dataset",
        type=str,
        default=None,
        help="Verify a specific dataset ID (e.g. calce_a123).",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print detailed file-by-file audit.",
    )
    args = parser.parse_args()

    data_dir = args.data_dir or get_soc_data_dir()
    ret = verify_datasets(data_dir=data_dir, target_dataset=args.dataset, verbose=args.verbose)
    sys.exit(ret)


if __name__ == "__main__":
    main()
