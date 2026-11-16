"""Data package initialization."""

from soc.data.splits import load_test_split, load_train_split, load_val_split
from soc.data.registry import (
    ChecksumMismatchError,
    DatasetMissingError,
    DatasetMetadata,
    DatasetManifest,
    ValidationSplitConfig,
    DATASET_METADATA,
    LOADER_REGISTRY,
    get_dataset_loader,
    list_registered_datasets,
    get_soc_data_dir,
    get_manifest_path,
    get_split_config_path,
    resolve_dataset_dir,
)

__all__ = [
    "load_test_split",
    "load_train_split",
    "load_val_split",
    "ChecksumMismatchError",
    "DatasetMissingError",
    "DatasetMetadata",
    "DatasetManifest",
    "ValidationSplitConfig",
    "DATASET_METADATA",
    "LOADER_REGISTRY",
    "get_dataset_loader",
    "list_registered_datasets",
    "get_soc_data_dir",
    "get_manifest_path",
    "get_split_config_path",
    "resolve_dataset_dir",
]
