#!/usr/bin/env python3
"""Generate verified dataset manifests and JSON sidecars from files on disk.

Enforces:
1. NEVER invent anything. A SHA-256 hash may ONLY come from hashing a file that exists on disk.
2. File names come ONLY from walking real folders on disk.
3. Metadata comes ONLY from verified facts or files on disk; anything else is marked UNVERIFIED.
4. Download date is set to file modification date on disk.
5. All file checks, walks, and globs skip Microsoft Office lock files starting with '~$' and .DS_Store.
6. Refuse to overwrite an existing manifest without --force and print a diff.
"""

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import sys
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_DATA_ROOT = Path(os.environ.get("SOC_DATA_DIR", Path.home() / "soc_data")).resolve()
REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST_DIR = REPO_ROOT / "data" / "manifests"


# Verified facts registry
DATASET_SPECS: Dict[str, Dict[str, Any]] = {
    "gustave_eiffel_g02iye": {
        "title": "Characterisation tests of LFP 105Ah cells",
        "doi": "10.57745/G02IYE",
        "source_url": "https://doi.org/10.57745/G02IYE",
        "repository": "Recherche Data Gouv",
        "licence": "Etalab 2.0",
        "version": "2.0",
        "published": "2024",
        "creators": "P. Von Hohendorff Seger and E. Redondo-Iglesias (Universite Gustave Eiffel)",
        "cell": "EVE Energy LFP 105 Ah, four cells BUGE388..BUGE391",
        "citation": "P. Seger, E. Redondo-Iglesias, S. Pelissier, \"Influence of parameter identification choices on a Li-ion battery electric model\", ELECTRIMACS 2024",
        "folder_rel": "gustave_eiffel_105ah",
        "is_stub": False,
        "notes": [
            "0_raw_data and 1_pre_processed_data archives are NOT_DOWNLOADED",
        ],
        # Filter: includes main_G02IYE archive and main_extracted tree
        "file_filter": lambda rel_p: rel_p.startswith("main_G02IYE_dataverse_files.zip") or rel_p.startswith("main_extracted/"),
    },
    "gustave_eiffel_sbno8w": {
        "title": "Electrical model parameters of LFP 105Ah cells",
        "doi": "10.57745/SBNO8W",
        "source_url": "https://doi.org/10.57745/SBNO8W",
        "repository": "Recherche Data Gouv",
        "licence": "UNVERIFIED",
        "version": "UNVERIFIED",
        "published": "2024",
        "creators": "UNVERIFIED",
        "cell": "EVE Energy LFP 105 Ah, four cells BUGE388..BUGE391",
        "citation": "UNVERIFIED",
        "folder_rel": "gustave_eiffel_105ah",
        "is_stub": False,
        "notes": [],
        # Filter: includes params_SBNO8W archive and params_extracted tree
        "file_filter": lambda rel_p: rel_p.startswith("params_SBNO8W_dataverse_files.zip") or rel_p.startswith("params_extracted/"),
    },
    "uconn_reil_dataset5": {
        "title": "UConn-ISU-ILCC LFP/Gr Battery Aging Dataset",
        "doi": "https://doi.org/10.1016/j.jpowsour.2024.235813",
        "source_url": "https://digitalcommons.lib.uconn.edu/reil_datasets/5",
        "repository": "DigitalCommons@UConn",
        "licence": "CC BY 4.0",
        "version": "UNVERIFIED",
        "published": "2025",
        "creators": "Benjamin Nowacki, Jayanth Ramamurthy, Adam Thelen, Chad Tischer, Cary L. Pint, Chao Hu",
        "cell": "LithiumWerks 18650 power cells (APR18650M1B), nominal capacity 1.2 Ah",
        "citation": "Benjamin Nowacki, Jayanth Ramamurthy, Adam Thelen, Chad Tischer, Cary L. Pint, Chao Hu, \"Rapid estimation of lithium-ion battery capacity and resistances from short duration current pulses\", Journal of Power Sources, Vol. 628 (2025), 235813",
        "folder_rel": "uconn_reil",
        "is_stub": False,
        "notes": [
            "Data repository DOI is UNVERIFIED; publication DOI is verified from README_Uconn.txt",
        ],
        "file_filter": lambda rel_p: True,
    },
    "tempest_zenodo": {
        "title": "TEMPEST project 280 Ah LFP prismatic cell dataset",
        "doi": "UNVERIFIED",
        "source_url": "https://zenodo.org/records/19632939",
        "repository": "Zenodo",
        "licence": "UNVERIFIED",
        "version": "UNVERIFIED",
        "published": "2026-04-17",
        "creators": "University of Bath, EU TEMPEST project",
        "cell": "280 Ah LFP prismatic cell (project TEMPEST 'LIC' cell)",
        "citation": "UNVERIFIED",
        "folder_rel": "tempest_280ah",
        "is_stub": False,
        "notes": [
            "Zenodo record URL verified: https://zenodo.org/records/19632939",
            "DOI in previous manifest was INVENTED and must not be used",
        ],
        "file_filter": lambda rel_p: True,
    },
    "uconn_reil_dataset1": {
        "title": "UConn-ISU-ILCC LFP/Gr Battery Aging Dataset (Dataset 1)",
        "doi": "UNVERIFIED",
        "source_url": "https://digitalcommons.lib.uconn.edu/reil_datasets/1/",
        "repository": "DigitalCommons@UConn",
        "licence": "CC BY 4.0",
        "version": "UNVERIFIED",
        "published": "2025",
        "creators": "UNVERIFIED",
        "cell": "64 LithiumWerks APR18650M1B cells, 11 conditions",
        "citation": "UNVERIFIED",
        "folder_rel": "uconn_reil_dataset1",
        "is_stub": True,
        "status": "NOT_DOWNLOADED",
        "notes": [
            "NOT_DOWNLOADED: cycling_part1.zip, cycling_part2.zip, CyclingParameters.csv not present on disk",
        ],
    },
    "wheeler_2025": {
        "title": "An ageing study of twenty 18650 lithium-ion Graphite/LFP cells in first and second life use",
        "doi": "10.1038/s41597-025-04712-7",
        "source_url": "UNVERIFIED",
        "repository": "UNVERIFIED",
        "licence": "UNVERIFIED",
        "version": "UNVERIFIED",
        "published": "2025",
        "creators": "Wheeler, Bultel, Venet, Sari",
        "cell": "twenty 18650 lithium-ion Graphite/LFP cells",
        "citation": "Wheeler, Bultel, Venet, Sari; Scientific Data 2025",
        "folder_rel": "wheeler_a123",
        "is_stub": True,
        "status": "NOT_DOWNLOADED",
        "notes": [
            "NOT_DOWNLOADED: Data repository and files not acquired",
            "Previous repository URL (Recherche Data Gouv) was INVENTED and must not be used",
        ],
    },
}


