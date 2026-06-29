"""Number platform for V2C settings."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from pytrydan import DynamicPowerMode, Trydan, TrydanData

from homeassistant.components.number import (
    DEFAULT_MAX_VALUE,
    DEFAULT_MIN_VALUE,
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import V2CConfigEntry, V2CUpdateCoordinator
from .entity import V2CBaseEntity

MIN_INTENSITY = 6
MAX_INTENSITY = 32
MIN_VOLTAGE = 1
MAX_VOLTAGE = 500


def _contracted_power_min(data: TrydanData) -> float:
    if data.dynamic_power_mode == DynamicPowerMode.TIMED_POWER_ENABLED:
        return float(data.contracted_power)
    if (
        data.dynamic_power_mode
        == DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    ):
        return float(-5000)
    return float(0)


def _contracted_power_max(data: TrydanData) -> float:
    if data.dynamic_power_mode == DynamicPowerMode.TIMED_POWER_ENABLED:
        return float(data.contracted_power)
    if (
        data.dynamic_power_mode
        == DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    ):
        return float(5000)
    return float(10000)


@dataclass(frozen=True, kw_only=True)
class V2CSettingsNumberEntityDescription(NumberEntityDescription):
    """Describes V2C EVSE number entity."""

    value_fn: Callable[[TrydanData], int | None]
    update_fn: Callable[[Trydan, int], Coroutine[Any, Any, None]]
    native_min_value_fn: Callable[[TrydanData], float] | None = None
    native_max_value_fn: Callable[[TrydanData], float] | None = None


TRYDAN_NUMBER_SETTINGS = (
    V2CSettingsNumberEntityDescription(
        key="intensity",
        translation_key="intensity",
        device_class=NumberDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_INTENSITY,
        native_max_value=MAX_INTENSITY,
        value_fn=lambda evse_data: evse_data.intensity,
        update_fn=lambda evse, value: evse.intensity(value),
    ),
    V2CSettingsNumberEntityDescription(
        key="min_intensity",
        translation_key="min_intensity",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_INTENSITY,
        native_max_value=MAX_INTENSITY,
        value_fn=lambda evse_data: evse_data.min_intensity,
        update_fn=lambda evse, value: evse.min_intensity(value),
    ),
    V2CSettingsNumberEntityDescription(
        key="max_intensity",
        translation_key="max_intensity",
        device_class=NumberDeviceClass.CURRENT,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        native_min_value=MIN_INTENSITY,
        native_max_value=MAX_INTENSITY,
        value_fn=lambda evse_data: evse_data.max_intensity,
        update_fn=lambda evse, value: evse.max_intensity(value),
    ),
    V2CSettingsNumberEntityDescription(
        key="voltage_installation",
        translation_key="voltage_installation",
        device_class=NumberDeviceClass.VOLTAGE,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        native_min_value=MIN_VOLTAGE,
        native_max_value=MAX_VOLTAGE,
        value_fn=lambda evse_data: evse_data.voltage_installation,
        update_fn=lambda evse, value: evse.voltage_installation(value),
        entity_registry_enabled_default=False,
    ),
    V2CSettingsNumberEntityDescription(
        key="contracted_power",
        translation_key="contracted_power",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value_fn=_contracted_power_min,
        native_max_value_fn=_contracted_power_max,
        native_step=100,
        value_fn=lambda evse_data: evse_data.contracted_power,
        update_fn=lambda evse, value: evse.contracted_power(value),
        entity_registry_enabled_default=False,
        mode=NumberMode.BOX,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up V2C Trydan number platform."""
    coordinator = config_entry.runtime_data

    async_add_entities(
        V2CSettingsNumberEntity(coordinator, description, config_entry.entry_id)
        for description in TRYDAN_NUMBER_SETTINGS
    )


class V2CSettingsNumberEntity(V2CBaseEntity, NumberEntity):
    """Representation of V2C EVSE settings number entity."""

    entity_description: V2CSettingsNumberEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CSettingsNumberEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C number entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @property
    @override
    def native_value(self) -> float | None:
        """Return the state of the setting entity."""
        return self.entity_description.value_fn(self.data)

    @property
    @override
    def native_max_value(self) -> float:
        """Return the native max value of the number."""
        if self.entity_description.native_max_value_fn:
            return self.entity_description.native_max_value_fn(self.data)
        if self.entity_description.native_max_value:
            return self.entity_description.native_max_value
        return DEFAULT_MAX_VALUE

    @property
    @override
    def native_min_value(self) -> float:
        """Return the native min value of the number."""
        if self.entity_description.native_min_value_fn:
            return self.entity_description.native_min_value_fn(self.data)
        if self.entity_description.native_min_value:
            return self.entity_description.native_min_value
        return DEFAULT_MIN_VALUE

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        await self.entity_description.update_fn(self.coordinator.evse, int(value))
        await self.coordinator.async_request_refresh()
