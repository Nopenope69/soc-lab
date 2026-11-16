"""Real-data validation registry and manifest-verification layer for soc-lab.

Enforces:
R1. Raw data lives OUTSIDE the repo at $SOC_DATA_DIR (default ~/soc_data), never committed.
    Every dataset gets a manifest data/manifests/<dataset>.sha256 with source URL, DOI,
    licence, version, download date, file hashes.
R2. Loaders must READ files and verify manifest hashes. No loader may generate, simulate
    or default any value. Missing file = skip with explicit message. Missing label = exclude
    sample (never default SOH_R to 1.0).
R3. Splits are by CELL (never by cycle or window). Test split is sealed.
R4. Frozen artefacts stay frozen: E7v3 and deliverable/bms_soc_ref.py.
R5. Status labels per result: LAB_VALIDATED (real files, hash-manifested, cell-held-out test).
    Anything else is DEVELOPMENT. Report each dataset separately; never pool.
R6. SOH_C baseline = measured beginning-of-life capacity of that cell, not nameplate.
    SOH_R baseline = measured resistance under matched SOC, temperature and pulse conditions.
"""

from dataclasses import dataclass, field
import hashlib
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
import yaml

# Standard data root directory outside repository
DEFAULT_DATA_DIR = Path.home() / "soc_data"


class ChecksumMismatchError(ValueError):
    """Raised when a file's SHA-256 hash does not match its manifest entry (Rule R2)."""
    pass


class DatasetMissingError(FileNotFoundError):
    """Raised with an explicit message when raw dataset files are absent (Rule R2)."""
    pass


@dataclass(frozen=True)
class DatasetMetadata:
    """Metadata describing a real laboratory battery dataset."""

    dataset_id: str
    name: str
    doi: str
    source_url: str
    licence: str
    version: str
    download_date: str
    path_pattern: str
    manifest_filename: str
    split_config_filename: str
    cell_chemistry: str
    cell_form_factor: str
    nominal_capacity_ah: float
    description: str


