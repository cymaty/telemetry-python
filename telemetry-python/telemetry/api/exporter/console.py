import os
import os
import sys
import typing

from opentelemetry.sdk.metrics import ConsoleMetricsExporter as OTConsoleMetricsExporter
from opentelemetry.sdk.metrics.export import ExportRecord, MetricsExportResult
from opentelemetry.sdk.trace.export import ConsoleSpanExporter as OTConsoleSpanExporter

from telemetry.api.trace import Span


class ConsoleMetricsExporter(OTConsoleMetricsExporter):
    """Implementation of `MetricsExporter` that prints metrics to the console.

    This class can be used for diagnostic purposes. It prints the exported
    metrics to the console STDOUT.
    """

    @classmethod
    def record_to_string(cls, record: ExportRecord) -> str:
        return '{}(data="{}", labels="{}", value={}, resource={})'.format(
            cls.__name__,
            record.instrument,
            record.labels,
            record.aggregator.checkpoint,
            record.resource.attributes,
        )

    def __init__(self,
                 out: typing.IO = sys.stdout,
                 formatter: typing.Callable[[ExportRecord], str] = lambda m: ConsoleMetricsExporter.record_to_string
                     (m) + os.linesep):
        self.out = out
        self.formatter = formatter

    def export(self, metric_records: typing.Sequence[ExportRecord]) -> "MetricsExportResult":
        for record in metric_records:
            self.out.write(self.formatter(record))

        return MetricsExportResult.SUCCESS

    def __str__(self) -> str:
        return f"Console"


class ConsoleSpanExporter(OTConsoleSpanExporter):
    def __init__(self,
                 out: typing.IO = sys.stdout,
                 formatter: typing.Callable[[Span], str] = lambda span: span.to_json() + os.linesep):
        super().__init__(out, formatter)

    def __str__(self) -> str:
        return f"Console"
