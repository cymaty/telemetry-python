import pytest
from telemetry.testing import TelemetryFixture
import time
import urllib3

from telemetry.testing.pytest_plugin import stateful
from tests.attributes import TestAttributes


class TestPrometheusExporter:
    @stateful(True)
    def test_http_server(self, monkeypatch, telemetry: TelemetryFixture):
        address = 'localhost:19102'
        monkeypatch.setenv('METRICS_EXPORTERS', 'prometheus')
        monkeypatch.setenv('METRICS_PROMETHEUS_PREFIX', 'test_prefix')
        monkeypatch.setenv('METRICS_INTERVAL', '1')
        monkeypatch.setenv('METRICS_PROMETHEUS_BIND_ADDRESS', address)

        telemetry.initialize()

        http = urllib3.PoolManager()

        with telemetry.span("category1", "span1", attributes={TestAttributes.ATTRIB1: "attrib1", TestAttributes.LABEL1: 'label1'}) as span:
            time.sleep(.5)

        # wait for Prometheus collection interval to pass (METRICS_INTERVAL)
        time.sleep(2)

        telemetry.collect()

        response = http.request('GET', 'http://localhost:19102/metrics')

        def fetch_metric(name: str):
            response = http.request('GET', 'http://localhost:19102/metrics')
            lines = response.data.decode('utf8').split('\n')

            matches = list(filter(lambda line: name in line, lines))
            if len(matches) == 1:
                return float(matches[0].split(' ')[1])
            else:
                pytest.fail(f"More than one match for metric: {name}")

        assert fetch_metric('test_prefix_trace_duration_count') == 1.0
        assert fetch_metric('test_prefix_trace_duration_sum') >= 500

        # double-check that metrics continue to be returned on duplicate fetches
        assert fetch_metric('test_prefix_trace_duration_count') == 1.0
        assert fetch_metric('test_prefix_trace_duration_sum') >= 500

        with telemetry.span("category1", "span1", attributes={TestAttributes.ATTRIB1: "attrib1", TestAttributes.LABEL1: 'label1'}) as span:
            time.sleep(.5)

        # wait for Prometheus collection interval to pass (METRICS_INTERVAL)
        time.sleep(2)

        telemetry.collect()

        assert fetch_metric('test_prefix_trace_duration_count') == 2.0
        assert fetch_metric('test_prefix_trace_duration_sum') >= 1000

        telemetry.shutdown()


