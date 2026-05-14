"""
Model registry CLI.

Commands:
  list                         — list all models with deployment status
  show <model_id>              — show full model entry
  deployments                  — list all active deployments
  audit                        — show trust status of all registry entries
  diff <model_id> <v1> <v2>   — compare two versions of a model

Usage:
  python src/cli.py list
  python src/cli.py show resnet18-tiatoolbox-pcam
  python src/cli.py audit
  python src/cli.py deployments
"""

import sys
from pathlib import Path

import yaml

REGISTRY = Path(__file__).parent.parent / "registry"


def _load_all(entry_type: str) -> list[dict]:
    path = REGISTRY / entry_type
    if not path.exists():
        return []
    entries = []
    for f in sorted(path.glob("*.yaml")):
        data = yaml.safe_load(open(f))
        data["_file"] = f.name
        entries.append(data)
    return entries


def cmd_list() -> None:
    """List all models with their deployment status."""
    models = {m["id"]: m for m in _load_all("models")}
    deployments = _load_all("deployments")

    deployed = {}
    for d in deployments:
        if d.get("status") == "active":
            deployed[d["model_id"]] = d

    print(f"{'ID':<40} {'VERSION':<8} {'SHA':<12} {'DEPLOYED':<10} {'ENVIRONMENT'}")
    print("-" * 90)
    for model_id, m in sorted(models.items()):
        sha = m.get("sha", "UNVERIFIED")
        sha_display = sha[:8] + "..." if len(sha) > 8 and sha != "UNVERIFIED" else sha
        dep = deployed.get(model_id)
        deployed_str = dep["environment"] if dep else "—"
        print(f"{model_id:<40} {m.get('version','?'):<8} {sha_display:<12} {'✓' if dep else '—':<10} {deployed_str}")


def cmd_show(model_id: str) -> None:
    """Show full entry for a model."""
    for f in (REGISTRY / "models").glob("*.yaml"):
        data = yaml.safe_load(open(f))
        if data.get("id") == model_id:
            print(yaml.dump(data, default_flow_style=False, sort_keys=False))
            return
    print(f"Model '{model_id}' not found")


def cmd_deployments() -> None:
    """List all active deployments."""
    deployments = _load_all("deployments")
    evaluations = {e["id"]: e for e in _load_all("evaluations")}

    print(f"{'ID':<40} {'MODEL':<35} {'ENV':<12} {'EVAL':<10} {'PARTIAL?'}")
    print("-" * 110)
    for d in deployments:
        if d.get("status") != "active":
            continue
        eval_id = d.get("evaluation_id", "—")
        ev = evaluations.get(eval_id, {})
        partial = "⚠ YES" if ev.get("notes") and "partial" in ev.get("notes", "").lower() else "no"
        print(f"{d['id']:<40} {d['model_id']:<35} {d.get('environment','?'):<12} {'✓':<10} {partial}")


def cmd_audit() -> None:
    """Show trust status of all registry entries."""
    print("=== TRUST AUDIT ===\n")

    issues = []

    for m in _load_all("models"):
        sha = m.get("sha", "UNVERIFIED")
        if sha == "UNVERIFIED":
            issues.append(f"  ✗ models/{m['id']}-{m['version']}: sha is UNVERIFIED")

    for e in _load_all("experiments"):
        sha = e.get("artifact", {}).get("sha", "UNVERIFIED")
        if sha == "UNVERIFIED":
            issues.append(f"  ✗ experiments/{e['id']}: artifact.sha is UNVERIFIED")

    for ev in _load_all("evaluations"):
        if ev.get("notes") and "partial" in ev.get("notes", "").lower():
            issues.append(f"  ⚠ evaluations/{ev['id']}: evaluation is partial — metrics may not be fully validated")

    for d in _load_all("deployments"):
        if d.get("status") == "active" and not d.get("evaluation_id"):
            issues.append(f"  ✗ deployments/{d['id']}: no evaluation_id — governance gate not satisfied")

    if issues:
        print("ISSUES FOUND:")
        for issue in issues:
            print(issue)
        print(f"\n{len(issues)} issue(s) require attention before this registry is fully trusted.")
    else:
        print("✓ All entries pass trust audit.")


def cmd_diff(model_id: str, v1: str, v2: str) -> None:
    """Compare two versions of a model."""
    import difflib

    def load_version(version: str) -> str:
        path = REGISTRY / "models" / f"{model_id}-{version}.yaml"
        if not path.exists():
            return f"# {path} not found\n"
        return open(path).read()

    text1 = load_version(v1).splitlines(keepends=True)
    text2 = load_version(v2).splitlines(keepends=True)
    diff = difflib.unified_diff(text1, text2, fromfile=f"{model_id}-{v1}", tofile=f"{model_id}-{v2}")
    result = "".join(diff)
    print(result if result else "No differences found.")


COMMANDS = {
    "list": (cmd_list, []),
    "show": (cmd_show, ["model_id"]),
    "deployments": (cmd_deployments, []),
    "audit": (cmd_audit, []),
    "diff": (cmd_diff, ["model_id", "v1", "v2"]),
}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: cli.py <command> [args]")
        print("Commands:", ", ".join(COMMANDS))
        sys.exit(1)

    cmd, arg_names = COMMANDS[sys.argv[1]]
    args = sys.argv[2:]
    if len(args) < len(arg_names):
        print(f"Usage: cli.py {sys.argv[1]} {' '.join(f'<{a}>' for a in arg_names)}")
        sys.exit(1)
    cmd(*args)
