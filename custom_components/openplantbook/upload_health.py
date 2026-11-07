"""The outcome of plant-sensor uploads, for the diagnostic sensors and triggers.

Each upload run is classified and kept here, and a dispatcher signal tells the
sensors and the upload triggers about it. Kept outside hass.data[DOMAIN], which
is cleared on unload, so triggers keep their history across a reload.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

DATA_UPLOAD_HEALTH = f"{DOMAIN}_upload_health"
SIGNAL_UPLOAD_HEALTH = f"{DOMAIN}_upload_health"

STATUS_UPLOADED = "uploaded"
STATUS_NOTHING_NEW = "nothing_new"
STATUS_FAILED = "failed"
STATUS_RATE_LIMITED = "rate_limited"
STATUS_DISABLED = "disabled"
UPLOAD_STATUSES = [
    STATUS_UPLOADED,
    STATUS_NOTHING_NEW,
    STATUS_FAILED,
    STATUS_RATE_LIMITED,
    STATUS_DISABLED,
]
FAILING_STATUSES = {STATUS_FAILED, STATUS_RATE_LIMITED}

# What a signal reports: a finished run, or values restored after a restart.
UPDATE_RUN = "run"
UPDATE_RESTORED = "restored"


@dataclass
class UploadHealth:
    """The latest upload outcome, and the one before it."""

    status: str | None = None
    last_upload: datetime | None = None
    last_run: datetime | None = None
    failed_plants: list[str] = field(default_factory=list)
    error: str | None = None
    previous_status: str | None = None
    previous_last_upload: datetime | None = None
    # An outage lasts from a failed run until data gets through again, however
    # many runs with nothing new come in between.
    in_outage: bool = False
    outage_started: bool = False
    outage_ended: bool = False


def get_upload_health(hass: HomeAssistant) -> UploadHealth:
    """Return the shared upload record, creating it on first use."""
    return hass.data.setdefault(DATA_UPLOAD_HEALTH, UploadHealth())


def classify_run(
    *, plants_total: int, plants_failed: int, sent: bool, accepted: bool
) -> str:
    """The status of a finished run.

    A run that sent data succeeded if the API accepted it. A run that sent
    nothing failed when no plant could be registered at all, which is what an
    expired token or a broken API looks like; otherwise there was nothing new.
    """
    if sent:
        return STATUS_UPLOADED if accepted else STATUS_FAILED
    if plants_total > 0 and plants_failed == plants_total:
        return STATUS_FAILED
    return STATUS_NOTHING_NEW


def newest(*times: datetime | None) -> datetime | None:
    """The latest of the given times, ignoring missing ones."""
    known = [time for time in times if time is not None]
    return max(known) if known else None


@callback
def record_run(
    hass: HomeAssistant,
    *,
    status: str,
    finished: datetime,
    cloud_latest: datetime | None = None,
    failed_plants: list[str] | None = None,
    error: str | None = None,
) -> None:
    """Keep the outcome of a run and tell the sensors and triggers."""
    health = get_upload_health(hass)
    health.previous_status = health.status
    health.previous_last_upload = health.last_upload
    uploaded_now = finished if status == STATUS_UPLOADED else None
    health.status = status
    health.last_upload = newest(health.last_upload, cloud_latest, uploaded_now)
    health.last_run = finished
    health.failed_plants = list(failed_plants or [])
    health.error = error
    health.outage_started = status in FAILING_STATUSES and not health.in_outage
    health.outage_ended = status == STATUS_UPLOADED and health.in_outage
    if status in FAILING_STATUSES:
        health.in_outage = True
    elif status == STATUS_UPLOADED:
        health.in_outage = False
    async_dispatcher_send(hass, SIGNAL_UPLOAD_HEALTH, UPDATE_RUN)


@callback
def record_restored(
    hass: HomeAssistant,
    *,
    status: str | None = None,
    last_run: datetime | None = None,
    failed_plants: list[str] | None = None,
    error: str | None = None,
    last_upload: datetime | None = None,
) -> None:
    """Seed the record from values the sensors restored after a restart.

    A run that finished since the restart is newer, so it is never overwritten.
    """
    health = get_upload_health(hass)
    if status is not None and health.status is None:
        health.status = status
        health.last_run = last_run
        health.failed_plants = list(failed_plants or [])
        health.error = error
        health.in_outage = status in FAILING_STATUSES
    health.last_upload = newest(health.last_upload, last_upload)
    async_dispatcher_send(hass, SIGNAL_UPLOAD_HEALTH, UPDATE_RESTORED)
