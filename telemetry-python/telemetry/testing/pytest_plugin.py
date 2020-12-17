import pytest

from telemetry.testing import TelemetryFixture


@pytest.fixture
def telemetry(caplog) -> TelemetryFixture:
    import telemetry
    fixture = TelemetryFixture()
    caplog.handler.setFormatter(fixture.caplog)
    with telemetry.with_telemetry(fixture):
        yield fixture