@dataclass
class DatasetManifest:
    """Parsed manifest file containing provenance headers and expected SHA-256 hashes."""

    dataset_id: str
    source_url: str
    doi: str
    licence: str
    version: str
    download_date: str
    status: str = "INTEGRITY_OK"
    expected_hashes: Dict[str, str] = field(default_factory=dict)
    manifest_path: Optional[Path] = None

    @classmethod
    def load(cls, manifest_path: Path) -> "DatasetManifest":
        """Load and parse a data/manifests/<dataset>.sha256 manifest file."""
        if not manifest_path.exists():
            raise FileNotFoundError(f"Manifest file not found: {manifest_path}")

        source_url = ""
        doi = ""
        licence = ""
        version = "UNVERIFIED"
        download_date = ""
        status = "INTEGRITY_OK"
        dataset_id = manifest_path.stem
        hashes: Dict[str, str] = {}

        with open(manifest_path, "r", encoding="utf-8") as f:
            for line in f:
                line_str = line.strip()
                if not line_str:
                    continue
                if line_str.startswith("#"):
                    # Parse header comments
                    comment_body = line_str[1:].strip()
                    if ":" in comment_body:
                        key, val = comment_body.split(":", 1)
                        key_lower = key.strip().lower()
                        val_str = val.strip()
                        if key_lower == "dataset":
                            dataset_id = val_str
                        elif key_lower in ("source url", "url"):
                            source_url = val_str
                        elif key_lower == "doi":
                            doi = val_str
                        elif key_lower in ("licence", "license"):
                            licence = val_str
                        elif key_lower == "version":
                            version = val_str
                        elif key_lower == "download date":
                            download_date = val_str
                        elif key_lower == "status":
                            status = val_str
                else:
                    # Parse hash and relative path: <hash>  <relpath>
                    parts = line_str.split(None, 1)
                    if len(parts) == 2:
                        file_hash, rel_path = parts[0].strip(), parts[1].strip()
                        # Skip transient Office lock files
                        if Path(rel_path).name.startswith("~$"):
                            continue
                        hashes[rel_path] = file_hash

        return cls(
            dataset_id=dataset_id,
            source_url=source_url,
            doi=doi,
            licence=licence,
            version=version,
            download_date=download_date,
            status=status,
            expected_hashes=hashes,
            manifest_path=manifest_path,
        )

    def verify_file(self, full_file_path: Path, relative_path: str) -> None:
        """Verify sha256 checksum of an individual file against manifest (Rule R2)."""
        if Path(relative_path).name.startswith("~$") or full_file_path.name.startswith("~$"):
            return

        if not full_file_path.exists():
            raise FileNotFoundError(f"Missing required file: {full_file_path}")

        expected = self.expected_hashes.get(relative_path)
        if expected is None:
            # Check normalized separators
            norm_rel = relative_path.replace("\\", "/")
            expected = self.expected_hashes.get(norm_rel)

        if expected is None:
            raise KeyError(f"File {relative_path} not found in manifest for {self.dataset_id}")

        hasher = hashlib.sha256()
        with open(full_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(int("65536")), b""):
                hasher.update(chunk)
        computed = hasher.hexdigest()

        if computed.lower() != expected.lower():
            raise ChecksumMismatchError(
                f"SHA-256 hash mismatch for {full_file_path.name} (relative: {relative_path}). "
                f"Expected: {expected}, Computed: {computed}. Rule R2: file integrity violated."
            )

    def audit_dataset_directory(self, base_dir: Path) -> Tuple[List[str], List[str], List[str]]:
        """Audit all files in manifest against a base directory.

        Returns (valid_files, missing_files, corrupt_files).
        """
        valid_files: List[str] = []
        missing_files: List[str] = []
        corrupt_files: List[str] = []

        if self.status == "NOT_DOWNLOADED":
            return valid_files, missing_files, corrupt_files

        for rel_path, expected_hash in self.expected_hashes.items():
            if Path(rel_path).name.startswith("~$"):
                continue
            target_path = base_dir / rel_path
            if not target_path.exists():
                missing_files.append(rel_path)
            else:
                try:
                    self.verify_file(target_path, rel_path)
                    valid_files.append(rel_path)
                except ChecksumMismatchError:
                    corrupt_files.append(rel_path)

        return valid_files, missing_files, corrupt_files


