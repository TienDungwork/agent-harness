from __future__ import annotations

import re
from dataclasses import dataclass


class CommandDenied(Exception):
    pass


_UNIT_RE = re.compile(r'^[A-Za-z0-9@:._\-]+\.(service|socket|timer|target|mount)$')

NVIDIA_SMI_QUERY = (
    'nvidia-smi --query-gpu=index,uuid,name,memory.total,memory.used,'
    'utilization.gpu,utilization.memory,temperature.gpu,power.draw '
    '--format=csv,noheader,nounits'
)


@dataclass(frozen=True)
class CommandSpec:
    command_id: str
    template: str
    needs_unit: bool = False


COMMAND_CATALOG: dict[str, CommandSpec] = {
    'echo_ok': CommandSpec('echo_ok', 'echo ok'),
    'gpu_query': CommandSpec('gpu_query', NVIDIA_SMI_QUERY),
    'service_list': CommandSpec(
        'service_list',
        'systemctl list-units --type=service --no-pager --plain --no-legend',
    ),
    'service_status': CommandSpec(
        'service_status',
        'systemctl show {unit} --no-pager --property=Id,LoadState,ActiveState,SubState,Description,ActiveEnterTimestamp',
        needs_unit=True,
    ),
    'service_restart': CommandSpec(
        'service_restart', 'systemctl restart {unit}', needs_unit=True
    ),
    'service_stop': CommandSpec(
        'service_stop', 'systemctl stop {unit}', needs_unit=True
    ),
}


def validate_unit(unit: str) -> str:
    if not _UNIT_RE.match(unit):
        raise CommandDenied(f'invalid unit name: {unit!r}')
    return unit


def render_command(command_id: str, *, unit: str | None = None) -> str:
    spec = COMMAND_CATALOG.get(command_id)
    if spec is None:
        raise CommandDenied(f'unknown command_id: {command_id}')
    if spec.needs_unit:
        if not unit:
            raise CommandDenied(f'command {command_id} requires unit')
        unit = validate_unit(unit)
        return spec.template.format(unit=unit)
    return spec.template
