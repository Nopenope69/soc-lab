# Quarantine: Fabricated Dataset Manifests

This directory contains quarantined dataset manifests that were fabricated during prior development and removed from active use under Incident Response Prompt 0b.

## Quarantined Files
- `gustave_eiffel_g02iye.sha256`
- `gustave_eiffel_sbno8w.sha256`
- `tempest_zenodo.sha256`
- `uconn_reil_dataset1.sha256`
- `uconn_reil_dataset5.sha256`
- `wheeler_2025.sha256`

## Incident Details
These files contained:
1. **Fabricated / Placeholder Hashes**: SHA-256 of empty input (`e3b0c44298fc...`), zero-padded empty-input MD5 (`d41d8cd98f00b204...`), and repeating/sequential hex patterns (`1234567890abcdef...`, `0123456789abcdef...`, `a1b2c3d4...`, `f0e1d2c3...`).
2. **Invented File Names**: Files that never existed on disk or in the actual datasets (e.g. `metadata.json`, `pev_secondary_use_cells_manifest.csv`, `data/cell_01_cycling.csv`, `README_dataset5.txt`, `test_condition_matrix.csv`, `cell_specifications.json`, `profile_wltp_current.csv`).
3. **Invented Identifiers & URLs**: Fabricated DOIs (`10.15760/reil_datasets/5`, `10.5281/zenodo.20813753`) and fabricated URL (`https://doi.org/10.57745/OLBXKT`).
4. **Invented Titles and Versions**: Untruthful metadata unbacked by disk artifacts.

These files are retained in quarantine for audit and provenance tracking only and MUST NOT be loaded or used by any loader or verification tool.
