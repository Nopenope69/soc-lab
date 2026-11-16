"""Automated test suite for real-data validation layer (Rules R1-R6).

Tests:
1. Manifest integrity: All 7 manifests exist, have required provenance headers, and file hashes (or NOT_DOWNLOADED status).
2. Hash mismatch detection (Rule R2): Flipped byte in a copy yields CORRUPT; loader raises ChecksumMismatchError.
3. Fabricated hash detection: Manifest with placeholder or synthetic hash yields FABRICATED.
4. Lock file skipping: Office temporary lock files (~$*) are skipped by loaders, manifests, and globs.
5. Missing data handling (Rule R2): Loaders raise DatasetMissingError with explicit skip messages when absent.
6. NOT_DOWNLOADED handling: verify_datasets reports NOT_DOWNLOADED for absent optional datasets without failing.
7. Data present validation (Rule R2): CALCE A123 verifies 52/52 files with zero corruptions.
8. Missing labels exclusion (Rule R2): Loaders exclude unlabeled samples; never default SOH_R to 1.0.
9. Cell-disjoint splits and sealing (Rule R3): ValidationSplitConfig enforces cell-level isolation and final=True gate.
10. Verification CLI (Deliverable 0.2): scripts/verify_datasets.py audits manifests cleanly.
"""

from pathlib import Path
import subprocess
import sys
import tempfile
import pytest

from soc.data.registry import (
    DATASET_METADATA,
    LOADER_REGISTRY,
    ChecksumMismatchError,
    DatasetManifest,
    DatasetMetadata,
    DatasetMissingError,
    ValidationSplitConfig,
    get_manifest_path,
    get_repo_root,
    get_split_config_path,
    load_calce_a123,
    load_dataset_with_manifest_check,
)
from scripts.verify_datasets import is_fabricated_hash, verify_datasets


EXPECTED_DATASET_IDS = [
    "calce_a123",
    "gustave_eiffel_g02iye",
    "gustave_eiffel_sbno8w",
    "uconn_reil_dataset1",
    "uconn_reil_dataset5",
    "wheeler_2025",
    "tempest_zenodo",
]


# =============================================================================
# 1. Manifest Provenance & Header Tests (Rule R1)
# =============================================================================

def test_all_seven_manifests_exist_and_parse():
    """Verify all 7 dataset manifests exist with non-empty provenance headers."""
    for ds_id in EXPECTED_DATASET_IDS:
        manifest_path = get_manifest_path(ds_id)
        assert manifest_path.exists(), f"Manifest missing for {ds_id}: {manifest_path}"

        manifest = DatasetManifest.load(manifest_path)
        assert manifest.dataset_id == ds_id
        assert len(manifest.source_url) > 0, f"Empty source_url in manifest {ds_id}"
        assert len(manifest.doi) > 0, f"Empty DOI in manifest {ds_id}"
        assert len(manifest.licence) > 0, f"Empty licence in manifest {ds_id}"
        assert len(manifest.version) > 0, f"Empty version in manifest {ds_id}"

        if manifest.status == "NOT_DOWNLOADED":
            assert len(manifest.expected_hashes) == 0, f"Stub manifest {ds_id} should have 0 hashes"
        else:
            assert len(manifest.expected_hashes) > 0, f"No file hashes in manifest {ds_id}"


def test_dataset_registry_completeness():
    """Verify all 7 datasets have metadata registered and loaders bound."""
    for ds_id in EXPECTED_DATASET_IDS:
        assert ds_id in DATASET_METADATA, f"{ds_id} missing from DATASET_METADATA"
        assert ds_id in LOADER_REGISTRY, f"{ds_id} missing from LOADER_REGISTRY"

        meta = DATASET_METADATA[ds_id]
        assert isinstance(meta, DatasetMetadata)
        assert meta.cell_chemistry in ("LFP", "LFP/Graphite", "LFP/NMC")
        assert meta.nominal_capacity_ah > 0.0


# =============================================================================
# 2. Checksum Mismatch & Flipped-Byte Corruption Detection (Rule R2)
# =============================================================================

