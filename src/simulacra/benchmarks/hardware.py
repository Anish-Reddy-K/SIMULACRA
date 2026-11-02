import platform
import re
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import psutil
from pydantic import BaseModel


class HardwareProfile(BaseModel):
    """Local hardware snapshot. Never transmitted anywhere (privacy requirement)."""

    captured_at: datetime
    os: str
    os_version: str
    arch: str
    chip: str | None
    apple_silicon: bool
    cpu_cores_total: int | None
    cpu_cores_performance: int | None
    ram_total_mb: int
    ram_available_mb: int
    swap_used_mb: int
    disk_free_mb: int
    disk_total_mb: int
    metal: str | None
    on_battery: bool | None
    low_power_mode: bool | None
    sleep_prevented: bool | None
    notes: list[str] = []


def _run(argv: list[str]) -> str | None:
    try:
        out = subprocess.run(  # noqa: S603
            argv, capture_output=True, text=True, timeout=10, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout if out.returncode == 0 else None


def parse_pmset_batt(text: str | None) -> bool | None:
    """True when running on battery. None when unknown."""
    if not text:
        return None
    if "Battery Power" in text:
        return True
    if "AC Power" in text:
        return False
    return None


def parse_pmset_settings(text: str | None) -> tuple[bool | None, bool | None]:
    """(low_power_mode, sleep_prevented) from `pmset -g`."""
    if not text:
        return None, None
    low = re.search(r"^\s*lowpowermode\s+(\d)", text, re.M)
    sleep = re.search(r"^\s*sleep\s+(\d+)(.*)$", text, re.M)
    sleep_prevented = None
    if sleep:
        sleep_prevented = "prevented" in sleep.group(2) or sleep.group(1) == "0"
    return (low.group(1) == "1" if low else None), sleep_prevented


def parse_metal(text: str | None) -> str | None:
    if not text:
        return None
    m = re.search(r"Metal Support:\s*(.+)", text)
    return m.group(1).strip() if m else None


def detect_hardware(data_dir: Path | None = None) -> HardwareProfile:
    mem = psutil.virtual_memory()
    disk = shutil.disk_usage(data_dir if data_dir and data_dir.exists() else Path.home())
    is_mac = platform.system() == "Darwin"
    arch = platform.machine()
    chip = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) if is_mac else None
    perf = _run(["sysctl", "-n", "hw.perflevel0.logicalcpu"]) if is_mac else None
    low, sleep_prevented = parse_pmset_settings(_run(["pmset", "-g"]) if is_mac else None)
    notes: list[str] = []
    if not is_mac:
        notes.append("Detection is most complete on macOS; some fields are unavailable here.")
    return HardwareProfile(
        captured_at=datetime.now(UTC),
        os=platform.system(),
        os_version=platform.mac_ver()[0] if is_mac else platform.release(),
        arch=arch,
        chip=chip.strip() if chip else None,
        apple_silicon=is_mac and arch == "arm64",
        cpu_cores_total=psutil.cpu_count(logical=True),
        cpu_cores_performance=int(perf) if perf and perf.strip().isdigit() else None,
        ram_total_mb=mem.total // 2**20,
        ram_available_mb=mem.available // 2**20,
        swap_used_mb=psutil.swap_memory().used // 2**20,
        disk_free_mb=disk.free // 2**20,
        disk_total_mb=disk.total // 2**20,
        metal=parse_metal(_run(["system_profiler", "SPDisplaysDataType"])) if is_mac else None,
        on_battery=parse_pmset_batt(_run(["pmset", "-g", "batt"]) if is_mac else None),
        low_power_mode=low,
        sleep_prevented=sleep_prevented,
        notes=notes,
    )
