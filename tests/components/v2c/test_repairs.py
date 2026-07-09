"""Test the V2C repairs."""

from unittest.mock import AsyncMock

import pytest

from homeassistant.components.v2c.const import CONF_PV_AVAILABLE, DOMAIN
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry as ir
from homeassistant.setup import async_setup_component

from . import init_integration

from tests.common import MockConfigEntry
from tests.components.repairs import process_repair_fix_flow, start_repair_fix_flow
from tests.typing import ClientSessionGenerator


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_reconfigure_repair_flow(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    issue_registry: ir.IssueRegistry,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the reconfigure repair flow updates the entry and clears the issue."""
    # The fixture config entry has no CONF_PV_AVAILABLE key, so the issue is created
    await init_integration(hass, mock_config_entry)

    issue_id = f"reconfigure_needed_{mock_config_entry.entry_id}"
    issue = issue_registry.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.is_fixable is True
    assert issue.data == {"entry_id": mock_config_entry.entry_id}
    assert CONF_PV_AVAILABLE not in mock_config_entry.data

    assert await async_setup_component(hass, "repairs", {})
    client = await hass_client()

    # Start the repair flow
    data = await start_repair_fix_flow(client, DOMAIN, issue_id)
    flow_id = data["flow_id"]
    assert data["step_id"] == "confirm"

    # Confirm the repair, enabling photovoltaic
    data = await process_repair_fix_flow(client, flow_id, {CONF_PV_AVAILABLE: True})
    assert data["type"] == "create_entry"
    await hass.async_block_till_done()

    # The entry is updated and the issue is cleared
    assert mock_config_entry.data == {CONF_HOST: "1.1.1.1", CONF_PV_AVAILABLE: True}
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_issue_not_created_when_pv_available_set(
    hass: HomeAssistant,
    issue_registry: ir.IssueRegistry,
    mock_v2c_client: AsyncMock,
) -> None:
    """Test the issue is not created when the entry already has CONF_PV_AVAILABLE."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="da58ee91f38c2406c2a36d0a1a7f8569",
        title="EVSE 1.1.1.1",
        data={CONF_HOST: "1.1.1.1", CONF_PV_AVAILABLE: True},
    )
    await init_integration(hass, config_entry)

    issue_id = f"reconfigure_needed_{config_entry.entry_id}"
    assert issue_registry.async_get_issue(DOMAIN, issue_id) is None
