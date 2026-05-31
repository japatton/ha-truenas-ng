"""DataUpdateCoordinators for the truenas_ng integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, TypeVar

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import (
    DataUpdateCoordinator,
    UpdateFailed,
)

from .client import TrueNASAuthError, TrueNASClient, TrueNASError
from .const import (
    SCAN_INTERVAL_DATASETS,
    SCAN_INTERVAL_REPORTING,
    SCAN_INTERVAL_STORAGE,
    SCAN_INTERVAL_SYSTEM,
)

_LOGGER = logging.getLogger(__name__)

_TOPOLOGY_CATEGORIES = ("data", "cache", "log", "spare", "special", "dedup")

_DataT = TypeVar("_DataT")


@dataclass
class StorageData:
    """Pools + disks snapshot for the StorageCoordinator."""

    pools: dict[str, dict]
    disks: dict[str, dict]


@dataclass
class SystemData:
    """system.info + alerts + services snapshot for the SystemCoordinator."""

    info: dict
    alerts: list[dict]
    services: dict[str, dict]


@dataclass
class ReportingData:
    """Derived CPU/memory metrics for the ReportingCoordinator."""

    cpu_percent: float | None
    cpu_temp: float | None
    memory_used: int | None
    memory_free: int | None
    memory_used_percent: float | None


class TrueNASBaseCoordinator(DataUpdateCoordinator[_DataT]):
    """Base coordinator: run the sync _fetch on the executor, map exceptions."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: TrueNASClient,
        name: str,
        interval_seconds: int,
    ) -> None:
        """Initialize the coordinator with a shared TrueNAS client."""
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=timedelta(seconds=interval_seconds),
        )
        self.client = client

    async def _async_update_data(self) -> _DataT:
        """Fetch on the executor; translate client errors to HA errors."""
        try:
            return await self.hass.async_add_executor_job(self._fetch)
        except TrueNASAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except TrueNASError as err:
            raise UpdateFailed(str(err)) from err

    def _fetch(self) -> _DataT:
        """Synchronous data fetch; overridden by concrete coordinators."""
        raise NotImplementedError


def _walk_topology_errors(pool: dict) -> dict[str, dict]:
    """Map every DISK leaf dev-name to its stats + status across all vdev categories."""
    result: dict[str, dict] = {}
    topology = pool.get("topology") or {}

    def _visit(node: dict) -> None:
        if node.get("type") == "DISK":
            # F4: skip DISK leaves with a falsy/null disk name (detached/unavail members)
            name = node.get("disk")
            if name:
                stats = node.get("stats") or {}
                result[name] = {
                    "errors": {
                        "read": stats.get("read_errors", 0),
                        "write": stats.get("write_errors", 0),
                        "checksum": stats.get("checksum_errors", 0),
                    },
                    "status": node.get("status"),
                }
        for child in node.get("children") or []:
            _visit(child)

    for category in _TOPOLOGY_CATEGORIES:
        for vdev in topology.get(category) or []:
            _visit(vdev)
    return result


class StorageCoordinator(TrueNASBaseCoordinator[StorageData]):
    """Pools + disks, with per-disk temperature and ZFS error/status injection."""

    def __init__(self, hass: HomeAssistant, client: TrueNASClient) -> None:
        """Initialize the storage coordinator."""
        super().__init__(hass, client, "TrueNAS Storage", SCAN_INTERVAL_STORAGE)

    def _fetch(self) -> StorageData:
        """Query pools/disks/temperatures and assemble StorageData."""
        raw_pools = self.client.call("pool.query")
        raw_disks = self.client.call("disk.query")
        temps = self.client.call("disk.temperatures")

        pools = {pool["guid"]: pool for pool in raw_pools}

        # Build a dev-name -> {errors, status} index from every pool's topology.
        by_devname: dict[str, dict] = {}
        for pool in raw_pools:
            by_devname.update(_walk_topology_errors(pool))

        disks: dict[str, dict] = {}
        for disk in raw_disks:
            dev_name = disk.get("name")
            # F5: use a stable id: serial if present, else identifier, else name
            stable_id = (
                disk.get("serial") or disk.get("identifier") or dev_name
            )
            # Skip entirely if no stable id can be derived
            if not stable_id:
                continue
            entry = dict(disk)
            entry["temperature"] = temps.get(dev_name) if temps else None
            topo = by_devname.get(dev_name)
            if topo is not None:
                entry["errors"] = topo["errors"]
                entry["zfs_status"] = topo["status"]
            else:
                entry["errors"] = {"read": 0, "write": 0, "checksum": 0}
                entry["zfs_status"] = None
            disks[stable_id] = entry

        return StorageData(pools=pools, disks=disks)


