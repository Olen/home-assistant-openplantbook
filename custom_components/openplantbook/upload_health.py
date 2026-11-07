"""The outcome of a plant-sensor upload run, for the upload entities.

The uploader classifies each run and sends it out as a signal. The sensors and
the "Upload problem" binary sensor keep what they need in their own state, so
Home Assistant restores it after a restart and drops it with the entry.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN

SIGNAL_UPLOAD_RUN = f"{DOMAIN}_upload_run"
SIGNAL_UPLOAD_SCHEDULE = f"{DOMAIN}_upload_schedule"

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

# No data reaching OpenPlantbook for this long is a problem.
OVERDUE_AFTER = timedelta(days=3)


@dataclass
class UploadRun:
    """What one upload run did."""

    # The client ID the run used. A run that finishes after the entry was
    # reconfigured for another account belongs to that old account.
    account: str
    status: str
    finished: datetime
    cloud_latest: datetime | None = None
    # Plant device id -> name, for plants that could not be registered.
    failed_plants: dict[str, str] = field(default_factory=dict)
    # Device ids of plants that registered.
    registered_plants: set[str] = field(default_factory=set)
    error: str | None = None

    @property
    def uploaded_at(self) -> datetime | None:
        """When this run got data to OpenPlantbook, if it did."""
        return self.finished if self.status == STATUS_UPLOADED else None


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
def announce_run(hass: HomeAssistant, run: UploadRun) -> None:
    """Tell the upload entities how a run went."""
    async_dispatcher_send(hass, SIGNAL_UPLOAD_RUN, run)


@callback
def announce_schedule(hass: HomeAssistant) -> None:
    """Tell the upload entities the daily upload was turned on or off."""
    async_dispatcher_send(hass, SIGNAL_UPLOAD_SCHEDULE)