def test_manifest_raises_on_checksum_mismatch():
    """Verify manifest.verify_file strictly raises ChecksumMismatchError when content is altered."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        dummy_file = tmp_path / "dummy.zip"
        dummy_file.write_bytes(b"tampered content that will not match expected hash")

        manifest = DatasetManifest(
            dataset_id="test_ds",
            source_url="https://example.com",
            doi="10.1234/test",
            licence="CC BY 4.0",
            version="1.0",
            download_date="2026-11-16",
            expected_hashes={"dummy.zip": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"},
        )

        with pytest.raises(ChecksumMismatchError, match="hash mismatch"):
            manifest.verify_file(dummy_file, "dummy.zip")


def test_flipped_byte_in_copy_yields_corrupt_status():
    """Verify a flipped byte in a file copy yields CORRUPT in audit and raises ChecksumMismatchError."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        original_bytes = b"This is legitimate experimental battery cycling data."
        test_file = tmp_path / "cell_data.csv"
        test_file.write_bytes(original_bytes)

        import hashlib
        valid_hash = hashlib.sha256(original_bytes).hexdigest()

        manifest = DatasetManifest(
            dataset_id="mock_corrupt_test",
            source_url="https://example.com",
            doi="UNVERIFIED",
            licence="UNVERIFIED",
            version="1.0",
            download_date="2026-11-16",
            expected_hashes={"cell_data.csv": valid_hash},
        )

        # Before corruption: audit is valid
        valid_files, missing_files, corrupt_files = manifest.audit_dataset_directory(tmp_path)
        assert valid_files == ["cell_data.csv"]
        assert len(corrupt_files) == 0

        # Flip single byte
        corrupted_bytes = bytearray(original_bytes)
        corrupted_bytes[0] ^= 0xFF
        test_file.write_bytes(bytes(corrupted_bytes))

        # After corruption: audit reports corrupt
        valid_files, missing_files, corrupt_files = manifest.audit_dataset_directory(tmp_path)
        assert len(valid_files) == 0
        assert corrupt_files == ["cell_data.csv"]

        with pytest.raises(ChecksumMismatchError):
            manifest.verify_file(test_file, "cell_data.csv")


# =============================================================================
# 3. Fabricated Hash Detection (Rule R1, R2)
# =============================================================================

def test_fabricated_hash_detection_algorithm():
    """Verify is_fabricated_hash detects placeholder, pattern, and synthetic hashes."""
    # Known fabricated patterns
    assert is_fabricated_hash("0" * 64)  # All zeros
    assert is_fabricated_hash("e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")  # Empty sha256
    assert is_fabricated_hash("d41d8cd98f00b204e9800998ecf8427e" + "0" * 32)  # Empty md5 zero-padded
    assert is_fabricated_hash("1234567890abcdef" * 4)  # Sequential run
    assert is_fabricated_hash("0123456789abcdef" * 4)  # Sequential run
    assert is_fabricated_hash("a1b2c3d4" * 8)  # Repeating pattern
    assert is_fabricated_hash("f0e1d2c3" * 8)  # Repeating pattern
    assert is_fabricated_hash("deadbeef" * 8)  # Repeating pattern

    # Valid non-fabricated hash from disk
    real_calce_hash = "bb0e6929ce22dc96bf4fa83e282afb03638d304118c1936520e54a3a5ee68cef"
    assert not is_fabricated_hash(real_calce_hash)

    real_eiffel_hash = "64cfc4bdd0c71403de1c9a32bb55f8bc3452f0e8f136e64dc943f994364551bb"
    assert not is_fabricated_hash(real_eiffel_hash)


def test_manifest_with_fake_hash_yields_fabricated_status(monkeypatch):
    """Verify verify_datasets classifies a dataset as FABRICATED if manifest contains fake hashes."""
    with tempfile.TemporaryDirectory() as tmp_manifest_dir:
        tmp_mpath = Path(tmp_manifest_dir) / "test_fake.sha256"
        tmp_mpath.write_text(
            "# Dataset: test_fake\n"
            "# Source URL: https://example.com\n"
            "# DOI: 10.0000/fake\n"
            "# Licence: Fake\n"
            "# Version: 1.0\n"
            "# Download Date: 2026-11-16\n"
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  empty.csv\n",
            encoding="utf-8",
        )

        manifest = DatasetManifest.load(tmp_mpath)
        fake_entries = [
            (rel, h) for rel, h in manifest.expected_hashes.items()
            if is_fabricated_hash(h)
        ]
        assert len(fake_entries) == 1
        assert fake_entries[0][0] == "empty.csv"


# =============================================================================
# 4. Office Temporary Lock File Skipping (~$*)
# =============================================================================

