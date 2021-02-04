import logging
import os
from typing import Sequence

from opentelemetry.exporter.prometheus import PrometheusMetricsExporter as OTPrometheusMetricsExporter
from opentelemetry.sdk.metrics.export import ExportRecord, MetricsExportResult


class PrometheusMetricsExporter(OTPrometheusMetricsExporter):
    def __init__(self,
                 bind_address: str = os.environ.get('METRICS_PROMETHEUS_BIND_ADDRESS', '0.0.0.0:9102'),
                 prefix: str = os.environ.get('METRICS_PROMETHEUS_PREFIX', '')):
        from prometheus_client import start_http_server

        if ':' not in bind_address:
            bind_address = f"{bind_address}:9091"

        self.prefix = prefix
        self.bind_address = bind_address

        metrics_bind_address, metrics_port = bind_address.split(':')

        start_http_server(port=int(metrics_port), addr=metrics_bind_address)
        super().__init__(prefix)

    def export(self, export_records: Sequence[ExportRecord]) -> MetricsExportResult:
        logging.info(f"Exporting {len(export_records)} records")
        return super().export(export_records)

    def __str__(self):
        return f"Prometheus [bind_address={self.bind_address}, prefix={self.prefix}]"

    def __repr__(self):
        return f"Prometheus [bind_address={self.bind_address}, prefix={self.prefix}]"
