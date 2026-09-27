"""Fixtures partagées par les essais."""

import pytest

from strava_fake import FakeStrava


@pytest.fixture
def fake():
    """Un faux Strava sur le réseau local, arrêté après l'essai."""
    server = FakeStrava()
    yield server
    server.close()
