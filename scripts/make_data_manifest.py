"""Generate SHA-256 checksum manifest of all CALCE A123 raw data files.

Usage:
    python scripts/make_data_manifest.py
Outputs:
    data/MANIFEST_calce_a123.sha256
"""

import hashlib
import os
from pathlib import Path


def hash_file(filepath: Path) -> str:
    """Compute SHA-256 hex digest of a file in streaming chunks."""
    hasher = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def main():
    repo_root = Path(__file__).resolve().parents[1]
    raw_dir_env = os.environ.get("SOC_DATA_DIR")
    if raw_dir_env:
        p = Path(raw_dir_env)
        raw_dir = p if p.name == "calce_a123" else p / "calce_a123"
    else:
        raw_dir = repo_root / "data" / "raw" / "calce_a123"

    if not raw_dir.exists():
        print(f"Error: CALCE raw data directory not found at {raw_dir}")
        return 1

    manifest_file = repo_root / "data" / "MANIFEST_calce_a123.sha256"
    manifest_file.parent.mkdir(parents=True, exist_ok=True)

    records = []
    for path in sorted(raw_dir.rglob("*")):
        if path.is_file():
            # Skip transient Office lock files
            if path.name.startswith("~$") or path.name.startswith("."):
                continue
            rel_path = path.relative_to(raw_dir)
            sha256 = hash_file(path)
            records.append((sha256, str(rel_path)))

    with open(manifest_file, "w", encoding="utf-8") as f:
        for sha256, rel_path in records:
            f.write(f"{sha256}  {rel_path}\n")

    print(f"Wrote {len(records)} entries to {manifest_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
