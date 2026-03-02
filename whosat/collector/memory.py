from __future__ import annotations

import subprocess

import psutil

from whosat.types import (
    GpuInfo,
    GpuProcessRecord,
    MemoryProcessRecord,
    MemorySnapshot,
)


def collect_memory_snapshot() -> MemorySnapshot:
    """Collect memory info for ALL system processes plus GPU if available."""
    vm = psutil.virtual_memory()
    sw = psutil.swap_memory()

    processes: list[MemoryProcessRecord] = []
    for proc in psutil.process_iter(
        ["pid", "name", "exe", "cmdline", "username", "cpu_percent",
         "memory_info", "memory_percent", "num_threads", "status"]
    ):
        try:
            info = proc.info
            mem_info = info.get("memory_info")
            rss = mem_info.rss if mem_info else 0
            vms = mem_info.vms if mem_info else 0
            processes.append(MemoryProcessRecord(
                pid=info["pid"],
                name=info.get("name") or "",
                username=info.get("username"),
                exe=info.get("exe"),
                cmdline=info.get("cmdline") or [],
                rss_bytes=rss,
                vms_bytes=vms,
                memory_percent=info.get("memory_percent") or 0.0,
                cpu_percent=info.get("cpu_percent") or 0.0,
                num_threads=info.get("num_threads") or 0,
                status=info.get("status") or "",
            ))
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
            continue

    processes.sort(key=lambda p: p.rss_bytes, reverse=True)

    # GPU collection
    gpu_available = False
    gpus: list[GpuInfo] = []
    gpu_processes: list[GpuProcessRecord] = []

    try:
        result = subprocess.run(
            ["nvidia-smi",
             "--query-gpu=index,name,memory.total,memory.used,utilization.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_available = True
            for line in result.stdout.strip().splitlines():
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 5:
                    gpus.append(GpuInfo(
                        index=int(parts[0]),
                        name=parts[1],
                        memory_total_bytes=int(float(parts[2])) * 1024 * 1024,
                        memory_used_bytes=int(float(parts[3])) * 1024 * 1024,
                        utilization_percent=float(parts[4]),
                    ))

            proc_result = subprocess.run(
                ["nvidia-smi",
                 "--query-compute-apps=pid,name,used_gpu_memory",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
            )
            if proc_result.returncode == 0 and proc_result.stdout.strip():
                for line in proc_result.stdout.strip().splitlines():
                    parts = [p.strip() for p in line.split(",")]
                    if len(parts) >= 3:
                        try:
                            gpu_processes.append(GpuProcessRecord(
                                pid=int(parts[0]),
                                name=parts[1],
                                gpu_memory_bytes=int(float(parts[2])) * 1024 * 1024,
                            ))
                        except (ValueError, IndexError):
                            continue
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    return MemorySnapshot(
        processes=processes,
        total_ram_bytes=vm.total,
        used_ram_bytes=vm.used,
        available_ram_bytes=vm.available,
        swap_total_bytes=sw.total,
        swap_used_bytes=sw.used,
        gpu_available=gpu_available,
        gpus=gpus,
        gpu_processes=gpu_processes,
    )
