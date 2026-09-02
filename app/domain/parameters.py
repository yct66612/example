from collections.abc import Mapping, Sequence
from typing import Any


def resolve_step_parameters(
    base_parameters: Mapping[str, Any],
    group_overrides: Mapping[str, Any],
    step_overrides: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    effective = dict(base_parameters)
    effective.update(group_overrides)

    snapshots: list[dict[str, Any]] = []
    for overrides in step_overrides:
        for key, value in overrides.items():
            if value != "":
                effective[key] = value
        snapshots.append(dict(effective))
    return snapshots
