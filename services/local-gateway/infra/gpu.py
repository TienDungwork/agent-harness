from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass
class GpuInfo:
    gpu_index: int
    gpu_uuid: str | None
    name: str | None
    mem_total_mb: int | None
    mem_used_mb: int | None
    util_gpu_pct: int | None
    util_mem_pct: int | None
    temp_c: int | None
    power_w: Decimal | None
    parse_error: str | None = None


def _int_or_none(value: str) -> int | None:
    value = value.strip()
    if not value or value.upper() in {'[N/A]', 'N/A'}:
        return None
    try:
        return int(float(value))
    except ValueError:
        return None


def _dec_or_none(value: str) -> Decimal | None:
    value = value.strip()
    if not value or value.upper() in {'[N/A]', 'N/A'}:
        return None
    try:
        return Decimal(value)
    except Exception:
        return None


def parse_nvidia_smi_csv(stdout: str) -> list[GpuInfo]:
    """Parse nvidia-smi csv,noheader,nounits output into GpuInfo rows."""
    lines = [ln.strip() for ln in stdout.splitlines() if ln.strip()]
    if not lines:
        return []
    gpus: list[GpuInfo] = []
    for line in lines:
        parts = [p.strip() for p in line.split(',')]
        if len(parts) < 9:
            gpus.append(
                GpuInfo(
                    gpu_index=0,
                    gpu_uuid=None,
                    name=None,
                    mem_total_mb=None,
                    mem_used_mb=None,
                    util_gpu_pct=None,
                    util_mem_pct=None,
                    temp_c=None,
                    power_w=None,
                    parse_error=f'unexpected columns: {line}',
                )
            )
            continue
        idx = _int_or_none(parts[0])
        gpus.append(
            GpuInfo(
                gpu_index=idx if idx is not None else 0,
                gpu_uuid=parts[1] or None,
                name=parts[2] or None,
                mem_total_mb=_int_or_none(parts[3]),
                mem_used_mb=_int_or_none(parts[4]),
                util_gpu_pct=_int_or_none(parts[5]),
                util_mem_pct=_int_or_none(parts[6]),
                temp_c=_int_or_none(parts[7]),
                power_w=_dec_or_none(parts[8]),
            )
        )
    return gpus


def is_nvidia_smi_missing(stdout: str, stderr: str, exit_code: int) -> bool:
    blob = f'{stdout}\n{stderr}'.lower()
    if exit_code == 0:
        return False
    if 'nvidia-smi' in blob and ('not found' in blob or 'no such file' in blob):
        return True
    return 'command not found' in blob and 'nvidia' in blob
