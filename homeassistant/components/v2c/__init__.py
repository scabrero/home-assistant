"""The V2C integration."""

from pytrydan import Trydan

from homeassistant.const import CONF_HOST, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.httpx_client import get_async_client
from homeassistant.helpers.issue_registry import (
    IssueSeverity,
    async_create_issue,
    async_delete_issue,
)

from .const import CONF_PV_AVAILABLE, DOMAIN
from .coordinator import V2CConfigEntry, V2CUpdateCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.LIGHT,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]


async def async_setup_entry(hass: HomeAssistant, entry: V2CConfigEntry) -> bool:
    """Set up V2C from a config entry."""

    trydan = Trydan(entry.data[CONF_HOST], get_async_client(hass, verify_ssl=False))
    coordinator = V2CUpdateCoordinator(hass, entry, trydan)

    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator

    if coordinator.data.ID and entry.unique_id != coordinator.data.ID:
        hass.config_entries.async_update_entry(entry, unique_id=coordinator.data.ID)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    if CONF_PV_AVAILABLE not in entry.data:
        async_create_issue(
            hass,
            DOMAIN,
            f"reconfigure_needed_{entry.entry_id}",
            is_fixable=True,
            is_persistent=False,
            severity=IssueSeverity.WARNING,
            translation_key="reconfigure_needed",
            data={"entry_id": entry.entry_id},
        )
    else:
        async_delete_issue(hass, DOMAIN, f"reconfigure_needed_{entry.entry_id}")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: V2CConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
