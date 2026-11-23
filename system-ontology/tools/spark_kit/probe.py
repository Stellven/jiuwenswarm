#!/usr/bin/env python3
"""Environment probe: collects measured data on the target machine and writes it as a System Ontology environment description.

Uses only the Python standard library; nothing has to be installed and no administrator rights are needed. It writes a temporary file
under --data-dir to measure the read speed from storage and deletes it afterwards.

Usage (on a DGX Spark):
  python3 probe.py --data-dir /path/on/the/ssd --out-dir .

Writes env-<name>.yaml. Copy it back into examples/given/ in the workspace, then run so_assess.py with it.
The file content is JSON, and JSON is itself valid YAML.
"""
import threading
import random
import argparse
import ctypes
import datetime
import json
import mmap
import os
import platform
import shutil
import subprocess
import sys
import time

GIB = 2 ** 30


def run(cmd):
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout.strip()
    except Exception:
        return ""


def memory():
    """Return (total memory in bytes, bytes available now, note)."""
    if sys.platform.startswith("linux"):
        info = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, v = line.split(":", 1)
                info[k] = int(v.split()[0]) * 1024
        return info["MemTotal"], info["MemAvailable"], "MemTotal and MemAvailable from /proc/meminfo"
    if sys.platform == "win32":
        class MS(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        ms = MS()
        ms.dwLength = ctypes.sizeof(MS)
        ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(ms))
        return ms.ullTotalPhys, ms.ullAvailPhys, "total and available physical memory from GlobalMemoryStatusEx"
    return None, None, "not implemented on this platform"


