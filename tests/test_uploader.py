
import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import timedelta, datetime
from types import SimpleNamespace
import homeassistant.util.dt as dt_util
from homeassistant.util import dt
from custom_components.openplantbook.uploader import plant_data_upload
from custom_components.openplantbook.const import DOMAIN, ATTR_API, FLOW_NOTIFY_WARNINGS
import custom_components.openplantbook.uploader as uploader

import logging


@pytest.mark.asyncio
async def test_async_setup_upload_schedule_random_time():
    hass = Mock()
    hass.data = {DOMAIN: {}}

    entry = Mock()
    entry.options = {uploader.FLOW_UPLOAD_DATA: True}
    entry.entry_id = "entry-id"
    entry.async_on_unload = Mock()

    remove_listener = Mock()
    random_instance = Mock()
    random_instance.randrange.return_value = 3661

    with patch(
        "custom_components.openplantbook.uploader.async_call_later"
    ) as async_call_later_mock, patch(
        "custom_components.openplantbook.uploader.async_track_time_change",
        return_value=remove_listener,
    ) as async_track_time_change_mock, patch(
        "custom_components.openplantbook.uploader.random.Random",
        return_value=random_instance,
    ) as random_mock:
        await uploader.async_setup_upload_schedule(hass, entry)

    async_call_later_mock.assert_called_once()
    random_mock.assert_called_once_with(entry.entry_id)
    args, kwargs = async_track_time_change_mock.call_args
    assert args[0] == hass
    assert kwargs["hour"] == 1
    assert kwargs["minute"] == 1
    assert kwargs["second"] == 1
    assert hass.data[DOMAIN]["remove_upload_listener"] == remove_listener
    entry.async_on_unload.assert_called_once_with(remove_listener)

@pytest.mark.asyncio
async def test_plant_data_upload_warning_old_data(caplog):
    caplog.set_level(logging.DEBUG)
    # Mock hass
    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    
    # Mock hass.data
    api_mock = AsyncMock()
    hass.data[DOMAIN] = {ATTR_API: api_mock}
    
    # Mock entry
    entry = Mock()
    entry.options = {}
    
    # Mock device registry
    device = Mock()
    # identifiers must be a set of tuples for Home Assistant device registry usually, 
    # but the code does: if "plant" in str(d.identifiers)
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"
    
    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}
    
    # Mock entity registry
    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"
    
    entity_reg = Mock()
    
    # Mock recorder
    with patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_entries_for_device", return_value=[plant_entity_entry]), \
         patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance:
        
        mock_recorder = Mock()
        mock_get_instance.return_value = mock_recorder
        
        # Mock get_last_state_changes for plant entity
        plant_state = Mock()
        # The code expects plant_device_state[plant_entity_id][0].attributes["species_original"]
        plant_state.attributes = {"species_original": "capsicum annuum"}
        
        # We need to mock the async_add_executor_job to return a coroutine or use AsyncMock
        mock_recorder.async_add_executor_job = AsyncMock(return_value={"plant.my_plant": [plant_state]})
        
        # Mock SDK response
        now = dt_util.now(dt.UTC)
        last_upload = now - timedelta(days=5)
        api_mock.async_plant_instance_register.return_value = [
            {
                "id": "opb_id",
                "latest_data": last_upload.isoformat()
            }
        ]
        
        # Ensure we are using UTC for everything
        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)
        
        assert "The last time plant sensors data was successfully uploaded 5 days ago" in caplog.text
        assert any(record.levelname == "WARNING" for record in caplog.records)

