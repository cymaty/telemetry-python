import typing
from typing import Sequence

from opentelemetry.sdk.metrics import MetricsExporter
from opentelemetry.sdk.metrics.export import ExportRecord, MetricsExportResult
from opentelemetry.sdk.trace import Span
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class NoOpSpanExporter(SpanExporter):

    def export(self, spans: typing.Sequence[Span]) -> "SpanExportResult":
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        pass


class NoOpMetricsExporter(MetricsExporter):
    def export(self, metric_records: Sequence[ExportRecord]) -> "MetricsExportResult":
        return MetricsExportResult.SUCCESS

    def shutdown(self) -> None:
        pass
