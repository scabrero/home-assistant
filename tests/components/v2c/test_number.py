"""Test the V2C number platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytrydan import DynamicPowerMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import (
    MockConfigEntry,
    mock_restore_cache_with_extra_data,
    snapshot_platform,
)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the number entities."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_set_value(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test setting number values."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.evse_1_1_1_1_installation_voltage",
            ATTR_VALUE: 240,
        },
        blocking=True,
    )

    mock_v2c_client.voltage_installation.assert_called_once_with(240)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_helpers_created_when_pv_available(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the helper entities are only created when photovoltaic is enabled."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    assert hass.states.get("number.evse_1_1_1_1_fv_exclusive_mode_balance") is not None
    assert hass.states.get("number.evse_1_1_1_1_contracted_power") is not None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_number_helpers_not_created_without_pv(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the helper entities are absent when photovoltaic is not enabled."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_config_entry)

    assert hass.states.get("number.evse_1_1_1_1_fv_exclusive_mode_balance") is None
    assert hass.states.get("number.evse_1_1_1_1_contracted_power") is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fv_excl_balance_set_value(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test setting the FV exclusive balance helper.

    In FV exclusive mode the API contracted power is written.
    """
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    )
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    entity_id = "number.evse_1_1_1_1_fv_exclusive_mode_balance"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: -500},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "-500"
    mock_v2c_client.contracted_power.assert_called_once_with(-500)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_fv_excl_balance_set_value_other_mode(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the FV exclusive balance helper is a no-op outside FV exclusive mode."""
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED
    )
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    entity_id = "number.evse_1_1_1_1_fv_exclusive_mode_balance"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: -500},
        blocking=True,
    )

    # The state is still updated locally, but the API is not touched
    assert hass.states.get(entity_id).state == "-500"
    mock_v2c_client.contracted_power.assert_not_called()


@pytest.mark.parametrize(
    "mode",
    [
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_STOP_MODE_SETTED,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contracted_power_set_value(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
    mode: DynamicPowerMode,
) -> None:
    """Test setting the contracted power helper updates the API in non FV exclusive mode."""
    mock_v2c_client.data.dynamic_power_mode = mode
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    entity_id = "number.evse_1_1_1_1_contracted_power"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 6000},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "6000"
    mock_v2c_client.contracted_power.assert_called_once_with(6000)


@pytest.mark.parametrize(
    "mode",
    [
        DynamicPowerMode.TIMED_POWER_ENABLED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contracted_power_set_value_excluded_modes(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
    mode: DynamicPowerMode,
) -> None:
    """Test the contracted power helper is a no-op in profile and FV exclusive modes."""
    mock_v2c_client.data.dynamic_power_mode = mode
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    entity_id = "number.evse_1_1_1_1_contracted_power"
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: 6000},
        blocking=True,
    )

    assert hass.states.get(entity_id).state == "6000"
    mock_v2c_client.contracted_power.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contracted_power_restore_state(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the contracted power helper restores its previous value."""
    entity_id = "number.evse_1_1_1_1_contracted_power"
    mock_v2c_client.data.dynamic_power_mode = (
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED
    )
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(entity_id, "5000"),
                {
                    "native_max_value": 10000,
                    "native_min_value": 0,
                    "native_step": 100,
                    "native_unit_of_measurement": "W",
                    "native_value": 5000,
                },
            ),
        ),
    )

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    # Restored value is applied and, since we are not in an excluded mode,
    # it is pushed to the API on startup.
    assert hass.states.get(entity_id).state == "5000"
    mock_v2c_client.contracted_power.assert_called_once_with(5000)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_contracted_power_restore_state_unknown(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the helper does not restore an unknown state."""
    entity_id = "number.evse_1_1_1_1_contracted_power"
    mock_restore_cache_with_extra_data(
        hass,
        (
            (
                State(entity_id, STATE_UNKNOWN),
                {
                    "native_max_value": 10000,
                    "native_min_value": 0,
                    "native_step": 100,
                    "native_unit_of_measurement": "W",
                    "native_value": 5000,
                },
            ),
        ),
    )

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.NUMBER]):
        await init_integration(hass, mock_pv_config_entry)

    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    mock_v2c_client.contracted_power.assert_not_called()