@pytest.mark.asyncio
async def test_plant_data_upload_warning_never_uploaded_sunday(caplog):
    caplog.set_level(logging.DEBUG)
    # Mock hass
    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()
    
    # Mock hass.data
    api_mock = AsyncMock()
    hass.data[DOMAIN] = {ATTR_API: api_mock}
    
    # Mock entry
    entry = Mock()
    entry.options = {}
    
    # Mock device registry
    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"
    
    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}
    
    # Mock entity registry
    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"
    
    entity_reg = Mock()
    
    # Mock recorder
    with patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_entries_for_device", return_value=[plant_entity_entry]), \
         patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance:
        
        mock_recorder = Mock()
        mock_get_instance.return_value = mock_recorder
        
        # Mock get_last_state_changes for plant entity
        plant_state = Mock()
        plant_state.attributes = {"species_original": "capsicum annuum"}
        
        mock_recorder.async_add_executor_job = AsyncMock(return_value={"plant.my_plant": [plant_state]})
        
        # Mock SDK response with no latest_data
        api_mock.async_plant_instance_register.return_value = [
            {
                "id": "opb_id",
                "latest_data": None
            }
        ]
        
        # Mock now to be a Sunday (2026-01-25 is a Sunday)
        sunday = datetime(2026, 1, 25, tzinfo=dt.UTC)
        with patch("homeassistant.util.dt.now", return_value=sunday):
            await plant_data_upload(hass, entry)
        
        assert "Plants sensors data has never been uploaded successfully" in caplog.text
        assert any(record.levelname == "WARNING" for record in caplog.records)


@pytest.mark.asyncio
async def test_plant_data_upload_registration_none_response_logs_error(caplog):
    caplog.set_level(logging.DEBUG)

    # Mock hass
    hass = Mock()
    hass.data = {}
    hass.config = Mock()

    # Mock hass.data
    api_mock = AsyncMock()
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    # Mock entry
    entry = Mock()
    entry.options = {}

    # Mock device registry
    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    # Mock entity registry
    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    entity_reg = Mock()

    # Mock recorder
    with patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_entries_for_device", return_value=[plant_entity_entry]), \
         patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance:

        mock_recorder = Mock()
        mock_get_instance.return_value = mock_recorder

        plant_state = Mock()
        plant_state.attributes = {"species_original": "capsicum annuum"}
        mock_recorder.async_add_executor_job = AsyncMock(return_value={"plant.my_plant": [plant_state]})

        # Simulate SDK returning None (e.g. unauthorized) without raising
        api_mock.async_plant_instance_register.return_value = None

        # Use a non-Sunday date to avoid the Sunday warning branch
        monday = datetime(2026, 1, 26, tzinfo=dt.UTC)
        with patch("homeassistant.util.dt.now", return_value=monday):
            await plant_data_upload(hass, entry)

        assert "Unable to register Plant-instance" in caplog.text
        assert "Registration is successful" not in caplog.text


@pytest.mark.asyncio
async def test_plant_data_upload_warns_when_sensor_last_update_is_stale_via_fallback(caplog):
    caplog.set_level(logging.DEBUG)

    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    sensor_entity_entry = Mock()
    sensor_entity_entry.domain = "sensor"
    sensor_entity_entry.entity_id = "sensor.temp"
    sensor_entity_entry.original_device_class = "temperature"

    entity_reg = Mock()

    now = datetime(2026, 2, 2, tzinfo=dt.UTC)
    stale_last_updated = now - timedelta(days=5)

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    stale_sensor_state = Mock()
    stale_sensor_state.state = "20"
    stale_sensor_state.last_updated = stale_last_updated

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            if entity_id == "sensor.temp":
                return {"sensor.temp": [stale_sensor_state]}
            return {entity_id: []}

        if func is uploader.get_significant_states:
            # Force fallback path by returning no history rows
            return {}

        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch(
            "custom_components.openplantbook.uploader.entity_registry.async_entries_for_device",
            return_value=[plant_entity_entry, sensor_entity_entry],
        ),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(
            side_effect=async_add_executor_job_side_effect
        )
        mock_get_instance.return_value = mock_recorder

        api_mock.async_plant_instance_register.return_value = [
            {"id": "opb_id", "latest_data": (now - timedelta(hours=1)).isoformat()}
        ]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    assert "sensor.temp" in caplog.text
    assert "stale data" in caplog.text
    assert any(record.levelname == "WARNING" for record in caplog.records)