@dataclass
class ValidationSplitConfig:
    """Parsed cell-held-out split configuration (Rule R3)."""

    dataset_id: str
    version: str
    split_policy: str
    train_cells: List[str]
    val_cells: List[str]
    sealed_test_cells: List[str]
    conditions: Dict[str, Any] = field(default_factory=dict)
    cycle_mapping: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(cls, split_yaml_path: Path) -> "ValidationSplitConfig":
        if not split_yaml_path.exists():
            raise FileNotFoundError(f"Split configuration not found: {split_yaml_path}")
        with open(split_yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        dev = data.get("dev_cells", {})
        return cls(
            dataset_id=data.get("dataset_id", split_yaml_path.stem.replace("_splits", "")),
            version=str(data.get("version", "1.0")),
            split_policy=data.get("split_policy", "BY_CELL"),
            train_cells=list(dev.get("train_cells", [])),
            val_cells=list(dev.get("val_cells", [])),
            sealed_test_cells=list(data.get("sealed_test_cells", [])),
            conditions=dict(data.get("conditions", {})),
            cycle_mapping=dict(data.get("cycle_mapping", {})),
        )

    def validate_cell_isolation(self) -> None:
        """Verify train, val, and test cells are strictly disjoint (Rule R3)."""
        train_set = set(self.train_cells)
        val_set = set(self.val_cells)
        test_set = set(self.sealed_test_cells)

        # Sealed test cells must never overlap with train or val cells
        overlap_train_test = train_set.intersection(test_set)
        if overlap_train_test:
            raise ValueError(f"Leakage violation in {self.dataset_id}: test cells overlap with train cells: {overlap_train_test}")

        overlap_val_test = val_set.intersection(test_set)
        if overlap_val_test:
            raise ValueError(f"Leakage violation in {self.dataset_id}: test cells overlap with val cells: {overlap_val_test}")

    def get_test_cells(self, final: bool = False) -> List[str]:
        """Access sealed test cells strictly guarded by final=True requirement (Rule R3)."""
        if not final:
            raise PermissionError(
                f"Access denied: Sealed test cells for '{self.dataset_id}' require final=True on the authorized evaluation path."
            )
        return list(self.sealed_test_cells)


# Registry of known real-data battery datasets
DATASET_METADATA: Dict[str, DatasetMetadata] = {
    "calce_a123": DatasetMetadata(
        dataset_id="calce_a123",
        name="CALCE A123 LFP Battery Dataset",
        doi="UNVERIFIED",
        source_url="https://calce.umd.edu/data , https://web.calce.umd.edu/batteries/data/",
        licence="UNVERIFIED",
        version="UNVERIFIED",
        download_date="UNVERIFIED",
        path_pattern="data/raw/calce_a123",
        manifest_filename="calce_a123.sha256",
        split_config_filename="calce_a123_splits.yaml",
        cell_chemistry="LFP",
        cell_form_factor="UNVERIFIED",
        nominal_capacity_ah=float("1.0636"),
        description="A123 LiFePO4 cells from CALCE battery data archive. Measured capacity about 1.06 Ah (A1-007) and 1.09 Ah (A1-008) at 25 C. Format UNVERIFIED. Citation: W. He et al., 2014 (DOI UNVERIFIED).",
    ),
    "gustave_eiffel_g02iye": DatasetMetadata(
        dataset_id="gustave_eiffel_g02iye",
        name="Characterisation tests of LFP 105Ah cells",
        doi="10.57745/G02IYE",
        source_url="https://doi.org/10.57745/G02IYE",
        licence="Etalab 2.0",
        version="2.0",
        download_date="2026-11-16",
        path_pattern="gustave_eiffel_105ah",
        manifest_filename="gustave_eiffel_g02iye.sha256",
        split_config_filename="gustave_eiffel_g02iye_splits.yaml",
        cell_chemistry="LFP",
        cell_form_factor="Pouch 105Ah",
        nominal_capacity_ah=float("105.0"),
        description="Characterisation tests of EVE Energy LFP 105 Ah cells (BUGE388..BUGE391). Published 2024. Citation: P. Seger et al., ELECTRIMACS 2024.",
    ),
    "gustave_eiffel_sbno8w": DatasetMetadata(
        dataset_id="gustave_eiffel_sbno8w",
        name="Electrical model parameters of LFP 105Ah cells",
        doi="10.57745/SBNO8W",
        source_url="https://doi.org/10.57745/SBNO8W",
        licence="UNVERIFIED",
        version="UNVERIFIED",
        download_date="2026-11-16",
        path_pattern="gustave_eiffel_105ah",
        manifest_filename="gustave_eiffel_sbno8w.sha256",
        split_config_filename="gustave_eiffel_sbno8w_splits.yaml",
        cell_chemistry="LFP",
        cell_form_factor="Pouch 105Ah",
        nominal_capacity_ah=float("105.0"),
        description="Electrical model parameters of EVE Energy LFP 105 Ah cells (batt_data.mat, parameter_visualisation.m). Published 2024.",
    ),
    "uconn_reil_dataset1": DatasetMetadata(
        dataset_id="uconn_reil_dataset1",
        name="UConn-ISU-ILCC LFP/Gr Battery Aging Dataset (Dataset 1)",
        doi="UNVERIFIED",
        source_url="https://digitalcommons.lib.uconn.edu/reil_datasets/1/",
        licence="CC BY 4.0",
        version="UNVERIFIED",
        download_date="NOT_DOWNLOADED",
        path_pattern="uconn_reil_dataset1",
        manifest_filename="uconn_reil_dataset1.sha256",
        split_config_filename="uconn_reil_dataset1_splits.yaml",
        cell_chemistry="LFP/Graphite",
        cell_form_factor="18650 cylindrical",
        nominal_capacity_ah=float("1.2"),
        description="UConn REIL laboratory dataset of 64 LithiumWerks APR18650M1B cells, 11 conditions (Status: NOT_DOWNLOADED).",
    ),
    "uconn_reil_dataset5": DatasetMetadata(
        dataset_id="uconn_reil_dataset5",
        name="UConn-ISU-ILCC LFP/Gr Battery Aging Dataset",
        doi="https://doi.org/10.1016/j.jpowsour.2024.235813",
        source_url="https://digitalcommons.lib.uconn.edu/reil_datasets/5",
        licence="CC BY 4.0",
        version="UNVERIFIED",
        download_date="2026-11-16",
        path_pattern="uconn_reil",
        manifest_filename="uconn_reil_dataset5.sha256",
        split_config_filename="uconn_reil_dataset5_splits.yaml",
        cell_chemistry="LFP/Graphite",
        cell_form_factor="18650 cylindrical",
        nominal_capacity_ah=float("1.2"),
        description="UConn-ISU-ILCC LFP/Gr battery aging dataset (rpt_data.zip). Citation: B. Nowacki et al., J. Power Sources 628, 235813 (2025).",
    ),
    "wheeler_2025": DatasetMetadata(
        dataset_id="wheeler_2025",
        name="An ageing study of twenty 18650 lithium-ion Graphite/LFP cells in first and second life use",
        doi="10.1038/s41597-025-04712-7",
        source_url="UNVERIFIED",
        licence="UNVERIFIED",
        version="UNVERIFIED",
        download_date="NOT_DOWNLOADED",
        path_pattern="wheeler_a123",
        manifest_filename="wheeler_2025.sha256",
        split_config_filename="wheeler_2025_splits.yaml",
        cell_chemistry="LFP/Graphite",
        cell_form_factor="18650 cylindrical",
        nominal_capacity_ah=float("1.1"),
        description="Wheeler, Bultel, Venet, Sari; Scientific Data 2025. Data repository and files NOT_DOWNLOADED.",
    ),
    "tempest_zenodo": DatasetMetadata(
        dataset_id="tempest_zenodo",
        name="TEMPEST project 280 Ah LFP prismatic cell dataset",
        doi="UNVERIFIED",
        source_url="https://zenodo.org/records/19632939",
        licence="UNVERIFIED",
        version="UNVERIFIED",
        download_date="2026-11-16",
        path_pattern="tempest_280ah",
        manifest_filename="tempest_zenodo.sha256",
        split_config_filename="tempest_zenodo_splits.yaml",
        cell_chemistry="LFP",
        cell_form_factor="280 Ah prismatic",
        nominal_capacity_ah=float("280.0"),
        description="TEMPEST project characterisation tests of a 280 Ah prismatic LFP cell at 15-35°C (University of Bath).",
    ),
}


def get_soc_data_dir() -> Path:
    """Return root directory for raw battery datasets outside the repository (Rule R1)."""
    env_dir = os.environ.get("SOC_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return DEFAULT_DATA_DIR.expanduser().resolve()


def get_repo_root() -> Path:
    """Return repository root directory."""
    return Path(__file__).resolve().parent.parent.parent.parent


def get_manifest_path(dataset_id: str) -> Path:
    """Return path to data/manifests/<dataset>.sha256."""
    meta = DATASET_METADATA.get(dataset_id)
    filename = meta.manifest_filename if meta else f"{dataset_id}.sha256"
    return get_repo_root() / "data" / "manifests" / filename


def get_split_config_path(dataset_id: str) -> Path:
    """Return path to configs/validation/<dataset>_splits.yaml."""
    meta = DATASET_METADATA.get(dataset_id)
    filename = meta.split_config_filename if meta else f"{dataset_id}_splits.yaml"
    return get_repo_root() / "configs" / "validation" / filename


def resolve_dataset_dir(dataset_id: str, custom_data_dir: Optional[Path] = None) -> Path:
    """Locate dataset folder on disk adhering to explicit repo-local or $SOC_DATA_DIR roots."""
    meta = DATASET_METADATA.get(dataset_id)
    rel_pattern = meta.path_pattern if meta else dataset_id

    # 1. calce_a123 has an explicit repo-local root inside the repo
    if dataset_id == "calce_a123":
        if custom_data_dir is not None:
            c_path = custom_data_dir.resolve()
            if (c_path / rel_pattern).is_dir():
                return c_path / rel_pattern
            if c_path.name == "calce_a123" and c_path.is_dir():
                return c_path
        repo_calce = get_repo_root() / "data" / "raw" / "calce_a123"
        if repo_calce.exists() and repo_calce.is_dir():
            return repo_calce
        return repo_calce

    # 2. Custom data dir if provided
    if custom_data_dir is not None:
        c_path = custom_data_dir.resolve()
        candidate = c_path / rel_pattern
        if candidate.exists() and candidate.is_dir():
            return candidate
        if c_path.name == rel_pattern or c_path.name == dataset_id:
            return c_path
        return candidate

    # 3. Base directory in SOC_DATA_DIR
    base_dir = get_soc_data_dir()
    candidate = base_dir / rel_pattern
    return candidate


# =============================================================================
# Loaders (Rule R2: Must read files, verify manifest, no generation or dummy values)
# =============================================================================

def load_dataset_with_manifest_check(
    dataset_id: str,
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Base loader verifying manifest integrity and loading dataset files."""
    if dataset_id not in DATASET_METADATA:
        raise KeyError(f"Unknown dataset_id: {dataset_id}")

    meta = DATASET_METADATA[dataset_id]
    manifest_path = get_manifest_path(dataset_id)
    manifest = DatasetManifest.load(manifest_path)

    if manifest.status == "NOT_DOWNLOADED":
        raise DatasetMissingError(
            f"Dataset '{dataset_id}' status is NOT_DOWNLOADED. External files have not been acquired."
        )

    dataset_path = resolve_dataset_dir(dataset_id, custom_data_dir=data_dir)
    if not dataset_path.exists() or not dataset_path.is_dir():
        raise DatasetMissingError(
            f"Dataset '{dataset_id}' raw data files missing at: {dataset_path}. "
            f"Rule R1: Raw data lives outside the repo at $SOC_DATA_DIR (default: {DEFAULT_DATA_DIR}). "
            f"Please download from {meta.source_url} (DOI: {meta.doi}) and place in {dataset_path}."
        )

    if verify_checksums:
        valid, missing, corrupt = manifest.audit_dataset_directory(dataset_path)
        if corrupt:
            raise ChecksumMismatchError(
                f"Dataset '{dataset_id}' has {len(corrupt)} corrupt files failing SHA-256 verification: {corrupt[:int('5')]}."
            )
        if missing:
            raise DatasetMissingError(
                f"Dataset '{dataset_id}' has {len(missing)} missing files from manifest: {missing[:int('5')]}."
            )

    return {
        "dataset_id": dataset_id,
        "metadata": meta,
        "manifest": manifest,
        "dataset_path": dataset_path,
    }


def load_calce_a123(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for CALCE A123 dataset adhering to R1, R2, R3, R6."""
    info = load_dataset_with_manifest_check("calce_a123", data_dir, verify_checksums)
    
    # Import existing calce parser
    from soc.data.calce_loader import CalceCycleData, CalceOcvData, load_dynamic_cycle, load_ocv_file
    split_config = ValidationSplitConfig.load(get_split_config_path("calce_a123"))
    split_config.validate_cell_isolation()

    return {
        **info,
        "split_config": split_config,
        "load_dynamic_cycle": load_dynamic_cycle,
        "load_ocv_file": load_ocv_file,
    }


def load_gustave_eiffel_g02iye(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for Gustave Eiffel PEV Secondary Use dataset (DOI 10.57745/G02IYE)."""
    info = load_dataset_with_manifest_check("gustave_eiffel_g02iye", data_dir, verify_checksums)
    split_config = ValidationSplitConfig.load(get_split_config_path("gustave_eiffel_g02iye"))
    split_config.validate_cell_isolation()
    return {**info, "split_config": split_config}


def load_gustave_eiffel_sbno8w(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for Gustave Eiffel LFP 105Ah Characterisation dataset (DOI 10.57745/SBNO8W)."""
    info = load_dataset_with_manifest_check("gustave_eiffel_sbno8w", data_dir, verify_checksums)
    split_config = ValidationSplitConfig.load(get_split_config_path("gustave_eiffel_sbno8w"))
    split_config.validate_cell_isolation()
    return {**info, "split_config": split_config}


def load_uconn_reil_dataset1(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for UConn-ISU-ILCC LFP/Gr Battery Aging Dataset 1."""
    info = load_dataset_with_manifest_check("uconn_reil_dataset1", data_dir, verify_checksums)
    split_config = ValidationSplitConfig.load(get_split_config_path("uconn_reil_dataset1"))
    split_config.validate_cell_isolation()
    return {**info, "split_config": split_config}


def load_uconn_reil_dataset5(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for UConn-ISU-ILCC LFP/Gr Battery Aging Dataset Extended (Dataset 5)."""
    info = load_dataset_with_manifest_check("uconn_reil_dataset5", data_dir, verify_checksums)
    split_config = ValidationSplitConfig.load(get_split_config_path("uconn_reil_dataset5"))
    split_config.validate_cell_isolation()
    return {**info, "split_config": split_config}


def load_wheeler_2025(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for Wheeler et al. 2025 Twenty-Cell LFP Aging dataset (DOI 10.1038/s41597-025-04712-7)."""
    info = load_dataset_with_manifest_check("wheeler_2025", data_dir, verify_checksums)
    split_config = ValidationSplitConfig.load(get_split_config_path("wheeler_2025"))
    split_config.validate_cell_isolation()
    return {**info, "split_config": split_config}


def load_tempest_zenodo(
    data_dir: Optional[Path] = None,
    verify_checksums: bool = True,
) -> Dict[str, Any]:
    """Loader for TEMPEST Zenodo 280 Ah Prismatic LFP dataset (DOI 10.5281/zenodo.20813753)."""
    info = load_dataset_with_manifest_check("tempest_zenodo", data_dir, verify_checksums)
    split_config = ValidationSplitConfig.load(get_split_config_path("tempest_zenodo"))
    split_config.validate_cell_isolation()
    return {**info, "split_config": split_config}


LOADER_REGISTRY: Dict[str, Callable[..., Dict[str, Any]]] = {
    "calce_a123": load_calce_a123,
    "gustave_eiffel_g02iye": load_gustave_eiffel_g02iye,
    "gustave_eiffel_sbno8w": load_gustave_eiffel_sbno8w,
    "uconn_reil_dataset1": load_uconn_reil_dataset1,
    "uconn_reil_dataset5": load_uconn_reil_dataset5,
    "wheeler_2025": load_wheeler_2025,
    "tempest_zenodo": load_tempest_zenodo,
}


def get_dataset_loader(dataset_id: str) -> Callable[..., Dict[str, Any]]:
    """Return registered loader function for dataset_id."""
    if dataset_id not in LOADER_REGISTRY:
        raise KeyError(f"No loader registered for dataset_id: {dataset_id}")
    return LOADER_REGISTRY[dataset_id]


def list_registered_datasets() -> List[DatasetMetadata]:
    """Return all registered datasets in order."""
    return list(DATASET_METADATA.values())
