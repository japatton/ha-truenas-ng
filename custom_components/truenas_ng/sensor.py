"""Sensor platform for the truenas_ng integration."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    EntityCategory,
    UnitOfInformation,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import TrueNASConfigEntry
from .client import epoch_ms_to_datetime, parsed, to_int
from .coordinator import (
    DatasetCoordinator,
    ReportingCoordinator,
    StorageCoordinator,
    SystemCoordinator,
)
from .entity import (
    TrueNASEntity,
    disk_device_info,
    hub_device_info,
    pool_device_info,
)


# --------------------------------------------------------------------------- #
# SYSTEM (SystemCoordinator.data.info)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class TrueNASSystemSensorDescription(SensorEntityDescription):
    """Describes a sensor derived from system.info."""

    value_fn: Callable[[dict], Any]


def _uptime(info: dict) -> datetime | None:
    return epoch_ms_to_datetime(info.get("boottime"))


def _loadavg(info: dict, index: int) -> float | None:
    load = info.get("loadavg")
    if not isinstance(load, (list, tuple)) or len(load) <= index:
        return None
    return load[index]


SYSTEM_SENSORS: tuple[TrueNASSystemSensorDescription, ...] = (
    TrueNASSystemSensorDescription(
        key="version",
        translation_key="version",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.get("version"),
    ),
    TrueNASSystemSensorDescription(
        key="hostname",
        translation_key="hostname",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.get("hostname"),
    ),
    TrueNASSystemSensorDescription(
        key="model",
        translation_key="model",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.get("model"),
    ),
    TrueNASSystemSensorDescription(
        key="cores",
        translation_key="cores",
        state_class=SensorStateClass.MEASUREMENT,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: to_int(info.get("cores")),
    ),
    TrueNASSystemSensorDescription(
        key="memory_total",
        translation_key="memory_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: to_int(info.get("physmem")),
    ),
    TrueNASSystemSensorDescription(
        key="uptime",
        translation_key="uptime",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_uptime,
    ),
    TrueNASSystemSensorDescription(
        key="load_1m",
        translation_key="load_1m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda info: _loadavg(info, 0),
    ),
    TrueNASSystemSensorDescription(
        key="load_5m",
        translation_key="load_5m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda info: _loadavg(info, 1),
    ),
    TrueNASSystemSensorDescription(
        key="load_15m",
        translation_key="load_15m",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda info: _loadavg(info, 2),
    ),
    # F9: ECC memory presence/status from system.info
    TrueNASSystemSensorDescription(
        key="ecc_memory",
        translation_key="ecc_memory",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda info: info.get("ecc_memory"),
    ),
)


class TrueNASSystemSensor(TrueNASEntity[SystemCoordinator], SensorEntity):
    """A sensor sourced from SystemCoordinator.data.info."""

    entity_description: TrueNASSystemSensorDescription

    def __init__(
        self,
        coordinator: SystemCoordinator,
        host_id: str,
        description: TrueNASSystemSensorDescription,
    ) -> None:
        super().__init__(coordinator, host_id)
        self.entity_description = description
        self._attr_unique_id = f"{host_id}_system_{description.key}"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data.info)


# --------------------------------------------------------------------------- #
# ALERTS (SystemCoordinator.data.alerts)
# --------------------------------------------------------------------------- #
class TrueNASAlertsSensor(TrueNASEntity[SystemCoordinator], SensorEntity):
    """Count of active (non-dismissed) alerts."""

    _attr_translation_key = "alerts_active"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: SystemCoordinator, host_id: str) -> None:
        super().__init__(coordinator, host_id)
        self._attr_unique_id = f"{host_id}_alerts_active"
        self._attr_device_info = hub_device_info(host_id, coordinator.data.info)

    @property
    def native_value(self) -> int:
        return sum(
            1
            for alert in self.coordinator.data.alerts
            if not alert.get("dismissed", False)
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        levels: dict[str, int] = {}
        for alert in self.coordinator.data.alerts:
            if alert.get("dismissed", False):
                continue
            level = str(alert.get("level", "UNKNOWN"))
            levels[level] = levels.get(level, 0) + 1
        return {"by_level": levels}


# --------------------------------------------------------------------------- #
# REPORTING (ReportingCoordinator.data)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class TrueNASReportingSensorDescription(SensorEntityDescription):
    """Describes a sensor derived from ReportingData."""

    value_fn: Callable[[Any], Any]


REPORTING_SENSORS: tuple[TrueNASReportingSensorDescription, ...] = (
    TrueNASReportingSensorDescription(
        key="cpu_percent",
        translation_key="cpu_percent",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.cpu_percent,
    ),
    TrueNASReportingSensorDescription(
        key="cpu_temp",
        translation_key="cpu_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.cpu_temp,
    ),
    TrueNASReportingSensorDescription(
        key="memory_used",
        translation_key="memory_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.memory_used,
    ),
    TrueNASReportingSensorDescription(
        key="memory_free",
        translation_key="memory_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: data.memory_free,
    ),
    TrueNASReportingSensorDescription(
        key="memory_used_pct",
        translation_key="memory_used_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: data.memory_used_percent,
    ),
)


class TrueNASReportingSensor(TrueNASEntity[ReportingCoordinator], SensorEntity):
    """A sensor sourced from ReportingCoordinator (lives on the hub device)."""

    entity_description: TrueNASReportingSensorDescription

    def __init__(
        self,
        coordinator: ReportingCoordinator,
        host_id: str,
        info: dict,
        description: TrueNASReportingSensorDescription,
    ) -> None:
        super().__init__(coordinator, host_id)
        self.entity_description = description
        self._attr_unique_id = f"{host_id}_system_{description.key}"
        self._attr_device_info = hub_device_info(host_id, info)

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator.data)


# --------------------------------------------------------------------------- #
# POOL (StorageCoordinator.data.pools)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class TrueNASPoolSensorDescription(SensorEntityDescription):
    """Describes a per-pool sensor."""

    value_fn: Callable[[dict], Any]


def _pool_used_pct(pool: dict) -> float | None:
    used = to_int(pool.get("allocated"))
    size = to_int(pool.get("size"))
    if used is None or not size:
        return None
    return round(used / size * 100, 1)


def _scrub_finished(pool: dict) -> datetime | None:
    scan = pool.get("scan") or {}
    return epoch_ms_to_datetime(scan.get("end_time"))


POOL_SENSORS: tuple[TrueNASPoolSensorDescription, ...] = (
    TrueNASPoolSensorDescription(
        key="status",
        translation_key="pool_status",
        value_fn=lambda pool: pool.get("status"),
    ),
    TrueNASPoolSensorDescription(
        key="used",
        translation_key="pool_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pool: to_int(pool.get("allocated")),
    ),
    TrueNASPoolSensorDescription(
        key="free",
        translation_key="pool_free",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        suggested_display_precision=2,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pool: to_int(pool.get("free")),
    ),
    TrueNASPoolSensorDescription(
        key="total",
        translation_key="pool_total",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.TEBIBYTES,
        suggested_display_precision=2,
        value_fn=lambda pool: to_int(pool.get("size")),
    ),
    TrueNASPoolSensorDescription(
        key="used_pct",
        translation_key="pool_used_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_pool_used_pct,
    ),
    TrueNASPoolSensorDescription(
        key="fragmentation",
        translation_key="pool_fragmentation",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pool: to_int(pool.get("fragmentation")),
    ),
    TrueNASPoolSensorDescription(
        key="scrub_state",
        translation_key="pool_scrub_state",
        value_fn=lambda pool: (pool.get("scan") or {}).get("state"),
    ),
    TrueNASPoolSensorDescription(
        key="scrub_finished",
        translation_key="pool_scrub_finished",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_scrub_finished,
    ),
    TrueNASPoolSensorDescription(
        key="scrub_errors",
        translation_key="pool_scrub_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda pool: to_int((pool.get("scan") or {}).get("errors")),
    ),
)


class TrueNASPoolSensor(TrueNASEntity[StorageCoordinator], SensorEntity):
    """A per-pool sensor keyed by pool guid."""

    entity_description: TrueNASPoolSensorDescription

    def __init__(
        self,
        coordinator: StorageCoordinator,
        host_id: str,
        guid: str,
        description: TrueNASPoolSensorDescription,
    ) -> None:
        super().__init__(coordinator, host_id)
        self.entity_description = description
        self._guid = guid
        self._attr_unique_id = f"{host_id}_pool_{guid}_{description.key}"
        self._attr_device_info = pool_device_info(host_id, self._pool)

    @property
    def _pool(self) -> dict:
        return self.coordinator.data.pools.get(self._guid, {})

    @property
    def available(self) -> bool:
        return super().available and self._guid in self.coordinator.data.pools

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._pool)


# --------------------------------------------------------------------------- #
# DISK (StorageCoordinator.data.disks)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class TrueNASDiskSensorDescription(SensorEntityDescription):
    """Describes a per-disk sensor."""

    value_fn: Callable[[dict], Any]


DISK_SENSORS: tuple[TrueNASDiskSensorDescription, ...] = (
    TrueNASDiskSensorDescription(
        key="temp",
        translation_key="disk_temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: disk.get("temperature"),
    ),
    TrueNASDiskSensorDescription(
        key="read_errors",
        translation_key="disk_read_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: (disk.get("errors") or {}).get("read"),
    ),
    TrueNASDiskSensorDescription(
        key="write_errors",
        translation_key="disk_write_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: (disk.get("errors") or {}).get("write"),
    ),
    TrueNASDiskSensorDescription(
        key="checksum_errors",
        translation_key="disk_checksum_errors",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda disk: (disk.get("errors") or {}).get("checksum"),
    ),
)


class TrueNASDiskSensor(TrueNASEntity[StorageCoordinator], SensorEntity):
    """A per-disk sensor keyed by stable disk id (serial → identifier → name)."""

    entity_description: TrueNASDiskSensorDescription

    def __init__(
        self,
        coordinator: StorageCoordinator,
        host_id: str,
        stable_id: str,
        description: TrueNASDiskSensorDescription,
    ) -> None:
        super().__init__(coordinator, host_id)
        self.entity_description = description
        # F5: stable_id is the coordinator-dict key, consistent with disk_device_info
        self._stable_id = stable_id
        self._attr_unique_id = f"{host_id}_disk_{stable_id}_{description.key}"
        self._attr_device_info = disk_device_info(host_id, self._disk, stable_id)

    @property
    def _disk(self) -> dict:
        return self.coordinator.data.disks.get(self._stable_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._stable_id in self.coordinator.data.disks

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._disk)


# --------------------------------------------------------------------------- #
# DATASET (DatasetCoordinator.data) — disabled by default
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, kw_only=True)
class TrueNASDatasetSensorDescription(SensorEntityDescription):
    """Describes a per-dataset sensor."""

    value_fn: Callable[[dict], Any]


def _dataset_used_pct(ds: dict) -> float | None:
    used = to_int(parsed(ds.get("used")))
    avail = to_int(parsed(ds.get("available")))
    if used is None or avail is None:
        return None
    total = used + avail
    if total <= 0:
        return None
    return round(used / total * 100, 1)


def _dataset_compressratio(ds: dict) -> float | None:
    value = parsed(ds.get("compressratio"))
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


DATASET_SENSORS: tuple[TrueNASDatasetSensorDescription, ...] = (
    TrueNASDatasetSensorDescription(
        key="used",
        translation_key="dataset_used",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda ds: to_int(parsed(ds.get("used"))),
    ),
    TrueNASDatasetSensorDescription(
        key="available",
        translation_key="dataset_available",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda ds: to_int(parsed(ds.get("available"))),
    ),
    TrueNASDatasetSensorDescription(
        key="quota",
        translation_key="dataset_quota",
        device_class=SensorDeviceClass.DATA_SIZE,
        native_unit_of_measurement=UnitOfInformation.BYTES,
        suggested_unit_of_measurement=UnitOfInformation.GIBIBYTES,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=lambda ds: to_int(parsed(ds.get("quota"))),
    ),
    TrueNASDatasetSensorDescription(
        key="used_pct",
        translation_key="dataset_used_pct",
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        entity_registry_enabled_default=False,
        value_fn=_dataset_used_pct,
    ),
    TrueNASDatasetSensorDescription(
        key="compressratio",
        translation_key="dataset_compressratio",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        entity_registry_enabled_default=False,
        value_fn=_dataset_compressratio,
    ),
    TrueNASDatasetSensorDescription(
        key="snapshots",
        translation_key="dataset_snapshots",
        state_class=SensorStateClass.MEASUREMENT,
        entity_registry_enabled_default=False,
        value_fn=lambda ds: to_int(ds.get("snapshot_count")),
    ),
)


class TrueNASDatasetSensor(TrueNASEntity[DatasetCoordinator], SensorEntity):
    """A per-dataset sensor keyed by dataset id (path); disabled by default."""

    entity_description: TrueNASDatasetSensorDescription

    def __init__(
        self,
        coordinator: DatasetCoordinator,
        host_id: str,
        dataset_id: str,
        device_info: "DeviceInfo",
        description: TrueNASDatasetSensorDescription,
    ) -> None:
        super().__init__(coordinator, host_id)
        self.entity_description = description
        self._dataset_id = dataset_id
        self._attr_unique_id = f"{host_id}_dataset_{dataset_id}_{description.key}"
        self._attr_translation_placeholders = {"dataset": dataset_id}
        self._attr_device_info = device_info

    @property
    def _dataset(self) -> dict:
        return self.coordinator.data.get(self._dataset_id, {})

    @property
    def available(self) -> bool:
        return super().available and self._dataset_id in self.coordinator.data

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self._dataset)


# --------------------------------------------------------------------------- #
# Platform setup
# --------------------------------------------------------------------------- #
async def async_setup_entry(
    hass: HomeAssistant,
    entry: TrueNASConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up truenas_ng sensors from a config entry."""
    data = entry.runtime_data
    host_id = data.host_id
    entities: list[SensorEntity] = []

    # System info sensors + active-alerts sensor.
    for description in SYSTEM_SENSORS:
        entities.append(TrueNASSystemSensor(data.system, host_id, description))
    entities.append(TrueNASAlertsSensor(data.system, host_id))

    # Reporting sensors (attached to the hub device via system.info).
    info = data.system.data.info
    for reporting_description in REPORTING_SENSORS:
        entities.append(
            TrueNASReportingSensor(data.reporting, host_id, info, reporting_description)
        )

    # Per-pool sensors.
    for guid in data.storage.data.pools:
        for pool_description in POOL_SENSORS:
            entities.append(
                TrueNASPoolSensor(data.storage, host_id, guid, pool_description)
            )

    # Per-disk sensors (keyed by stable_id: serial → identifier → name).
    for stable_id in data.storage.data.disks:
        for disk_description in DISK_SENSORS:
            entities.append(
                TrueNASDiskSensor(data.storage, host_id, stable_id, disk_description)
            )

    # Per-dataset sensors (disabled by default).
    # F6: attach each to its REAL pool device when that pool is known; when the
    # pool name is not found among the actual pools, attach to the hub device
    # instead of synthesising a phantom "ZFS Pool" device entry.
    pools_by_name = {
        pool.get("name"): pool for pool in data.storage.data.pools.values()
    }
    system_info = data.system.data.info
    for dataset_id, dataset in data.datasets.data.items():
        real_pool = pools_by_name.get(dataset.get("pool"))
        if real_pool is not None:
            dataset_device_info: DeviceInfo = pool_device_info(host_id, real_pool)
        else:
            dataset_device_info = hub_device_info(host_id, system_info)
        for dataset_description in DATASET_SENSORS:
            entities.append(
                TrueNASDatasetSensor(
                    data.datasets,
                    host_id,
                    dataset_id,
                    dataset_device_info,
                    dataset_description,
                )
            )

    async_add_entities(entities)
