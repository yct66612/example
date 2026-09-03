from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any


def _merge_mapping(
    current: Mapping[str, Any],
    overrides: Mapping[str, Any],
    *,
    skip_empty_strings: bool,
) -> tuple[dict[str, Any], bool]:
    merged = deepcopy(dict(current))
    changed = False
    for key, value in overrides.items():
        if skip_empty_strings and value == "":
            continue
        if isinstance(value, Mapping):
            existing = merged.get(key)
            existing_mapping = existing if isinstance(existing, Mapping) else {}
            nested, nested_changed = _merge_mapping(
                existing_mapping,
                value,
                skip_empty_strings=skip_empty_strings,
            )
            if nested_changed or isinstance(existing, Mapping):
                merged[key] = nested
                changed = True
            continue
        merged[key] = deepcopy(value)
        changed = True
    return merged, changed


def resolve_step_parameters(
    base_parameters: Mapping[str, Any],
    group_overrides: Mapping[str, Any],
    step_overrides: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    effective, _ = _merge_mapping(
        base_parameters,
        group_overrides,
        skip_empty_strings=False,
    )

    snapshots: list[dict[str, Any]] = []
    for overrides in step_overrides:
        effective, _ = _merge_mapping(
            effective,
            overrides,
            skip_empty_strings=True,
        )
        snapshots.append(deepcopy(effective))
    return snapshots