@pytest.mark.asyncio
async def test_plant_data_upload_does_not_warn_when_sensor_is_fresh(caplog):
    caplog.set_level(logging.DEBUG)

    hass = Mock()
    hass.data = {}
    hass.config = Mock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    sensor_entity_entry = Mock()
    sensor_entity_entry.domain = "sensor"
    sensor_entity_entry.entity_id = "sensor.temp"
    sensor_entity_entry.original_device_class = "temperature"

    entity_reg = Mock()

    now = datetime(2026, 2, 2, tzinfo=dt.UTC)
    fresh_last_updated = now - timedelta(minutes=5)

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    fresh_sensor_state = Mock()
    fresh_sensor_state.state = "20"
    fresh_sensor_state.last_updated = fresh_last_updated

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            if entity_id == "sensor.temp":
                return {"sensor.temp": [fresh_sensor_state]}
            return {entity_id: []}

        if func is uploader.get_significant_states:
            return {}

        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch(
            "custom_components.openplantbook.uploader.entity_registry.async_entries_for_device",
            return_value=[plant_entity_entry, sensor_entity_entry],
        ),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(
            side_effect=async_add_executor_job_side_effect
        )
        mock_get_instance.return_value = mock_recorder

        api_mock.async_plant_instance_register.return_value = [
            {"id": "opb_id", "latest_data": (now - timedelta(hours=1)).isoformat()}
        ]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    assert not any(record.levelname == "WARNING" for record in caplog.records)


@pytest.mark.asyncio
async def test_plant_data_upload_warns_when_stale_state_is_seen_in_history(caplog):
    caplog.set_level(logging.DEBUG)

    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    sensor_entity_entry = Mock()
    sensor_entity_entry.domain = "sensor"
    sensor_entity_entry.entity_id = "sensor.temp"
    sensor_entity_entry.original_device_class = "temperature"

    entity_reg = Mock()

    now = datetime(2026, 2, 2, tzinfo=dt.UTC)
    stale_last_updated = now - timedelta(days=5)

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    history_state = Mock()
    history_state.state = "20"
    history_state.last_updated = stale_last_updated
    history_state.attributes = {
        "device_class": "temperature",
        "unit_of_measurement": "°C",
    }

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            return {entity_id: []}

        if func is uploader.get_significant_states:
            return {"sensor.temp": [history_state]}

        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch(
            "custom_components.openplantbook.uploader.entity_registry.async_entries_for_device",
            return_value=[plant_entity_entry, sensor_entity_entry],
        ),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(
            side_effect=async_add_executor_job_side_effect
        )
        mock_get_instance.return_value = mock_recorder

        # Make the query window include our stale state (latest_data far enough in the past)
        api_mock.async_plant_instance_register.return_value = [
            {"id": "opb_id", "latest_data": (now - timedelta(days=6)).isoformat()}
        ]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    assert "sensor.temp" in caplog.text
    assert "stale data" in caplog.text
    assert any(record.levelname == "WARNING" for record in caplog.records)



@pytest.mark.asyncio
async def test_notification_stale_sensor_enabled():
    """Test combined notification is created for stale sensor when enabled."""
    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {FLOW_NOTIFY_WARNINGS: True}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    sensor_entity_entry = Mock()
    sensor_entity_entry.domain = "sensor"
    sensor_entity_entry.entity_id = "sensor.temp"
    sensor_entity_entry.original_device_class = "temperature"

    entity_reg = Mock()

    # Include microseconds to ensure user-facing timestamps drop fractional seconds
    now = datetime(2026, 2, 2, 12, 34, 56, 987654, tzinfo=dt.UTC)
    stale_last_updated = now - timedelta(days=5)

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    stale_sensor_state = Mock()
    stale_sensor_state.state = "20"
    stale_sensor_state.last_updated = stale_last_updated

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            if entity_id == "sensor.temp":
                return {"sensor.temp": [stale_sensor_state]}
            return {entity_id: []}
        if func is uploader.get_significant_states:
            return {}
        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_entries_for_device", return_value=[plant_entity_entry, sensor_entity_entry]),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(side_effect=async_add_executor_job_side_effect)
        mock_get_instance.return_value = mock_recorder
        api_mock.async_plant_instance_register.return_value = [{"id": "opb_id", "latest_data": (now - timedelta(hours=1)).isoformat()}]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    hass.services.async_call.assert_called()
    calls = hass.services.async_call.call_args_list
    notification_calls = [c for c in calls if c[0][0] == "persistent_notification" and c[0][1] == "create"]
    assert len(notification_calls) == 1
    notification_data = notification_calls[0][0][2]
    assert notification_data["title"] == "OpenPlantbook: Sensor Data Warnings"
    assert notification_data["notification_id"] == "openplantbook_sensor_data_warnings"
    assert "Stale" in notification_data["message"]
    assert "My Plant" in notification_data["message"]
    assert "sensor.temp" in notification_data["message"]
    assert "OPB Cloud latest data:" in notification_data["message"]
    assert ".987654" not in notification_data["message"]


