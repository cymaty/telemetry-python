import pytest

from telemetry.testing import TelemetryFixture


stateful = pytest.mark.stateful

@pytest.fixture
def telemetry(caplog, request) -> TelemetryFixture:
    import telemetry
    stateful = False
    for marker in request.node.own_markers:
        if marker.name == 'stateful':
            if len(marker.args) == 0:
                stateful = True
            else:
                stateful = bool(marker.args[0])

    fixture = TelemetryFixture(stateful=stateful)
    caplog.handler.setFormatter(fixture.caplog)
    with telemetry.with_telemetry(fixture):
        yield fixture
