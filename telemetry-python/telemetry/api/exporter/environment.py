from typing import Sequence

from opentelemetry.sdk.metrics.export import ExportRecord, MetricsExporter

from telemetry.api.helpers.environment import Environment


class EnvironmentMetricsDecorator(MetricsExporter):
    def __init__(self, delegate: MetricsExporter):
        self.delegate = delegate

    def export(self, export_records: Sequence[ExportRecord]) -> "MetricsExportResult":
        for metric in export_records:
            labels = dict(metric.labels)
            labels.update(Environment.labels)
            metric.labels = tuple(labels.items())

        return self.delegate.export(export_records)