@pytest.mark.asyncio
async def test_notification_combines_multiple_sensors():
    """Test combined notification includes multiple sensors and is created only once."""
    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {FLOW_NOTIFY_WARNINGS: True}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    temp_sensor_entry = Mock()
    temp_sensor_entry.domain = "sensor"
    temp_sensor_entry.entity_id = "sensor.temp"
    temp_sensor_entry.original_device_class = "temperature"

    moisture_sensor_entry = Mock()
    moisture_sensor_entry.domain = "sensor"
    moisture_sensor_entry.entity_id = "sensor.moisture"
    moisture_sensor_entry.original_device_class = "moisture"

    entity_reg = Mock()

    now = datetime(2026, 2, 2, tzinfo=dt.UTC)
    stale_last_updated = now - timedelta(days=5)

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    stale_temp_state = Mock()
    stale_temp_state.state = "20"
    stale_temp_state.last_updated = stale_last_updated

    stale_moisture_state = Mock()
    stale_moisture_state.state = "45"
    stale_moisture_state.last_updated = stale_last_updated

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            if entity_id == "sensor.temp":
                return {"sensor.temp": [stale_temp_state]}
            if entity_id == "sensor.moisture":
                return {"sensor.moisture": [stale_moisture_state]}
            return {entity_id: []}
        if func is uploader.get_significant_states:
            return {}
        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch(
            "custom_components.openplantbook.uploader.entity_registry.async_entries_for_device",
            return_value=[plant_entity_entry, temp_sensor_entry, moisture_sensor_entry],
        ),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(
            side_effect=async_add_executor_job_side_effect
        )
        mock_get_instance.return_value = mock_recorder
        api_mock.async_plant_instance_register.return_value = [
            {"id": "opb_id", "latest_data": (now - timedelta(hours=1)).isoformat()}
        ]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    calls = hass.services.async_call.call_args_list
    notification_calls = [
        c
        for c in calls
        if c[0][0] == "persistent_notification" and c[0][1] == "create"
    ]
    assert len(notification_calls) == 1
    notification_data = notification_calls[0][0][2]
    assert notification_data["title"] == "OpenPlantbook: Sensor Data Warnings"
    assert "My Plant" in notification_data["message"]
    assert "sensor.temp" in notification_data["message"]
    assert "sensor.moisture" in notification_data["message"]
    assert "OPB Cloud latest data:" in notification_data["message"]


@pytest.mark.asyncio
async def test_notification_disabled():
    """Test notification is NOT created when disabled."""
    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = SimpleNamespace(options={FLOW_NOTIFY_WARNINGS: False})

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    entity_reg = Mock()

    with patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg), \
         patch("custom_components.openplantbook.uploader.entity_registry.async_entries_for_device", return_value=[plant_entity_entry]), \
         patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance:

        mock_recorder = Mock()
        mock_get_instance.return_value = mock_recorder
        plant_state = Mock()
        plant_state.attributes = {"species_original": "capsicum annuum"}
        mock_recorder.async_add_executor_job = AsyncMock(return_value={"plant.my_plant": [plant_state]})

        now = dt_util.now(dt.UTC)
        last_upload = now - timedelta(days=5)
        api_mock.async_plant_instance_register.return_value = [{"id": "opb_id", "latest_data": last_upload.isoformat()}]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    if hass.services.async_call.called:
        calls = hass.services.async_call.call_args_list
        notification_calls = [c for c in calls if c[0][0] == "persistent_notification"]
        assert len(notification_calls) == 0


