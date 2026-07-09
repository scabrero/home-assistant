"""Test the V2C select platform."""

from unittest.mock import AsyncMock, patch

import pytest
from pytrydan import DynamicPowerMode
from pytrydan.models.trydan import ChargeMode
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration

from tests.common import MockConfigEntry, snapshot_platform

DYNAMIC_POWER_MODE_ENTITY = "select.evse_1_1_1_1_dynamic_power_mode"
FV_EXCL_BALANCE_ENTITY = "number.evse_1_1_1_1_fv_exclusive_mode_balance"
CONTRACTED_POWER_ENTITY = "number.evse_1_1_1_1_contracted_power"


async def test_select(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test states of the select entities."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_select_option(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test selecting an option."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: "select.evse_1_1_1_1_charge_mode",
            ATTR_OPTION: "mixed",
        },
        blocking=True,
    )

    mock_v2c_client.charge_mode.assert_awaited_once_with(ChargeMode.MIXED)


async def test_select_not_created_when_missing(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test missing charge mode entity is not created."""
    mock_v2c_client.get_data.return_value.charge_mode = None

    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    entity_id = "select.evse_1_1_1_1_charge_mode"
    assert entity_registry.async_get(entity_id) is None
    assert hass.states.get(entity_id) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_created_when_pv_available(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test the dynamic power mode select is created when photovoltaic is enabled."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    assert hass.states.get(DYNAMIC_POWER_MODE_ENTITY) is not None


async def test_dynamic_power_mode_not_created_without_pv(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the dynamic power mode select is absent without photovoltaic."""
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_config_entry)

    assert hass.states.get(DYNAMIC_POWER_MODE_ENTITY) is None


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_profile(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test selecting the profile mode does not set the contracted power.

    The V2C cloud profile is responsible for the contracted power.
    """
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
            ATTR_OPTION: str(DynamicPowerMode.TIMED_POWER_ENABLED.value),
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(
        DynamicPowerMode.TIMED_POWER_ENABLED
    )
    mock_v2c_client.contracted_power.assert_not_called()


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_fv_exclusive(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test FV exclusive mode pushes the FV balance helper as contracted power."""
    with patch(
        "homeassistant.components.v2c.PLATFORMS",
        [Platform.NUMBER, Platform.SELECT],
    ):
        await init_integration(hass, mock_pv_config_entry)

    # Seed the FV balance helper with a known value
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: FV_EXCL_BALANCE_ENTITY, ATTR_VALUE: -500},
        blocking=True,
    )

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
            ATTR_OPTION: str(
                DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED.value
            ),
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_EXCL_MODE_SETTED
    )
    mock_v2c_client.contracted_power.assert_awaited_once_with(-500)


@pytest.mark.parametrize(
    "mode",
    [
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_MIN_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED,
        DynamicPowerMode.TIMED_POWER_DISABLED_AND_STOP_MODE_SETTED,
    ],
)
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_other_modes(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
    mode: DynamicPowerMode,
) -> None:
    """Test non-FV-exclusive modes push the contracted power helper value."""
    with patch(
        "homeassistant.components.v2c.PLATFORMS",
        [Platform.NUMBER, Platform.SELECT],
    ):
        await init_integration(hass, mock_pv_config_entry)

    # Seed the contracted power helper with a known value
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: CONTRACTED_POWER_ENTITY, ATTR_VALUE: 6000},
        blocking=True,
    )
    mock_v2c_client.contracted_power.reset_mock()

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {
            ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
            ATTR_OPTION: str(mode.value),
        },
        blocking=True,
    )

    mock_v2c_client.dynamic_power_mode.assert_awaited_once_with(mode)
    mock_v2c_client.contracted_power.assert_awaited_once_with(6000)


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_dynamic_power_mode_no_helper_state(
    hass: HomeAssistant,
    mock_v2c_client: AsyncMock,
    mock_pv_config_entry: MockConfigEntry,
) -> None:
    """Test that a missing helper state raises when changing mode.

    When only the SELECT platform is loaded the number helpers do not exist,
    so _get_contracted_power cannot find the entity.
    """
    with patch("homeassistant.components.v2c.PLATFORMS", [Platform.SELECT]):
        await init_integration(hass, mock_pv_config_entry)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: DYNAMIC_POWER_MODE_ENTITY,
                ATTR_OPTION: str(
                    DynamicPowerMode.TIMED_POWER_DISABLED_AND_FV_GRID_MODE_SETTED.value
                ),
            },
            blocking=True,
        )