def should_skip_file(path: Path) -> bool:
    """Check if file is an ignored lock file or OS metadata."""
    if path.name.startswith("~$"):
        return True
    if path.name in (".DS_Store", "Thumbs.db"):
        return True
    return False


def hash_file_sha256(path: Path) -> str:
    """Compute sha256 checksum reading in chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def format_manifest(
    dataset_id: str,
    spec: Dict[str, Any],
    file_records: List[Dict[str, Any]],
    download_date: str,
) -> str:
    """Generate canonical manifest text with verified facts header and sorted hashes."""
    lines: List[str] = [
        f"# Dataset: {dataset_id}",
        f"# Name: {spec['title']}",
        f"# Source URL: {spec['source_url']}",
        f"# DOI: {spec['doi']}",
        f"# Licence: {spec['licence']}",
        f"# Version: {spec['version']}",
        f"# Published: {spec.get('published', 'UNVERIFIED')}",
        f"# Download Date: {download_date}",
    ]
    if spec.get("is_stub"):
        lines.append(f"# Status: {spec.get('status', 'NOT_DOWNLOADED')}")
    if spec.get("cell"):
        lines.append(f"# Cell: {spec['cell']}")
    if spec.get("citation") and spec["citation"] != "UNVERIFIED":
        lines.append(f"# Citation: {spec['citation']}")
    if spec.get("creators") and spec["creators"] != "UNVERIFIED":
        lines.append(f"# Creators: {spec['creators']}")
    for note in spec.get("notes", []):
        lines.append(f"# Note: {note}")

    for rec in file_records:
        lines.append(f"{rec['sha256']}  {rec['rel_path']}")

    return "\n".join(lines) + "\n"


def make_manifest_for_dataset(
    dataset_id: str,
    data_root: Path,
    manifest_dir: Path,
    force: bool = False,
) -> Tuple[bool, str]:
    """Generate manifest and sidecar for dataset. Returns (success, message)."""
    if dataset_id not in DATASET_SPECS:
        return False, f"Unknown dataset ID: {dataset_id}"

    spec = DATASET_SPECS[dataset_id]
    manifest_path = manifest_dir / f"{dataset_id}.sha256"
    sidecar_path = manifest_dir / f"{dataset_id}.json"

    file_records: List[Dict[str, Any]] = []
    latest_mtime: float = 0.0

    if spec.get("is_stub"):
        download_date = "NOT_DOWNLOADED"
    else:
        folder = data_root / spec["folder_rel"]
        if not folder.exists() or not folder.is_dir():
            return False, f"Dataset folder does not exist on disk: {folder}"

        filter_fn = spec.get("file_filter", lambda p: True)

        for root, dirs, files in os.walk(folder):
            # Sort for reproducibility
            dirs.sort()
            files.sort()
            for fname in files:
                fpath = Path(root) / fname
                if should_skip_file(fpath):
                    continue
                rel_p = str(fpath.relative_to(folder)).replace("\\", "/")
                if not filter_fn(rel_p):
                    continue

                stat = fpath.stat()
                mtime = stat.st_mtime
                if mtime > latest_mtime:
                    latest_mtime = mtime

                file_hash = hash_file_sha256(fpath)
                file_records.append({
                    "rel_path": rel_p,
                    "size_bytes": stat.st_size,
                    "mtime_iso": datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat(),
                    "sha256": file_hash,
                })

        if latest_mtime > 0:
            download_date = datetime.fromtimestamp(latest_mtime, tz=timezone.utc).strftime("%Y-%m-%d")
        else:
            download_date = "UNVERIFIED"

    # Sort file records deterministically
    file_records.sort(key=lambda r: r["rel_path"])

    manifest_content = format_manifest(dataset_id, spec, file_records, download_date)

    sidecar_data = {
        "dataset_id": dataset_id,
        "title": spec["title"],
        "source_url": spec["source_url"],
        "doi": spec["doi"],
        "licence": spec["licence"],
        "version": spec["version"],
        "status": spec.get("status", "INTEGRITY_OK" if file_records else "NOT_DOWNLOADED"),
        "download_date": download_date,
        "cell": spec.get("cell", "UNVERIFIED"),
        "file_count": len(file_records),
        "total_bytes": sum(r["size_bytes"] for r in file_records),
        "files": file_records,
    }

    # Check overwrite protection
    if manifest_path.exists() and not force:
        existing_text = manifest_path.read_text(encoding="utf-8")
        if existing_text != manifest_content:
            diff = "".join(
                difflib.unified_diff(
                    existing_text.splitlines(keepends=True),
                    manifest_content.splitlines(keepends=True),
                    fromfile=str(manifest_path),
                    tofile="new_manifest",
                )
            )
            return False, (
                f"Manifest for {dataset_id} already exists and differs. "
                f"Refusing to overwrite without --force.\nDiff:\n{diff}"
            )
        else:
            # Identical content, write sidecar if missing
            if not sidecar_path.exists() or force:
                sidecar_path.write_text(json.dumps(sidecar_data, indent=2), encoding="utf-8")
            return True, f"Manifest for {dataset_id} is identical. No changes needed."

    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(manifest_content, encoding="utf-8")
    sidecar_path.write_text(json.dumps(sidecar_data, indent=2), encoding="utf-8")

    return True, f"Successfully wrote manifest ({len(file_records)} files) and sidecar for {dataset_id}"


def main():
    parser = argparse.ArgumentParser(description="Generate dataset manifests from disk files.")
    parser.add_argument("--dataset", type=str, help="Dataset ID to generate manifest for")
    parser.add_argument("--all", action="store_true", help="Generate manifests for all datasets")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing manifests")
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT, help="Path to soc_data root")
    parser.add_argument("--manifest-dir", type=Path, default=DEFAULT_MANIFEST_DIR, help="Output manifest directory")

    args = parser.parse_args()

    if not args.dataset and not args.all:
        parser.error("Must specify either --dataset <id> or --all")

    targets = list(DATASET_SPECS.keys()) if args.all else [args.dataset]

    errors = []
    for ds_id in targets:
        success, msg = make_manifest_for_dataset(
            dataset_id=ds_id,
            data_root=args.data_root,
            manifest_dir=args.manifest_dir,
            force=args.force,
        )
        print(f"[{'OK' if success else 'FAIL'}] {ds_id}: {msg}")
        if not success:
            errors.append(ds_id)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
