import os

from opentelemetry.exporter.prometheus import PrometheusMetricsExporter as OTPrometheusMetricsExporter


class PrometheusMetricsExporter(OTPrometheusMetricsExporter):
    def __init__(self,
                 bind_address: str = os.environ.get('METRICS_BIND_ADDRESS', 'localhost:9091'),
                 prefix: str = os.environ.get('METRICS_PREFIX', '')):
        from prometheus_client import start_http_server

        if ':' not in bind_address:
            bind_address = f"{bind_address}:9091"

        self.prefix = prefix
        self.bind_address = bind_address

        metrics_bind_address, metrics_port = bind_address.split(':')

        start_http_server(port=int(metrics_port), addr=metrics_bind_address)
        super().__init__(prefix)

    def __str__(self):
        return f"Prometheus [bind_address={self.bind_address}, prefix={self.prefix}]"
