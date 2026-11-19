#!/usr/bin/env python3
"""Verify byte-identity of extracted UConn REIL CSV files against rpt_data.zip.

Directly compares the SHA-256 hash of each member in $SOC_DATA_DIR/uconn_reil/rpt_data.zip
with the corresponding extracted file on disk ($SOC_DATA_DIR/uconn_reil/extracted/rpt_data/...).
"""

import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path


def compute_sha256(data_bytes: bytes) -> str:
    h = hashlib.sha256()
    h.update(data_bytes)
    return h.hexdigest()


def compute_file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify extracted UConn REIL CSV files against rpt_data.zip members."
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path(os.environ.get("SOC_DATA_DIR", "/Users/tecbusiness/soc_data")),
        help="Path to soc_data root directory.",
    )
    args = parser.parse_args()

    zip_path = args.data_dir / "uconn_reil" / "rpt_data.zip"
    extracted_root = args.data_dir / "uconn_reil" / "extracted"

    if not zip_path.is_file():
        print(f"ERROR: Zip archive not found: {zip_path}", file=sys.stderr)
        return 2

    if not extracted_root.is_dir():
        print(f"ERROR: Extracted directory not found: {extracted_root}", file=sys.stderr)
        return 2

    print(f"Verifying extracted UConn CSV files against archive: {zip_path}")
    print(f"Extracted directory root: {extracted_root}")
    print("-" * 72)

    total_members = 0
    identical_count = 0
    different_count = 0
    missing_count = 0

    with zipfile.ZipFile(zip_path, "r") as z:
        infolist = [info for info in z.infolist() if not info.is_dir()]
        total_members = len(infolist)

        for info in infolist:
            member_name = info.filename
            extracted_file = extracted_root / member_name

            if not extracted_file.is_file():
                print(f"MISSING: {member_name} not found at {extracted_file}")
                missing_count += 1
                continue

            zip_member_bytes = z.read(info)
            zip_member_hash = compute_sha256(zip_member_bytes)
            extracted_file_hash = compute_file_sha256(extracted_file)

            if zip_member_hash == extracted_file_hash:
                identical_count += 1
            else:
                print(
                    f"DIFFERENT: {member_name} (zip: {zip_member_hash}, disk: {extracted_file_hash})"
                )
                different_count += 1

    print("-" * 72)
    print(f"Total zip members: {total_members}")
    print(f"Identical files:   {identical_count}")
    print(f"Different files:   {different_count}")
    print(f"Missing files:     {missing_count}")

    if different_count > 0 or missing_count > 0 or identical_count != total_members:
        print("VERIFICATION FAILED: Mismatched or missing extracted files.", file=sys.stderr)
        return 1

    print("VERIFICATION SUCCESS: All extracted files match zip members byte-for-byte.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
