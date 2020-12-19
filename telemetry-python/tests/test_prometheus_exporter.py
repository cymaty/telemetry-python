from telemetry.testing import TelemetryFixture
import time
import urllib3

class TestPrometheusExporter:
    def test_http_server(self, monkeypatch, telemetry: TelemetryFixture):
        address = '0.0.0.0:9102'
        monkeypatch.setenv('METRICS_EXPORTERS', 'prometheus')
        monkeypatch.setenv('METRICS_PROMETHEUS_PREFIX', 'test_prefix')
        monkeypatch.setenv('METRICS_INTERVAL', '1')
        monkeypatch.setenv('METRICS_PROMETHEUS_BIND_ADDRESS', address)

        telemetry.initialize()

        with telemetry.span("category1", "span1", tags={"tag1": "tag1"}, attributes={"attrib1": "attrib1"}) as span:
            time.sleep(.5)

        telemetry.collect()

        # wait for Prometheus collection interval to pass (METRICS_INTERVAL)
        time.sleep(1)
        
        http = urllib3.PoolManager()
        response = http.request('GET', 'http://localhost:9102/metrics')
        lines = response.data.decode('utf8').split('\n')

        assert len(list(filter(lambda line: 'test_prefix_category1_span1_duration_count' in line, lines))) == 1
        assert len(list(filter(lambda line: 'test_prefix_category1_span1_duration_sum' in line, lines))) == 1

        telemetry.shutdown()


