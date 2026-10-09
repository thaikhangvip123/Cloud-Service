#!/usr/bin/env python3
"""Create a value-free Terraform plan summary for deployment review."""

import argparse
import json
import re
from pathlib import Path
from typing import Any


def strip_address_indices(address: str) -> str:
    """Remove Terraform index expressions, including quoted keys with brackets."""
    result: list[str] = []
    depth = 0
    in_string = False
    escaped = False
    for char in address:
        if depth:
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
            elif char == '"':
                in_string = True
            elif char == "[":
                depth += 1
            elif char == "]":
                depth -= 1
            continue
        if char == "[":
            depth = 1
        else:
            result.append(char)
    return "".join(result)


def safe_resource_address(resource: dict[str, Any]) -> str:
    """Return a resource address without instance keys that may contain sensitive data."""
    module_address = strip_address_indices(str(resource.get("module_address", "")))
    module_names = re.findall(r"(?:^|\.)module\.([A-Za-z0-9_-]+)", module_address)
    parts = [part for name in module_names for part in ("module", name)]
    resource_type = resource.get("type")
    resource_name = resource.get("name")
    if isinstance(resource_type, str) and isinstance(resource_name, str):
        parts.extend((resource_type, resource_name))
        return ".".join(parts)

    address = strip_address_indices(str(resource.get("address", "unknown")))
    address = re.sub(r"\b\d{12}\b", "<account-id>", address)
    return re.sub(
        r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
        "<email>",
        address,
    )


def summarize_plan(plan: dict[str, Any]) -> str:
    """Return resource addresses, actions, and aggregate counts without values."""
    changed: list[tuple[str, list[str]]] = []
    counts = {"create": 0, "update": 0, "delete": 0, "replace": 0}

    for resource in plan.get("resource_changes", []):
        actions = resource.get("change", {}).get("actions", [])
        if actions in (["no-op"], ["read"]) or not actions:
            continue
        address = safe_resource_address(resource)
        changed.append((address, actions))
        if "create" in actions and "delete" in actions:
            counts["replace"] += 1
        else:
            for action in ("create", "update", "delete"):
                if action in actions:
                    counts[action] += 1

    lines = [
        "## Terraform plan summary",
        "",
        (
            f"Create: {counts['create']}, Update: {counts['update']}, "
            f"Delete: {counts['delete']}, Replace: {counts['replace']}"
        ),
        "",
    ]
    if not changed:
        lines.append("No infrastructure changes.")
    else:
        lines.extend(f"- `{address}`: {', '.join(actions)}" for address, actions in changed)
    return "\n".join(lines)


def main() -> None:
    """Read Terraform JSON and print its value-free summary."""
    parser = argparse.ArgumentParser()
    parser.add_argument("plan_json", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan_json.read_text(encoding="utf-8"))
    print(summarize_plan(plan))


if __name__ == "__main__":
    main()
