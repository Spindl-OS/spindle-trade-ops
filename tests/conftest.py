"""Fixtures: a real EvidenceService on temp storage with this module registered the same way
the engine does it (entry-point discovery), the simulator channel and a fixed clock."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from spindle_agents.evidence.extraction import DeterministicTextExtractor
from spindle_agents.evidence.messaging import ChannelRegistry, SimulatorChannel
from spindle_agents.evidence.models import Actor
from spindle_agents.evidence.registry import load_installed
from spindle_agents.evidence.service import EvidenceService
from spindle_agents.evidence.store import BlobStore, EvidenceStore

COMPANY = UUID("00000000-0000-4000-8000-00000000c0de")
OTHER_COMPANY = UUID("00000000-0000-4000-8000-00000000beef")
REVIEWER = Actor(kind="user", id="reviewer-1", label="Priya (trade compliance)")


class Clock:
    def __init__(self) -> None:
        self.at = datetime.now(UTC).replace(microsecond=0)

    def __call__(self) -> datetime:
        return self.at

    def advance(self, **kw: float) -> None:
        self.at += timedelta(**kw)


@pytest.fixture
def clock() -> Clock:
    return Clock()


@pytest.fixture
def make_service(tmp_path: Path, clock: Clock) -> Callable[[], EvidenceService]:
    def make() -> EvidenceService:
        store = EvidenceStore(tmp_path / "evidence.sqlite3")
        return EvidenceService(
            store,
            BlobStore(tmp_path / "blobs"),
            load_installed(),  # discovers spindle_trade_export through its entry point
            ChannelRegistry([SimulatorChannel(store)]),
            DeterministicTextExtractor(),
            clock=clock,
        )

    return make


@pytest.fixture
def service(make_service: Callable[[], EvidenceService]) -> EvidenceService:
    return make_service()
