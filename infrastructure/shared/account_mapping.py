"""Account mapping helpers."""

from typing import Any

from shared.errors import GroupMappingNotFoundError


def find_access_group(
    account: str, access_type: str, tier: str, mapping: dict[str, Any]
) -> dict[str, Any]:
    key = f"{account}-{access_type}-{tier}"
    try:
        return mapping["access_groups"][key]
    except KeyError as exc:
        raise GroupMappingNotFoundError(f"No access group mapping for {key}") from exc
