"""Repairs platform for the V2C integration."""

from typing import cast

import voluptuous as vol

from homeassistant.components.repairs import RepairsFlow, RepairsFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import selector

from .const import CONF_PV_AVAILABLE, DOMAIN
from .coordinator import V2CConfigEntry


class ReconfigureRepairFlow(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, entry: V2CConfigEntry) -> None:
        """Create flow."""
        super().__init__()
        self.entry = entry

    async def async_step_init(
        self, user_input: dict[str, bool] | None = None
    ) -> RepairsFlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, bool] | None = None
    ) -> RepairsFlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            new_data = {**self.entry.data, **user_input}
            self.hass.config_entries.async_update_entry(self.entry, data=new_data)
            await self.hass.config_entries.async_reload(self.entry.entry_id)
            return self.async_create_entry(data={})

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_PV_AVAILABLE): selector.BooleanSelector(),
                }
            ),
            description_placeholders={"id": self.entry.unique_id or "Trydan"},
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    if issue_id.startswith("reconfigure_needed"):
        if not data or "entry_id" not in data:
            raise ValueError("Missing data for repair flow")
        entry_id = cast(str, data["entry_id"])
        entry = hass.config_entries.async_get_entry(entry_id)
        if not entry:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unknown_config_entry_id",
                translation_placeholders={"entry_id": entry_id},
            )
        return ReconfigureRepairFlow(entry)
    raise HomeAssistantError(
        translation_domain=DOMAIN,
        translation_key="unknown_issue_id",
        translation_placeholders={"issue_id": issue_id},
    )