@pytest.mark.asyncio
async def test_plant_data_upload_warns_when_one_sensor_has_only_unavailable_unknown_states(caplog):
    """Test warning when one sensor has only unavailable/unknown states but others have valid ones."""
    caplog.set_level(logging.DEBUG)

    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    # Temperature sensor with valid recent states
    temp_sensor_entry = Mock()
    temp_sensor_entry.domain = "sensor"
    temp_sensor_entry.entity_id = "sensor.temp"
    temp_sensor_entry.original_device_class = "temperature"

    # Moisture sensor with only unavailable/unknown states
    moisture_sensor_entry = Mock()
    moisture_sensor_entry.domain = "sensor"
    moisture_sensor_entry.entity_id = "sensor.moisture"
    moisture_sensor_entry.original_device_class = "moisture"

    entity_reg = Mock()

    now = datetime(2026, 2, 10, tzinfo=dt.UTC)
    stale_last_updated = now - timedelta(days=5)  # 5 days ago, exceeds 3-day threshold
    recent_last_updated = now - timedelta(hours=2)  # 2 hours ago, fresh

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    # Temperature sensor has valid recent state
    temp_sensor_state = Mock()
    temp_sensor_state.state = "22.5"
    temp_sensor_state.last_updated = recent_last_updated
    temp_sensor_state.attributes = {"unit_of_measurement": "°C"}

    # Moisture sensor's last valid state was 5 days ago
    moisture_sensor_stale_state = Mock()
    moisture_sensor_stale_state.state = "45"
    moisture_sensor_stale_state.last_updated = stale_last_updated
    moisture_sensor_stale_state.attributes = {"unit_of_measurement": "%"}

    # Moisture sensor's recent states are all unavailable/unknown
    moisture_unavailable_state_1 = Mock()
    moisture_unavailable_state_1.state = "unavailable"
    moisture_unavailable_state_1.last_updated = now - timedelta(hours=12)

    moisture_unknown_state_2 = Mock()
    moisture_unknown_state_2.state = "unknown"
    moisture_unknown_state_2.last_updated = now - timedelta(hours=6)

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            if entity_id == "sensor.temp":
                return {"sensor.temp": [temp_sensor_state]}
            if entity_id == "sensor.moisture":
                # Return the stale valid state from 5 days ago
                return {"sensor.moisture": [moisture_sensor_stale_state]}
            return {entity_id: []}

        if func is uploader.get_significant_states:
            # Temperature sensor returns valid recent states
            if "sensor.temp" in args[3]:
                return {"sensor.temp": [temp_sensor_state]}
            # Moisture sensor returns only unavailable/unknown states
            if "sensor.moisture" in args[3]:
                return {"sensor.moisture": [moisture_unavailable_state_1, moisture_unknown_state_2]}
            return {}

        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch(
            "custom_components.openplantbook.uploader.entity_registry.async_entries_for_device",
            return_value=[plant_entity_entry, temp_sensor_entry, moisture_sensor_entry],
        ),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(
            side_effect=async_add_executor_job_side_effect
        )
        mock_get_instance.return_value = mock_recorder

        api_mock.async_plant_instance_register.return_value = [
            {"id": "opb_id", "latest_data": (now - timedelta(hours=1)).isoformat()}
        ]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    # Verify warning is logged about the stale moisture sensor
    assert "sensor.moisture" in caplog.text
    assert "stale data" in caplog.text
    assert any(record.levelname == "WARNING" for record in caplog.records)
    
    # Verify the warning mentions it's been 5 days
    assert "5 days ago" in caplog.text or "5 days" in caplog.text