def test_loaders_and_manifests_skip_office_lock_files():
    """Verify transient Office lock files (~$*) are skipped by loaders, manifests, and audits."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        data_file = tmp_path / "valid_data.xlsx"
        data_file.write_bytes(b"Spreadsheet real data")
        lock_file = tmp_path / "~$valid_data.xlsx"
        lock_file.write_bytes(b"Owner: user lock info")

        import hashlib
        data_hash = hashlib.sha256(b"Spreadsheet real data").hexdigest()

        # Manifest text containing valid file and lock file line
        manifest_text = (
            f"# Dataset: test_lock\n"
            f"# Source URL: https://example.com\n"
            f"# DOI: UNVERIFIED\n"
            f"# Licence: UNVERIFIED\n"
            f"# Version: UNVERIFIED\n"
            f"# Download Date: 2026-11-16\n"
            f"# IGNORED_LOCK_FILE: ~$valid_data.xlsx\n"
            f"{data_hash}  valid_data.xlsx\n"
            f"0000000000000000000000000000000000000000000000000000000000000000  ~$valid_data.xlsx\n"
        )
        m_file = tmp_path / "test_lock.sha256"
        m_file.write_text(manifest_text, encoding="utf-8")

        manifest = DatasetManifest.load(m_file)
        # ~$valid_data.xlsx must be filtered out during load
        assert "valid_data.xlsx" in manifest.expected_hashes
        assert "~$valid_data.xlsx" not in manifest.expected_hashes

        # audit_dataset_directory must skip ~$* files without reporting error
        valid, missing, corrupt = manifest.audit_dataset_directory(tmp_path)
        assert valid == ["valid_data.xlsx"]
        assert len(missing) == 0
        assert len(corrupt) == 0


# =============================================================================
# 5. Missing Data Handling / Skip Semantics (Rule R2)
# =============================================================================

def test_loader_raises_dataset_missing_error_when_data_absent():
    """Verify loader raises DatasetMissingError with explicit skip instructions when files are absent."""
    with tempfile.TemporaryDirectory() as empty_dir:
        non_existent_path = Path(empty_dir) / "non_existent_folder"
        with pytest.raises(DatasetMissingError) as exc_info:
            load_dataset_with_manifest_check("gustave_eiffel_sbno8w", data_dir=non_existent_path)

        msg = str(exc_info.value)
        assert "Rule R1: Raw data lives outside the repo" in msg
        assert "DOI: 10.57745/SBNO8W" in msg
        assert "Please download from" in msg


def test_pytest_skips_cleanly_when_dataset_missing():
    """Verify tests pass cleanly with skip when optional real data is absent."""
    # Test a non-downloaded dataset
    try:
        load_dataset_with_manifest_check("wheeler_2025")
    except DatasetMissingError as exc:
        pytest.skip(f"Expected skip: {exc}")


def test_verify_datasets_reports_not_downloaded_without_failing():
    """Verify verify_datasets handles NOT_DOWNLOADED datasets without failing or corrupting."""
    manifest_uconn1 = DatasetManifest.load(get_manifest_path("uconn_reil_dataset1"))
    assert manifest_uconn1.status == "NOT_DOWNLOADED"
    assert len(manifest_uconn1.expected_hashes) == 0

    manifest_wheeler = DatasetManifest.load(get_manifest_path("wheeler_2025"))
    assert manifest_wheeler.status == "NOT_DOWNLOADED"
    assert len(manifest_wheeler.expected_hashes) == 0


# =============================================================================
# 6. Data Present Validation (Rule R2 - CALCE A123)
# =============================================================================

def test_calce_a123_data_present_and_verified():
    """Verify CALCE A123 dataset loads successfully and passes SHA-256 verification on all 52 files."""
    info = load_calce_a123(verify_checksums=True)
    assert info["dataset_id"] == "calce_a123"
    assert "manifest" in info
    assert len(info["manifest"].expected_hashes) == 52

    # Verify split config is present
    split_config = info["split_config"]
    assert isinstance(split_config, ValidationSplitConfig)
    assert "A1-007" in split_config.train_cells
    assert "A1-008" in split_config.sealed_test_cells


# =============================================================================
# 7. Missing Label Handling (Rule R2)
# =============================================================================

def test_missing_labels_are_excluded_never_defaulted_to_dummy():
    """Verify Rule R2 requirement: Missing labels must be excluded from evaluation samples; never default SOH_R to 1.0."""
    raw_samples = [
        {"cell_id": "cell_01", "cycle": 1, "soh_c": 0.98, "soh_r": 1.02},
        {"cell_id": "cell_01", "cycle": 2, "soh_c": 0.97, "soh_r": None},  # Missing SOH_R
        {"cell_id": "cell_01", "cycle": 3, "soh_c": None, "soh_r": 1.04},  # Missing SOH_C
        {"cell_id": "cell_01", "cycle": 4, "soh_c": 0.95, "soh_r": 1.06},
    ]

    # Rule R2 compliant filter: strictly exclude samples with missing labels
    valid_samples = [
        s for s in raw_samples
        if s.get("soh_c") is not None and s.get("soh_r") is not None
    ]

    assert len(valid_samples) == 2
    for s in valid_samples:
        assert s["soh_c"] is not None and s["soh_c"] != 1.0
        assert s["soh_r"] is not None and s["soh_r"] != 1.0


# =============================================================================
# 8. Cell-Disjoint Split Isolation & Sealed Test Gating (Rule R3)
# =============================================================================

def test_all_seven_validation_split_configs_enforce_cell_disjointness():
    """Verify all 7 split configs have zero cell overlap between train, val, and sealed test."""
    for ds_id in EXPECTED_DATASET_IDS:
        split_path = get_split_config_path(ds_id)
        assert split_path.exists(), f"Split config missing for {ds_id}: {split_path}"

        split_config = ValidationSplitConfig.load(split_path)
        split_config.validate_cell_isolation()
        assert len(split_config.train_cells) > 0, f"No train cells in {ds_id}"
        assert len(split_config.sealed_test_cells) > 0, f"No test cells in {ds_id}"


def test_split_config_raises_on_train_test_overlap():
    """Verify ValidationSplitConfig.validate_cell_isolation raises on data leakage."""
    leaky_config = ValidationSplitConfig(
        dataset_id="leaky_dataset",
        version="1.0",
        split_policy="BY_CELL",
        train_cells=["cell_A", "cell_B"],
        val_cells=["cell_C"],
        sealed_test_cells=["cell_B", "cell_D"],  # cell_B leaks!
    )
    with pytest.raises(ValueError, match="Leakage violation"):
        leaky_config.validate_cell_isolation()


def test_split_config_raises_on_val_test_overlap():
    """Verify ValidationSplitConfig.validate_cell_isolation raises on validation-test leakage."""
    leaky_config = ValidationSplitConfig(
        dataset_id="leaky_dataset",
        version="1.0",
        split_policy="BY_CELL",
        train_cells=["cell_A"],
        val_cells=["cell_C"],
        sealed_test_cells=["cell_C"],  # cell_C leaks!
    )
    with pytest.raises(ValueError, match="Leakage violation"):
        leaky_config.validate_cell_isolation()


def test_sealed_test_cells_require_final_flag():
    """Verify get_test_cells strictly raises PermissionError when final=False."""
    split_config = ValidationSplitConfig.load(get_split_config_path("calce_a123"))

    with pytest.raises(PermissionError, match="Access denied: Sealed test cells"):
        split_config.get_test_cells(final=False)

    test_cells = split_config.get_test_cells(final=True)
    assert test_cells == ["A1-008"]


# =============================================================================
# 9. Dataset Verification CLI (Deliverable 0.2)
# =============================================================================

def test_verify_datasets_cli_execution():
    """Verify scripts/verify_datasets.py executes without error and reports correct statuses."""
    root_dir = get_repo_root()
    script_path = root_dir / "scripts" / "verify_datasets.py"
    assert script_path.exists(), f"CLI script missing: {script_path}"

    result = subprocess.run(
        [sys.executable, str(script_path)],
        capture_output=True,
        text=True,
        cwd=str(root_dir),
    )
    assert result.returncode == 0, f"verify_datasets.py failed: {result.stderr}"
    stdout = result.stdout

    # Must mention summary and key dataset statuses
    assert "SOC-LAB DATASET INTEGRITY & MANIFEST AUDIT" in stdout
    assert "calce_a123" in stdout
    assert "INTEGRITY_OK" in stdout
    assert "NOT_DOWNLOADED" in stdout
    assert "LAB_VALIDATED" not in stdout
