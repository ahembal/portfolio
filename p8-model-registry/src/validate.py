"""
Validate registry entries against their schemas.

Checks:
  - All required fields are present
  - No critical fields are UNVERIFIED or null
  - Cross-references are valid (deployment references existing evaluation, etc.)

Usage:
  python src/validate.py                     # validate all entries
  python src/validate.py models              # validate model entries only
  python src/validate.py models/resnet18-tiatoolbox-pcam-v1.yaml
"""

import sys
from pathlib import Path
from typing import Any

import yaml

REGISTRY = Path(__file__).parent.parent / "registry"

# Required fields per entry type — value is a list of dot-notation paths
REQUIRED: dict[str, list[str]] = {
    "models": [
        "id", "version", "created_at", "task", "architecture",
        "source", "format", "sha", "origin", "preprocessing", "class_mapping",
    ],
    "experiments": [
        "id", "date", "model_id", "framework", "compute",
        "hyperparameters", "artifact",
    ],
    "evaluations": [
        "id", "date", "model_id", "model_version",
        "evaluator", "dataset", "threshold", "metrics",
    ],
    "deployments": [
        "id", "model_id", "model_version", "evaluation_id",
        "environment", "deployed_at", "deployed_by", "status", "service",
    ],
}

# Fields that must never be UNVERIFIED or null in a trusted entry
TRUST_FIELDS: dict[str, list[str]] = {
    "models": ["sha"],
    "experiments": ["artifact.sha"],
    "evaluations": [],
    "deployments": ["evaluation_id"],
}


def _get(data: dict, path: str) -> Any:
    """Get a nested field by dot-notation path."""
    parts = path.split(".")
    current = data
    for part in parts:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def validate_entry(path: Path, entry_type: str) -> list[str]:
    """
    Validate a single registry entry. Returns list of error messages.
    Empty list means valid.
    """
    errors = []
    with open(path) as f:
        data = yaml.safe_load(f)

    if data is None:
        return [f"{path.name}: empty file"]

    # Check required fields
    for field in REQUIRED.get(entry_type, []):
        val = _get(data, field)
        if val is None:
            errors.append(f"{path.name}: missing required field '{field}'")

    # Check trust fields
    for field in TRUST_FIELDS.get(entry_type, []):
        val = _get(data, field)
        if val == "UNVERIFIED" or val is None:
            errors.append(
                f"{path.name}: trust field '{field}' is {val!r} — "
                f"run verify.py to compute the SHA before deploying"
            )

    return errors


def validate_cross_references() -> list[str]:
    """
    Check that deployments reference existing evaluations,
    and evaluations reference existing models.
    """
    errors = []

    model_ids = {
        yaml.safe_load(open(f))["id"]
        for f in (REGISTRY / "models").glob("*.yaml")
    }
    evaluation_ids = {
        yaml.safe_load(open(f))["id"]
        for f in (REGISTRY / "evaluations").glob("*.yaml")
    }

    for dep_file in (REGISTRY / "deployments").glob("*.yaml"):
        dep = yaml.safe_load(open(dep_file))
        if dep.get("evaluation_id") not in evaluation_ids:
            errors.append(
                f"{dep_file.name}: evaluation_id '{dep.get('evaluation_id')}' "
                f"does not exist in evaluations/"
            )
        if dep.get("model_id") not in model_ids:
            errors.append(
                f"{dep_file.name}: model_id '{dep.get('model_id')}' "
                f"does not exist in models/"
            )

    for eval_file in (REGISTRY / "evaluations").glob("*.yaml"):
        ev = yaml.safe_load(open(eval_file))
        if ev.get("model_id") not in model_ids:
            errors.append(
                f"{eval_file.name}: model_id '{ev.get('model_id')}' "
                f"does not exist in models/"
            )

    return errors


def validate_all(target: str | None = None) -> bool:
    """
    Validate all registry entries or a specific subset.

    Args:
        target: optional — entry type ("models") or specific file path

    Returns:
        True if all valid, False if any errors found
    """
    all_errors = []

    if target and target.endswith(".yaml"):
        path = Path(target) if Path(target).is_absolute() else REGISTRY / target
        entry_type = path.parent.name
        all_errors.extend(validate_entry(path, entry_type))
    else:
        types = [target] if target else list(REQUIRED.keys())
        for entry_type in types:
            dir_path = REGISTRY / entry_type
            if not dir_path.exists():
                continue
            for yaml_file in dir_path.glob("*.yaml"):
                all_errors.extend(validate_entry(yaml_file, entry_type))

        if not target:
            all_errors.extend(validate_cross_references())

    if all_errors:
        print("VALIDATION FAILED")
        for err in all_errors:
            print(f"  ✗ {err}")
        return False

    print("VALIDATION PASSED — all entries are valid")
    return True


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else None
    ok = validate_all(target)
    sys.exit(0 if ok else 1)
