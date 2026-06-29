"""Number platform for V2C settings."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from pytrydan import DynamicPowerMode, Trydan, TrydanData

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_PV_AVAILABLE, DOMAIN
from .coordinator import V2CConfigEntry, V2CUpdateCoordinator
from .entity import V2CBaseEntity

MIN_INTENSITY = 6
MAX_INTENSITY = 32
MIN_VOLTAGE = 1
MAX_VOLTAGE = 500


@dataclass(frozen=True, kw_only=True)
class V2CSettingsNumberEntityDescription(NumberEntityDescription):
    """Describes V2C EVSE number entity."""

    value_fn: Callable[[TrydanData], int | None]
    update_fn: Callable[[Trydan, int], Coroutine[Any, Any, None]]


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
)


@dataclass(frozen=True, kw_only=True)
class V2CHelperNumberEntityDescription(NumberEntityDescription):
    """Describes V2C EVSE helper entity."""

    update_fn: Callable[[Trydan, int], Coroutine[Any, Any, None]]


async def _update_fv_excl_balance(evse: Trydan, value: float) -> None:
    if not evse.data:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_data")
    if (
        evse.data.dynamic_power_mode
        == DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    ):
        await evse.contracted_power(round(float(value)))


async def _update_contracted_power(evse: Trydan, value: float) -> None:
    if not evse.data:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key="no_data")
    if evse.data.dynamic_power_mode not in (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_ENABLED,
    ):
        await evse.contracted_power(round(float(value)))


# These numbers are helpers completely detached from the Trydan API to adjust
# the contracted power Trydan parameter. They are used by the dynamic power
# selector to adjust the device contracted power depending on the selected
# mode.
TRYDAN_NUMBER_HELPERS = (
    V2CHelperNumberEntityDescription(
        key="fv_excl_balance",
        translation_key="fv_excl_balance",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=-5000,
        native_max_value=5000,
        native_step=100,
        mode=NumberMode.BOX,
        update_fn=_update_fv_excl_balance,
    ),
    V2CHelperNumberEntityDescription(
        key="contracted_power",
        translation_key="contracted_power",
        device_class=NumberDeviceClass.POWER,
        entity_category=EntityCategory.CONFIG,
        native_unit_of_measurement=UnitOfPower.WATT,
        native_min_value=0,
        native_max_value=10000,
        native_step=100,
        mode=NumberMode.BOX,
        update_fn=_update_contracted_power,
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
    if config_entry.data.get(CONF_PV_AVAILABLE):
        async_add_entities(
            V2CHelperNumberEntity(coordinator, description, config_entry.entry_id)
            for description in TRYDAN_NUMBER_HELPERS
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

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the setting."""
        await self.entity_description.update_fn(self.coordinator.evse, int(value))
        await self.coordinator.async_request_refresh()


class V2CHelperNumberEntity(V2CBaseEntity, RestoreNumber):
    """Representation of V2C EVSE helper number entity."""

    entity_description: V2CHelperNumberEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CHelperNumberEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C number helper entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"

    @override
    async def async_added_to_hass(self) -> None:
        """When entity is added to Home Assistant."""
        await super().async_added_to_hass()

        if (
            (last_state := await self.async_get_last_state())
            and (last_number_data := await self.async_get_last_number_data())
            and last_state.state not in (STATE_UNKNOWN, STATE_UNAVAILABLE)
            and last_number_data.native_value is not None
        ):
            await self.async_set_native_value(last_number_data.native_value)

    @override
    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        self._attr_native_value = round(float(value))
        self.async_write_ha_state()
        await self.entity_description.update_fn(
            self.coordinator.evse, round(float(value))
        )
        await self.coordinator.async_request_refresh()
