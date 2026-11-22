"""What the site's Fly machines and volumes cost a month, estimated from what runs (0.87.0), for the admin screen.

Read through Fly's Machines API with a read-only token (FLY_API_TOKEN: `fly tokens create readonly`) and priced at
Fly's published rates. An estimate: it leaves out what the API can't see here (the shared Postgres cluster, the
media bucket, bandwidth, IP addresses), and says so. Read at most once an hour."""
import threading
import time
from typing import Callable

from .books import Fly

API = "https://api.machines.dev/v1"
# Fly's published prices (docs.fly.io/about/pricing, read 2026-11-22), in dollars for 30 days running
SHARED_CPU = 0.70        # a shared vCPU, before its memory (shared-cpu-1x at 256 MB is 2.19)
PERFORMANCE_CPU = 20.19  # a performance vCPU, before its memory
MEMORY_GB = 6.00         # each GB of memory
VOLUME_GB = 0.15         # each GB of volume, attached or not
STOPPED_GB = 0.15        # a stopped machine's root file system, per GB (counted as 1 GB each)
LEFT_OUT = ("the shared Postgres cluster", "the media bucket", "bandwidth out", "IP addresses", "volume snapshots")
TTL = 3600

_lock = threading.Lock()
_cache: dict[str, tuple[float, Fly]] = {}


def _get(token: str, path: str):
    import httpx
    auth = token if token.startswith("FlyV1 ") else f"Bearer {token}"
    r = httpx.get(f"{API}{path}", headers={"Authorization": auth}, timeout=10, follow_redirects=False)
    r.raise_for_status()
    return r.json()


def price(machines: list, volumes: list) -> Fly:
    """The month's estimate from the Machines API's lists: a line per machine and per volume."""
    lines, total = [], 0.0
    for m in machines if isinstance(machines, list) else []:
        guest = ((m or {}).get("config") or {}).get("guest") or {}
        state = str((m or {}).get("state") or "")
        if state == "destroyed":
            continue
        cpus, mem = int(guest.get("cpus") or 1), int(guest.get("memory_mb") or 256)
        kind = str(guest.get("cpu_kind") or "shared")
        group = (((m or {}).get("config") or {}).get("metadata") or {}).get("fly_process_group") or ""
        if state == "started":
            usd = cpus * (PERFORMANCE_CPU if kind == "performance" else SHARED_CPU) + mem / 1024 * MEMORY_GB
        else:
            usd = STOPPED_GB
        total += usd
        lines.append({"what": f"{group or 'machine'}: {kind}-cpu-{cpus}x, {mem // 1024 if mem >= 1024 else mem}"
                              f"{' GB' if mem >= 1024 else ' MB'}" + ("" if state == "started" else f" ({state})"),
                      "monthly": round(usd, 2)})
    for v in volumes if isinstance(volumes, list) else []:
        gb = int((v or {}).get("size_gb") or 0)
        if gb and (v or {}).get("state") != "destroyed":
            usd = gb * VOLUME_GB
            total += usd
            lines.append({"what": f"volume {(v or {}).get('name') or ''}: {gb} GB".replace("  ", " "),
                          "monthly": round(usd, 2)})
    return Fly(round(total, 2), tuple(lines), LEFT_OUT)


def estimate(token: str, app: str, get: Callable = _get, clock: Callable[[], float] = time.monotonic) -> Fly:
    """The estimate for `app`, or why there's none; a failed read is said, never priced as nothing."""
    if not token or not app:
        return Fly(None, why="Set FLY_API_TOKEN (fly tokens create readonly) to estimate Fly's cost.")
    with _lock:
        hit = _cache.get(app)
        if hit and clock() - hit[0] < TTL:
            return hit[1]
    try:
        got = price(get(token, f"/apps/{app}/machines"), get(token, f"/apps/{app}/volumes"))
    except Exception as e:  # noqa: BLE001 - any failure reads as "not known", never as $0
        return Fly(None, why=f"Couldn't read Fly's machines ({type(e).__name__}).")
    with _lock:
        _cache[app] = (clock(), got)
    return got
