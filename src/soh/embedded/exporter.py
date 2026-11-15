"""Embedded exporter utility."""

from pathlib import Path
from soh.estimators.base import SupportsEmbeddedExport


def export_estimator_to_c(estimator: SupportsEmbeddedExport, output_path: Path) -> Path:
    """Export an estimator satisfying SupportsEmbeddedExport to a C header file."""
    if not isinstance(estimator, SupportsEmbeddedExport):
        raise TypeError(f"Estimator {type(estimator)} does not implement SupportsEmbeddedExport.")
    estimator.export_c_header(output_path)
    return output_path