class DatasetCoordinator(TrueNASBaseCoordinator[dict[str, dict]]):
    """Datasets, flattened from the nested children[] tree, keyed by id path."""

    def __init__(self, hass: HomeAssistant, client: TrueNASClient) -> None:
        """Initialize the dataset coordinator."""
        super().__init__(hass, client, "TrueNAS Datasets", SCAN_INTERVAL_DATASETS)

    def _fetch(self) -> dict[str, dict]:
        """Query datasets (with snapshot counts) and flatten the tree."""
        raw = self.client.call(
            "pool.dataset.query", [], {"extra": {"snapshots_count": True}}
        )
        flattened: dict[str, dict] = {}

        def _visit(node: dict) -> None:
            flattened[node["id"]] = node
            for child in node.get("children") or []:
                _visit(child)

        for dataset in raw:
            _visit(dataset)
        return flattened


class SystemCoordinator(TrueNASBaseCoordinator[SystemData]):
    """system.info + alert.list + service.query, services keyed by name."""

    def __init__(self, hass: HomeAssistant, client: TrueNASClient) -> None:
        """Initialize the system coordinator."""
        super().__init__(hass, client, "TrueNAS System", SCAN_INTERVAL_SYSTEM)

    def _fetch(self) -> SystemData:
        """Query system info, alerts, and services."""
        info = self.client.call("system.info")
        alerts = self.client.call("alert.list")
        raw_services = self.client.call("service.query")
        services = {svc["service"]: svc for svc in raw_services}
        return SystemData(info=info, alerts=alerts, services=services)


def _latest(graph: dict, column: str) -> float | None:
    """Return the last data row's value for `column`, or None if no data."""
    # F2: guard missing data or missing legend column (avoids ValueError from .index)
    if not graph.get("data") or column not in graph.get("legend", []):
        return None
    return graph["data"][-1][graph["legend"].index(column)]


class ReportingCoordinator(TrueNASBaseCoordinator[ReportingData]):
    """CPU busy %, CPU temperature, and memory usage derived from reporting graphs."""

    def __init__(
        self, hass: HomeAssistant, client: TrueNASClient, physmem: int
    ) -> None:
        """Initialize the reporting coordinator with total physical memory."""
        super().__init__(
            hass, client, "TrueNAS Reporting", SCAN_INTERVAL_REPORTING
        )
        self._physmem = physmem

    def _fetch(self) -> ReportingData:
        """Query the cpu/cputemp/memory graphs and derive metrics."""
        graphs = self.client.call(
            "reporting.get_data",
            [{"name": "cpu"}, {"name": "cputemp"}, {"name": "memory"}],
            {"unit": "HOUR", "page": 1},
        )
        by_name = {graph["name"]: graph for graph in graphs}

        cpu_percent = _latest(by_name.get("cpu", {}), "cpu")

        cpu_temp: float | None = None
        cputemp = by_name.get("cputemp", {})
        if cputemp.get("data"):
            # F1: filter out None values before averaging (netdata can return null temps)
            nums = [v for v in cputemp["data"][-1][1:] if v is not None]
            cpu_temp = sum(nums) / len(nums) if nums else None

        memory_free = _latest(by_name.get("memory", {}), "available")
        memory_used: int | None = None
        memory_used_percent: float | None = None
        if memory_free is not None:
            memory_free = int(memory_free)
            memory_used = self._physmem - memory_free
            # F3: guard divide-by-zero when physmem is 0 or falsy
            memory_used_percent = (
                round(memory_used / self._physmem * 100, 1) if self._physmem else None
            )

        return ReportingData(
            cpu_percent=cpu_percent,
            cpu_temp=cpu_temp,
            memory_used=memory_used,
            memory_free=memory_free,
            memory_used_percent=memory_used_percent,
        )
