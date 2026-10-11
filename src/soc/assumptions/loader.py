"""Configuration loader, deep-merger, and CLI override resolver."""

import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml
from pydantic import ValidationError

from soc.assumptions.schema import Assumptions

# Constants exported from the defaults loader for system scaling
PERCENT_FACTOR = 100.0
SECONDS_PER_DAY = 86400.0
DEFAULT_PERCENTILE_95 = 95.0
DEFAULT_PLATEAU_MIN = 0.20
DEFAULT_PLATEAU_MAX = 0.80
DEFAULT_WARMUP_COUNT = 10
DEFAULT_DRIFT_MIN_RUN_S = 86400.0
DEFAULT_MISMATCH_CAPACITY_PCT = -5.0
DEFAULT_MISMATCH_R0_PCT = 10.0
DEFAULT_MISMATCH_OCV_OFFSET_MV = 5.0
FLOAT_EPSILON = 1e-6


def derive_scenario_noise_seed(base_seed: int, scenario_name: str, seed_index: int = 0) -> int:
    """Derive reproducible, scenario-specific noise seed from run seed, scenario name, and seed index."""
    combined_str = f"{scenario_name}_{seed_index}"
    hash_hex = hashlib.sha256(combined_str.encode("utf-8")).hexdigest()
    hash_int = int(hash_hex[:8], 16)
    return int((base_seed + hash_int + seed_index) % 2147483647)



def get_default_config_dir() -> Path:
    """Return the absolute path to configs/assumptions/."""
    # Find relative to this source file
    this_dir = Path(__file__).resolve().parent
    # Project root is three levels up: src/soc/assumptions -> src/soc -> src -> root
    root_dir = this_dir.parent.parent.parent
    return root_dir / "configs" / "assumptions"


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively deep-merge override dictionary into base dictionary."""
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            # Check if target is an AssumptionEntry dict with 'value' key
            # If override provides a scalar instead of a full dict, set result[key]['value']
            if "value" in result[key] and "unit" in result[key] and "value" not in val:
                # Override is partial or setting entry value directly
                result[key]["value"] = copy.deepcopy(val)
            else:
                result[key] = deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def apply_cli_override(config_dict: Dict[str, Any], key_path: str, raw_val: str) -> None:
    """Apply a dot-separated CLI override into a dictionary with automatic type coercion.

    Example: 'plant.nominal_capacity_Ah.value=105.0' or 'plant.nominal_capacity_Ah=105.0'
    """
    parsed_val = yaml.safe_load(raw_val)
    parts = key_path.split(".")

    curr = config_dict
    for idx, part in enumerate(parts[:-1]):
        if part not in curr or not isinstance(curr[part], dict):
            curr[part] = {}
        curr = curr[part]

    last_part = parts[-1]
    if last_part in curr and isinstance(curr[last_part], dict):
        if "value" in curr[last_part]:
            curr[last_part]["value"] = parsed_val
        else:
            curr[last_part] = parsed_val
    else:
        curr[last_part] = parsed_val


def compute_config_hash(raw_dict: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 digest of resolved configuration dictionary."""
    serialized = json.dumps(raw_dict, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(serialized).hexdigest()


def get_git_commit_hash() -> str:
    """Retrieve current git commit hash, or return fallback if git unavailable."""
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return commit
    except Exception:
        return "uncommitted"


def is_git_dirty() -> bool:
    """Check if git working tree has uncommitted changes."""
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"], stderr=subprocess.DEVNULL
        ).decode("utf-8").strip()
        return len(out) > 0
    except Exception:
        return False


def count_assumption_statuses(data: Any) -> Dict[str, int]:
    """Audit counts of placeholder, assumed, measured, and fitted values in configuration."""
    counts = {
        "placeholder": 0,
        "assumed": 0,
        "measured": 0,
        "fitted": 0,
    }

    def _traverse(node: Any) -> None:
        if isinstance(node, dict):
            if "status" in node and isinstance(node["status"], str) and "value" in node:
                status_key = node["status"]
                if status_key in counts:
                    counts[status_key] += 1
            for child in node.values():
                _traverse(child)
        elif isinstance(node, list):
            for item in node:
                _traverse(item)

    _traverse(data)
    return counts


def load_assumptions(
    base_file: Optional[Path] = None,
    profile: Optional[str] = None,
    scenario_file: Optional[Path] = None,
    cli_overrides: Optional[List[str]] = None,
) -> Tuple[Assumptions, Dict[str, Any], str]:
    """Load, merge, validate, and hash assumptions from hierarchy.

    Precedence: base.yaml -> profiles/{profile}.yaml -> scenario_file -> cli_overrides.
    Returns: (validated Assumptions object, resolved raw dictionary, sha256 hash).
    """
    config_dir = get_default_config_dir()
    if base_file is None:
        base_file = config_dir / "base.yaml"

    if not base_file.exists():
        raise FileNotFoundError(f"Base configuration file not found: {base_file}")

    with open(base_file, "r", encoding="utf-8") as f:
        resolved_dict = yaml.safe_load(f) or {}

    # Apply profile if specified
    if profile:
        profile_path = Path(profile)
        if not profile_path.is_absolute() and not profile_path.exists():
            profile_path = config_dir / "profiles" / f"{profile}.yaml"
        if not profile_path.exists():
            profile_path = config_dir / "profiles" / profile
        if profile_path.exists():
            with open(profile_path, "r", encoding="utf-8") as f:
                prof_dict = yaml.safe_load(f) or {}
                resolved_dict = deep_merge(resolved_dict, prof_dict)
        else:
            raise FileNotFoundError(f"Profile configuration file not found: {profile_path}")

    # Apply scenario if specified
    if scenario_file:
        scen_path = Path(scenario_file)
        if not scen_path.is_absolute() and not scen_path.exists():
            scen_path = config_dir / "scenarios" / scen_path.name
        if scen_path.exists():
            with open(scen_path, "r", encoding="utf-8") as f:
                scen_dict = yaml.safe_load(f) or {}
                resolved_dict = deep_merge(resolved_dict, scen_dict)
        else:
            raise FileNotFoundError(f"Scenario configuration file not found: {scen_path}")

    # Apply CLI overrides: --set path.to.key=value
    if cli_overrides:
        for override in cli_overrides:
            if "=" not in override:
                raise ValueError(f"Invalid CLI override '{override}': must follow key=value format")
            key_p, raw_v = override.split("=", 1)
            apply_cli_override(resolved_dict, key_p.strip(), raw_v.strip())

    # Validate with Pydantic
    try:
        assumptions = Assumptions.model_validate(resolved_dict)
    except ValidationError as exc:
        raise ValueError(f"Assumptions validation failed:\n{exc}") from exc

    config_hash = compute_config_hash(resolved_dict)
    return assumptions, resolved_dict, config_hash


def resolve_assumptions(
    profile: Optional[str] = None,
    scenario_file: Optional[Path] = None,
    cli_overrides: Optional[List[str]] = None,
) -> Assumptions:
    """Convenience wrapper returning validated Assumptions instance."""
    assumptions, _, _ = load_assumptions(
        profile=profile, scenario_file=scenario_file, cli_overrides=cli_overrides
    )
    return assumptions
