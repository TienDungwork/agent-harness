from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ServiceInfo:
    unit_name: str
    load_state: str | None = None
    active_state: str | None = None
    sub_state: str | None = None
    description: str | None = None


def parse_systemctl_list_units(stdout: str) -> list[ServiceInfo]:
    """Parse `systemctl list-units --type=service --plain --no-legend`."""
    services: list[ServiceInfo] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(None, 4)
        if len(parts) < 4:
            continue
        unit, load, active, sub = parts[0], parts[1], parts[2], parts[3]
        desc = parts[4] if len(parts) > 4 else None
        if not unit.endswith('.service'):
            continue
        services.append(
            ServiceInfo(
                unit_name=unit,
                load_state=load,
                active_state=active,
                sub_state=sub,
                description=desc,
            )
        )
    return services