@pytest.mark.asyncio
async def test_notification_missing_sensor_data_enabled(caplog):
    """Test warning + notification when a sensor has no valid state and fallback cannot determine last valid update."""
    caplog.set_level(logging.WARNING)

    hass = Mock()
    hass.data = {}
    hass.config = Mock()
    hass.services = Mock()
    hass.services.async_call = AsyncMock()

    api_mock = AsyncMock()
    api_mock.async_plant_data_upload.return_value = True
    hass.data[DOMAIN] = {ATTR_API: api_mock}

    entry = Mock()
    entry.options = {FLOW_NOTIFY_WARNINGS: True}

    device = Mock()
    device.identifiers = {("plant", "something")}
    device.name_by_user = None
    device.id = "device_id"
    device.name = "My Plant"
    device.model = "Plant Model"

    device_reg = Mock()
    device_reg.devices.data = {"device_id": device}

    plant_entity_entry = Mock()
    plant_entity_entry.domain = "plant"
    plant_entity_entry.entity_id = "plant.my_plant"

    temp_sensor_entry = Mock()
    temp_sensor_entry.domain = "sensor"
    temp_sensor_entry.entity_id = "sensor.temp"
    temp_sensor_entry.original_device_class = "temperature"

    moisture_sensor_entry = Mock()
    moisture_sensor_entry.domain = "sensor"
    moisture_sensor_entry.entity_id = "sensor.moisture"
    moisture_sensor_entry.original_device_class = "moisture"

    entity_reg = Mock()

    # Include microseconds to ensure user-facing timestamps drop fractional seconds
    now = datetime(2026, 2, 10, 1, 2, 3, 654321, tzinfo=dt.UTC)

    plant_state = Mock()
    plant_state.attributes = {"species_original": "capsicum annuum"}

    recent_temp_state = Mock()
    recent_temp_state.state = "22.5"
    recent_temp_state.last_updated = now - timedelta(minutes=10)
    recent_temp_state.attributes = {"unit_of_measurement": "°C"}

    moisture_unavailable_state = Mock()
    moisture_unavailable_state.state = "unavailable"
    moisture_unavailable_state.last_updated = now - timedelta(hours=1)

    moisture_unknown_state = Mock()
    moisture_unknown_state.state = "unknown"
    moisture_unknown_state.last_updated = now - timedelta(minutes=30)

    async def async_add_executor_job_side_effect(func, *args, **kwargs):
        if func is uploader.get_last_state_changes:
            entity_id = args[2]
            if entity_id == "plant.my_plant":
                return {"plant.my_plant": [plant_state]}
            if entity_id == "sensor.moisture":
                # No last state change (or no valid state) can be determined
                return {"sensor.moisture": []}
            return {entity_id: []}

        if func is uploader.get_significant_states:
            if "sensor.temp" in args[3]:
                return {"sensor.temp": [recent_temp_state]}
            if "sensor.moisture" in args[3]:
                return {
                    "sensor.moisture": [
                        moisture_unavailable_state,
                        moisture_unknown_state,
                    ]
                }
            return {}

        raise AssertionError(f"Unexpected executor job: {func}")

    with (
        patch("custom_components.openplantbook.uploader.device_registry.async_get", return_value=device_reg),
        patch("custom_components.openplantbook.uploader.entity_registry.async_get", return_value=entity_reg),
        patch(
            "custom_components.openplantbook.uploader.entity_registry.async_entries_for_device",
            return_value=[plant_entity_entry, temp_sensor_entry, moisture_sensor_entry],
        ),
        patch("custom_components.openplantbook.uploader.get_instance") as mock_get_instance,
    ):
        mock_recorder = Mock()
        mock_recorder.async_add_executor_job = AsyncMock(
            side_effect=async_add_executor_job_side_effect
        )
        mock_get_instance.return_value = mock_recorder

        api_mock.async_plant_instance_register.return_value = [
            {"id": "opb_id", "latest_data": (now - timedelta(hours=1)).isoformat()}
        ]

        with patch("homeassistant.util.dt.now", return_value=now):
            await plant_data_upload(hass, entry)

    assert "sensor.moisture" in caplog.text
    assert "has no valid data" in caplog.text

    calls = hass.services.async_call.call_args_list
    notification_calls = [
        c
        for c in calls
        if c[0][0] == "persistent_notification" and c[0][1] == "create"
    ]
    assert len(notification_calls) == 1
    notification_data = notification_calls[0][0][2]
    assert notification_data["title"] == "OpenPlantbook: Sensor Data Warnings"
    assert notification_data["notification_id"] == "openplantbook_sensor_data_warnings"
    assert "No valid data" in notification_data["message"]
    assert "My Plant" in notification_data["message"]
    assert "sensor.moisture" in notification_data["message"]
    assert "OPB Cloud latest data:" in notification_data["message"]
    assert ".654321" not in notification_data["message"]