def gpu():
    """Query the GPU with nvidia-smi. Returns a dict, empty when there is no NVIDIA GPU."""
    line = run(["nvidia-smi", "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])
    if not line:
        return {}
    name, driver, mem = [x.strip() for x in line.splitlines()[0].split(",")]
    cuda = ""
    for l in run(["nvidia-smi"]).splitlines():
        if "CUDA Version" in l:
            cuda = l.split("CUDA Version:")[1].split()[0]
            break
    return {"name": name, "driver": driver, "memory_total_raw": mem, "cuda": cuda}


def copy_bandwidth(size):
    """Speed of a single-thread memory copy (bytes per second). The buffer is filled first and then copied, so that no unallocated zero pages are read."""
    block = os.urandom(2 ** 20)
    buf = bytearray(block * (size // len(block)))
    best = 0.0
    for _ in range(3):
        t = time.perf_counter()
        dst = bytes(buf)
        dt = time.perf_counter() - t
        best = max(best, len(buf) / dt)
        del dst
    return best


def make_test_file(data_dir, size):
    """Write a temporary file in data_dir for the read test. Returns (path or None, note)."""
    if not sys.platform.startswith("linux"):
        return None, "reading that bypasses the page cache is implemented only on Linux; not measured on this platform"
    free = shutil.disk_usage(data_dir).free
    if free < size + 2 * GIB:
        return None, "not enough free disk space (%.0f GiB plus a 2 GiB margin is needed); not measured" % (size / GIB)
    path = os.path.join(data_dir, ".so_probe_%d.tmp" % os.getpid())
    block = os.urandom(64 * 2 ** 20)
    try:
        with open(path, "wb") as f:
            written = 0
            while written < size:
                f.write(block)
                written += len(block)
            f.flush()
            os.fsync(f.fileno())
        return path, "file size %.0f GiB" % (size / GIB)
    except Exception as e:
        if os.path.exists(path):
            os.remove(path)
        return None, "writing the temporary file failed: %r" % (e,)


def open_uncached(path):
    """Open the file for reading, bypassing the system page cache where possible. Returns (fd, note on the method)."""
    try:
        return os.open(path, os.O_RDONLY | os.O_DIRECT), "O_DIRECT"
    except OSError:
        fd = os.open(path, os.O_RDONLY)
        os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        return fd, "the file system does not support O_DIRECT, so the page cache was dropped with fadvise before reading and the result may be too high;"


def ssd_read(path):
    """Speed of reading the whole file sequentially (bytes per second). Returns (speed or None, note on the method)."""
    try:
        chunk = 16 * 2 ** 20
        buf = mmap.mmap(-1, chunk)          # page-aligned buffer, which O_DIRECT needs
        fd, how = open_uncached(path)
        try:
            total = 0
            t = time.perf_counter()
            while True:
                n = os.readv(fd, [buf])
                if n <= 0:
                    break
                total += n
            dt = time.perf_counter() - t
        finally:
            os.close(fd)
        return total / dt, how + " sequential read, 16 MiB blocks, single thread"
    except Exception as e:
        return None, "measurement failed: %r" % (e,)


def ssd_read_scattered(path, object_bytes, concurrency, count, seed=20261113):
    """Scattered read: read count contiguous ranges of object_bytes each from random positions in the file, concurrency of them at a time.
    This is how an engine reads weights object by object. Returns (bytes per second or None, note)."""
    try:
        align = 4096
        object_bytes = max(align, object_bytes // align * align)
        size = os.path.getsize(path)
        slots = (size - object_bytes) // align
        if slots <= 0:
            return None, "the temporary file is smaller than one object; not measured"
        rng = random.Random(seed + concurrency)
        offsets = [rng.randrange(slots + 1) * align for _ in range(count)]
        fd, how = open_uncached(path)
        lock = threading.Lock()
        state = {"next": 0, "bytes": 0, "error": None}

        def worker():
            buf = mmap.mmap(-1, object_bytes)
            view = memoryview(buf)
            try:
                while True:
                    with lock:
                        i = state["next"]
                        state["next"] += 1
                    if i >= len(offsets) or state["error"]:
                        return
                    got = 0
                    while got < object_bytes:            # one read may return less than asked for; read until full
                        n = os.preadv(fd, [view[got:]], offsets[i] + got)
                        if n <= 0:
                            raise IOError("reached the end of the file at offset %d" % (offsets[i] + got))
                        got += n
                    with lock:
                        state["bytes"] += got
            except Exception as e:                        # noqa: BLE001
                state["error"] = e
            finally:
                view.release()
                buf.close()

        threads = [threading.Thread(target=worker) for _ in range(concurrency)]
        t = time.perf_counter()
        try:
            for th in threads:
                th.start()
            for th in threads:
                th.join()
        finally:
            dt = time.perf_counter() - t
            os.close(fd)
        if state["error"]:
            return None, "measurement failed: %r" % (state["error"],)
        return state["bytes"] / dt, "%s scattered read, %d ranges of %.1f MB each, %d at a time, random positions" % (
            how, count, object_bytes / 1e6, concurrency)
    except Exception as e:
        return None, "measurement failed: %r" % (e,)


def main():
    for stream in (sys.stdout, sys.stderr):        # so that non-ASCII text prints even when the terminal is not UTF-8
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description="Environment probe; writes a System Ontology environment description")
    ap.add_argument("--name", default="dgx-spark-measured", help="name of the environment description, used in the file name and in the id")
    ap.add_argument("--hardware-id", default="hw/dgx-spark", help="id of the hardware description of this machine")
    ap.add_argument("--pool", default="mem0", help="id of the main memory pool in the hardware description")
    ap.add_argument("--ssd-path-id", default="ssd0-to-mem0", help="id of the access path from the SSD to memory in the hardware description")
    ap.add_argument("--data-dir", default=".", help="directory for the temporary file of the read test; it should be on the SSD that will hold the model files")
    ap.add_argument("--io-size-gib", type=float, default=16.0, help="size of the temporary file of the read test")
    ap.add_argument("--ssd-pool-id", default="ssd0", help="id of the SSD in the hardware description")
    ap.add_argument("--object-mb", type=float, default=25.2, help="size of one range in the scattered read test; use the size of one object the engine reads at a time")
    ap.add_argument("--concurrency", default="1,8,16,32", help="numbers of simultaneous reads in the scattered read test, comma separated")
    ap.add_argument("--objects", type=int, default=96, help="how many ranges the scattered read test reads at each number of simultaneous reads")
    ap.add_argument("--mem-size-gib", type=float, default=1.0)
    ap.add_argument("--emit-hardware", action="store_true", help="also write a hardware description (for a machine that has none yet)")
    ap.add_argument("--out-dir", default=".")
    args = ap.parse_args()

    when = datetime.datetime.now().astimezone().isoformat(timespec="seconds")
    src = "spark_kit/probe.py @ " + when
    total, avail, mem_how = memory()
    g = gpu()
    print("memory: total %s, available %s" % tuple("unknown" if x is None else "%.1f GB" % (x / 1e9) for x in (total, avail)))
    print("GPU: %s" % (g or "no NVIDIA GPU found"))
    print("measuring memory copy speed ...")
    copy_bps = copy_bandwidth(int(args.mem_size_gib * GIB))
    print("  single-thread copy %.1f GB/s" % (copy_bps / 1e9))
    print("measuring read speed from storage (directory %s, %.0f GiB) ..." % (args.data_dir, args.io_size_gib))
    path, file_how = make_test_file(args.data_dir, int(args.io_size_gib * GIB))
    scattered = []
    try:
        if path is None:
            ssd_bps, ssd_how = None, file_how
        else:
            ssd_bps, ssd_how = ssd_read(path)
            if ssd_bps:
                ssd_how += ", " + file_how
        print("  %s" % ("%.2f GB/s, %s" % (ssd_bps / 1e9, ssd_how) if ssd_bps else ssd_how))
        if path is not None:
            print("measuring scattered read speed (%.1f MB per range) ..." % args.object_mb)
            for c in [int(x) for x in args.concurrency.split(",") if x.strip()]:
                bps, how = ssd_read_scattered(path, int(args.object_mb * 1e6), c, args.objects)
                print("  %2d at a time: %s" % (c, "%.2f GB/s" % (bps / 1e9) if bps else how))
                scattered.append((c, bps, how))
    finally:
        if path is not None and os.path.exists(path):
            os.remove(path)

    def cell(value):
        return {"value": value, "status": "measured", "source": src}

    env = {
        "kind": "environment", "id": "env/" + args.name, "hardware": args.hardware_id,
        "software": {"os": cell(platform.platform()), "python": cell(platform.python_version()),
                     "machine": cell(platform.machine()), "cpu_count": cell(os.cpu_count())},
        "allocatable": [], "statements": [],
    }
    if g:
        env["software"]["gpu_name"] = cell(g["name"])
        env["software"]["gpu_driver"] = cell(g["driver"])
        env["software"]["cuda"] = cell(g["cuda"])
        env["software"]["gpu_memory_total_reported"] = cell(g["memory_total_raw"])
    if avail is not None:
        env["allocatable"].append({"pool": args.pool, "value": round(avail / 1e9, 2), "unit": "GB",
                                   "unit_basis": "decimal", "status": "measured",
                                   "source": src + "; " + mem_how + "; the value at the moment of the probe, which the memory use of other processes changes"})
        env["statements"].append({"subject": args.pool, "property": "capacity_reported_by_os",
                                  "value": round(total / 1e9, 2), "unit": "GB", "unit_basis": "decimal",
                                  "status": "measured", "source": src})
    env["statements"].append({"subject": args.pool, "property": "copy_bandwidth_single_thread",
                              "value": round(copy_bps / 1e9, 2), "unit": "GB/s", "status": "measured",
                              "source": src + "; Python bytes() copy of %.0f GiB, fastest of three" % args.mem_size_gib})
    if ssd_bps:
        env["statements"].append({"subject": args.ssd_path_id, "property": "read_bandwidth",
                                  "value": round(ssd_bps / 1e9, 3), "unit": "GB/s", "status": "measured",
                                  "source": src + "; " + ssd_how})
    else:
        env["software"]["ssd_read_not_measured"] = {"value": ssd_how, "status": "measured", "source": src}
    for c, bps, how in scattered:
        if bps:
            env["statements"].append({"subject": args.ssd_path_id, "property": "scattered_read_bandwidth",
                                      "value": round(bps / 1e9, 3), "unit": "GB/s", "status": "measured",
                                      "conditions": {"concurrency": c, "object_mb": args.object_mb, "objects": args.objects},
                                      "source": src + "; " + how})
        else:
            env["software"]["scattered_read_not_measured_at_%d" % c] = {"value": how, "status": "measured", "source": src}
    try:
        disk_total = shutil.disk_usage(args.data_dir).total
        env["statements"].append({"subject": args.ssd_pool_id, "property": "capacity_reported_by_os",
                                  "value": round(disk_total / 1e9, 1), "unit": "GB", "unit_basis": "decimal",
                                  "status": "measured", "source": src + "; " + "total size of the file system that holds --data-dir"})
    except OSError:
        pass

    os.makedirs(args.out_dir, exist_ok=True)
    out = os.path.join(args.out_dir, "env-%s.yaml" % args.name)
    with open(out, "w", encoding="utf-8") as f:
        f.write("# Measured environment description written by spark_kit/probe.py. The content is JSON, which is also valid YAML.\n")
        json.dump(env, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print("wrote %s" % out)

    if args.emit_hardware:
        discrete = bool(g) and g["memory_total_raw"].split()[0].isdigit()
        hw = {"kind": "hardware", "id": args.hardware_id, "title": "Machine found by probe.py: " + platform.platform(),
              "compute_units": [{"id": "cpu0", "kind": "cpu"}, {"id": "gpu0", "kind": "gpu"}],
              "memory_pools": [], "access_paths": []}
        ram = {"value": round((total or 0) / 1e9, 2), "unit": "GB", "unit_basis": "decimal", "status": "measured", "source": src}
        disk = {"value": round(shutil.disk_usage(args.data_dir).total / 1e9, 1), "unit": "GB", "unit_basis": "decimal",
                "status": "measured", "source": src}
        if discrete:
            vram = {"value": round(int(g["memory_total_raw"].split()[0]) * 2 ** 20 / 1e9, 2), "unit": "GB",
                    "unit_basis": "decimal", "status": "measured", "source": src}
            hw["memory_pools"] = [{"id": "vram", "kind": "device_ram", "capacity_nominal": vram},
                                  {"id": args.pool, "kind": "host_ram", "capacity_nominal": ram},
                                  {"id": "ssd0", "kind": "nvme", "capacity_nominal": disk}]
            hw["access_paths"] = [{"id": "gpu0-vram", "kind": "direct", "unit": "gpu0", "pool": "vram"},
                                  {"id": "cpu0-" + args.pool, "kind": "direct", "unit": "cpu0", "pool": args.pool},
                                  {"id": args.pool + "-to-vram", "kind": "transfer", "origin": args.pool, "destination": "vram"},
                                  {"id": args.ssd_path_id, "kind": "page_in", "origin": "ssd0", "destination": args.pool}]
        else:
            hw["memory_pools"] = [{"id": args.pool, "kind": "unified_ram", "capacity_nominal": ram},
                                  {"id": "ssd0", "kind": "nvme", "capacity_nominal": disk}]
            hw["access_paths"] = [{"id": "cpu0-" + args.pool, "kind": "direct", "unit": "cpu0", "pool": args.pool},
                                  {"id": "gpu0-" + args.pool, "kind": "direct", "unit": "gpu0", "pool": args.pool},
                                  {"id": args.ssd_path_id, "kind": "page_in", "origin": "ssd0", "destination": args.pool}]
        out_hw = os.path.join(args.out_dir, "hw-%s.yaml" % args.name)
        with open(out_hw, "w", encoding="utf-8") as f:
            f.write("# Hardware description written by spark_kit/probe.py. Whether the GPU has memory of its own is judged by whether nvidia-smi reports a memory size.\n")
            json.dump(hw, f, ensure_ascii=False, indent=2)
            f.write("\n")
        print("wrote %s" % out_hw)


if __name__ == "__main__":
    main()
