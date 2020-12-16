import pytest
import responses

from .fixture import TelemetryFixture

        
@pytest.fixture
def telemetry(caplog) -> TelemetryFixture:
    import telemetry
    fixture = TelemetryFixture()
    caplog.handler.setFormatter(fixture.caplog)
    with telemetry.with_telemetry(fixture):
        yield fixture
