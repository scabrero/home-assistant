"""Select platform for V2C settings."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any, override

from pytrydan import TrydanData
from pytrydan.models.trydan import ChargeMode, DynamicPowerMode

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import (
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
    EntityCategory,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import CONF_PV_AVAILABLE, DOMAIN
from .coordinator import V2CConfigEntry, V2CUpdateCoordinator
from .entity import V2CBaseEntity


def charge_mode_value(value: ChargeMode) -> str:
    """Return the charge mode option value."""
    return value.name.lower()


async def _get_contracted_power(
    hass: HomeAssistant, config_entry: V2CConfigEntry, helper_key: str
) -> int:
    dev_reg = dr.async_get(hass)
    device = dev_reg.async_get_device(identifiers={(DOMAIN, config_entry.entry_id)})
    if not device:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_device",
            translation_placeholders={"config_entry_id": config_entry.entry_id},
        )

    ent_reg = er.async_get(hass)
    entries = er.async_entries_for_device(
        ent_reg, device.id, include_disabled_entities=True
    )
    entity = next(
        (
            e
            for e in entries
            if e.domain == Platform.NUMBER and e.unique_id.endswith(f"_{helper_key}")
        ),
        None,
    )
    if not entity:
        raise HomeAssistantError(
            translation_domain=DOMAIN,
            translation_key="no_entity",
            translation_placeholders={"key": helper_key},
        )

    if (state := hass.states.get(entity.entity_id)) and state.state not in (
        STATE_UNKNOWN,
        STATE_UNAVAILABLE,
    ):
        return round(float(state.state))

    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="no_state",
        translation_placeholders={"entity_id": entity.entity_id},
    )


async def _dynamic_power_mode(entity: V2CSelectEntity, option: str) -> None:
    evse = entity.coordinator.evse
    mode = DynamicPowerMode(int(option))

    if mode == DynamicPowerMode.TIMED_POWER_ENABLED:
        # The profile will set the contracted power
        await evse.dynamic_power_mode(mode)
        return

    # Read the contracted power before touching the device as exception
    # can be raised if the helpers are not yet configured
    if mode == DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED:
        contracted_power = await _get_contracted_power(
            entity.hass, entity.coordinator.config_entry, "fv_excl_balance"
        )
    else:
        contracted_power = await _get_contracted_power(
            entity.hass, entity.coordinator.config_entry, "contracted_power"
        )
    await evse.dynamic_power_mode(mode)
    # Trigger API cached data refresh so it matches the mode just set because
    # the contracted power validator depends on the mode.
    await evse.get_data()
    await evse.contracted_power(contracted_power)


@dataclass(frozen=True, kw_only=True)
class V2CSelectEntityDescription(SelectEntityDescription):
    """Describes V2C EVSE select entity."""

    current_option_fn: Callable[[TrydanData], str | None]
    options: list[str]
    update_fn: Callable[[V2CSelectEntity, str], Coroutine[Any, Any, None]]


CHARGE_MODE_OPTIONS = [charge_mode_value(mode) for mode in ChargeMode]
DYNAMIC_POWER_MODE_OPTIONS = [str(mode.value) for mode in DynamicPowerMode]

TRYDAN_SELECTS = (
    V2CSelectEntityDescription(
        key="charge_mode",
        translation_key="charge_mode",
        entity_category=EntityCategory.CONFIG,
        options=CHARGE_MODE_OPTIONS,
        current_option_fn=lambda evse_data: (
            charge_mode_value(evse_data.charge_mode)
            if evse_data.charge_mode is not None
            else None
        ),
        update_fn=lambda entity, option: entity.coordinator.evse.charge_mode(
            ChargeMode[option.upper()]
        ),
    ),
)

TRYDAN_PV_SELECTS = (
    V2CSelectEntityDescription(
        key="dynamic_power_mode",
        translation_key="dynamic_power_mode",
        entity_category=EntityCategory.CONFIG,
        options=DYNAMIC_POWER_MODE_OPTIONS,
        current_option_fn=lambda evse_data: (
            str(evse_data.dynamic_power_mode.value)
            if evse_data.dynamic_power_mode is not None
            else None
        ),
        update_fn=_dynamic_power_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: V2CConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up V2C Trydan select platform."""
    coordinator = config_entry.runtime_data
    data = coordinator.data
    assert data is not None

    entities: list[V2CSelectEntity] = []

    entities.extend(
        V2CSelectEntity(
            coordinator,
            description,
            config_entry.entry_id,
        )
        for description in TRYDAN_SELECTS
        if description.current_option_fn(data) is not None
    )
    if coordinator.config_entry.data.get(CONF_PV_AVAILABLE):
        entities.extend(
            V2CSelectEntity(
                coordinator,
                description,
                config_entry.entry_id,
            )
            for description in TRYDAN_PV_SELECTS
            if description.current_option_fn(data) is not None
        )
    async_add_entities(entities)


class V2CSelectEntity(V2CBaseEntity, SelectEntity):
    """Representation of V2C EVSE settings select entity."""

    entity_description: V2CSelectEntityDescription

    def __init__(
        self,
        coordinator: V2CUpdateCoordinator,
        description: V2CSelectEntityDescription,
        entry_id: str,
    ) -> None:
        """Initialize the V2C select entity."""
        super().__init__(coordinator, description)
        self._attr_unique_id = f"{entry_id}_{description.key}"
        self._attr_options = description.options

    @property
    @override
    def current_option(self) -> str | None:
        """Return the current charge mode."""
        return self.entity_description.current_option_fn(self.data)

    @override
    async def async_select_option(self, option: str) -> None:
        """Update the setting."""
        await self.entity_description.update_fn(self, option)
        await self.coordinator.async_request_refresh()
